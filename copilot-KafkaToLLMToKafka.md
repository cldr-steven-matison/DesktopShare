### Overview
**Goal:** Build the Matrix Monitor NiFi flow manually on your CFM 3.0 NiFi so you avoid import/JSON issues.  
**Flow shape:** **ConsumeKafkaRecord → ReplaceText (build vLLM request) → InvokeHTTP → EvaluateJsonPath → PublishKafkaRecord** plus **RouteOnAttribute → PublishKafkaRecord (alerts)**.  
From your attached doc: **"Awesome — GPU already showing up in Minikube pods means you're past the hardest part on this WSL2/Docker Desktop stack."**  
From your attached doc: **"Since your setup is lightweight (single-node Minikube, consumer GPU), focus on real-time/streaming AI inference that ties beautifully into your data pipeline tools."**

---

### 1. Access NiFi UI on CFM 3.0
- **Port‑forward** the NiFi service to your workstation if you don’t have direct access:
  ```bash
  kubectl -n cfm-streaming port-forward svc/mynifi 8080:8080
  ```
- Open `http://localhost:8080/nifi` in your browser and log in with your CFM credentials.

---

### 2. Create a Parameter Context
1. In NiFi UI top-right, **hamburger → Parameter Contexts → Create**.  
2. Name it **matrix_monitor_params**.  
3. Add parameters:
   - **Kafka Broker Endpoint** = `my-cluster-kafka-bootstrap.cld-streaming.svc:9092` 
   - **Input Topic** = `events`
   - **Inference Topic** = `inference-results`
   - **Alerts Topic** = `alerts`
   - **vLLM Base URL** = `http://localhost:8000`
4. Save and **apply** the Parameter Context to the Process Group you will create.

---

### 3. Create Controller Services
Inside the Process Group (or root if you prefer):
1. Open **Controller Services** tab → **+** → add:
   - **JsonTreeReader** (org.apache.nifi.json.JsonTreeReader)  
     - **Schema Access Strategy** = `Infer Schema`
   - **JsonRecordSetWriter** (org.apache.nifi.json.JsonRecordSetWriter)  
     - **Schema Write Strategy** = `Do not write schema`
2. **Enable** both services (click the lightning bolt and enable).  
3. If your Kafka requires security, also add and configure the appropriate **KafkaClientService** or SSL/SASL controller services per your cluster.

---

### 4. Build the processors and wire them
Create processors in this order and configure the properties exactly as shown.

#### ConsumeKafkaRecord
- **Type**: `ConsumeKafkaRecord_2_6`  
- **Properties**
  - **Topic Name** = `#{Input Topic}`
  - **Bootstrap Servers** = `#{Kafka Broker Endpoint}`
  - **Group ID** = `matrix-monitor-consumer`
  - **Reader** = `JsonTreeReader`
  - **Writer** = `JsonRecordSetWriter`
- **Scheduling**: 1 sec

#### ReplaceText Build vLLM Request
- **Type**: `ReplaceText`  
- **Properties**
  - **Search Value** = `(?s)(.*)`  
  - **Replacement Value** (exact JSON body):
    ```json
    {"model":"meta-llama/Llama-3.2-3B-Instruct","messages":[{"role":"user","content":"Summarize this event: ${record:value('/payload')}" }],"temperature":0.0}
    ```
  - **Replacement Strategy** = `Regex`
  - **Evaluation Mode** = `Entire text`
  - **Character Set** = `UTF-8`
- **Auto‑terminate**: failure

#### InvokeHTTP to vLLM
- **Type**: `InvokeHTTP`  
- **Properties**
  - **HTTP Method** = `POST`
  - **Remote URL** = `#{vLLM Base URL}/v1/chat/completions`


#### EvaluateJsonPath
- **Type**: `EvaluateJsonPath`  
- **Properties**
  - **Destination** = `flowfile-attribute`
  - **response_text** = `$.choices[0].message.content`
  - **status_code** = `$.status`
  - **Return Type** = `auto-detect`
- **Auto‑terminate**: failure, unmatched

#### PublishKafkaRecord Inference Results
- **Type**: `PublishKafka_2_6`  
- **Properties**
  - **Topic Name** = `#{inference.topic}`
  - **Bootstrap Servers** = `#{Kafka Broker Endpoint}`
  - **Record Writer** = `JsonRecordSetWriter`
  - **Key** = `#{record:value('/id')}` (or `id` attribute)
  - **acks** = `all`
  - **security.protocol** = `PLAINTEXT` (or your cluster setting)

