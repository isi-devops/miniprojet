
# Utilise une image Python légère
FROM python:3.12-slim

# Définit le répertoire de travail
WORKDIR /app

# Copie le fichier Python dans le conteneur
COPY calculator.py .

# Définit la commande de démarrage
CMD ["python", "calculator.py"]
