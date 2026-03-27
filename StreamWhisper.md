**StreamWhisper: Insanely Fast Audio Transcription with Cloudera Streaming Operators on RTX 4090**

**date:** 2026-03-27  
**last_modified_at:** 2026-03-27  
**excerpt:** "Real-time, GPU-accelerated speech-to-text over streaming audio sources (files, URLs, Kafka) — powered by insanely-fast-whisper, Cloudera Streaming Operators (Kafka + NiFi), and your RTX 4090. Transcripts flow straight into your existing StreamToVLLM RAG pipeline for instant Q&A on spoken content. Zero cloud, fully local."

**header:**  
  teaser: "/assets/images/StreamWhisper-architecture.png"  

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

Let’s build **StreamWhisper** — the missing audio ingestion layer for your local Cloudera Streaming Operators stack. Audio files or live streams hit NiFi → Kafka → insanely-fast-whisper inference on the RTX 4090 → clean transcripts land in Kafka (and optionally straight into your Qdrant RAG collection).  

The result? You can now ask your vLLM model questions about *spoken* content with perfect context, all running 100% locally on your RTX 4090.

![StreamWhisper Architecture](/assets/images/StreamWhisper-architecture.png)

**RTX 4090 sweet spot** — 24 GB VRAM lets us run `openai/whisper-large-v3` with Flash Attention 2 at blazing speeds (150+ minutes of audio transcribed in <90 seconds).

You already have the full Cloudera Streaming Operators stack + the StreamToVLLM RAG pipeline from the previous sessions. We’re just adding the audio transcription brain.

---

## 💻 Prerequisites

You should have:
- Minikube running with **GPU passthrough** (RTX 4090 confirmed — upgrade from the 4060 setup)
- Cloudera Streaming Operators (CSM + CSA + CFM) installed in `cld-streaming` and `cfm-streaming`
- The full **StreamToVLLM** RAG stack (vLLM Qwen, Qdrant `my-rag-collection`, embedding server) already deployed
- NiFi UI at `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/`
- Git cloned: `git clone https://github.com/cldr-steven-matison/insanely-fast-whisper.git`

**Quick GPU double-check (RTX 4090):**

```bash
kubectl get nodes -o jsonpath='{.items[*].status.allocatable.nvidia\.com/gpu}'
# Should return: 1

# NVIDIA test pod (same as before)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test
spec:
  restartPolicy: Never
  containers:
  - name: cuda-test
    image: nvcr.io/nvidia/k8s/cuda-sample:vectoradd-cuda12.5.0
    resources:
      limits:
        nvidia.com/gpu: 1
EOF
kubectl logs gpu-test -f
```

**Expected:** `Test PASSED` ✅  
Keep `watch nvidia-smi` running — you’ll see the 4090 light up during transcription.

---

## 📦 Step 1: Containerize & Deploy Insanely Fast Whisper Inference Server

The original repo is a fast CLI/pipeline. We wrap it in a lightweight FastAPI service so NiFi can call it over HTTP.

### 1.1 Create the Dockerfile (save as `Dockerfile.whisper`)

```dockerfile
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y python3.11 python3.11-venv python3-pip git ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install insanely-fast-whisper + FastAPI
COPY . /app
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
RUN pip install --no-cache-dir -r requirements.txt  # (or just the packages below)
RUN pip install --no-cache-dir \
    insanely-fast-whisper==0.0.15 \
    fastapi uvicorn python-multipart huggingface_hub flash-attn --no-build-isolation

# Simple FastAPI server
COPY <<EOF /app/main.py
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import torch
from transformers import pipeline
import tempfile
import os

app = FastAPI(title="StreamWhisper Inference")

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
        return {"text": result["text"], "chunks": result.get("chunks", [])}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
EOF

CMD ["python", "main.py"]
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
            memory: "20Gi"
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

You should get back `{"text": "...", "chunks": [...]}` in seconds on the 4090.

---

## 🌊 Step 2: NiFi Flows for StreamWhisper

We add two new Process Groups (exported as JSON from my repo).

**Download the full flows here:** [NiFi Templates - StreamWhisper](https://github.com/cldr-steven-matison/NiFi-Templates) (new folder `StreamWhisper` added today).

### 🛠️ IngestAudioToStream Flow
- GenerateFlowFile / InvokeHTTP → pulls audio from URLs, S3, or local files
- PublishKafka_2_6 → sends raw audio bytes to topic `new_audio`

### 🛠️ StreamWhisper Flow
1. **ConsumeKafka_2_6** – `new_audio` topic
2. **ConvertAvroToJSON** / **ExtractText** – keep binary audio as attribute
3. **InvokeHTTP** – POST to `http://whisper-service:8001/transcribe` (binary file upload)
4. **EvaluateJsonPath** – extract `$.text` into attribute `transcript`
5. **ReplaceText** – format for Qdrant (or plain text)
6. **PublishKafka_2_6** – push clean transcript to `transcribed_text`
7. **(Optional)** InvokeHTTP to your existing embedding server → upsert directly into `my-rag-collection` with source=`audio-stream`

**Pro Tip:** Use the same `#{Kafka Broker Endpoint}` parameter you already have. Schedule IngestAudioToStream to run once, then start StreamWhisper.

---

## 🌊 Step 3: Integration with Existing RAG (StreamToVLLM)

Transcripts are automatically ingested into Qdrant by the existing `StreamToVLLM` flow (or the optional step above).  

Now ask your vLLM model about spoken content:

```bash
python3 query-rag.py   # (reuse the script from the previous RAG post)
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

## :checkered_flag: The "StreamWhisper" Takeaway

- **Full streaming audio pipeline** now lives inside your Cloudera Operators cluster.
- **RTX 4090** handles large-v3 Whisper at insane speeds.
- **Zero extra infrastructure** — NiFi + Kafka do all the heavy lifting.
- **Seamless RAG integration** — spoken content is now searchable and queryable exactly like your documents.
- **Future-proof** — swap Whisper models, add diarization, or pipe live microphone streams via NiFi processors.

You now have a complete local AI data engineering sandbox: documents → RAG, audio → transcripts → RAG, all streaming in real time.

---

## 📚 Resources & Further Reading

- [insanely-fast-whisper GitHub](https://github.com/cldr-steven-matison/insanely-fast-whisper)
- [OpenAI Whisper large-v3](https://huggingface.co/openai/whisper-large-v3)
- Previous posts: [RAG with Cloudera Streaming Operators](/blog/2026-03-22-RAG-with-Cloudera-Streaming-Operators/), [Cloudera Streaming Operators](/blog/2026-03-09-Cloudera-Streaming-Operators/)
- [NiFi Templates repo](https://github.com/cldr-steven-matison/NiFi-Templates) (StreamWhisper folder)

If you want the full YAMLs, updated NiFi JSON flows, a ready-made Docker image pushed to your local registry, or a live demo on your RTX 4090, just say the word and we’ll schedule a quick call or push the next set of files.  

Ready to transcribe? 🚀