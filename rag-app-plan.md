Here's a clear, step-by-step plan to build a simple, easily deployable web app that interacts with your **StreamToVLLM** RAG setup on Minikube. The app will feature a decent, polished UI using React + Vite + TypeScript + Tailwind CSS + shadcn/ui for:

- Sending the example question ("What is streamtovllm?") — or any custom query — to the **vLLM** API (OpenAI-compatible `/v1/chat/completions`).
- Buttons to **delete and recreate** the Qdrant collection (`my-rag-collection`).
- Buttons to **start/stop** the relevant NiFi flows/process groups (e.g., `StreamTovLLM` and `IngestToStream`).

The app will be a lightweight **FastAPI + React** single-container deployment via Kubernetes Deployment + Service. This keeps it "easily deployable" on Minikube alongside your existing components.

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
- **Frontend**: React (Vite + TypeScript + Tailwind CSS + shadcn/ui) – Chat-like interface for queries, control panels for Qdrant and NiFi.
- **Backend (FastAPI/Python)**: Handles API calls to vLLM, Qdrant, and NiFi. Acts as a proxy to avoid CORS issues and centralize logic.
- **Communication**: Frontend fetches from backend (`/api/query`, `/api/qdrant/*`, `/api/nifi/*`).
- **Full RAG Support** (recommended for realism): The query flow mirrors the blog:
  1. Embed query via **embedding-server-service**.
  2. Search **my-rag-collection** in Qdrant for context.
  3. Build prompt with context + question.
  4. Call **vLLM** `/v1/chat/completions`.
- **Deployment**: One Docker image containing both frontend (built static files) and backend. Deploy as a single Kubernetes Deployment + NodePort Service.

**Key Services (from your setup)**:
- vLLM: `http://vllm-service.default.svc.cluster.local:8000/v1/chat/completions` (model: `Qwen/Qwen2.5-3B-Instruct`).
- Qdrant: `http://qdrant.default.svc.cluster.local:6333` (collection: `my-rag-collection`, vector size 768, Cosine).
- Embedding: `http://embedding-server-service.default.svc.cluster.local:80/embed` (or 8080 depending on exact config).
- NiFi: In namespace `cfm-streaming` (service likely `mynifi` or similar; use full DNS or env vars). Process groups: `StreamTovLLM` and `IngestToStream`.

### 3. Project Structure
```
streamtovllm-ui/
├── backend/                  # FastAPI
│   ├── main.py
│   ├── routers/ (query.py, qdrant.py, nifi.py)
│   ├── config.py             # Env vars for service URLs
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                 # React + Vite
│   ├── src/
│   │   ├── components/ (Chat.tsx, QueryPanel.tsx, Controls.tsx, etc.)
│   │   ├── App.tsx
│   │   ├── api.ts            # Axios or fetch wrappers
│   │   └── types.ts
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── package.json
├── k8s/                      # Deployment YAMLs
│   ├── deployment.yaml
│   ├── service.yaml
│   └── configmap.yaml
├── docker-compose.yml        # Local dev
└── deploy.sh                 # Build + minikube deploy script
```

### 4. Step-by-Step Implementation Plan

#### Step A: Create the Backend (FastAPI)
1. Set up a new project (same as before).
2. Define environment/config (use a `.env` or Kubernetes ConfigMap):
   - Service URLs and NiFi process group IDs.
3. Key endpoints in `main.py`:
   - `POST /api/query`: Performs full RAG (embed → Qdrant search → context → vLLM call). Support `stream: true` for token streaming (use SSE).
   - `POST /api/qdrant/delete`: `DELETE /collections/my-rag-collection`.
   - `POST /api/qdrant/recreate`: Delete first, then `PUT /collections/my-rag-collection` with `{"vectors": {"size": 768, "distance": "Cosine"}}`.
   - `POST /api/nifi/start` and `/api/nifi/stop`: Target specific process groups (`StreamTovLLM`, `IngestToStream`).
     - Fetch current revision/version first (`GET /flow/process-groups/{id}`).
     - Then `PUT /flow/process-groups/{id}` with `{"id": "...", "state": "RUNNING" | "STOPPED"}`.
   Use `httpx.AsyncClient` for calls. Handle errors gracefully and return JSON responses.

