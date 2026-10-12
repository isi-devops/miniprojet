
pipeline {
    agent any

    environment {
        APP_NAME = 'demo-devops'
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Etape 1 : Recuperation du code source'
                checkout scm
            }
        }

        stage('Build') {
            steps {
                echo 'Etape 2 : Construction du projet'
                sh 'echo "Build de ${APP_NAME} en cours..."'
                sh 'mkdir -p build'
                sh 'echo "Application construite" > build/result.txt'
            }
        }

        stage('Test') {
            steps {
                echo 'Etape 3 : Execution des tests'
                sh 'test -f build/result.txt'
                sh 'grep -q "Application construite" build/result.txt'
                echo 'Tests reussis !'
            }
        }

        stage('Package') {
            steps {
                echo 'Etape 4 : Preparation de l artefact'
                sh 'tar -czf demo-artifact.tar.gz build/'
            }
        }

        stage('Deploy') {
            steps {
                echo 'Etape 5 : Deploiement simule'
                sh 'echo "Deploiement de ${APP_NAME} termine !"'
            }
        }
    }

    post {
        success {
            echo 'Pipeline termine avec succes.'
            archiveArtifacts artifacts: 'demo-artifact.tar.gz',
                             fingerprint: true
        }

        failure {
            echo 'Echec du pipeline. Consulte les logs.'
        }

        always {
            echo 'Fin du pipeline.'
        }
    }
}
