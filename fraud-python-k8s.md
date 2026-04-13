**Plan: Containerize your Python script as a Minikube Kubernetes pod (local testing replacement for Cloudera Workbench + InvokeHTTP)**

This follows the exact same structured approach we used last time for the NiFi flow (the one with the InvokeHTTP processor you attached). We'll turn the Python HTTP endpoint into a lightweight, self-contained Kubernetes Deployment + Service in Minikube so you can point your existing NiFi InvokeHTTP straight at it for local testing. No Cloudera Workbench required.

### Prerequisites (quick check – you already have most of this from our previous Minikube setups)
- Minikube running (`minikube status` should show Running)
- kubectl configured for Minikube (`kubectl config current-context` should show minikube)
- Docker Desktop (or Docker in WSL) running – we’ll build the image locally
- Your Python script (the one that was running in Cloudera Workbench) – it should be an HTTP server (Flask, FastAPI, etc.) listening on a port (usually 8080 or 5000)

If your Python app is not already an HTTP server, let me know the exact code and I’ll adjust the Dockerfile.

### Step 1: Create project folder and files
Create a new folder on your machine (e.g. `python-endpoint-k8s`):

```bash
mkdir python-endpoint-k8s && cd python-endpoint-k8s
```

Inside it, place these 3 files:

**1. `app.py`** (your existing Python script – just make sure it binds to `0.0.0.0`)
Example if you’re using Flask (replace with your real code):
```python
from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route('/', methods=['POST', 'GET'])
def handle_request():
    # Your original logic here (whatever InvokeHTTP was sending)
    data = request.get_json() if request.is_json else request.data
    print("Received from NiFi:", data)
    return jsonify({"status": "success", "message": "Python pod received it!"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
```

**2. `requirements.txt`** (add whatever your script needs)
```txt
flask==3.0.3
# add any other packages your script uses
```

**3. `Dockerfile`** (copy-paste exactly)
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080

CMD ["python", "app.py"]
```

### Step 2: Build the Docker image locally and load it into Minikube
```bash
# 1. Build the image
docker build -t python-endpoint:latest .

# 2. Tell Minikube to use the local Docker daemon (important!)
eval $(minikube docker-env)

# 3. Build again inside Minikube's Docker (so it sees the image)
docker build -t python-endpoint:latest .

# Optional: verify
docker images | grep python-endpoint
```

### Step 3: Create Kubernetes manifests
Create two files in the same folder:

**deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: python-endpoint
  namespace: default   # or your preferred namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: python-endpoint
  template:
    metadata:
      labels:
        app: python-endpoint
    spec:
      containers:
      - name: python-endpoint
        image: python-endpoint:latest
        imagePullPolicy: Never   # important for local images
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "256Mi"
```

**service.yaml**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: python-endpoint
  namespace: default
spec:
  type: ClusterIP     # use LoadBalancer or NodePort if you prefer external
  selector:
    app: python-endpoint
  ports:
  - port: 8080
    targetPort: 8080
    protocol: TCP
```

### Step 4: Deploy to Minikube
```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml

# Wait for pod to be ready
kubectl get pods -l app=python-endpoint -w
```

### Step 5: Get the URL for your NiFi InvokeHTTP processor
```bash
# Easiest way (opens in browser automatically and gives you the URL)
minikube service python-endpoint --url

# Or get it manually
minikube ip
# Then the URL will be: http://<minikube-ip>:8080
```

Example output you’ll see:
```
http://192.168.49.2:8080
```

### Step 6: Update your existing NiFi flow (the one you attached)
In your InvokeHTTP processor:
- **Remote URL** → change to the Minikube service URL you just got  
  Example: `http://192.168.49.2:8080`
- **HTTP Method** → keep whatever you were using (POST/GET)
- **Content-Type** → keep the same as before
- **Send Message Body** → true (or whatever you had)

No other changes needed to the rest of the flow.

### Step 7: Test it
1. Start your NiFi flow (or just the InvokeHTTP part)
2. Send a test message through the flow
3. Check the Python pod logs:
   ```bash
   kubectl logs -l app=python-endpoint --follow
   ```
   You should see the data you sent from NiFi appear in the logs.

### Bonus: Quick restart / cleanup commands you’ll use often
```bash
# Restart just the pod
kubectl rollout restart deployment/python-endpoint

# Delete everything (if you want to rebuild)
kubectl delete -f deployment.yaml -f service.yaml
```

That’s it — this is a direct drop-in replacement for the Cloudera Workbench Python endpoint.  

Let me know:
- The exact framework your Python script uses (Flask? FastAPI? plain http.server?), or paste the `app.py` if you want me to tweak the Dockerfile.
- Whether your NiFi is also running inside the same Minikube cluster (then we can use the internal service name `http://python-endpoint.default.svc.cluster.local:8080` instead of the external IP).

Ready when you are — just say “go” or “tweak XYZ” and I’ll give you the updated files!