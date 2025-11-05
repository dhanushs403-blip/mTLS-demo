#!/bin/sh

if [ "$USE_MTLS" = "true" ]; then
    echo "Starting backend in mTLS mode..."
    exec gunicorn \
        --bind 0.0.0.0:8080 \
        --certfile /var/run/secrets/mtls/tls.crt \
        --keyfile /var/run/secrets/mtls/tls.key \
        --ca-certs /var/run/secrets/mtls/ca.crt \
        --cert-reqs 2 \
        --log-level info \
        app:app
else
    echo "Starting backend in PLAINTEXT HTTP mode..."
    exec python app.py
fi
