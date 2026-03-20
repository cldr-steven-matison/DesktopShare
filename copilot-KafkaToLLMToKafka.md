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
  - **Replacement Value** (exact JSON body):
    ```json
    {"model":"meta-llama/Llama-3.2-3B-Instruct","messages":[{"role":"user","content":"Summarize this event: $1" }],"temperature":0.0}
    ```
  - **Evaluation Mode** = `Entire text`
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

#### RouteOnAttribute Score/Alert
- **Type**: `RouteOnAttribute`  
- **Properties**
  - **high_risk** = `${response_text:matches('(?i).*\\b(attack|breach|exploit|error|failed|unauthorized)\\b.*')}`

#### PublishKafkaRecord Alerts
- **Type**: `PublishKafka_2_6`  
- **Properties**
  - **Topic Name** = `#{Alerts Topic}`
  - **Bootstrap Servers** = `#{Kafka Broker Endpoint}`
  - **Record Writer** = `JsonRecordSetWriter`
  - **Key** = `${record:value('/id')}`

---

### 5. Wire the processors
- **ConsumeKafkaRecord → ReplaceText** (relationship `success`)  
- **ReplaceText → InvokeHTTP** (`success`)  
- **InvokeHTTP → EvaluateJsonPath** (`Response`)  
- **EvaluateJsonPath → PublishKafkaRecord (inference)** (`success`)  
- **EvaluateJsonPath → RouteOnAttribute** (`success`)  
- **RouteOnAttribute high_risk → PublishKafkaRecord (alerts)**  
- **RouteOnAttribute unmatched → PublishKafkaRecord (inference)**


---