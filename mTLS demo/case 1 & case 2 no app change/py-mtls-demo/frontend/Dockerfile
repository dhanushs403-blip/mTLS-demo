# Use official Python slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Run Gunicorn with single worker for persistent mTLS connection
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--log-level", "debug", \
     "--workers", "1", \
     "--timeout", "300", \
     "app:app"]