#### Step B: Create the Frontend (React)
- **Vite + React + TypeScript + Tailwind CSS + shadcn/ui**.
- **Recommended UI Layout** (modern, dashboard-style):
  - **Top Navbar**: "StreamToVLLM Control Panel" + Minikube status indicator (simple ping).
  - **Main Area** (tabs or sections with cards):
    1. **Query Interface** (Chat-style, most prominent):
       - Textarea or input pre-filled with "What is streamtovllm?".
       - "Send Query" button (with loading spinner).
       - Response area: Markdown-rendered answer (use `react-markdown`), with copy button.
       - Optional: Streaming tokens (append as they arrive via SSE).
       - History of past questions/responses (local state or simple array).
    2. **Qdrant Management** (collapsible card):
       - Buttons: **Delete Collection** (red, with confirmation modal), **Recreate Collection**.
       - Status message after action.
    3. **NiFi Flow Controls** (separate card):
       - Two sections or tabs: **StreamTovLLM** and **IngestToStream**.
       - Buttons: **Start Flow**, **Stop Flow** for each.
       - Optional: Refresh button to poll current state (via additional `/api/nifi/status` endpoint).
       - Success/error toasts (use `sonner` or `react-hot-toast`).
- **Styling**: Tailwind + shadcn/ui components (Button, Card, Modal, Toast, Spinner) for a professional, responsive look. Dark mode optional.
- **State Management**: React hooks (`useState`, `useEffect`). For streaming, use `EventSource` or fetch with readable stream.
- **API Layer**: `src/api.ts` with typed functions using `axios` or native fetch. Base URL from env (`VITE_API_URL`).

#### Step C: Containerization & Easy Minikube Deployment
**Multi-stage Dockerfile** (recommended):
```dockerfile
# Stage 1: Build React
FROM node:20 AS frontend-build
WORKDIR /frontend
COPY frontend/ .
RUN npm ci && npm run build

# Stage 2: FastAPI + serve static
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
COPY --from=frontend-build /frontend/dist /app/static

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Kubernetes**:
- **ConfigMap** for backend env vars (service DNS names, ports, NiFi process group IDs).
- **Deployment**: 1 replica, resource requests low (CPU/memory only, no GPU).
- **Service**: `type: NodePort` (e.g., nodePort 30001) → Access at `http://$(minikube ip):30001`.
- Optional: Minikube Ingress for cleaner URL.

**Deployment Script** (`deploy.sh`):
```bash
minikube image build -t streamtovllm-ui:latest -f Dockerfile .
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
minikube service streamtovllm-ui
```

#### Step D: Development Workflow
1. Develop backend locally (point env vars to `localhost` ports via `kubectl port-forward` for vllm-service, qdrant, etc.).
2. Develop frontend (`npm run dev`) against local backend (`VITE_API_URL=http://localhost:8000`).
3. Test full RAG query, Qdrant delete/recreate, NiFi start/stop.
4. Build & deploy to Minikube.
5. Polish: Add confirmation modals for destructive actions, loading states, error boundaries, and basic logging.

### 5. Potential Challenges & Tips
- **NiFi API details**: Process group start/stop often requires revision/version in the payload. Fetch it first or use the `/flow/process-groups/{id}` endpoint. Test with curl against your running NiFi.
- **Service Discovery**: Use full Kubernetes DNS in production config; fallback to env vars.
- **Security**: In a real setup, add API keys or mTLS, but skip for local Minikube.
- **Streaming Responses**: Use Server-Sent Events (SSE) in FastAPI for nice LLM token streaming in the UI.
- **Dependencies**: If your NiFi flows need specific IDs, expose them via the NiFi API discovery endpoints.
- **Resource Limits**: Keep the UI pod light (no GPU needed).

### 6. Next Steps
- Start with the backend proxy for vLLM + full RAG query (easiest to test first).
- Then add Qdrant and NiFi controls.
- Finally wire up the React frontend.