Hey Steven, sounds like a solid Friday night — rum & cokes and a humming minikube cluster with GPU-accelerated Llama inference? That's the way to cap the week! 🎉

Your setup looks strong:
- vLLM server pod running (`vllm-server-56b96dd94c-7q4hq`) using quite a bit of memory (~8.4GB), which is expected
- Exposed at `http://localhost:8000/v1/chat/completions` (OpenAI-compatible endpoint)
- mynifi-0 pod healthy with high CPU usage (likely because of your max-CPU tuning blog post)

Let's build a simple **NiFi flow** inside your mynifi instance to:
1. Generate/test a prompt
2. Call your local LLM via InvokeHTTP
3. Check the response (and indirectly verify GPU usage via speed/latency)

### Basic Flow Overview
```
GenerateFlowFile → UpdateAttribute (set prompt) → UpdateAttribute (set JSON body) → InvokeHTTP → LogAttribute / PutFile (for response)
                   └──────────────────────────────┘
```

Or more minimal for quick testing:
```
GenerateFlowFile → ReplaceText (build JSON) → InvokeHTTP → LogAttribute
```

### Step-by-Step to Build It in NiFi UI

1. **Drag in a GenerateFlowFile** processor (good for testing – creates 1 FlowFile with dummy content)
   - Scheduling → Run Schedule = 0 sec / 1 sec (or just timer driven once)
   - Custom Text = (can leave blank or put "test")

2. **Connect to a ReplaceText** processor (easiest way to build the JSON payload)
   - Search / Replacement Strategy = **Literal Replace**
   - Replacement Value = (use this exact expression – copy-paste it)

```json
{
  "model": "whatever-your-vllm-uses",  
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful AI assistant running on a GPU in minikube."
    },
    {
      "role": "user",
      "content": "Tell me a short dad joke about Kubernetes and rum."
    }
  ],
  "temperature": 0.7,
  "max_tokens": 120
}
```

   - If you want dynamic prompt, you can use EL later (e.g. `${prompt}`)

   - Or simpler test body (many local servers accept this too):

```json
{
  "prompt": "Hello from NiFi! Write a haiku about GPUs and rum.",
  "max_tokens": 80
}
```

3. **Connect to InvokeHTTP** processor

   Key properties to set:

   | Property                        | Value                                                                 | Notes |
   |---------------------------------|-----------------------------------------------------------------------|-------|
   | Remote URL                      | `http://host.minikube.internal:8000/v1/chat/completions`             | Important: use `host.minikube.internal` to reach minikube host services from inside pod |
   | HTTP Method                     | POST                                                                  |       |
   | Content-Type                    | `application/json`                                                    | (add as dynamic property if not auto-set) |
   | Send Message Body               | true                                                                  |       |
   | Attributes to Send              | (leave blank or `*` if you want to send attrs as headers)            | Usually not needed |
   | SSL Context Service             | (none)                                                                | Unless you added TLS |
   | Connection Timeout              | 30 sec                                                                |       |
   | Read Timeout                    | 120 sec                                                               | Give it time for generation |
   | Ignore Response Code            | false                                                                 |       |
   | Follow Redirects                | false                                                                 |       |
   | Use Chunked Transfer-Encoding   | false                                                                 |       |

   **Important hostname note**  
   From inside the NiFi pod → your vLLM service is probably a ClusterIP service in default namespace.  
   Try these in order until one works:

   - `http://vllm-server:8000/v1/chat/completions` (if service name = vllm-server)
   - `http://host.minikube.internal:8000/v1/chat/completions` (reaches localhost of minikube VM)
   - `http://localhost:8000/...` → usually **does not work** from pod to host

   Quick test from NiFi pod shell:  
   `curl http://host.minikube.internal:8000/v1/models` or similar to confirm connectivity.

4. **Auto-terminate / route success & failure**
   - For quick test: Auto-terminate success + failure on InvokeHTTP
   - Better: → LogAttribute processor on success (to see the JSON response in nifi-app.log)
   - Or → PutFile to `/tmp/llm-responses` inside the pod so you can `kubectl cp` or `kubectl exec` in and see files

5. **Optional – make prompt dynamic**
   - Add UpdateAttribute before ReplaceText
   - Add property: `prompt` = `Tell me why rum and coke is the best Friday drink after tuning NiFi CPU limits`
   - Then in ReplaceText body use `"content": "${prompt}"`

6. **Start the flow & watch**
   - Right-click → Start
   - Watch InvokeHTTP → status history / view data provenance
   - Look at duration: if generation is fast (seconds instead of minutes), GPU is being used
   - Check pod logs of vllm-server (`kubectl logs vllm-server-...`) — you should see CUDA/GPU ops, tensor loading on GPU, etc.

### Quick GPU Usage Check
While the flow runs a few times:
- `kubectl top pod vllm-server-...` — memory should stay high, CPU may spike during generation
- `nvidia-smi` inside the vllm pod (if you can exec in): watch GPU util & memory jump during inference

If you hit connection refused / timeout → most likely hostname issue (host.minikube.internal vs service DNS).

Let me know what error you get (or paste a screenshot of InvokeHTTP config) and we can tweak it live. Or if you want to go fancier (streaming response, parse JSON with JoltTransformJSON, send prompt from Kafka, etc.) — just say the word.

Cheers to a great week, and enjoy the rest of those rum & cokes! 🥃🚀