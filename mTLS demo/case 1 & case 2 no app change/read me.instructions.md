# Demo: Phase 1 - "Legacy App" mTLS Rotation & Restart

This document provides a step-by-step guide to demonstrate a common failure scenario for "legacy" applications in a modern, automated mTLS environment.

## Overview

This demo proves that a "legacy" application, which holds a *single persistent mTLS connection* in memory, will fail when `cert-manager`'s CSI driver automatically rotates the certificate on disk. It will also demonstrate that the **only** fix for this type of application is a forced `rollout restart`.

## Prerequisites

  * [Minikube](https://minikube.sigs.k8s.io/docs/start/)
  * [Docker](https://www.docker.com/get-started/)
  * [Helm](https://helm.sh/docs/intro/install/)
  * [kubectl](https://kubernetes.io/docs/tasks/tools/)
  * [Git for Windows](https://git-scm.com/downloads/) (provides `openssl` via Git Bash)
  * A PowerShell terminal (the provided commands are in PowerShell format)

-----

## Step 1: Start Minikube & Connect Docker Environment

First, start your local Kubernetes cluster.

```powershell
minikube start
```

Next, connect your local shell's Docker client to the Docker daemon *inside* the Minikube cluster.

```powershell
# This command configures your PowerShell session
minikube docker-env | Invoke-Expression
```

> **Note:** This is a **critical step**. It ensures that when you build Docker images in Step 3, they are built directly inside Minikube's environment. This allows the cluster to find the images locally (`imagePullPolicy: Never`) without needing an external registry.

-----

## Step 2: Install Cert-Manager with CSI-SPIFFE Driver

We will use Helm to install `cert-manager`. The flags `--set csiDriver.enabled=true` and `--set csiDriver.spiffe.enabled=true` are essential for this demo. They enable the [CSI (Container Storage Interface) driver](https://cert-manager.io/docs/usage/csi-driver/), which will automatically mount the mTLS certificates and keys directly into our application pods as a volume.

```powershell
# 1. Add the Jetstack Helm repository
helm repo add jetstack https://charts.jetstack.io

# 2. Update your repository list
helm repo update

# 3. Install cert-manager
helm install cert-manager jetstack/cert-manager `
  --namespace cert-manager `
  --create-namespace `
  --set installCRDs=true `
  --set csiDriver.enabled=true `
  --set csiDriver.spiffe.enabled=true
```

After running the install command, wait for all pods in the `cert-manager` namespace to be in the `Running` state before proceeding.

```powershell
# Check the status of the cert-manager pods
kubectl get pods -n cert-manager
```

-----

## Step 3: Build Application Docker Images

With your shell connected to Minikube's Docker daemon, build the application images. These commands assume you are in the root directory containing the `backend/` and `frontend/` sub-directories.

```powershell
# 1. Build the backend image
# (Note: The path './backend' tells Docker where to find the Dockerfile)
docker build -t py-backend:gunicorn ./backend

# 2. Build the frontend image
# (Note: The path './frontend' tells Docker where to find the Dockerfile)
docker build --no-cache -t py-mtls-frontend:phase1-persistent ./frontend
```

-----

## Step 4: Deploy Kubernetes Applications

This step first cleans up any resources from a previous deployment and then applies all the new Kubernetes manifests.

### 4.1. Cleanup (Optional)

Run these commands to delete all resources from any previous demo. The `--ignore-not-found=true` flag prevents errors if the resources don't exist.

```powershell
kubectl delete deployment frontend-deployment --ignore-not-found=true
kubectl delete deployment backend-deployment --ignore-not-found=true
kubectl delete service backend-svc --ignore-not-found=true
kubectl delete service frontend-svc --ignore-not-found=true
kubectl delete pod curl-client --ignore-not-found=true
kubectl delete certificate demo-ca --ignore-not-found=true
kubectl delete issuer demo-ca --ignore-not-found=true
kubectl delete clusterissuer selfsigned-ca --ignore-not-found=true

# Wait 5-10 seconds for resources to terminate
Start-Sleep -s 10
```

### 4.2. Deploy Resources

Apply all the `.yaml` manifests to create the services, deployments, and certificate issuers.

> **Note:** These commands assume all your `.yaml` files are located in the current directory.

```powershell
# 1. Apply the Certificate Authority Issuer
kubectl apply -f ca-issuer.yaml

# 2. Apply the backend deployment and service
kubectl apply -f backend.yaml

# 3. Apply the frontend service
kubectl apply -f frontend-svc.yaml

# 4. Apply the frontend deployment (with 1-minute cert)
kubectl apply -f frontend.yaml

# 5. Apply the curl client pod to start sending traffic
kubectl apply -f curl-client.yaml
```

-----

## Step 5: Execute the K8s Demo (Failure & Recovery)

This is the main Kubernetes test. You will observe the system working, then failing, and then being manually recovered.

### 5.1. Open Log Terminals

You need **3 separate terminals** to watch the logs from all components simultaneously.

**🖥️ Terminal 1: Watch the `curl-client` (The Requester)**

```powershell
kubectl logs -f curl-client
```

**🖥️ Terminal 2: Watch the `frontend` (The "Legacy" App)**

```powershell
kubectl logs -f -l app=frontend
```

**🖥️ Terminal 3: Watch the `backend` (The Target)**

```powershell
kubectl logs -f -l app=backend
```

### 5.2. Observe Initial Success (Time: 0m to 1m)

For the first minute, you will see all three logs streaming `SUCCESS` messages.

  * **Terminal 1 (`curl-client`):**
    ```
    Sending ReqID: 1
    SUCCESS: [ReqID: 1] Success! mTLS connection...
    Sending ReqID: 2
    SUCCESS: [ReqID: 2] Success! mTLS connection...
    ```
  * **Terminal 2 (`frontend`):**
    ```
    [ReqID: 1] [TLS_ID: abcdef...] SUCCESS from backend: [ReqID: 1]...
    [ReqID: 2] [TLS_ID: abcdef...] SUCCESS from backend: [ReqID: 2]...
    ```
  * **Terminal 3 (`backend`):**
    ```
    [ReqID: 1] Successful GET / request received...
    [ReqID: 2] Successful GET / request received...
    ```

### 5.3. Observe the Failure (Time: 5m+)

When the 1-minute certificate expires, the frontend's persistent connection will break.

  * **Terminal 1 (`curl-client`):** The `curl` command will now print the error message being returned by the frontend.
    ```
    Sending ReqID: 1234
    SUCCESS: [ReqID: 1234] Success! mTLS connection...
    Sending ReqID: 1235
    503 Error: mTLS connection from Frontend to Backend is down.
    Sending ReqID: 1236
    503 Error: mTLS connection from Frontend to Backend is down.
    ```
  * **Terminal 2 (`frontend`):** It will log the connection error *once* and then log "DROPPING REQUEST" for all future requests.
    ```
    [ReqID: 1235] mTLS CONNECTION ERROR (Frontend to Backend): SSLError...
    [ReqID: 1235] The persistent mTLS connection has FAILED.
    [ReqID: 1236] DROPPING REQUEST. 503 Error: mTLS connection...
    [ReqID: 1237] DROPPING REQUEST. 503 Error: mTLS connection...
    ```
  * **Terminal 3 (`backend`):** ...**Total silence.** The logs will stop completely.

### 5.4. Apply the Fix (The `rollout restart`)

Open a **4th terminal** and execute the fix.

```powershell
kubectl rollout restart deployment/frontend-deployment
```

### 5.5. Observe the Recovery

The `frontend` pod will restart, and the logs will recover.

  * **Terminal 1 (`curl-client`):** You will see a few requests get dropped (no output), and then `SUCCESS` messages will resume (e.g., starting at `ReqID: 2468`).
  * **Terminal 2 (`frontend`):** The `kubectl logs -f` command will show the old pod terminating and connect to the **new pod**. The new pod's logs will show it creating a *new* connection and resuming `SUCCESS` logs.
  * **Terminal 3 (`backend`):** The logs will suddenly spring back to life, starting from the first request the new frontend pod processed (e.g., `ReqID: 2468`).

**Conclusion:** This test successfully proves that the "legacy" application fails on certificate rotation, drops requests, and **requires a disruptive restart** to recover.

-----

## Step 6: Optional Test: "Base App" mTLS (No Docker/K8s)

This test proves the "developer story": that the `backend/app.py` script works as a "base app" on a local machine with manual, self-signed certificates, completely independent of Docker or Kubernetes.

### 6.1. Create Self-Signed Certificates

You only need to do this step once.

1.  **Open Git Bash:** This is required for the `openssl` command. (Do *not* use PowerShell for this step).

2.  **Navigate to Project Folder:**

    ```bash
    # Example path. Use the path to your project.
    cd "C:/k8s-python-demo/mTLS gemini/case 2 ( no app change) testing self signed certificate/py-mtls-demo/"
    ```

3.  **Go into `local-certs`:**

    ```bash
    cd local-certs
    ```

4.  **Run `openssl` Commands:** Run these commands one by one to create your local CA, server certificate, and client certificate. The double-slash `//` is required to prevent a Git Bash path error.

    ```bash
    # 1. Create your new "Root CA" (10 years)
    openssl genrsa -out my-ca.key 4096
    openssl req -x509 -new -nodes -key my-ca.key -sha256 -days 3650 -out my-ca.crt -subj "//CN=My Local Test CA"

    # 2. Create the "Server" certificate (for the backend)
    openssl genrsa -out server.key 4096
    openssl req -new -key server.key -out server.csr -subj "//CN=localhost"
    openssl x509 -req -in server.csr -CA my-ca.crt -CAkey my-ca.key -CAcreateserial -out server.crt -days 3650 -sha256

    # 3. Create the "Client" certificate (for the frontend/client)
    openssl genrsa -out client.key 4096
    openssl req -new -key client.key -out client.csr -subj "//CN=my-local-client"
    openssl x509 -req -in client.csr -CA my-ca.crt -CAkey my-ca.key -CAcreateserial -out client.crt -days 3650 -sha256
    ```

5.  You can now close Git Bash.

### 6.2. Start the Backend Server (Terminal 1)

1.  **Open PowerShell** and navigate to your project's root folder.
2.  **Go into the `backend` folder:**
    ```powershell
    cd backend
    ```
3.  **Run the Server:** Use the `py` command (or `python` if you have fixed your PATH).
    ```powershell
    py app.py
    ```
4.  **Expected Output:** The server will start and wait.
    ```
    INFO - mTLS configured. Server listening on https://0.0.0.0:8443
    ```

### 6.3. Start the Client (Terminal 2)

1.  **Open a *new* PowerShell terminal** and navigate to your project's **root** folder.
2.  **Run the Client:** Use the `py` command.
    ```powershell
    py test_client.py
    ```
3.  **Expected Output:** The client will start and successfully connect.
    ```
    INFO - [ReqID: 1] SUCCESS! Response from backend: [ReqID: 1] Success! ...
    INFO - [ReqID: 2] SUCCESS! Response from backend: [ReqID: 2] Success! ...
    ```

**Conclusion:** This test proves the `backend/app.py` script is a "dual-use" application. It can be run locally by a developer via its `if __name__ == "__main__":` block, and it can *also* be run by Gunicorn (in Docker/K8s) which ignores that block, all without code changes.

-----

## Step 7: Optional Test: Verify mTLS Security Enforcement

This test confirms that the Kubernetes `backend` service is truly secure and will **reject** any connection that does not present a valid mTLS certificate.

### 7.1. Watch Backend Logs (Terminal 1)

In one terminal, keep the *Kubernetes* backend logs running. (You must have completed Step 4 for this).

```powershell
kubectl logs -f -l app=backend
```

### 7.2. Run a "Rogue" Pod (Terminal 2)

In a *second* terminal, run a temporary `alpine` pod.

```powershell
kubectl run rogue-client --image=alpine --rm -it -- sh
```

### 7.3. Install curl (Inside the Rogue Pod)

Once inside the pod's shell (you'll see a `/ #` prompt), update the package manager and install `curl`:

```powershell
# / #
apk update && apk add curl
```

### 7.4. Attempt Connection (Inside the Rogue Pod)

Now, try to connect to the backend's secure port. This client has *no certificate* to present.

```powershell
# / #
curl -v -k https://backend-svc:8443
```

> **Note:** We use `-k` (insecure) only to tell `curl` to not validate the *server's* certificate. The server, however, will still validate the *client's* certificate.

### 7.5. Observe the Failure

You will see the `curl` command (in **Terminal 2**) fail.

**Expected `curl` Output (Failure):**

```
* TLSv1.3 (IN), TLS handshake, Request CERT (13):
...
* OpenSSL SSL_read: ... tlsv13 alert certificate required, errno 0
curl: (56) OpenSSL SSL_read: ... tlsv13 alert certificate required, errno 0
```

Simultaneously, you will see the explicit rejection message in your backend logs (**Terminal 1**).

**Expected Backend Log (Rejection):**

```
[...timestamp...] [WARNING] Invalid request from ip=10.244.X.X: [SSL: PEER_DID_NOT_RETURN_A_CERTIFICATE] peer did not return a certificate
```

### 7.6. Clean Up

In the rogue pod's terminal (Terminal 2), type `exit` and press Enter. The pod will be automatically deleted. This test confirms your backend is secure and correctly enforcing mTLS.

