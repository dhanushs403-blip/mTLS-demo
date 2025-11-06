# End-to-End mTLS on Kubernetes
### cert-manager + CSI Driver + Auto-Rotation | Python Frontend & Backend

This project demonstrates how to evolve a standard HTTP microservice architecture into a zero-trust, mTLS-secured architecture on Kubernetes. It is broken into three distinct cases.

| Case | Description | Cert Rotation | Code Change |
| :--- | :--- | :--- | :--- |
| Case 1 | Local apps, no Kubernetes | ❌ | ❌ |
| Case 2 | Kubernetes mTLS (cert-manager + CSI) | ✅ (Restart needed) | ❌ |
| Case 3 | Kubernetes mTLS with Auto-Reload & Toggling | ✅ (No restart) | ✅ (Small change) |

---

## Architecture Evolution

This repository demonstrates three phases of application development:

1.  **Phase 1: Local Baseline (Case 1)**
    * Standard local Python development.
    * The frontend and backend services communicate over plain, unencrypted HTTP.
    * This serves as our non-secure baseline.

2.  **Phase 2: Lift-and-Shift to mTLS (Case 2)**
    * The *exact same* application code is containerized and deployed to Kubernetes.
    * mTLS is enforced **externally** by `cert-manager` and the `cert-manager-csi-driver`, which injects certificates directly into the pod's filesystem.
    * **Key Behavior:** The application is unaware of mTLS and must be manually restarted (`kubectl rollout restart`) to pick up newly rotated certificates. This demonstrates a "lift-and-shift" approach with zero code changes.

3.  **Phase 3: Cloud-Native Auto-Reload & Toggling (Case 3)**
    * A minimal, cloud-native code change is introduced.
    * The Python applications are enhanced to:
        1.  Watch the certificate files on disk and reload them without a restart.
        2.  Read a `USE_MTLS` environment variable to toggle between mTLS and plain HTTP, allowing for final-state validation.

---

## Prerequisites

* Minikube
* Docker
* kubectl
* Helm
* Python 3.9+
* Wireshark (for final validation)

---

## Initial Cluster Setup

1.  **Start Minikube**
    ```bash
    minikube start
    ```

2.  **Point Docker to Minikube**
    This ensures your `docker build` commands build images inside Minikube's runtime.

    *For PowerShell:*
    ```bash
    minikube docker-env | Invoke-Expression
    ```
    *For macOS/Linux (bash/zsh):*
    ```bash
    eval $(minikube docker-env)
    ```

---

## CASE 1: Local Mode (No Kubernetes)

This runs the apps locally as standard Python scripts.

1.  **Run Backend (in Terminal 1)**
    ```bash
    cd backend
    python app.py
    ```

2.  **Run Frontend (in Terminal 2)**
    ```bash
    cd frontend
    python app.py
    ```

3.  **Run Test Client (in Terminal 3)**
    From the project root directory:
    ```bash
    python test_client.py
    ```
    *Expected Output: You should see logs showing successful plaintext HTTP communication.*

    `<img width="851" height="202" alt="image" src="https://github.com/user-attachments/assets/180638a3-1ce0-488b-beae-6885edd79b14" />
`

---

## CASE 2: Kubernetes mTLS (CSI + Restart)

This deploys the original, unchanged application to Kubernetes and enforces mTLS.

1.  **Install cert-manager & CSI Driver**
    ```bash
    helm repo add jetstack [https://charts.jetstack.io](https://charts.jetstack.io)
    helm repo update

    # Install cert-manager
    helm install cert-manager jetstack/cert-manager \
      --namespace cert-manager \
      --create-namespace \
      --set installCRDs=true

    # Install the CSI driver
    helm install cert-manager-csi-driver jetstack/cert-manager-csi-driver \
      --namespace cert-manager
    ```

2.  **Verify cert-manager Pods**
    Wait until all pods are in a `Running` state.
    ```bash
    kubectl get pods -n cert-manager
    ```
    `<img width="647" height="93" alt="image" src="https://github.com/user-attachments/assets/397c411f-0ca7-47cb-9527-f07deb80ed33" />
`

3.  **Build Docker Images (Case 2)**
    (Ensure you are in the project root)
    ```bash
    docker build -t py-backend:gunicorn .
    docker build -t py-mtls-frontend:phase1-persistent .
    ```

