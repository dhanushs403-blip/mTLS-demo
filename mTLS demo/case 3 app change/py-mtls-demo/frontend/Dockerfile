FROM python:3.10-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--log-level", "info", \
     "app:app"]
