**StreamToWhisper: Insanely Fast Audio Transcription with Cloudera Streaming Operators on RTX 4060**

**date:** 2026-03-27  
**last_modified_at:** 2026-03-27  
**excerpt:** "Real-time, GPU-accelerated speech-to-text over streaming audio sources — powered by insanely-fast-whisper, Cloudera Streaming Operators (Kafka + NiFi), and my RTX 4060. Transcripts flow straight into my existing StreamToVLLM RAG pipeline for instant Q&A on spoken content."

**header:**  
  teaser: "/assets/images/StreamToWhisper-architecture.png"  

**categories:**  
  - blog  

**tags:**  
  - cloudera  
  - operator  
  - nifi  
  - kafka  
  - whisper  
  - vllm  
  - rag  
  - gpu  

---

I seen this on X the other day and thought it was really cool. I bookmarked, and later forked the repo.  It turns out this is another perfect integration with my previous post [RAG with Cloudera Streaming Operators]().  

So Let’s build **StreamToWhisper** — the missing audio ingestion layer for your local Cloudera Streaming Operators stack. Audio files or live streams hit NiFi → Kafka → insanely-fast-whisper inference on the RTX 4060 → clean transcripts land in Kafka and optionally straight into your Qdrant RAG collection.  

The result? You can now ask your vLLM model questions about *spoken* content with perfect context.

![StreamToWhisper Architecture](/assets/images/StreamToWhisper-architecture.png)

**RTX 4060 sweet spot** — 8 GB VRAM lets us run `openai/whisper-large-v3` with Flash Attention 2 at blazing speeds (150+ minutes of audio transcribed in <90 seconds).

You already have the full [Cloudera Streaming Operators]() stack + the StreamToVLLM RAG pipeline from the previous session. We’re just adding the audio transcription ability to the brain.

---

## 💻 Prerequisites

You should have:
- Minikube running with **GPU passthrough** (RTX 4060 confirmed)
- Cloudera Streaming Operators (CSM + CSA + CFM) installed in `cld-streaming` and `cfm-streaming`
- The full **StreamToVLLM** RAG stack (vLLM Qwen, Qdrant `my-rag-collection`, embedding server) already deployed
- NiFi UI at `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/`
- Git cloned: `git clone https://github.com/cldr-steven-matison/insanely-fast-whisper.git`
---

## 📦 Step 1: Containerize & Deploy Insanely Fast Whisper Inference Server

The original repo is a fast CLI/pipeline. We wrap it in a lightweight FastAPI service so NiFi can call it over HTTP.

### 1.1 Create the Dockerfile (save as `Dockerfile.whisper`)

```dockerfile
# Dockerfile.whisper.12 - Final Stable "G1" Build
# Targets: CUDA 12.4, Flash Attention 2, Whisper-Large-v3
# Author: Steven Matison (Solutions Engineer, Cloudera)

# STAGE 1: The Heavy Lifting (Builder)
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 AS builder

ARG HF_TOKEN
ENV HF_TOKEN=${HF_TOKEN}
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3.11 python3.11-venv python3-pip git ffmpeg ninja-build \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 1. Essential Build Tools for C++ Compilation
RUN pip install --no-cache-dir --upgrade pip setuptools wheel packaging

# 2. Hard-pin Torch to CUDA 12.4 (RTX 4060 Optimization)
RUN pip install --no-cache-dir \
    torch==2.4.1+cu124 torchvision==0.19.1+cu124 torchaudio==2.4.1+cu124 \
    --extra-index-url https://download.pytorch.org/whl/cu124

# 3. Web Stack (Allowing Transitive Dependencies for Starlette/Pydantic)
RUN pip install --no-cache-dir \
    fastapi uvicorn starlette pydantic pydantic-core \
    anyio idna sniffio typing-extensions click h11 python-multipart

# 4. AI Stack (Guarded with --no-deps to prevent Torch overwrites)
RUN pip install --no-cache-dir --no-deps \
    transformers insanely-fast-whisper==0.0.15 huggingface_hub

# 5. Manual AI Dependency Tree
RUN pip install --no-cache-dir \
    pyyaml requests tqdm numpy regex sentencepiece \
    httpx filelock fsspec safetensors accelerate \
    soundfile librosa scipy tokenizers

# 6. Compile Flash Attention 2 (Hardware-Specific Build)
RUN pip install --no-cache-dir flash-attn --no-build-isolation

# 7. Pre-Bake Whisper-Large-v3 (Authenticated Download)
RUN python3 -c "from transformers import pipeline; pipeline('automatic-speech-recognition', model='openai/whisper-large-v3')"

# ==========================================
# STAGE 2: The Lean Runtime
# ==========================================
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    python3.11 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface
ENV PATH="/opt/venv/bin:$PATH"

# FastAPI Inference Logic
COPY <<EOF /app/main.py
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import torch
from transformers import pipeline
import tempfile
import os

app = FastAPI(title="StreamToWhisper")

pipe = pipeline(
    "automatic-speech-recognition",
    model="openai/whisper-large-v3",
    torch_dtype=torch.float16,
    device="cuda:0",
    model_kwargs={"attn_implementation": "flash_attention_2"}
)

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = pipe(tmp_path, chunk_length_s=30, batch_size=24, return_timestamps=True)
        os.unlink(tmp_path)
        return {"text": result["text"]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
EOF

EXPOSE 8001
ENTRYPOINT ["/opt/venv/bin/python3", "main.py"]
```

