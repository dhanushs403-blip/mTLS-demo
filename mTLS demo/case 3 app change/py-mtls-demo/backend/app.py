from flask import Flask, request
import logging, os, ssl

app = Flask(__name__)

# Use Gunicorn logger
gunicorn_logger = logging.getLogger('gunicorn.error')
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)
log = app.logger

USE_MTLS = os.getenv("USE_MTLS", "true").lower() == "true"
LISTEN_PORT = int(os.getenv("LISTEN_PORT", "8080"))

@app.route("/", methods=['GET', 'POST'])
def hello_secure():
    # Extract request id
    request_id = "N/A"
    if request.is_json:
        try:
            data = request.get_json()
            request_id = data.get('request_id', 'N/A')
        except:
            pass

    mode = "mTLS" if USE_MTLS else "PLAIN-HTTP"
    log.info(f"BACKEND ({mode}): Received request with ID: {request_id}")
    return f"BACKEND ({mode}): Success! ID: {request_id}", 200


# Fallback HTTP mode (only runs in local or plain mode)
if __name__ == "__main__":
    if USE_MTLS:
        raise RuntimeError("Run with Gunicorn in mTLS mode!")
    log.info(f"Starting backend in HTTP mode on port {LISTEN_PORT} ...")
    app.run(host="0.0.0.0", port=LISTEN_PORT)