4.  **Deploy mTLS Infrastructure & Apps**
    ```bash
    kubectl apply -f ca-issuer.yaml
    kubectl apply -f backend.yaml
    kubectl apply -f frontend.yaml
    ```
    *(Note: Ensure the YAMLs point to the `py-backend:gunicorn` and `py-frontend:phase1` images)*

5.  **Test the Application**
    *In a new terminal, start port forwarding:*
    ```bash
    kubectl port-forward svc/frontend-svc 8080:8080
    ```
    *In another terminal, run the client:*
    ```bash
    python test_client.py
    ```
    *Expected Output: You should see successful mTLS communication.*

6.  **Demonstrate Certificate Rotation (Manual Restart)**
    To force the pods to pick up new certs, you must restart them:
    ```bash
    kubectl rollout restart deployment frontend-deployment backend-deployment
    ```

    `<img width="893" height="279" alt="image" src="https://github.com/user-attachments/assets/ed851272-294a-4c90-977e-e409ea157dea" />
`
`<img width="887" height="314" alt="image" src="https://github.com/user-attachments/assets/90e32b1c-1918-47d3-ac08-c1caaca9cbff" />
`

---

## CASE 3: Kubernetes mTLS with Auto-Reload & Wireshark Validation

This deploys the *updated* application code that can reload certs and be toggled for validation.

1.  **Reset Environment**
    ```bash
    kubectl delete deployment frontend-deployment --ignore-not-found=true
    kubectl delete deployment backend-deployment --ignore-not-found=true
    kubectl delete service frontend-svc --ignore-not-found=true
    kubectl delete service backend-svc --ignore-not-found=true
    kubectl delete certificate demo-ca --ignore-not-found=true
    kubectl delete issuer demo-ca --ignore-not-found=true
    kubectl delete clusterissuer selfsigned-ca --ignore-not-found=true
    ```

2.  **Build Updated Auto-Reload Images (Case 3)**
    (Ensure you are in the project root)
    ```bash
    docker build --no-cache -t py-mtls-frontend:case3 .
    docker build --no-cache -t py-mtls-backend:case3 .
    ```

3.  **Deploy Applications**
    *(Note: Ensure your `frontend.yaml` and `backend.yaml` files are updated to use the `:case3` image tags)*
    ```bash
    kubectl apply -f ca-issuer.yaml
    kubectl apply -f backend.yaml
    kubectl apply -f frontend.yaml
    ```

4.  **Final Proof: Packet Capture (mTLS vs. HTTP)**

    **Step 4.1: Get Backend Service IP**
    Copy the IP address returned by this command. You will need it for the capture filters.
    ```bash
    kubectl get svc backend-svc -o jsonpath='{.spec.clusterIP}'
    ```

    **Step 4.2: Capture Plain HTTP (mTLS=false)**
    First, we set the apps to `mTLS=false` mode.
    ```bash
    kubectl set env deploy/frontend-deployment USE_MTLS=false
    kubectl set env deploy/backend-deployment USE_MTLS=false
    kubectl rollout restart deploy/frontend-deployment
    kubectl rollout restart deploy/backend-deployment
    ```
    Wait 20-30 seconds for the pods to restart. In a new terminal, start the capture (replace `<BACKEND_IP>`):
    ```bash
    minikube ssh -- sudo tcpdump -i any -w ~/plain.pcap "host <BACKEND_IP> and port 8080"
    ```
    While `tcpdump` is running, generate traffic:
    *In a new terminal, start port forwarding:*
    ```bash
    kubectl port-forward svc/frontend-svc 8080:8080
    ```
    ```bash
    python test_client.py
    ```
    Let it run for 5-10 seconds, then stop both the `tcpdump` and the `test_client` (`Ctrl+C`).

    **Step 4.3: Capture Encrypted mTLS (mTLS=true)**
    Now, we flip the flag to `mTLS=true`.
    ```bash
    kubectl set env deploy/frontend-deployment USE_MTLS=true
    kubectl set env deploy/backend-deployment USE_MTLS=true
    kubectl rollout restart deploy/frontend-deployment
    kubectl rollout restart deploy/backend-deployment
    ```
    Wait 20-30 seconds. In your `tcpdump` terminal, start a new capture:
    ```bash
    minikube ssh -- sudo tcpdump -i any -w ~/mtls.pcap "host <BACKEND_IP> and port 8080"
    ```
    While `tcpdump` is running, generate traffic again:
    *In a new terminal, start port forwarding:*
    ```bash
    kubectl port-forward svc/frontend-svc 8080:8080
    ```
    ```bash
    python test_client.py
    ```
    Let it run for 5-10 seconds, then stop both `tcpdump` and the `test_client`.

    **Step 4.4: Copy Capture Files**
    Copy the `.pcap` files from the Minikube node to your local machine:
    ```bash
    minikube cp minikube:/home/docker/plain.pcap plain.pcap
    minikube cp minikube:/home/docker/mtls.pcap mtls.pcap
    ```

    **Step 4.5: Analyze in Wireshark**
    Open both files in Wireshark. For `mtls.pcap`, you must **Right-click a packet -> Decode As... -> Set Port 8080 to "SSL"** to see the TLS handshake.

