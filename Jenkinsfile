
pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                // Recuperer le code source depuis Git
                checkout scm
            }
        }

        stage('Python Version') {
            steps {
                // Verifier la version de Python
                sh 'python3 --version'
            }
        }

        stage('Syntax Check') {
            steps {
                // Verifier la syntaxe des fichiers Python
                sh 'python3 -m py_compile calculator.py test_calculator.py'
            }
        }

        stage('Unit Tests') {
            steps {
                // Executer les tests unitaires
                sh 'python3 -m unittest -v test_calculator.py'
            }
        }

        stage('Success') {
            steps {
                echo 'Build et tests termines avec succes !'
            }
        }
    }

    post {
        success {
            echo 'Pipeline execute avec succes.'
        }

        failure {
            echo 'Echec du pipeline. Verifier les logs.'
        }

        always {
            echo 'Execution du pipeline terminee.'
        }
    }
}
