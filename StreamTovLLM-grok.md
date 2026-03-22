**StreamTovLLM** — a streaming-aware, Cloudera-powered local RAG system running on your Minikube cluster.

### StreamTovLLM: Real-Time Local RAG with Cloudera Streaming Operators + vLLM

**Goal**  
Build a privacy-first, fully local semantic search & question-answering system over your documents/Git repos/URLs that:
- Ingests in real time (or batch) via Kafka
- Processes & embeds using NiFi + lightweight embedding model
- Stores vectors in a local vector DB (we'll use Qdrant, same as DeepFindr — easy to run in Minikube)
- Answers questions via your existing vLLM inference server (OpenAI-compatible endpoint)

**High-Level Architecture**

```
Kafka Topic (new docs/events)  
       ↓ (NiFi or Flink job)
Chunk + Embed (nomic or lightweight model)  
       ↓
Qdrant Vector DB (Deployment in Minikube)  
       ↔ Query → Retrieve chunks → Prompt → vLLM (your GPU pod) → Answer
       ↔ Optional: Surveyor for observability, SSB for SQL analytics over metadata
```

**Prerequisites** (You Already Have Most!)
- Minikube running with your Cloudera Streaming stack (Kafka, NiFi, Flink, vLLM pod from earlier guides)
- GPU-enabled vLLM service exposed (e.g., http://localhost:8000 from port-forward)
- Docker / kubectl / Helm access
- A small embedding model (we'll use ONNX runtime or sentence-transformers in a container)
- Qdrant Docker image (official)

### Step 1: Deploy Qdrant in Minikube

Qdrant is lightweight and perfect for local vector storage.

Create `qdrant-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qdrant
spec:
  replicas: 1
  selector:
    matchLabels:
      app: qdrant
  template:
    metadata:
      labels:
        app: qdrant
    spec:
      containers:
      - name: qdrant
        image: qdrant/qdrant:latest
        ports:
        - containerPort: 6333
        - containerPort: 6334  # gRPC
        volumeMounts:
        - name: qdrant-data
          mountPath: /qdrant/storage
      volumes:
      - name: qdrant-data
        emptyDir: {}   # For dev; use persistentVolumeClaim for real use
---
apiVersion: v1
kind: Service
metadata:
  name: qdrant
spec:
  selector:
    app: qdrant
  ports:
  - name: http
    port: 6333
    targetPort: 6333
  - name: grpc
    port: 6334
    targetPort: 6334
  type: ClusterIP
```

Apply it:

```bash
kubectl apply -f qdrant-deployment.yaml
```

Port-forward to test:

```bash
kubectl port-forward svc/qdrant 6333:6333
# Then curl http://localhost:6333/ → should respond
```

### Step 2: Ingest Documents via NiFi (The Streaming Magic)

NiFi is perfect here.

1. In your NiFi UI (`https://mynifi-web.../nifi/`), create a new process group "StreamFindr-Ingestion".

2. **Example Flow** (high-level):
   - **ConsumeKafka** → topic `new-documents` (or `urls-to-crawl`, `github-webhooks`)
   - **ConvertRecord** / **ExtractText** (for PDF/Text/JSON)
   - **SplitText** or custom script → chunk into ~512 token pieces
   - **InvokeHTTP** or ExecuteScript → call a lightweight embedding service (see Step 3)
   - **InvokeHTTP** → POST to Qdrant `/collections/{collection}/points` with vector + payload (text, source, timestamp)

   For GitHub repos or URLs, add **GetHTTP** + **JoltTransformJSON** processors.

   Save + start the flow.

   (If you prefer Flink, write a simple Table API job to read Kafka → embed → write to Qdrant via JDBC/HTTP sink.)

### Step 3: Lightweight Embedding Service (Optional but Recommended)

To avoid calling external APIs, deploy a tiny embedding server.

Use sentence-transformers or ONNX version of nomic-embed.

Quick Deployment (`embedding-server.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: embedding-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: embedding
  template:
    metadata:
      labels:
        app: embedding
    spec:
      containers:
      - name: embedder
        image: ghcr.io/huggingface/text-embeddings-inference:1.5  # or custom with nomic
        args: ["--model-id", "nomic-ai/nomic-embed-text-v1", "--pooling", "cls"]
        ports:
        - containerPort: 8080
        resources:
          limits:
            cpu: "2"
            memory: 4Gi
---
apiVersion: v1
kind: Service
metadata:
  name: embedding-service
spec:
  selector:
    app: embedding
  ports:
  - port: 8080
    targetPort: 8080
```

Apply → port-forward → POST text to `http://localhost:8080/embed` for vectors.

NiFi can call this service per chunk.

### Step 4: Query Time – Ask Questions via vLLM

Create a simple query script or NiFi flow (or Python client) that:
1. Takes your question
2. Embeds it (same embedding service)
3. Searches Qdrant (`/collections/{name}/points/search`) for top-5 chunks
4. Builds prompt: "Answer using only this context: {chunks}\nQuestion: {q}"
5. Calls your vLLM endpoint (`/v1/chat/completions`)

Example curl (assuming port-forward on vLLM):

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-3B-Instruct",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant answering from provided context only."},
      {"role": "user", "content": "Context:\n[chunk1]\n[chunk2]\nQuestion: What is StreamToVLLM?"}
    ]
  }'
```

### Step 5: Make It Stream Even Better

- **Real-time updates** — Kafka topic triggers re-embed on change
- **Metadata enrichment** — Use Flink to add timestamps, sources, entities
- **Observability** — Cloudera Surveyor on the ingestion topic
- **Scale** — Add more vLLM replicas or switch to larger model (e.g., Qwen2.5-14B if VRAM allows)

### Cleanup

```bash
kubectl delete -f qdrant-deployment.yaml
# Delete embedding if deployed
```