| Mode | `plain.pcap` | `mtls.pcap` |
| :--- | :--- | :--- |
| **Filter** | `http` | `tls` |
| **Result** | Readable HTTP `POST` requests. | `Client Hello`, `Server Hello`, `CertificateRequest`. |
| **Payload**| JSON is visible: `{"request_id": "1"}` | `Application Data` (Encrypted). |

`<img width="1920" height="740" alt="image" src="https://github.com/user-attachments/assets/d86f329e-285a-439a-b5cb-91d931ab9935" />
`

`<img width="1920" height="797" alt="image" src="https://github.com/user-attachments/assets/577029a6-d253-4c02-a7d7-1c1d1ace01fd" />
`

---

## Appendix: Optional Verification Steps

These steps are not required for the demo but are useful for debugging and proving the system is working as expected.

### 1. Verifying mTLS Enforcement (Rogue Pod Test)

This test proves that our mTLS setup enforces a "zero-trust" policy by blocking unauthorized clients.

**Prerequisite:** This test must be run while `CASE 3` is deployed and running with `USE_MTLS=true`.

1.  **Deploy the Rogue Pod**
    This pod does *not* have the CSI driver and therefore has no client certificates.
    ```bash
    kubectl run rogue-client --image=alpine --rm -it -- sh
    ```

2.  **Install curl (Inside the Pod Shell)**
    Once you are inside the pod's shell (`/ #`), install `curl`:
    ```bash
    apk update && apk add curl
    ```

3.  **Attempt to Access the Backend**
    Try to communicate directly with the `backend-svc`.
    *(Note: Our backend service is running on port `8080`)*
    ```bash
    curl -v -k https://backend-svc:8080
    ```

4.  **Analyze the Result (Proof of Failure)**
    The command will **fail** during the SSL/TLS handshake. This is the **correct and desired behavior**. The `backend-svc` (running Gunicorn in mTLS mode) sent a `CertificateRequest`, but our "rogue-client" had no certificate to provide.

    This proves that only pods with valid, CA-signed client certificates (like our `frontend` pod) are authorized to communicate.

    Type `exit` to close the rogue pod's shell.

### 2. Inspecting Live Certificates

You can pull the certificates directly from the running pods to inspect their details (like expiration time, common name, etc.).

1.  **Get the Exact Pod Names**
    Run this and copy the full names of your frontend and backend pods.
    ```bash
    kubectl get pods
    ```

2.  **Extract Certificates**
    Paste the full pod names into the commands below.

    *Extract backend cert:*
    ```bash
    kubectl exec <YOUR_BACKEND_POD_NAME_HERE> -- cat /var/run/secrets/mtls/tls.crt > backend-cert.crt
    ```

    *Extract frontend cert:*
    ```bash
    kubectl exec <YOUR_FRONTEND_POD_NAME_HERE> -- cat /etc/tls/tls.crt > frontend-cert.crt
    ```

3.  **Inspect with OpenSSL (Optional)**
    You can now read the contents of the saved certificates. This is useful to confirm the `Common Name` or check the `Not After` timestamp to verify rotation.
    ```bash
    openssl x509 -in backend-cert.crt -text -noout
    openssl x509 -in frontend-cert.crt -text -noout
    ```






