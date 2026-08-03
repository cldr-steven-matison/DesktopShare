# Real GPU inference inside MiNiFi on the Jetson Orin Nano

The `ExecuteScript` on my Jetson's MiNiFi agent had been "the TensorRT processor" for months. Here's what it actually did:

```python
logger = trt.Logger(trt.Logger.INFO)
tensorrt_info = {"version": str(trt.__version__), "status": "Active"}
```

It imported `tensorrt` and reported the version string. That's a smoke test wearing an AI costume. This is the replacement: a real MobileNetV2 FP16 engine doing real GPU inference at **4 ms**, reachable three different ways — from `ExecuteScript`, from a custom Python processor type, and from a Java agent that has no Python at all — with **zero new pip packages** on a box with 18 GB of disk left.

The interesting part isn't the model. It's that the obvious design is wrong, and the box had already shown me the right one.

## The obvious design is wrong

The obvious move is `import tensorrt` in the processor, load the `.engine`, run inference. It doesn't work, for a reason that isn't in any doc I'd read:

**MiNiFi C++'s `ExecuteScript` re-reads its script file on every trigger.** That's a feature — you edit the `.py` on disk and the next FlowFile picks it up, no restart. It also means nothing stays resident. A `.engine` deserialized per request costs far more than the inference it's there to do.

The custom Python processor route has the same problem from the other end. It *can* hold state in its instance, but it's not a hot patch — `PythonCreator` scans the processor dir once, at boot — so every model change becomes a full agent restart of the process that also drives this device's matrix screensaver and stream launcher.

And the Java agent can't run Python at all. Its `ExecuteScript` is Groovy/Clojure only.

Three consumers, three different reasons the engine can't live in the processor.

## The box had already solved it

`agent-NvidiaNano-launch_stream.py` on this same agent is a nine-line `ExecuteScript` that POSTs to `127.0.0.1:5902` and gets out of the way. The thing that actually owns state — a persistent mpv process — lives in `mpv_stream_launcher_linux.py`, a systemd *user* service.

So: same shape for inference. One resident daemon, three thin front doors.

```
                          ┌────────────────────────────────────────┐
                          │ trt_infer_server.py  127.0.0.1:5910    │
  3 front doors ────────▶ │ mobilenetv2.fp16.engine resident       │
                          │ TRT context + CUDA buffers allocated 1×│
                          │ POST /classify    GET /health          │
                          └────────────────────────────────────────┘
  1. C++ ExecuteScript      gpu_nifi_tensorRT-4.py       :8080 → PublishKafka
  2. C++ custom processor   ClassifyImageTensorRT        first-class type, EFM Designer
  3. Java agent             HandleHttpRequest → InvokeHTTP → HandleHttpResponse
```

The payoff is that `systemctl --user restart trt-infer` reloads the model without going near MiNiFi. I verified that: restarted the daemon mid-session, the agent (pid 2616, 2h34m uptime) never noticed, and the next POST classified normally.

## No new packages, and that's the whole trick

The gap in "run TensorRT from Python" is device memory allocation. Everyone reaches for torch or pycuda. On this box torch is a 427 MB generic aarch64 wheel that isn't a JetPack build, and `onnxruntime-gpu` has no aarch64/py3.12 distribution at all.

You don't need either. `ctypes` against `libcudart` is four functions wide:

```python
self.lib.cudaMalloc.argtypes  = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_size_t]
self.lib.cudaMemcpyAsync.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                     ctypes.c_size_t, ctypes.c_int, ctypes.c_void_p]
self.lib.cudaStreamCreate.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
self.lib.cudaStreamSynchronize.argtypes = [ctypes.c_void_p]
```

`tensorrt` 10.16.2.10, `numpy` 1.26.4 and `cv2` 4.8.0 were already installed. Total added footprint: a 14 MB ONNX and a 7.5 MB engine.

## Build the engine

The `.engine` is bound to this GPU and this TensorRT version, so it gets built on the box and stays out of git:

