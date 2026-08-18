FROM python:3.11-slim

WORKDIR /app

# Configuração de timezone (útil para os logs da aplicação)
RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ="America/Sao_Paulo"

# Copia os requisitos e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da aplicação
COPY . .

# Comando de execução
CMD ["python", "main.py"]