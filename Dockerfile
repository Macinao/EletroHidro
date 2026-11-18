FROM python:3.12-slim
WORKDIR /srv
# Dependências primeiro: o Docker reaproveita essa camada enquanto o requirements.txt não mudar.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
