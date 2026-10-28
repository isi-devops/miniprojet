pipeline {
  agent any
  options {
    skipDefaultCheckout(false)
    timestamps()
    disableConcurrentBuilds()
  }

  environment {
    IMAGE_NAME  = 'calculator'
    // Le tag est calculé dans le stage "Prepare"
    IMAGE_TAG   = ''
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
          env.IMAGE_TAG  = "${safeBranch}-${env.BUILD_NUMBER}-${shortSha}"
          env.FULL_IMAGE = "${env.IMAGE_NAME}:${env.IMAGE_TAG}"
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
              docker run --rm \
                -v /var/run/docker.sock:/var/run/docker.sock \
                goodwithtech/dockle:latest \
                  --exit-code 1 --exit-level fatal \
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
      // Nettoyage de l'image locale pour ne pas saturer le disque
    }
    failure { echo 'Pipeline en échec : consultez les rapports archivés (hadolint, trivy).' }
    success { echo "Image ${env.FULL_IMAGE} construite et scannée avec succès." }
  }
}
