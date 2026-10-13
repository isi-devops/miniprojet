pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Python Version') {
            steps {
                sh 'python3 --version'
                sh 'pip3 --version'
            }
        }

        stage('Syntax Check') {
            steps {
                sh 'python3 -m compileall .'
            }
        }

        stage('Unit Tests') {
            steps {
                sh 'python3 -m unittest discover -v'
            }
        }

        stage('Success') {
            steps {
                echo 'Pipeline execute avec succes !'
            }
        }
    }

    post {
        success {
            echo 'Pipeline termine avec succes.'
        }
        failure {
            echo 'Echec du pipeline. Verifier les logs.'
        }
    }
}
