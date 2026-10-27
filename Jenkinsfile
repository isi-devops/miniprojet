pipeline {
  agent any
  options { skipDefaultCheckout(false) }

  stages {
    stage('Checkout') {
      steps { checkout scm }
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
  }
}