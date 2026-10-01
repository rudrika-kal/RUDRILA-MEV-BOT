FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rudrila_mev ./rudrila_mev
COPY config.json ./config.json

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "rudrila_mev.main", "--config", "config.json"]
