# TP — Pipeline CI/CD sécurisé : Jenkins + SonarQube + scan d'image Docker

## 1. Objectifs

À la fin de ce TP, vous aurez un pipeline Jenkins (lancé dans un conteneur) qui, à chaque commit :

1. analyse le code avec **SonarQube** et applique un **Quality Gate** ;
2. vérifie le **Dockerfile** avec **Hadolint** ;
3. **construit l'image Docker** de l'application ;
4. **scanne l'image** avec **Trivy**, **Dockle** et **Grype** (en parallèle) ;
5. génère un **SBOM** (inventaire des composants) avec **Syft** ;
6. archive les rapports et conserve uniquement les images validées.

## 2. Prérequis

- Docker et Docker Compose installés sur la machine hôte.
- 4 Go de RAM libres minimum (SonarQube est gourmand).
- Pour SonarQube sous Linux : `sudo sysctl -w vm.max_map_count=262144`
- Un dépôt Git contenant votre application et un **Dockerfile à la racine**.

Architecture :

```
 Hôte Docker
 ├── jenkins      (client docker + socket de l'hôte monté)
 ├── sonarqube    ──> sonarqube-db (PostgreSQL)
 └── conteneurs "éphémères" lancés par le pipeline :
     hadolint, trivy, dockle, grype, syft
```

> Jenkins pilote le Docker **de l'hôte** via le socket `/var/run/docker.sock`.
> Les outils de scan sont donc des conteneurs frères, pas des conteneurs dans Jenkins.

## 3. Étape 1 — Démarrer la stack (Jenkins + SonarQube)

### 3.1 `Dockerfile.jenkins`

L'image officielle de Jenkins n'a pas le client Docker. On l'ajoute :

```dockerfile
FROM jenkins/jenkins:lts-jdk21

USER root
# Client Docker (binaire statique) copié depuis l'image officielle docker:cli
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker

# Pour garder l'utilisateur jenkins (plus propre que root), voir group_add dans docker-compose.yml
USER jenkins
```

### 3.2 `docker-compose.yml`

```yaml
services:
  jenkins:
    build:
      context: .
      dockerfile: Dockerfile.jenkins
    image: jenkins-docker:lts-jdk21
    container_name: jenkins
    restart: unless-stopped
    # Lab : root pour pouvoir utiliser le socket Docker de l'hôte.
    # Alternative plus propre : supprimer "user: root" et décommenter group_add
    # avec le GID du groupe docker de l'hôte (getent group docker | cut -d: -f3)
    user: root
    # group_add:
    #   - "999"
    ports:
      - "8080:8080"
      - "50000:50000"
    volumes:
      - jenkins_home:/var/jenkins_home
      - /var/run/docker.sock:/var/run/docker.sock

  sonarqube:
    image: sonarqube:lts-community
    container_name: sonarqube
    restart: unless-stopped
    depends_on:
      - sonarqube-db
    ports:
      - "9000:9000"
    environment:
      SONAR_JDBC_URL: jdbc:postgresql://sonarqube-db:5432/sonar
      SONAR_JDBC_USERNAME: sonar
      SONAR_JDBC_PASSWORD: sonar_password
    volumes:
      - sonarqube_data:/opt/sonarqube/data
      - sonarqube_extensions:/opt/sonarqube/extensions
      - sonarqube_logs:/opt/sonarqube/logs

  sonarqube-db:
    image: postgres:15
    container_name: sonarqube-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: sonar
      POSTGRES_PASSWORD: sonar_password
      POSTGRES_DB: sonar
    volumes:
      - sonarqube_db:/var/lib/postgresql/data

volumes:
  jenkins_home:
  sonarqube_data:
  sonarqube_extensions:
  sonarqube_logs:
  sonarqube_db:
```

### 3.3 Lancement et vérification

```bash
docker compose up -d --build
docker compose ps
docker compose exec jenkins docker version
```

`docker version` doit afficher **Client** et **Server**. Sinon, voir la section Dépannage.

Mot de passe initial de Jenkins :

