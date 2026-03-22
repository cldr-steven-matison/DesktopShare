Here's how to interact with your deployed **vLLM service** (from the latest YAML using `Qwen/Qwen2.5-3B-Instruct` on port 8000, OpenAI-compatible API). No authentication is required by default (unless you added `--api-key` to the args).

First, ensure the service is accessible:
- In minikube, use port-forwarding:
  ```bash
  kubectl port-forward svc/vllm-service 8000:8000
  ```
  (Or forward the pod directly: `kubectl port-forward deployment/vllm-server 8000:8000`)

  This makes the API available at `http://localhost:8000`

### 1. curl Examples

#### Basic Chat Completion (single user message)
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-3B-Instruct",
    "messages": [
      {"role": "user", "content": "Tell me a short joke about programming."}
    ],
    "temperature": 0.7,
    "max_tokens": 150
  }'
```

#### With System Prompt + Multi-turn Conversation
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-3B-Instruct",
    "messages": [
      {"role": "system", "content": "You are a helpful and witty AI assistant."},
      {"role": "user", "content": "What is the capital of Japan?"},
      {"role": "assistant", "content": "Tokyo!"},
      {"role": "user", "content": "Now tell me something fun about it."}
    ],
    "temperature": 0.8,
    "max_tokens": 200,
    "top_p": 0.95
  }'
```

#### Streaming Response (add `"stream": true`)
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-3B-Instruct",
    "messages": [{"role": "user", "content": "Explain quantum entanglement in simple terms."}],
    "stream": true,
    "max_tokens": 300
  }'
```
(This outputs Server-Sent Events line-by-line; pipe to `jq` or a tool that handles streaming.)

#### List Available Models (debug endpoint)
```bash
curl http://localhost:8000/v1/models
```

### 2. Postman Setup

Postman works perfectly since vLLM mimics the OpenAI API. Here's a step-by-step to set it up:

1. **Create a New Collection**
   - Open Postman → Click "Collections" → New Collection
   - Name it: `vLLM Local Server` (or similar)

2. **Add Environment Variables** (optional but recommended for easy switching)
   - Click the eye icon (top right) → Add → New Environment
   - Name: `vLLM-minikube`
   - Add variables:
     - `base_url` = `http://localhost:8000/v1`  (or your forwarded URL)
     - `model_name` = `Qwen/Qwen2.5-3B-Instruct`
   - Save and select this environment.

3. **Create a Request for Chat Completions**
   - In your collection → Add Request
   - Name: `Chat Completion`
   - Method: **POST**
   - URL: `{{base_url}}/chat/completions`  (uses your env var)
   - Headers tab:
     - Key: `Content-Type` → Value: `application/json`
     - (No Authorization needed unless you enabled API key)
   - Body tab → raw → JSON:
     ```json
     {
       "model": "{{model_name}}",
       "messages": [
         {
           "role": "system",
           "content": "You are a helpful assistant."
         },
         {
           "role": "user",
           "content": "Hello! What's the weather like in a parallel universe?"
         }
       ],
       "temperature": 0.7,
       "max_tokens": 200,
       "stream": false
     }
     ```
   - For streaming: change `"stream": true` and test in Postman's console (it shows chunks).

4. **Optional Extra Requests**
   - Duplicate the above for variations:
     - Name: `List Models` → GET → `{{base_url}}/models`
     - Name: `Streaming Chat` → same as above but `"stream": true`

5. **Tips in Postman**
   - Use **Pre-request Script** if you want dynamic messages (e.g., via variables).
   - For streaming responses: Postman shows them in real-time in the response pane.
   - If you later add API key auth (by editing YAML args to include `--api-key YOURKEY`):
     - Add header: `Authorization` = `Bearer YOURKEY`
   - Export the collection as JSON and share/reuse it.

Test the curl first to confirm everything's live, then import or build in Postman for a nicer UI (visual editor, save examples, etc.). If you get errors like connection refused, double-check port-forward is running and pod logs show the server healthy (`kubectl logs deployment/vllm-server`). Let me know if you need a full Postman collection JSON export example!