```bash
mkdir -p ~/trt-infer/models && cd ~/trt-infer/models
curl -sSL -o mobilenetv2-12.onnx \
  https://github.com/onnx/models/raw/main/validated/vision/classification/mobilenet/model/mobilenetv2-12.onnx
curl -sSL -o imagenet_classes.txt \
  https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt

trtexec --onnx=mobilenetv2-12.onnx --saveEngine=mobilenetv2.fp16.engine --fp16
```

About 2 minutes on an Orin Nano. `trtexec`'s own benchmark on the result:

```
Throughput: 674.295 qps
GPU Compute Time: min = 1.34424 ms, median = 1.36755 ms, percentile(99%) = 3.98267 ms
```

Then install the daemon as a user service — no root, because this box already runs its user manager with lingering:

```bash
cp files/trt_infer_server.py ~/DesktopShare/files/      # runs from the repo checkout
cp files/trt-infer.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now trt-infer
```

## What it costs, measured

100 iterations against the live daemon, `dog.jpg` from the PyTorch hub (a Samoyed — useful because the right answer is known):

| | p50 | p95 |
|---|---|---|
| `inference_ms` (GPU) | **4.05 ms** | 7.21 ms |
| `preprocess_ms` (CPU) | **32.59 ms** | 35.99 ms |
| end-to-end | 38.90 ms | 43.79 ms |

**Preprocessing costs 8× the inference.** The GPU is not the bottleneck — CPU-side JPEG decode is, on a 1546×1213 image at 729 MHz. Send a smaller image and it collapses:

| input | preprocess p50 | end-to-end p50 |
|---|---|---|
| 1546 px (661 KB) | 32.59 ms | 38.90 ms |
| **640 px (75 KB)** | **8.05 ms** | **14.87 ms** |

Confidence went *up* at 640 px (0.72 vs 0.64) because the resize path is shorter. So: **tell callers to send ~640 px.** That's 67 req/s single-threaded instead of 26.

GPU utilisation during the loop, from `tegrastats`, against an idle baseline of 0%:

```
GR3D_FREQ 60%   56%   55%   47%   31%   29%
```

That's the proof the GPU is doing the work and not a CPU fallback.

## Front door 1 — `ExecuteScript`, and a live drop-warning that lies

`gpu_nifi_tensorRT-4.py` has no `import tensorrt` at all. It reads the FlowFile as **bytes** (the old stub decoded UTF-8, which throws on any real JPEG), infers the content type from the first byte, POSTs, and lifts the top-1 into attributes.

Wired by changing one property on the live flow — `Script File` from `-3.py` to `-4.py` — then `validate` (clean) and `publish`. Agent hot-reloaded on the next heartbeat, no restart:

```
[2026-08-02 21:00:08.179] [FlowController] [info] Starting to reload Flow Controller
[2026-08-02 21:00:12.266] [ListenHTTP] [info] ListenHTTP starting HTTP server on port 8080 and path /contentListener
```

Then the interesting bit. Every POST to `:8080/contentListener` logs this:

```
[ListenHTTP] [warning] ListenHTTP buffer is NOT full 1/1, 'POST' request for '/contentListener' uri was dropped
```

That's the signature from #54 — `Buffer Size` and `Batch Size` are both already `1`. It reads like every request is being dropped. **It isn't.** Controlled run, counting at both ends:

```
POSTs sent = 20    reached the inference daemon = 20    'was dropped' warnings = 20
```

20 of 20 classified. The warning is spurious — it fires on requests that are delivered and processed normally. Anyone diagnosing this leg by grepping the log will conclude the opposite of the truth.

One honest caveat: three POSTs sent within ~35 s of the flow reload genuinely did not reach the daemon (the counter did not move for those). Everything after a quiet gap did. I have not explained those three, and I'm not going to pretend the warning tells you which is which.

## Front door 2 — a first-class processor type

