# Use official Python slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Run Gunicorn with mTLS
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8443", \
     "--certfile", "/var/run/secrets/mtls/tls.crt", \
     "--keyfile", "/var/run/secrets/mtls/tls.key", \
     "--ca-certs", "/var/run/secrets/mtls/ca.crt", \
     "--cert-reqs", "2", \
     "--log-level", "debug", \
     "app:app"]