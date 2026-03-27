Here's a clear, step-by-step plan to build a simple, easily deployable web app that interacts with your **StreamToVLLM** RAG setup on Minikube. The app will feature a decent but minimal UI for:

- Sending the example question ("What is streamtovllm?") — or any custom query — to the **vLLM** API (OpenAI-compatible `/v1/chat/completions`).
- Buttons to **delete and recreate** the Qdrant collection (`my-rag-collection`).
- Buttons to **start/stop** the relevant NiFi flows/process groups (e.g., `StreamTovLLM` and `IngestToStream`).

The app will be a lightweight **FastAPI + React** (or simpler: **FastAPI + HTMX/Tailwind** for minimal frontend) single-container deployment via Kubernetes Deployment + Service. This keeps it "easily deployable" on Minikube alongside your existing components.

### 1. Prerequisites & Assumptions (Based on the Blog Setup)
- Your Minikube cluster already runs:
  - Cloudera Streaming Operators (CFM for NiFi in namespace `cfm-streaming`).
  - vLLM service (`vllm-service` in `default`, port 8000, OpenAI-compatible API).
  - Qdrant service (`qdrant`, port 6333).
  - Embedding server (if needed for full RAG, but your UI focuses on query).
  - NiFi web UI accessible (likely via port-forward or ingress).
- Services are ClusterIP. The app will use Kubernetes service DNS (e.g., `http://vllm-service.default.svc.cluster.local:8000`).
- For local testing: Use `kubectl port-forward` for services during development.
- No authentication assumed on internal APIs (common in local Minikube setups). Add basic auth or tokens later if needed.
- GPU passthrough already enabled for vLLM.

If any services differ (e.g., exact NiFi process group IDs or collection name), adjust the config.

### 2. High-Level Architecture of the New App
- **Backend (FastAPI/Python)**: Handles API calls to vLLM, Qdrant, and NiFi. Acts as a proxy to avoid CORS issues and centralize logic.
- **Frontend**: Simple single-page UI with:
  - Text input + "Ask" button for queries (pre-filled with "What is streamtovllm?").
  - Response display area (with streaming support if you want polish).
  - Buttons: "Delete Qdrant Collection" + "Recreate Qdrant Collection".
  - Buttons: "Start NiFi Flows" / "Stop NiFi Flows" (target specific process groups or the whole flow).
- **Deployment**: One Kubernetes Deployment (with optional ConfigMap for endpoints/ports). Expose via NodePort or Minikube Ingress for easy browser access.
- **Why this stack?** FastAPI is lightweight, async-friendly (good for API calls), and deploys easily. HTMX keeps the frontend simple (no heavy React build step if you prefer). Full React/Vite works too for a "decent" polished look.

### 3. Step-by-Step Implementation Plan

#### Step A: Create the Backend (FastAPI)
1. Set up a new project:
   ```bash
   mkdir streamtovllm-ui && cd streamtovllm-ui
   python -m venv venv
   source venv/bin/activate
   pip install fastapi uvicorn httpx python-dotenv jinja2  # Add openai if using client
   ```

