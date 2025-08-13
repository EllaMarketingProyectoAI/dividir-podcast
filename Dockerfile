FROM python:3.11-slim

# Instalar ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080

# Gunicorn con timeout alto por trabajos de video
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8080", "--timeout", "900", "app:app"]