`ClassifyImageTensorRT.py` is a real processor type, not an `ExecuteScript` body: it appears in the agent manifest under its own name with its own properties (`Inference Endpoint`, `Top K`, `Request Timeout`, `Image Source`) and is wired in the EFM Designer like any stock processor.

Validated on a **disposable sandbox agent**, never the production one — a second `1.26.02` install under `~/minifi-pytest/`, process-mode, no systemd, no sudo.

```
[PythonCreator] [info] Adding .../asset/ClassifyImageTensorRT.py to paths
[PythonCreator] [info] Registering MiNiFi python processor: ClassifyImageTensorRT
```

Built `ListenHTTP(:9096) → ClassifyImageTensorRT → LogAttribute` through the Designer API, published, POSTed 3 images. 3/3:

```
key:inference.label value:Samoyed
key:inference.confidence value:0.723496
key:inference.model value:mobilenetv2-12 (ImageNet-1k, FP16)
key:inference.ms value:5.51
```

### The new gotcha — a static class→manifest mapping refuses the PUT

Issue #65 found that pointing a class at a refreshed manifest needed a `PUT /agent-classes/{name}` plus a delete-and-recreate of the processor component. On this box it's worse: the PUT is rejected outright.

```
The input agent manifest id = 2736f393-... is not equal to configured
static mapping agent manifest id = 044ee0cd-...
HTTP 409
```

`NvidiaNanoPyTest` is pinned by a **static class→manifest mapping in EFM's own configuration**, which lives on the EFM host, not here. No amount of API work from the agent side moves it.

The fix that doesn't need EFM-side access: register under a class name that has no static mapping. Change `nifi.c2.agent.class`, rotate `nifi.c2.agent.identifier` at the same time (reusing one across a class change leaves a stale agent row EFM never garbage-collects), restart the sandbox agent. EFM auto-creates the class from the heartbeat, with the manifest that actually contains the new type:

```bash
# in ~/minifi-pytest/nifi-minifi-cpp-1.26.02/conf/minifi.properties
nifi.c2.agent.class=NvidiaNanoTrtTest
nifi.c2.agent.identifier=<fresh uuid>
```

## Front door 3 — the Java agent, and a claim that was wrong

#28 wants a XIAO to POST and get a **real answer back**, not a fire-and-forget ack. MiNiFi C++ can't do that — it has no `HandleHttpRequest`/`HandleHttpResponse` pair. MiNiFi Java does.

`NvidiaNanoJava` is recorded elsewhere as "deployed and online." On this device that is not true, and it can't have been:

```bash
$ ls /usr/lib/jvm/
ls: cannot access '/usr/lib/jvm/': No such file or directory
$ which java
$
```

**There is no JRE on this Jetson.** None installed, none bundled in the `minifi-2.24.08.0-19` tarball. The agent is unpacked at `~/minifi-java-nano/` and had never run. Fix:

```bash
sudo apt install -y openjdk-21-jre-headless   # 3 packages, needs a real sudo password on this box
cd ~/minifi-java-nano/minifi-2.24.08.0-19 && ./bin/minifi.sh start
```

With OpenJDK 21.0.11 in, the agent came up in 4.9 s and registered. The flow is four processors and one controller service:

```
HandleHttpRequest-Inference  (0,   0)    :8090, path /classify, HTTP Context Map
InvokeHTTP-Classify          (0,   300)  POST → http://127.0.0.1:5910/classify
HandleHttpResponse-OK        (0,   600)  200          ← success spine, centre column
HandleHttpResponse-Error     (600, 600)  502          ← Failure + No Retry, branch pitch
```

`Retry` self-loops with a 10 min `FlowFile Expiration` rather than being auto-terminated. And the three timeouts are set deliberately — `Connection 5 secs`, `Socket Read 10 secs`, `Socket Write 10 secs` — not the 15 s framework default that cost most of a session in #79.

The round trip, which is the whole point of #28:

