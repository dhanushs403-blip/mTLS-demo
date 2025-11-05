import http.client
import time
import logging
import os
import sys

# Configure logging to stream to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    stream=sys.stdout
)
log = logging.getLogger(__name__)

# --- Configuration ---
# Get frontend target from environment variables, with defaults
FRONTEND_HOST = os.environ.get("FRONTEND_HOST", "localhost")
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", 8080))
# -----------------------------

def run_test():
    """
    Runs a continuous stream of HTTP GET requests to the frontend service
    to simulate constant user traffic.
    """
    log.info(f"--- Starting Test Client ---")
    log.info(f"Targeting Frontend at: http://{FRONTEND_HOST}:{FRONTEND_PORT}")

    conn = None
    req_id = 1

    while True:
        try:
            # (Re)establish connection if it's lost or not yet created
            if conn is None:
                log.info("Establishing new connection to frontend...")
                conn = http.client.HTTPConnection(FRONTEND_HOST, FRONTEND_PORT, timeout=2.0)

            # Set the custom header that will be tracked through the system
            headers = {"X-Request-ID": str(req_id)}
            log.info(f"Sending ReqID: {req_id}...")

            # Send the plain HTTP GET request
            conn.request("GET", "/", headers=headers)
            response = conn.getresponse()
            data = response.read().decode()

            # Log the final response from the frontend
            log.info(f"   -> STATUS: {response.status} | RESPONSE: {data}\n")

            req_id += 1
            time.sleep(0.05)  # Send requests rapidly (20 requests/second)

        except (http.client.NotConnected, http.client.RemoteDisconnected, ConnectionRefusedError) as e:
            # Handle cases where the frontend service is not reachable
            log.error(f"Connection failed: {e}. Retrying in 3s...")
            conn = None  # Force re-connection on next loop
            time.sleep(3)
            
        except KeyboardInterrupt:
            # Allow graceful shutdown with Ctrl+C
            log.info("\nTest stopped.")
            if conn:
                conn.close()
            break

if __name__ == "__main__":
    run_test()