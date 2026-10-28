# TP — Pipeline Jenkins Multibranch + analyse SonarQube

**Contexte** : 2 conteneurs Docker sur WSL2 (Jenkins + SonarQube 9.9 Community), repo `isi-devops/miniprojet` (Python).
**Objectif** : un pipeline multibranch qui récupère le SCM, lance l'analyse Sonar, puis attend le Quality Gate.

---

## 1. Réseau Docker commun

Les conteneurs communiquent par nom, pas par `localhost`.

```bash
docker network create ci-net
docker network connect ci-net jenkins
docker network connect ci-net sonarqube
```

Test :

```bash
docker exec jenkins curl -s http://sonarqube:9000/api/system/status
# attendu : {"status":"UP",...}
```

---

## 2. Configuration SonarQube

1. Générer un token : *My Account → Security → Generate Token*.
2. Créer le webhook (*Administration → Configuration → Webhooks → Create*) :
   - URL : `http://jenkins:8080/sonarqube-webhook/` (le `/` final est obligatoire)
3. Si le webhook échoue (adresse privée Docker bloquée), ajouter sur le conteneur Sonar :

```yaml
environment:
  - SONAR_VALIDATEWEBHOOKS=false
```

puis `docker compose up -d sonarqube`.

---

## 3. Configuration Jenkins

**Plugins** : Pipeline Multibranch, SonarQube Scanner, Git / GitHub Branch Source.

**Credentials** : *Manage Jenkins → Credentials → Global → Add* → type *Secret text*, ID `sonar-token`.

**Serveur Sonar** : *Manage Jenkins → System → SonarQube servers*
- Cocher *Enable injection of SonarQube server configuration*
- *Add SonarQube* : Name = `sonarqube` (exact), URL = `http://sonarqube:9000`, Token = `sonar-token`

**Outil scanner** : *Manage Jenkins → Tools → SonarQube Scanner* : nom `SonarScanner`, *Install automatically*.

---

## 4. Job Multibranch

*New Item → Multibranch Pipeline* :
- **Branch Sources** : `https://github.com/isi-devops/miniprojet.git` (+ credentials si repo privé)
- **Build Configuration** : *by Jenkinsfile*
- **Scan Multibranch Pipeline Triggers** : *Periodically* (ex. 5 min) ou webhook GitHub

---

## 5. Jenkinsfile final

```groovy
pipeline {
  agent any

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Tests & couverture') {
      steps {
        sh '''
          pip install pytest pytest-cov
          pytest --cov=. --cov-report=xml
        '''
      }
    }

    stage('Sonar Analysis') {
      steps {
        script {
          def scannerHome = tool 'SonarScanner'
          def safeBranch  = env.BRANCH_NAME.replaceAll('[^A-Za-z0-9_.:-]', '_')
          withSonarQubeEnv('sonarqube') {
            sh """
              ${scannerHome}/bin/sonar-scanner \
                -Dsonar.projectKey=calculator-${safeBranch} \
                -Dsonar.projectName='calculator (${env.BRANCH_NAME})' \
                -Dsonar.sources=. \
                -Dsonar.python.coverage.reportPaths=coverage.xml
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
  }
}
```

> L'étape *Tests & couverture* suppose Python/pip disponibles dans l'agent Jenkins (branche `install-python`).

---

## 6. Erreurs rencontrées et corrections

| # | Erreur | Cause | Correction |
|---|--------|-------|------------|
| 1 | `SonarQube installation ... does not match any configured installation. Number of installations: 0` | Aucun serveur Sonar déclaré dans Jenkins | Déclarer le serveur `sonarqube` (section 3) |
| 2 | `Did you forget the def keyword? ... scannerHome` | Variable Groovy globale | `def scannerHome = tool 'SonarScanner'` |
| 3 | `To use the property "sonar.branch.name" ... Developer Edition or above is required` | Analyse de branches non supportée en Community | Supprimer `-Dsonar.branch.name`, utiliser un `projectKey` par branche |
| 4 | `waitForQualityGate` bloqué en `PENDING` | Jenkins ne reçoit pas le webhook Sonar | Créer le webhook + `SONAR_VALIDATEWEBHOOKS=false` (section 2) |
| 5 | `Invalid directory path in 'source' element: /home/oussema/...` | `coverage.xml` commité depuis un autre poste | Le générer dans le pipeline, l'ajouter au `.gitignore` |

Note : `anis.benali/sonar` contient un `/`, interdit dans un `projectKey` → d'où le `replaceAll`.

---

## 7. Vérifications finales

- [ ] Branch indexing : les 7 branches sont détectées
- [ ] Build vert sur `anis.benali/sonar`
- [ ] Projet `calculator-anis.benali_sonar` visible dans SonarQube
- [ ] Webhook : *Last delivery* = Success
- [ ] Quality Gate renvoyé à Jenkins (stage vert ou échec explicite)

## 8. Pour aller plus loin

- Ne scanner que `main`/`develop` : `when { anyOf { branch 'main'; branch 'develop' } }`
- Ajouter `-Dsonar.python.version=3` pour supprimer le warning d'analyse Python 2/3
- Passer en Developer Edition pour l'analyse native des branches et des PR
