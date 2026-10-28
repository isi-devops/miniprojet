# miniprojet

docker run --rm \
  --network miniprojet_default \
  -e SONAR_HOST_URL="http://sonarqube:9000" \
  -e SONAR_TOKEN="TON_NOUVEAU_TOKEN" \
  -v "$PWD:/usr/src" \
  sonarsource/sonar-scanner-cli \
  -Dsonar.projectKey=calculator
