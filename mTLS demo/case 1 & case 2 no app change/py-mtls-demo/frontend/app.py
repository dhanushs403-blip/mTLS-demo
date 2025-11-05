# In frontend/app.py
import http.client
import ssl
import time
import logging
import os
from flask import Flask, request
from waitress import serve  # Use Waitress for a production-grade WSGI server

# --- Flask & Logging Setup ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO) # Configure basic logging
log = logging.getLogger(__name__)

# --- Unified Configuration ---
# Read configuration from Environment Variables, with defaults for local testing
CERT_PATH = os.environ.get("CERT_PATH", "../local-certs/client.crt")
KEY_PATH = os.environ.get("KEY_PATH", "../local-certs/client.key")
CA_PATH = os.environ.get("CA_PATH", "../local-certs/my-ca.crt")
BACKEND_HOST = os.environ.get("BACKEND_HOST", "localhost")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", 8443))
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", 8080))
# -----------------------------

def check_certs():
    """Checks if the required certificate files exist on disk."""
    if not os.path.exists(CERT_PATH): 
        log.warning(f"Cert file not found at: {CERT_PATH}")
        return False
    if not os.path.exists(KEY_PATH): 
        log.warning(f"Key file not found at: {KEY_PATH}")
        return False
    if not os.path.exists(CA_PATH): 
        log.warning(f"CA file not found at: {CA_PATH}")
        return False
    log.info("All certificate files found on disk.")
    return True

def create_mtls_connection():
    """
    Creates a single, persistent HTTPSConnection object.
    This "legacy" function loads certificates from disk ONCE at startup.
    """
    log.info("Creating persistent SSLContext and loading certs into memory...")
    try:
        # Create a client-side SSL context
        # This explicit method is more reliable in containers
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        
        # Load the CA cert to verify the server
        context.load_verify_locations(cafile=CA_PATH)
        
        # Load our client cert and key to prove our identity
        context.load_cert_chain(certfile=CERT_PATH, keyfile=KEY_PATH)
        log.info(f"Certs successfully loaded. Creating persistent connection to {BACKEND_HOST}:{BACKEND_PORT}...")
        
        # Create the reusable connection object
        conn = http.client.HTTPSConnection(
            host=BACKEND_HOST,
            port=BACKEND_PORT,
            context=context
        )
        log.info("Persistent mTLS connection object created.")
        return conn
    except Exception as e:
        log.error(f"FATAL: Failed to create persistent SSLContext or connection: {e}")
        return None

# --- Global State ---
# Wait for certs to be mounted (e.g., by cert-manager) before proceeding
log.info("Waiting for certs to be available on disk...")
while not check_certs():
    log.warning("Certs not yet available, sleeping 3s...")
    time.sleep(3)

# Create the one-and-only connection object when the app starts.
persistent_conn = create_mtls_connection()
# --------------------

@app.route("/")
def handle_request():
    """
    Handles HTTP requests from the test-client.
    It attempts to forward the request over the single, persistent mTLS connection.
    """
    global persistent_conn
    
    req_id = request.headers.get('X-Request-ID', 'N/A')
    ERROR_MSG = f"503 Error: mTLS connection from Frontend to Backend is down."
    
    # If the connection failed (either at startup or later), drop the request
    if persistent_conn is None:
        log.error(f"[ReqID: {req_id}] DROPPING REQUEST. {ERROR_MSG} (Connection was None)")
        return ERROR_MSG, 503

    try:
        # --- HAPPY PATH ---
        # Attempt to use the existing persistent connection
        log.info(f"[ReqID: {req_id}] (HTTP IN) -> Forwarding request on persistent mTLS connection...")
        
        persistent_conn.request("GET", "/", headers={"X-Request-ID": req_id})
        response = persistent_conn.getresponse()
        data = response.read().decode()

        log.info(f"[ReqID: {req_id}] (mTLS OUT) -> Got response from backend: {data.strip()}")
        
        final_response = f"[FRONTEND-HTTP]: Forwarded ReqID {req_id}. Got: ({data})"
        return final_response, 200
    
    except (ssl.SSLError, http.client.NotConnected, http.client.RemoteDisconnected, BrokenPipeError, ConnectionRefusedError, TimeoutError) as e:
        # --- FAILURE PATH ---
        # This block catches any error with the persistent connection (e.g., certificate rotation).
        # This "legacy" app is designed to FAIL and NOT RECOVER.
        log.error(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        log.error(f"[ReqID: {req_id}] mTLS CONNECTION ERROR (Frontend to Backend): {type(e).__name__} - {e}")
        log.error(f"[ReqID: {req_id}] The persistent mTLS connection has FAILED.")
        log.error("This 'legacy' app will NOT reconnect. Dropping all future requests.")
        log.error(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        
        # Close the broken connection and set it to None to stop future attempts
        if persistent_conn:
            persistent_conn.close()
        persistent_conn = None 
        
        return ERROR_MSG, 503

if __name__ == "__main__":
    # Start the Waitress server for the Flask app
    log.info(f"Starting Case 1/2: 'Legacy' Flask server listening on http://{LISTEN_HOST}:{LISTEN_PORT}")
    serve(
        app,
        host=LISTEN_HOST, 
        port=LISTEN_PORT
    )