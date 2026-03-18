It’s been a bit of a journey to align the Host Headers, the Service Selectors, and the Ingress rules! Here is the summarized, consolidated "Golden Path" to get NiFi running on Minikube with a stable URL and no 503 errors.

---

## 1. Environment Setup
Start Minikube and enable the Ingress controller. This allows you to use standard ports (80/443) instead of random tunnel ports.

```bash
minikube start
minikube addons enable ingress
```

## 2. Identify Connectivity Info
Get the internal IP of the Minikube VM. This is the "Entry Point" for your traffic.

```bash
minikube ip
# Example Output: 192.168.49.2
```

## 3. Update /etc/hosts
Map the NiFi internal domain name to that Minikube IP. This allows your browser to find the cluster.

```text
# Add this line to /etc/hosts
192.168.49.2  mynifi-web.cfm-streaming.svc.cluster.local
```

---

## 4. Create the Configuration (The 2 YAMLs)
You need two components: the **Service** (to find the pods) and the **Ingress** (to handle the URL and SSL). 

> **Note:** The `selector` below uses the specific labels we found on your `mynifi-0` pod.

### File: `nifi-combined.yaml`
```yaml
---
apiVersion: v1
kind: Service
metadata:
  name: mynifi-web
  namespace: cfm-streaming
spec:
  type: ClusterIP
  selector:
    # This now matches your pod exactly
    app.kubernetes.io/instance: mynifi
    app.kubernetes.io/name: server
  ports:
    - name: nifi-https
      protocol: TCP
      port: 443
      targetPort: 8443
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mynifi-ingress
  namespace: cfm-streaming
  annotations:
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    nginx.ingress.kubernetes.io/ssl-passthrough: "true"
spec:
  rules:
  - host: mynifi-web.mynifi.cfm-streaming.svc.cluster.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mynifi-web
            port:
              name: nifi-https

```

---

## 5. Apply and Verify
Apply the configuration and check that the "Bridge" between the Service and Pod is active.

```bash
# Apply the YAML
kubectl apply -f nifi-combined.yaml

# Verify Endpoints (Wait until an IP appears in the ENDPOINTS column)
kubectl get endpoints mynifi-web -n cfm-streaming
```

---

## 6. The Final URL
Since the Ingress is listening on the standard HTTPS port (443) and the hostname matches your `nifi.properties` whitelist exactly, use this URL:

**URL:** `https://mynifi-web.cfm-streaming.svc.cluster.local/nifi/`