```bash
docker compose exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

Ouvrez ensuite http://localhost:8080 et installez les plugins suggérés.

## 4. Étape 2 — Configurer SonarQube

1. Ouvrez http://localhost:9000 (identifiants initiaux `admin` / `admin`, changement de mot de passe demandé).
2. Créez un **token** : *My Account → Security → Generate Tokens* (type *User* ou *Global Analysis*). Copiez-le, il ne sera plus affiché.
3. Créez un **webhook** vers Jenkins (indispensable pour que `waitForQualityGate` reçoive le résultat) :
   *Administration → Configuration → Webhooks → Create*
   - Nom : `jenkins`
   - URL : `http://jenkins:8080/sonarqube-webhook/` (les deux conteneurs sont sur le même réseau Compose)

## 5. Étape 3 — Configurer Jenkins

### 5.1 Plugins

*Manage Jenkins → Plugins → Available plugins*, installer :
- **SonarQube Scanner**
- **Pipeline** et **Pipeline: Multibranch** (normalement déjà présents)
- **Git**

### 5.2 Credential du token Sonar

*Manage Jenkins → Credentials → Global → Add Credentials*
- Kind : **Secret text**
- Secret : le token Sonar
- ID : `sonar-token`

### 5.3 Serveur SonarQube

*Manage Jenkins → System → SonarQube servers → Add*
- Name : **`sonarqube`** (doit correspondre à `withSonarQubeEnv('sonarqube')`)
- Server URL : `http://sonarqube:9000`
- Server authentication token : `sonar-token`

### 5.4 Outil SonarScanner

*Manage Jenkins → Tools → SonarQube Scanner installations → Add*
- Name : **`SonarScanner`** (doit correspondre à `tool 'SonarScanner'`)
- Cochez *Install automatically*.

## 6. Étape 4 — Préparer le projet

À la racine du dépôt, il faut le code de l'application, un `Dockerfile` et le `Jenkinsfile`.

Exemple de `Dockerfile` (à adapter à votre application) qui respecte les bonnes pratiques contrôlées par Hadolint et Dockle :

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

# Ne jamais exécuter l'application en root (contrôle Dockle CIS-DI-0001)
RUN useradd --system --create-home appuser
USER appuser

# Contrôle Dockle CIS-DI-0006 : adaptez la commande à votre application
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "print('ok')" || exit 1

