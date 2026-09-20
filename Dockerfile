# Slim Python base image.
FROM python:3.12-slim

# Unbuffered stdout, no .pyc writes, and container-safe server defaults.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    FLASK_DEBUG=0

WORKDIR /app

# Install dependencies first to leverage Docker layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source.
COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