#### RouteOnAttribute Score/Alert
- **Type**: `RouteOnAttribute`  
- **Properties**
  - **high_risk** = `#{response_text:matches('(?i).*\\b(attack|breach|exploit|error|failed|unauthorized)\\b.*')}`

#### PublishKafkaRecord Alerts
- **Type**: `PublishKafka_2_6`  
- **Properties**
  - **Topic Name** = `#{Alerts Topic}`
  - **Bootstrap Servers** = `#{Kafka Broker Endpoint}`
  - **Record Writer** = `JsonRecordSetWriter`
  - **Key** = `#{record:value('/id')}`

---

### 5. Wire the processors
- **ConsumeKafkaRecord → ReplaceText** (relationship `success`)  
- **ReplaceText → InvokeHTTP** (`success`)  
- **InvokeHTTP → EvaluateJsonPath** (`Response`)  
- **EvaluateJsonPath → PublishKafkaRecord (inference)** (`success`)  
- **EvaluateJsonPath → RouteOnAttribute** (`success`)  
- **RouteOnAttribute high_risk → PublishKafkaRecord (alerts)**  
- **RouteOnAttribute unmatched → PublishKafkaRecord (inference)**

Use the NiFi drag‑and‑drop connection UI and select the relationships shown.

---

### 6. Securely inject HF token and other secrets
- **Do not** hardcode tokens in processors. Use one of:
  - NiFi **Variable Registry** (encrypted in CFM) for non-sensitive values.
  - NiFi **Sensitive Parameters** in the Parameter Context for tokens.
  - A secrets controller service (e.g., HashiCorp Vault controller) if available in your CFM environment.
- Example: add a Parameter `hf.token` (sensitive) and set `http.headers.Authorization` attribute to `Bearer #{hf.token}` before `InvokeHTTP`.

---

### 7. Test the flow end-to-end
1. **Start** processors in order (enable controller services first).  
2. Produce a test message to Kafka (run from a pod that has Kafka client tools or from your machine if networked):
   ```bash
   kubectl -n cfm-streaming exec -it deploy/kafka-client -- \
     kafka-console-producer --broker-list my-cluster-kafka-bootstrap.cld-streaming.svc:9092 --topic events
   ```
   Then send:
   ```json
   {"id":"evt-1","payload":"Multiple failed logins from 10.0.0.5"}
   ```
3. Watch NiFi provenance or the `inference-results` topic:
   ```bash
   kubectl -n cfm-streaming exec -it deploy/kafka-client -- \
     kafka-console-consumer --bootstrap-server my-cluster-kafka-bootstrap.cld-streaming.svc:9092 --topic inference-results --from-beginning --max-messages 5
   ```
4. Tail NiFi logs if something fails:
   ```bash
   kubectl -n cfm-streaming logs -f mynifi-0 -c nifi
   kubectl -n cfm-streaming exec -it mynifi-0 -- tail -n 200 -f /opt/nifi/nifi-current/logs/nifi-app.log
   ```

---

### 8. Troubleshooting checklist
- **Controller services disabled** → processors that reference them will fail to start. Enable them first.  
- **Wrong Parameter names** → ensure Parameter Context name and parameter keys match exactly.  
- **Bundle/type mismatch** → when creating processors manually in the UI you avoid bundle version mismatches that break imports.  
- **InvokeHTTP 401/403** → check `http.headers.Authorization` and token placement.  
- **OOM or slow vLLM responses** → add `MergeContent` to batch small events, throttle `ConsumeKafkaRecord`, or add Kafka buffering.  
- **No messages in Kafka topics** → verify topic names and Kafka bootstrap address; test with `kafka-console-producer/consumer`.

---

### Quick reference snippets you can copy
**InvokeHTTP body example** (ReplaceText output):
```json
{"model":"meta-llama/Llama-3.2-3B-Instruct","messages":[{"role":"user","content":"Summarize this event: Multiple failed logins from 10.0.0.5"}],"temperature":0.0}
```

**RouteOnAttribute expression**
```
#{response_text:matches('(?i).*\\b(attack|breach|exploit|error|failed|unauthorized)\\b.*')}
```

---

### Final notes and next offers
- Building the flow manually in the NiFi UI avoids the import/JSON schema mismatch you hit.  
- If you want, I’ll now **generate the exact NiFi UI step sequence** as a checklist you can follow click‑by‑click, or produce the minimal `curl` calls to create the processors via the NiFi REST API instead of the UI. Tell me which you prefer and I’ll produce it in the same style as your blog.