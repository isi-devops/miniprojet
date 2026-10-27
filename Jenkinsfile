pipeline {
  agent any
  options { skipDefaultCheckout(false) }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Sonar Analysis') {
      steps {
        script { scannerHome = tool 'SonarScanner' }
        withSonarQubeEnv('sonarqube') {
          sh """
            ${scannerHome}/bin/sonar-scanner \
              -Dsonar.projectKey=calculator \
              -Dsonar.projectName=calculator \
              -Dsonar.sources=. \
              -Dsonar.branch.name=${env.BRANCH_NAME}
          """
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