CMD ["python", "calculator.py"]
```

## 7. Étape 5 — Le Jenkinsfile

```groovy
pipeline {
  agent any
  options {
    skipDefaultCheckout(false)
    timestamps()
    disableConcurrentBuilds()
  }

  environment {
    IMAGE_NAME  = 'calculator'
    // Gravités qui font échouer le pipeline
    TRIVY_SEVERITY = 'HIGH,CRITICAL'
    // Cache Trivy partagé entre les builds (volume Docker nommé)
    TRIVY_CACHE = 'trivy-cache'
  }

  stages {

    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Prepare') {
      steps {
        script {
          def safeBranch = env.BRANCH_NAME.toLowerCase().replaceAll('[^a-z0-9_.-]', '-')
          def shortSha   = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
          def tag        = "${safeBranch}-${env.BUILD_NUMBER}-${shortSha}"
          env.IMAGE_TAG  = tag
          env.FULL_IMAGE = "${env.IMAGE_NAME}:${tag}"
          echo "Image cible : ${env.FULL_IMAGE}"
        }
      }
    }

    stage('Sonar Analysis') {
      steps {
        script {
          def scannerHome = tool 'SonarScanner'
          def safeBranch = env.BRANCH_NAME.replaceAll('[^A-Za-z0-9_.:-]', '_')
          withSonarQubeEnv('sonarqube') {
            sh """
              ${scannerHome}/bin/sonar-scanner \
                -Dsonar.projectKey=calculator-${safeBranch} \
                -Dsonar.projectName='calculator (${env.BRANCH_NAME})' \
                -Dsonar.sources=.
            """
          }
        }
      }
    }

    stage('Quality Gate') {
      steps {
        timeout(time: 5, unit: 'MINUTES') {
          waitForQualityGate abortPipeline: true
        }
      }
    }

    // ---------- Lint du Dockerfile (avant le build) ----------
    stage('Lint Dockerfile (Hadolint)') {
      steps {
        // Le Dockerfile est passé via stdin : pas de problème de chemin
        // quand Jenkins tourne lui-même dans un conteneur.
        sh '''
          docker run --rm -i hadolint/hadolint hadolint \
            --failure-threshold warning \
            --format json - < Dockerfile > hadolint-report.json || HADOLINT_RC=$?
          docker run --rm -i hadolint/hadolint hadolint \
            --failure-threshold warning - < Dockerfile || exit ${HADOLINT_RC:-0}
        '''
      }
      post {
        always { archiveArtifacts artifacts: 'hadolint-report.json', allowEmptyArchive: true }
      }
    }

    // ---------- Build de l'image ----------
    stage('Build Docker Image') {
      steps {
        sh '''
          docker build \
            --pull \
            --label org.opencontainers.image.revision=$(git rev-parse HEAD) \
            --label org.opencontainers.image.source=${GIT_URL:-unknown} \
            -t ${FULL_IMAGE} .
        '''
      }
    }

    // ---------- Scans de l'image (en parallèle) ----------
    stage('Image Security Scans') {
      parallel {

        stage('Trivy - vulnérabilités + secrets') {
          steps {
            sh '''
              # Rapport complet (JSON) pour archivage : ne bloque pas
              docker run --rm \
                -v /var/run/docker.sock:/var/run/docker.sock \
                -v ${TRIVY_CACHE}:/root/.cache/ \
                aquasec/trivy:latest image \
                  --scanners vuln,secret \
                  --format json \
                  --exit-code 0 \
                  ${FULL_IMAGE} > trivy-report.json

              # Rapport lisible + blocage sur HIGH/CRITICAL (CVE avec correctif dispo)
              docker run --rm \
                -v /var/run/docker.sock:/var/run/docker.sock \
                -v ${TRIVY_CACHE}:/root/.cache/ \
                aquasec/trivy:latest image \
                  --scanners vuln,secret \
                  --severity ${TRIVY_SEVERITY} \
                  --ignore-unfixed \
                  --exit-code 1 \
                  ${FULL_IMAGE}
            '''
          }
          post {
            always { archiveArtifacts artifacts: 'trivy-report.json', allowEmptyArchive: true }
          }
        }

        stage('Dockle - bonnes pratiques image') {
          steps {
            sh '''
              # DKL-DI-0005 ignoré : faux positif sur les images Debian récentes
              # (apt-get dist-clean nettoie bien le cache mais Dockle ne le reconnaît pas)
              docker run --rm \
                -v /var/run/docker.sock:/var/run/docker.sock \
                goodwithtech/dockle:latest \
                  --exit-code 1 --exit-level fatal \
                  -i DKL-DI-0005 \
                  ${FULL_IMAGE}
            '''
          }
        }

        stage('Grype - second avis CVE') {
          steps {
            sh '''
              docker run --rm \
                -v /var/run/docker.sock:/var/run/docker.sock \
                anchore/grype:latest \
                  docker:${FULL_IMAGE} \
                  --fail-on high \
                  --only-fixed
            '''
          }
        }
      }
    }

    // ---------- SBOM (inventaire des composants) ----------
    stage('SBOM (Syft)') {
      steps {
        sh '''
          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            anchore/syft:latest \
              docker:${FULL_IMAGE} \
              -o cyclonedx-json > sbom.cdx.json
        '''
      }
      post {
        always { archiveArtifacts artifacts: 'sbom.cdx.json', allowEmptyArchive: true }
      }
    }

    // ---------- Push (à activer quand vous avez un registry) ----------
    // stage('Push Image') {
    //   when { branch 'main' }
    //   steps {
    //     withCredentials([usernamePassword(credentialsId: 'registry-creds',
    //                      usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
    //       sh '''
    //         echo "$REG_PASS" | docker login registry.example.com -u "$REG_USER" --password-stdin
    //         docker tag  ${FULL_IMAGE} registry.example.com/${FULL_IMAGE}
    //         docker push registry.example.com/${FULL_IMAGE}
    //       '''
    //     }
    //   }
    // }
  }

  post {
    always {
      // On garde les 5 images les plus récentes de calculator, on supprime les plus anciennes
      sh '''
        docker images ${IMAGE_NAME} --format '{{.Repository}}:{{.Tag}}' | tail -n +6 | xargs -r docker rmi || true
      '''
    }
    failure {
      // Une image qui a échoué aux contrôles n'est pas conservée
      sh 'docker rmi ${FULL_IMAGE} || true'
      echo 'Pipeline en échec : consultez les rapports archivés (hadolint, trivy).'
    }
    success { echo "Image ${env.FULL_IMAGE} construite et scannée avec succès." }
  }
}
```

### Rôle de chaque stage

| Stage | Outil | Rôle | Bloque le pipeline si… |
|---|---|---|---|
| Checkout | Git | Récupère le code | erreur Git |
| Prepare | Groovy | Calcule le tag `branche-build-sha` | — |
| Sonar Analysis | SonarScanner | Analyse statique du code | erreur d'analyse |
| Quality Gate | SonarQube | Vérifie les seuils qualité | le gate est rouge |
| Lint Dockerfile | Hadolint | Bonnes pratiques du Dockerfile | warning ou plus |
| Build Docker Image | Docker | Construit l'image | erreur de build |
| Trivy | Trivy | CVE et secrets dans l'image | CVE HIGH/CRITICAL corrigeables |
| Dockle | Dockle | Bonnes pratiques de l'image (CIS) | niveau FATAL |
| Grype | Grype | Second avis sur les CVE | CVE high corrigeables |
| SBOM | Syft | Inventaire des composants (CycloneDX) | — |

## 8. Étape 6 — Créer le job

1. *New Item* → nom `calculator` → **Multibranch Pipeline**.
2. *Branch Sources* → **Git** → URL de votre dépôt (+ credentials si le dépôt est privé).
3. *Build Configuration* : Mode *by Jenkinsfile*, Script Path `Jenkinsfile`.
4. Sauvegardez : Jenkins scanne le dépôt et lance un build par branche.

## 9. Étape 7 — Lire les résultats

- **Console / Stage View** de Jenkins : état de chaque stage.
- **SonarQube** (http://localhost:9000) : un projet `calculator-<branche>` par branche.
  La version Community n'analyse pas les branches nativement, d'où une clé de projet par branche.
- **Artefacts du build** : `trivy-report.json`, `hadolint-report.json`, `sbom.cdx.json`.
- **Image conservée** (build réussi) :

```bash
docker compose exec jenkins docker images calculator
```

## 10. Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| `docker: not found` (code 127) | Pas de client Docker dans le conteneur Jenkins | Utiliser `Dockerfile.jenkins` et reconstruire (`up -d --build`) |
| `permission denied` sur `/var/run/docker.sock` | L'utilisateur `jenkins` n'a pas accès au socket | `user: root` (lab) ou `group_add` avec le GID du groupe docker de l'hôte |
| Image nommée `calculator:null` | Variable `IMAGE_TAG` déclarée dans `environment {}` qui masque la valeur calculée | Tag calculé dans une variable locale du stage `Prepare` |
| Dockle FATAL `DKL-DI-0005` | Faux positif sur `apt-get dist-clean` des images Debian récentes | `-i DKL-DI-0005` dans la commande Dockle |
| `waitForQualityGate` expire | Webhook Sonar absent ou mal configuré | Créer le webhook `http://jenkins:8080/sonarqube-webhook/` |
| L'image construite n'apparaît pas dans `docker images` | Supprimée par le nettoyage en fin de pipeline (ou build en échec) | Le nettoyage garde les 5 dernières images validées ; une image en échec est supprimée |
| Trivy bloque sur des CVE | Image de base vulnérable | Mettre à jour/changer l'image de base, ou ajuster `TRIVY_SEVERITY` |

## 11. Pour aller plus loin

1. **Push vers un registry** : activer le stage `Push Image` (Docker Hub, GitHub/GitLab Registry, ou `registry:2` en conteneur).
2. **Scan de la configuration** avec `trivy config` (nécessite Trivy installé dans Jenkins ou un volume partagé avec l'hôte).
3. **Durcir le socket Docker** : un accès au socket équivaut à un accès root à l'hôte. En production, préférer des agents Jenkins dédiés ou Docker rootless.
4. **Rendre les scans moins stricts au départ** : passer `--exit-code 1` à `0` (Trivy, Dockle) puis durcir progressivement.

## 12. Questions de réflexion

1. Pourquoi lancer Hadolint **avant** le build et Trivy **après** ?
2. Quelle différence entre Trivy, Grype (CVE) et Dockle (bonnes pratiques de configuration) ?
3. Pourquoi les scans tournent-ils en parallèle ?
4. À quoi sert un SBOM en cas de nouvelle vulnérabilité publiée ?
5. Quels risques apporte le montage du socket Docker dans Jenkins, et comment les réduire ?
