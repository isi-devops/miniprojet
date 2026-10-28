
# Utilise une image Python légère
FROM python:3.12-slim

# Définit le répertoire de travail
WORKDIR /app

# Crée un utilisateur non privilégié
RUN useradd --create-home --uid 10001 appuser

# Copie le fichier Python
COPY --chown=appuser:appuser calculator.py .

# Utilise un utilisateur non-root
USER appuser

# Définit la commande de démarrage
CMD ["python", "calculator.py"]
