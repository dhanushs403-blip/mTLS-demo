# frontend/app.py

import http.client
import ssl
import logging
import os
import json
from flask import Flask, request

app = Flask(__name__)

# Use Gunicorn logger
gunicorn_logger = logging.getLogger('gunicorn.error')
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)
log = app.logger

# Config
USE_MTLS = os.getenv("USE_MTLS", "true").lower() == "true"

# CERT paths (still mounted even if not used)
CERTPATH = "/etc/tls/tls.crt"
KEYPATH = "/etc/tls/tls.key"
CAPATH = "/etc/tls/ca.crt"

BACKEND_HOST = os.getenv("BACKEND_HOST", "backend-svc")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8080"))

backend_connection = None
ssl_context = None

def create_connection():
    global backend_connection, ssl_context

    if not USE_MTLS:
        log.info("Using plain HTTP --> backend")
        backend_connection = http.client.HTTPConnection(
            host=BACKEND_HOST, port=BACKEND_PORT, timeout=1.0
        )
        return

    try:
        log.info("Creating new mTLS SSLContext...")
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=CAPATH)
        context.load_cert_chain(certfile=CERTPATH, keyfile=KEYPATH)
        ssl_context = context

        backend_connection = http.client.HTTPSConnection(
            host=BACKEND_HOST,
            port=BACKEND_PORT,
            context=ssl_context,
            timeout=1.0
        )

        init_payload = json.dumps({"request_id": "INIT"})
        backend_connection.request("POST", "/", body=init_payload, headers={"Content-Type": "application/json"})
        resp = backend_connection.getresponse()
        resp.read()
        log.info(f"Initial mTLS connection OK: {resp.status}")

    except Exception as e:
        log.error(f"Failed to create mTLS connection: {e}")
        backend_connection = None


# Initial connection
create_connection()

@app.route("/", methods=['GET', 'POST'])
def handler():
    global backend_connection

    request_id = request.headers.get('X-Request-ID', 'N/A')
    mode = "mTLS" if USE_MTLS else "PLAINTEXT"
    log.info(f"FRONTEND ({mode}): Incoming ID {request_id}")

    if backend_connection is None:
        log.warning("Backend connection lost — reconnecting...")
        create_connection()
        return "Reconnecting", 503

    try:
        data = json.dumps({"request_id": request_id})
        backend_connection.request("POST", "/", body=data, headers={'Content-Type': 'application/json'})
        resp = backend_connection.getresponse()
        body = resp.read().decode()

        if resp.status == 200:
            return f"FRONTEND ({mode}): {body}", 200
        else:
            return f"Error from backend: {resp.status}", 500

    except Exception as e:
        log.error(f"{mode} connection failed: {e}")
        backend_connection = None
        create_connection()
        return "Connection reset", 503
