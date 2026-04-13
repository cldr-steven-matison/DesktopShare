To move your setup from your MacBook to an airgapped desktop, you need to "bundle" three main components: the **Helm Charts**, the **Container Images**, and the **External Manifests** (like cert-manager).

Since your MacBook has internet access and a working setup, you will use it as your "build station" to pull these assets down.

### Phase 1: Prepare the "Bundle" Directory
On your MacBook, create a folder to hold everything.
```bash
mkdir -p ~/csa-airgap/charts ~/csa-airgap/images ~/csa-airgap/manifests
cd ~/csa-airgap
```

### Phase 2: Pull the Helm Charts
Instead of installing from the OCI registry directly, you need to "pull" the compressed chart files.
```bash
# Export the chart to your local directory
helm pull oci://container.repository.cloudera.com/cloudera-helm/csa-operator/csa-operator --version 1.5.0-b275 -d ./charts
# Repeat for any other operators (CSM, CFM) you used
```

### Phase 3: Download External Manifests
Any file you previously used a URL for (like `kubectl create -f https://...`) needs to be downloaded as a physical file.
```bash
curl -L https://github.com/jetstack/cert-manager/releases/download/v1.8.2/cert-manager.yaml -o ./manifests/cert-manager.yaml
```

### Phase 4: Save the Container Images (Crucial)
In an airgapped environment, `kubectl` cannot pull images from Cloudera or DockerHub. You must save them as `.tar` files.

1.  **List the images** your current MacBook setup is using:
    ```bash
    kubectl get pods -A -o jsonpath="{.items[*].spec.containers[*].image}" | tr -s '[[:space:]]' '\n' | sort | uniq
    ```
2.  **Pull and Save** each image. For example, for the CSA operator:
    ```bash
    docker pull container.repository.cloudera.com/cloudera-helm/csa-operator/csa-operator:1.5.0-b275
    docker save container.repository.cloudera.com/cloudera-helm/csa-operator/csa-operator:1.5.0-b275 > ./images/csa-operator.tar
    ```
    *Note: Do this for every image found in step 1 (Flink, SSB, Cert-manager, etc.).*

### Phase 5: Transfer and Install on Desktop
1.  **Copy** the `~/csa-airgap` folder to your USB drive.
2.  **On the Airgapped Desktop**, plug in the USB and load the images into your local Docker/Minikube registry:
    ```bash
    docker load < ./images/csa-operator.tar
    # If using Minikube, use: minikube image load ./images/csa-operator.tar
    ```
3.  **Install the Manifests**:
    ```bash
    kubectl apply -f ./manifests/cert-manager.yaml
    ```
4.  **Install the Helm Chart** using the local file you pulled:
    ```bash
    helm install csa-operator --namespace cld-streaming \
    --version 1.5.0-b275 \
    --set 'flink-kubernetes-operator.imagePullSecrets[0].name=cloudera-creds' \
    --set 'ssb.sse.image.imagePullSecrets[0].name=cloudera-creds' \
    --set 'ssb.sqlRunner.image.imagePullSecrets[0].name=cloudera-creds' \
    --set 'ssb.mve.image.imagePullSecrets[0].name=cloudera-creds' \
    --set 'ssb.database.imagePullSecrets[0].name=cloudera-creds' \
    --set-file flink-kubernetes-operator.clouderaLicense.fileContent=./license.txt \
    ./charts/csa-operator-1.5.0-b275.tgz
    ```