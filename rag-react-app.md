Here's an updated **plan** specifically for building a modern **React** frontend app (with a lightweight FastAPI backend) that integrates with your **StreamToVLLM** RAG setup on Minikube.

This version emphasizes a **decent, polished UI** using React + Vite + TypeScript + Tailwind CSS + shadcn/ui (or plain Tailwind with Lucide icons). The app stays simple, single-page, and easily deployable as one container alongside your existing components.

### 1. Overall Architecture
- **Frontend**: React (Vite) app – Chat-like interface for queries, control panels for Qdrant and NiFi.
- **Backend**: FastAPI (Python) – Acts as a secure proxy to internal Kubernetes services (avoids CORS, centralizes logic, handles auth if added later). Exposes clean REST endpoints.
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

### 2. Project Structure
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

### 3. Backend Implementation (FastAPI)
- Use `httpx` for async calls, `openai` Python client for vLLM (set `base_url` and dummy `api_key="not-needed"`).
- Endpoints:
  - `POST /api/query` — Accepts `{question: string}`. Performs full RAG: embed → Qdrant search → context → vLLM call. Support `stream: true` for token streaming (use SSE).
  - `POST /api/qdrant/delete` — `DELETE /collections/my-rag-collection`.
  - `POST /api/qdrant/recreate` — Delete first, then `PUT /collections/my-rag-collection` with `{"vectors": {"size": 768, "distance": "Cosine"}}`.
  - `POST /api/nifi/start` & `/api/nifi/stop` — Target specific process groups (`StreamTovLLM`, `IngestToStream`).
    - Fetch current revision/version first (`GET /flow/process-groups/{id}`).
    - Then `PUT /flow/process-groups/{id}` with `{"id": "...", "state": "RUNNING" | "STOPPED"}`.
    - Provide dropdown or separate buttons for each flow. Return status.
- Config via environment variables or ConfigMap (service URLs, collection name, NiFi base URL + process group IDs).
- Error handling + loading states returned as JSON.

### 4. Frontend Implementation (React)
Use **Vite + React + TypeScript + Tailwind CSS** for fast development and a clean look.

**Recommended UI Layout** (modern, dashboard-style):
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
     - Status message after action (e.g., "Collection deleted successfully").
  3. **NiFi Flow Controls** (separate card):
     - Two sections or tabs: **StreamTovLLM** and **IngestToStream**.
     - Buttons: **Start Flow**, **Stop Flow** for each.
     - Optional: Refresh button to poll current state (via additional `/api/nifi/status` endpoint).
     - Success/error toasts (use `sonner` or `react-hot-toast`).
- **Styling**: Tailwind + shadcn/ui components (Button, Card, Modal, Toast, Spinner) for a professional, responsive look. Dark mode optional.
- **State Management**: React hooks (`useState`, `useEffect`). For streaming, use `EventSource` or fetch with readable stream.
- **API Layer**: `src/api.ts` with typed functions using `axios` or native fetch. Base URL from env (`VITE_API_URL`).

Example simple component flow:
- Query form → calls `api.query(question)` → displays result.
- Control buttons → `api.qdrantDelete()` → shows toast.

### 5. Containerization & Easy Minikube Deployment
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

# Serve React from FastAPI (mount /static) or use nginx; simple: FastAPI serves index.html + API
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

### 6. Development Workflow
1. Develop backend locally (point env vars to `localhost` ports via `kubectl port-forward` for vllm-service, qdrant, etc.).
2. Develop frontend (`npm run dev`) against local backend (`VITE_API_URL=http://localhost:8000`).
3. Test full RAG query, Qdrant delete/recreate, NiFi start/stop.
4. Build & deploy to Minikube.
5. Polish: Add confirmation modals for destructive actions, loading states, error boundaries, and basic logging.

### 7. Potential Enhancements (Keep Simple First)
- Streaming responses for a more interactive feel.
- Button to trigger ingestion (e.g., via NiFi or direct Kafka publish).
- View Qdrant points count after recreate.
- Dark theme + responsive mobile support.
- Basic auth on the UI if exposing beyond Minikube.

This React plan gives you a **clean, professional UI** while keeping deployment straightforward (one pod). It fully leverages your existing Cloudera Streaming Operators setup without changing the core RAG pipeline.

**Next Steps**:
- Start with the backend proxy for vLLM + full RAG query (easiest to test first).
- Then add Qdrant and NiFi controls.
- Finally wire up the React frontend.

If you want sample code for any part (e.g., React Chat component, FastAPI query router with full RAG, or the exact NiFi start/stop logic with revision handling), specific YAML manifests, or help with process group IDs discovery, just let me know! I can also suggest exact commands to extract NiFi IDs from your running instance.
