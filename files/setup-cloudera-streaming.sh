#!/bin/bash
set -euo pipefail

echo "🚀 Cloudera Streaming Operators Full Setup (Minikube + All Operators)"

# ====================== CONFIG ======================
MINIKUBE_CPUS=6
MINIKUBE_MEMORY=16384   # 16GB recommended
LICENSE_FILE="./license.txt"
CLUSTER_NAMESPACE="cld-streaming"
CFM_NAMESPACE="cfm-streaming"

# Change this if you prefer NiFi 2.6.0 instead of 1.28.1
NIFI_VERSION="2x"   # or "2x"

# ===================================================

echo "🔍 Checking prerequisites..."
command -v minikube >/dev/null 2>&1 || { echo "minikube not found"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "helm not found"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl not found"; exit 1; }

if [ ! -f "$LICENSE_FILE" ]; then
  echo "❌ license.txt not found in current directory!"
  echo "   Place your Cloudera license file as ./license.txt"
  exit 1
fi

# 1. Start Minikube (idempotent)
if ! minikube status >/dev/null 2>&1; then
  echo "Starting Minikube with ${MINIKUBE_CPUS} CPUs and ${MINIKUBE_MEMORY}MB RAM..."
  minikube start --cpus "$MINIKUBE_CPUS" --memory "$MINIKUBE_MEMORY" --driver=docker
else
  echo "✅ Minikube already running"
fi

# Enable ingress (needed for NiFi)
minikube addons enable ingress

# 2. Cert-Manager (for CSA + NiFi certs)
echo "📦 Installing cert-manager..."
kubectl create namespace cert-manager --dry-run=client -o yaml | kubectl apply -f -
helm repo add jetstack https://charts.jetstack.io --force-update
helm repo update

if ! helm list -n cert-manager | grep -q cert-manager; then
  helm install cert-manager jetstack/cert-manager \
    --namespace cert-manager \
    --version v1.16.3 \
    --set installCRDs=true \
    --create-namespace
else
  echo "✅ cert-manager already installed"
fi

kubectl wait --namespace cert-manager --for=condition=Available deployment --all --timeout=300s

# 3. Cloudera Helm Registry Login
echo "🔑 Logging into Cloudera Helm registry..."
echo "   Enter your Cloudera username when prompted:"
helm registry login container.repository.cloudera.com

helm repo update

# 4. Namespaces + Secrets
echo "📂 Creating namespaces and secrets..."
kubectl create namespace "$CLUSTER_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace "$CFM_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# License secret (both namespaces)
kubectl create secret generic cfm-operator-license \
  --from-file=license.txt="$LICENSE_FILE" \
  --namespace "$CLUSTER_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic cfm-operator-license \
  --from-file=license.txt="$LICENSE_FILE" \
  --namespace "$CFM_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# Ask for Cloudera creds (only once)
if ! kubectl get secret cloudera-creds -n "$CLUSTER_NAMESPACE" >/dev/null 2>&1; then
  read -rp "Enter Cloudera container repository username: " CL_USERNAME
  read -rsp "Enter Cloudera container repository password: " CL_PASSWORD
  echo

  kubectl create secret docker-registry cloudera-creds \
    --docker-server=container.repository.cloudera.com \
    --docker-username="$CL_USERNAME" \
    --docker-password="$CL_PASSWORD" \
    --namespace "$CLUSTER_NAMESPACE"

  kubectl create secret docker-registry cloudera-creds \
    --docker-server=container.repository.cloudera.com \
    --docker-username="$CL_USERNAME" \
    --docker-password="$CL_PASSWORD" \
    --namespace "$CFM_NAMESPACE"
else
  echo "✅ cloudera-creds secret already exists"
fi

# NiFi admin creds
kubectl create secret generic nifi-admin-creds \
  --from-literal=username=admin \
  --from-literal=password=admin12345678 \
  --namespace "$CFM_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# 5. Install Operators
echo "🛠️ Installing Strimzi Kafka Operator..."
helm upgrade --install strimzi-cluster-operator \
  oci://container.repository.cloudera.com/cloudera-helm/csm-operator/strimzi-kafka-operator \
  --namespace "$CLUSTER_NAMESPACE" \
  --version 1.6.0-b99 \
  --set 'image.imagePullSecrets[0].name=cloudera-creds' \
  --set-file clouderaLicense.fileContent="$LICENSE_FILE" \
  --set watchAnyNamespace=true

#echo "🛠️ Installing CSA (Flink) Operator..."
#helm upgrade --install csa-operator \
#  oci://container.repository.cloudera.com/cloudera-helm/csa-operator/csa-operator \
#  --namespace "$CLUSTER_NAMESPACE" \
#  --version 1.5.0-b275 \
#  --set 'flink-kubernetes-operator.imagePullSecrets[0].name=cloudera-creds' \
#  --set 'ssb.sse.image.imagePullSecrets[0].name=cloudera-creds' \
#  --set 'ssb.sqlRunner.image.imagePullSecrets[0].name=cloudera-creds' \
#  --set 'ssb.mve.image.imagePullSecrets[0].name=cloudera-creds' \
#  --set 'ssb.database.imagePullSecrets[0].name=cloudera-creds' \
#  --set-file flink-kubernetes-operator.clouderaLicense.fileContent="$LICENSE_FILE"

echo "🛠️ Installing CFM (NiFi) Operator..."
helm upgrade --install cfm-operator \
  oci://container.repository.cloudera.com/cloudera-helm/cfm-operator/cfm-operator \
  --namespace "$CFM_NAMESPACE" \
  --version 3.0.0-b126 \
  --set installCRDs=true \
  --set image.repository=container.repository.cloudera.com/cloudera/cfm-operator \
  --set image.tag=3.0.0-b126 \
  --set "image.imagePullSecrets[0].name=cloudera-creds" \
  --set "imagePullSecrets={cloudera-creds}" \
  --set "authProxy.image.repository=container.repository.cloudera.com/cloudera_thirdparty/hardened/kube-rbac-proxy" \
  --set "authProxy.image.tag=0.19.0-r3-202503182126" \
  --set licenseSecret=cfm-operator-license

echo "📦 Deploying Schema Registry..."
helm upgrade --install schema-registry \
  oci://container.repository.cloudera.com/cloudera-helm/csm-operator/schema-registry \
  --namespace "$CLUSTER_NAMESPACE" \
  --version 1.6.0-b99 \
  --values sr-values.yaml \
  --set "image.imagePullSecrets[0].name=cloudera-creds"

echo "📦 Deploying Surveyor..."
helm upgrade --install cloudera-surveyor \
  oci://container.repository.cloudera.com/cloudera-helm/csm-operator/surveyor \
  --namespace "$CLUSTER_NAMESPACE" \
  --version 1.6.0-b99 \
  --values kafka-surveyor.yaml \
  --set image.imagePullSecrets=cloudera-creds \
  --set-file clouderaLicense.fileContent="$LICENSE_FILE"