2. Define environment/config (use a `.env` or Kubernetes ConfigMap):
   - `VLLM_URL=http://vllm-service.default.svc.cluster.local:8000/v1/chat/completions`
   - `QDRANT_URL=http://qdrant.default.svc.cluster.local:6333`
   - `NIFI_URL=http://<nifi-service>.cfm-streaming.svc.cluster.local:8080/nifi-api` (adjust based on your CFM deployment; often needs port-forward initially).
   - Collection name: `my-rag-collection`
   - NiFi process group IDs or names (you'll need to fetch these via NiFi API or hardcode from your flows: `StreamTovLLM`, `IngestToStream`).

3. Key endpoints in `main.py`:
   - `POST /query`: Takes user question, builds a proper RAG prompt (system: "Briefly answer using this context." + retrieved context if you implement retrieval; or simple direct call as in the blog example). Forwards to vLLM. Support streaming with `stream=True`.
   - `POST /qdrant/delete`: `DELETE {QDRANT_URL}/collections/my-rag-collection`
   - `POST /qdrant/recreate`: First delete, then `PUT {QDRANT_URL}/collections/my-rag-collection` with body `{"vectors": {"size": 768, "distance": "Cosine"}}`
   - `POST /nifi/start` and `/nifi/stop`: Use NiFi REST API.
     - Common pattern: GET process group or processor details → extract revision/version → PUT to `/flow/process-groups/{id}` or `/processors/{id}/run-status` with `{"state": "RUNNING" or "STOPPED"}`.
     - Target the root process group or specific ones for your two flows. You may need to list components first (`/flow/search-results` or `/process-groups/{id}/processors`).

   Use `httpx.AsyncClient` for calls. Handle errors gracefully and return JSON responses.

4. Add a simple root endpoint serving HTML (or separate static files).

Example vLLM call (using OpenAI client for simplicity):
```python
from openai import AsyncOpenAI
client = AsyncOpenAI(base_url=VLLM_BASE, api_key="not-needed")
response = await client.chat.completions.create(
    model="Qwen/Qwen2.5-3B-Instruct",
    messages=[{"role": "user", "content": question}],
    temperature=0.7
)
```

For full RAG, you'd add embedding + Qdrant search steps before the LLM call (optional for your "decent but simple" request).

#### Step B: Create the Frontend (Simple & Decent UI)
Options:
- **Easiest (recommended for speed)**: FastAPI with Jinja2 + Tailwind + HTMX. One HTML page with cards/buttons. Query input → results div updates via HTMX (no page reload).
- **Polished alternative**: Vite + React + Tailwind. Buttons trigger fetch to backend. Use a chat-like interface for queries.

UI Layout:
- Header: "StreamToVLLM Control Panel"
- Section 1: Query — Input box (default: "What is streamtovllm?"), "Send to vLLM" button, response box (markdown-friendly).
- Section 2: Qdrant Management — "Delete Collection" (warning modal), "Recreate Collection".
- Section 3: NiFi Controls — "Start StreamTovLLM Flow", "Stop StreamTovLLM Flow", same for Ingest flow. Status indicators (poll `/flow` endpoints optionally).
- Add loading spinners and toast notifications for feedback.

Keep it responsive and clean (Tailwind makes this quick).

#### Step C: Containerize the App
Create a `Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build & test locally: `docker build -t streamtovllm-ui . && docker run -p 8000:8000 streamtovllm-ui`

#### Step D: Kubernetes Manifests for Easy Minikube Deployment
Create these YAML files (apply with `kubectl apply -f`):

- **ConfigMap** for endpoints/ports (so you can update without rebuilding).
- **Deployment**:
  ```yaml
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: streamtovllm-ui
  spec:
    replicas: 1
    template:
      spec:
        containers:
        - name: ui
          image: streamtovllm-ui:latest  # or your registry
          ports:
          - containerPort: 8000
          envFrom:
          - configMapRef:
              name: streamtovllm-config
  ```
- **Service** (NodePort for easy Minikube access):
  ```yaml
  apiVersion: v1
  kind: Service
  metadata:
    name: streamtovllm-ui
  spec:
    type: NodePort
    ports:
    - port: 8000
      targetPort: 8000
      nodePort: 30000  # Access via http://$(minikube ip):30000
    selector:
      app: streamtovllm-ui
  ```

Optional: Add Minikube Ingress for a nice domain-like URL.

To make it "easily deployable":
- Put all YAML + Dockerfile in a Git repo with a `deploy.sh` script (`minikube image build ...` then `kubectl apply`).
- Or package as a Helm chart (simple one-chart for the UI).

#### Step E: Testing & Iteration
1. Deploy your existing RAG components first.
2. Port-forward services as needed during dev.
3. Run the UI locally, point config to `localhost:port` via port-forward.
4. Deploy to Minikube, access via NodePort, test:
   - Query button → should return vLLM response.
   - Qdrant buttons → verify with Qdrant dashboard (`kubectl port-forward svc/qdrant 6333:6333`).
   - NiFi buttons → check NiFi UI for flow states.
5. Enhance: Add retrieval (embed query → Qdrant search → inject context to vLLM). Add logs/status polling.

### 4. Potential Challenges & Tips
- **NiFi API details**: Process group start/stop often requires revision/version in the payload. Fetch it first or use the `/flow/process-groups/{id}` endpoint. Test with curl against your running NiFi.
- **Service Discovery**: Use full Kubernetes DNS in production config; fallback to env vars.
- **Security**: In a real setup, add API keys or mTLS, but skip for local Minikube.
- **Streaming Responses**: Use Server-Sent Events (SSE) in FastAPI for nice LLM token streaming in the UI.
- **Dependencies**: If your NiFi flows need specific IDs, expose them via the NiFi API discovery endpoints.
- **Resource Limits**: Keep the UI pod light (no GPU needed).

### 5. Timeline & Next Actions
- **Day 1**: Build backend + basic HTML frontend, test against port-forwarded services.
- **Day 2**: Add Qdrant/NiFi controls, polish UI with Tailwind/HTMX.
- **Day 3**: Dockerize + create Kubernetes manifests, test full deployment on Minikube.
- **Polish (optional)**: Add chat history, error handling, or integrate full RAG retrieval.

This setup keeps everything self-contained and leverages your existing `StreamToVLLM` architecture without major changes. Start by cloning/extracting the relevant YAMLs from the blog and fetching your exact NiFi component IDs via the NiFi REST API or UI.

If you share more specifics (e.g., exact NiFi service name, process group IDs, or if you prefer React vs. HTMX), I can provide sample code snippets for the FastAPI routes or full manifests. Let me know where you want to dive deeper!