```console
$ curl --data-binary @dog-640.jpg -H "Content-Type: application/octet-stream" \
       http://127.0.0.1:8090/classify
{"ok": true, "model": "mobilenetv2-12 (ImageNet-1k, FP16)", "source": "body",
 "predictions": [{"label": "Samoyed", "class_id": 258, "confidence": 0.723496}, ...],
 "preprocess_ms": 6.53, "inference_ms": 4.12}
HTTP 200
```

One POST, a real answer in the response body. No Kafka, no `request_id` correlation, no fire-and-forget ack. 20/20 round-trips:

| | p50 | p95 | min |
|---|---|---|---|
| through the Java agent | 132 ms | 258 ms | 42 ms |
| daemon direct (loopback) | 14.9 ms | — | — |

MiNiFi Java costs about 117 ms on top — FlowFile repository, scheduling, Jetty. Worth it for an EFM-managed flow; worth knowing before anyone promises a latency number.

The error path returns rather than hanging, which matters when the caller is a microcontroller with a fixed timeout:

```console
$ curl --data-binary "definitely not an image" http://127.0.0.1:8090/classify
--- HTTP 502 in 0.028073s ---
```

And it binds `*:8090`, not loopback, so a XIAO on the LAN reaches it directly.

## What NOT to do

- **Don't `import tensorrt` in an `ExecuteScript`.** The script is re-read every trigger; the engine can't stay resident and you'll pay deserialization per request.
- **Don't reach for torch or pycuda on a Jetson to get device memory.** `torch` on PyPI for aarch64/py3.12 is a 427 MB generic build with no Orin `sm_87` validation, and `onnxruntime-gpu` has no matching distribution at all. `ctypes` + `libcudart` is already installed and is four functions.
- **Don't commit the `.engine`.** It's bound to this GPU and this TensorRT version. Commit the `trtexec` line instead.
- **Don't trust `ListenHTTP buffer is NOT full 1/1 ... was dropped`.** Measured 20/20 delivered while it fired on every one. Count at the far end before believing it.
- **Don't test a new processor type on the production agent.** `PythonCreator` only scans at boot, so it costs a restart of the agent that drives the desktop automation. The disposable `~/minifi-pytest/` install exists for this.
- **Don't `pkill -f trt_infer_server.py`.** The pattern matches the shell running it. Use the systemd user unit, or match `pgrep -x minifi` and filter on `/proc/<pid>/cwd`.
- **Don't leave `InvokeHTTP`'s timeouts at the framework default** when the target is a local daemon answering in milliseconds. 15 s of default socket read timeout is 15 s the caller spends hanging on a failure that was knowable immediately.

## Current state on the box

| | |
|---|---|
| `trt-infer.service` | user unit, enabled, `127.0.0.1:5910` |
| Production `NvidiaNano` C++ agent | pid 2616, flowVersion 18, `:8080` → `gpu_nifi_tensorRT-4.py` → Kafka `agent-nvidia-tensorRT`. **Never restarted this session** |
| `NvidiaNanoTrtTest` C++ sandbox | `~/minifi-pytest/`, process-mode, `:9096`, disposable — safe to tear down |
| `NvidiaNanoJava` | `~/minifi-java-nano/`, OpenJDK 21, `*:8090`, flowVersion 1 |
| Power mode | 15 W (`pmode:0000`), 6 cores — someone had already switched it up from 7 W |
| Camera | **not attached.** The `{"source":"camera"}` path is tested for absence, not tested in use |

## Related

- `completed/nvidianano-minifi-ops.md` — the agent ops runbook for this box.
- `efm-nvidia-jetson-nano.md` — EFM on Kubernetes, Kafka NodePort exposure.
- `efm-nvidia-nano-research.md` — the ceiling: what Jetson-class hardware can reach for in 2026. This doc is the floor made real.
- `minifi-python-processors.md` — custom Python processors vs `ExecuteScript`, and the delivery recipe.
