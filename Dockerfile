FROM python:3.9-slim

WORKDIR /app

# Copiar solo requirements para aprovechar cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código
COPY srpk_v3_1.py .
COPY README.md .

# Comando por defecto
ENTRYPOINT ["python", "srpk_v3_1.py"]