### 1.2 Build & load into Minikube

```bash
eval $(minikube docker-env)
docker build -t streamwhisper:latest -f Dockerfile.whisper .
```

### 1.3 Deploy YAML (save as `whisper-server.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: whisper-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: whisper-server
  template:
    metadata:
      labels:
        app: whisper-server
    spec:
      containers:
      - name: whisper-server
        image: streamwhisper:latest
        imagePullPolicy: Never
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: "8Gi"
        ports:
        - containerPort: 8001
---
apiVersion: v1
kind: Service
metadata:
  name: whisper-service
spec:
  selector:
    app: whisper-server
  ports:
  - protocol: TCP
    port: 8001
    targetPort: 8001
  type: ClusterIP
```

Apply it:

```bash
kubectl apply -f whisper-server.yaml
kubectl get pods -w -l app=whisper-server
kubectl port-forward svc/whisper-service 8001:8001
```

**Test the API** (use any .wav or .mp3 file):

```bash
curl -X POST http://localhost:8001/transcribe \
  -F "file=@/path/to/your/test-audio.wav" \
  | jq
```

You should get back `{"text": "...", "chunks": [...]}` in seconds on the 4060.

---

## 🌊 Step 2: NiFi Flows for StreamToWhisper

![StreamToWhisper Architecture](/assets/images/StreamToWhisper-nifi-flow.png)

**Download the full flows here:** [NiFi Templates - StreamToWhisper](https://github.com/cldr-steven-matison/NiFi-Templates) (new `StreamToWhisper` flow added today).

### 🛠️ IngestAudioToStream Flow
- GenerateFlowFile / InvokeHTTP → pulls audio from URLs, S3, or local files
- PublishKafka_2_6 → sends raw audio bytes to topic `new_audio`

### 🛠️ StreamToWhisper Flow
1. **ConsumeKafka_2_6** – `new_audio` topic
3. **InvokeHTTP** – POST to `http://whisper-service:8001/transcribe` (binary file upload)
4. **EvaluateJsonPath** – extract `$.text` into attribute `transcript`
5. **ReplaceText** - format flowfile with our transcript
6. **PublishKafka_2_6** – publish to `new_documents` to process as a document in `StreamToVLLM`

---

## 🌊 Step 3: Integration with Existing RAG (StreamToVLLM)

Transcripts are automatically ingested into Qdrant by the existing `StreamToVLLM` flow (or the optional step above).  

Now ask your vLLM model about spoken content:

```bash
python3 query-rag-whisper.py   # (you could reuse the script from the previous RAG post)
```

**Example question:** “What did the speaker say about Cloudera Streaming Operators in the podcast?”

You’ll get a perfect context-aware answer pulled from the transcribed audio.

---

## 💻 Terminal Commands For This Session

```bash
# Build & deploy
eval $(minikube docker-env)
docker build -t streamwhisper:latest -f Dockerfile.whisper .
kubectl apply -f whisper-server.yaml

# Port forwards (add to your existing chain)
kubectl port-forward svc/whisper-service 8001:8001 &

# Check GPU usage
watch nvidia-smi

# Delete / restart
kubectl delete -f whisper-server.yaml
```

---

## :checkered_flag: The "StreamToWhisper" Takeaway

- **Full streaming audio pipeline** now lives inside your Cloudera Operators cluster.
- **RTX 4060** handles large-v3 Whisper at insane speeds.
- **Zero extra infrastructure** — NiFi + Kafka do all the heavy lifting.
- **Seamless RAG integration** — spoken content is now searchable and queryable exactly like your documents.
- **Future-proof** — swap Whisper models, add diarization, or pipe live microphone streams via NiFi processors.

You now have a complete local AI data engineering sandbox: documents → RAG, audio → transcripts → RAG, all streaming in real time.

---

## 📚 Resources & Further Reading

- [Insanely-fast-whisper GitHub](https://github.com/cldr-steven-matison/insanely-fast-whisper)
- [OpenAI Whisper large-v3](https://huggingface.co/openai/whisper-large-v3)
- Previous posts: [RAG with Cloudera Streaming Operators](/blog/2026-03-22-RAG-with-Cloudera-Streaming-Operators/), [Cloudera Streaming Operators](/blog/2026-03-09-Cloudera-Streaming-Operators/)
- [NiFi Templates repo](https://github.com/cldr-steven-matison/NiFi-Templates)
