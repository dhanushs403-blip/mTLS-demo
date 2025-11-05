from flask import Flask, request
import logging
import ssl
import os
import sys

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# --- mTLS Configuration from Environment Variables ---
# These paths are read from the environment, with defaults for local testing
CERT_PATH = os.environ.get("CERT_PATH", "../local-certs/server.crt")
KEY_PATH = os.environ.get("KEY_PATH", "../local-certs/server.key")
CA_PATH = os.environ.get("CA_PATH", "../local-certs/my-ca.crt")
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", 8443))
# -----------------------------------------------------

@app.route("/")
def hello_secure():
    """
    Main endpoint that logs the request ID from a successful mTLS connection.
    """
    # Read the ID from the header for tracking
    req_id = request.headers.get('X-Request-ID', 'N/A')
    log.info(f"[ReqID: {req_id}] Successful GET / request received from an authorized mTLS client.")
    return f"[BACKEND-mTLS]: Received ReqID {req_id}."

# This block runs when you execute "python app.py" directly
if __name__ == "__main__":
    log.info(f"Starting Flask server with manual mTLS context...")
    log.info(f" > Listening on: https://{LISTEN_HOST}:{LISTEN_PORT}")
    log.info(f" > Server Cert: {CERT_PATH}")
    log.info(f" > Server Key:  {KEY_PATH}")
    log.info(f" > Client CA:   {CA_PATH}")

    # --- Manual mTLS Context Creation ---
    
    
    # 1. Create an SSL context that requires a client certificate
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    
    try:
        # 2. Load the server's own certificate and private key
        context.load_cert_chain(certfile=CERT_PATH, keyfile=KEY_PATH)
        
        # 3. Load the trusted CA certificate to verify clients against
        context.load_verify_locations(cafile=CA_PATH)
        
    except FileNotFoundError as e:
        log.error(f"FATAL: Could not load certificate files. File not found: {e}")
        log.error("Please check your paths and ensure certificates are present.")
        sys.exit(1)
        
    # 4. Enforce mTLS: Require a client certificate, and fail if it's not valid
    context.verify_mode = ssl.CERT_REQUIRED
    
    # 5. Run the Flask app, passing in our custom mTLS context
    app.run(
        host=LISTEN_HOST, 
        port=LISTEN_PORT, 
        ssl_context=context  # This applies all our mTLS rules
    )