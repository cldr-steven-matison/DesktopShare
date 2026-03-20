Here is a **corrected and improved version** of your NiFi flow instructions for the **Matrix Monitor** pipeline (Consume from Kafka → LLM summarization via vLLM → Publish results back to Kafka + route high-risk alerts).

### Key Corrections & Improvements Made

- **ConsumeKafkaRecord_2_6** → Use correct property names: `Kafka Brokers` (not Bootstrap Servers), `Topic Name`, `Group ID`, etc. Added missing essential properties like `Offset Reset`.
- **ReplaceText** → Changed to use **Literal Replace** strategy (safer for building full JSON). Used proper escaping and Expression Language to insert the original event content dynamically. Added system prompt for better summarization behavior.
- **InvokeHTTP** → Added critical properties: `Content-Type` header = `application/json`, `Send Message Body` = true, and proper URL formatting.
- **EvaluateJsonPath** → Correct path for vLLM/OpenAI-compatible response: `$.choices[0].message.content`. Added extraction of `id` or other fields if needed.
- **RouteOnAttribute** → Fixed expression syntax (added quotes around regex, proper case-insensitivity).
- **PublishKafkaRecord** → Use `PublishKafkaRecord_2_6` (consistent version), correct property names (`Kafka Brokers`, `Topic Name`, `Record Writer`).
- General → Added missing relationships routing, failure handling suggestions, scheduling tweaks, and parameter usage consistency. Assumed input events are JSON with at least a field like `text`, `message`, or `content` to summarize (adjust as needed).

### Updated Instructions: Build Matrix Monitor NiFi Flow (CFM 3.0 / NiFi)

#### 1. Access the NiFi UI
```bash
kubectl -n cfm-streaming port-forward svc/mynifi 8080:8080
```
Open: `http://localhost:8080/nifi`  
Log in with your CFM credentials.

#### 2. Create a Parameter Context (recommended)
Hamburger menu → **Parameter Contexts** → **Create**  
Name: `matrix_monitor_params`

Add these parameters (adjust values to match your environment):

- `kafka_brokers` = `my-cluster-kafka-bootstrap.cld-streaming.svc:9092`
- `input_topic` = `events`
- `inference_topic` = `inference-results`
- `alerts_topic` = `alerts`
- `vllm_base_url` = `http://localhost:8000`   (or your actual vLLM service URL, e.g. inside-cluster service name)
- `consumer_group` = `matrix-monitor-consumer`

Save → Enable → Apply to your target Process Group (or root canvas).

#### 3. Create & Enable Controller Services
In your Process Group (or root canvas) → Controller Services tab → **+**

Add and configure/enable:

- **JsonTreeReader** (`org.apache.nifi.json.JsonTreeReader`)
  - Schema Access Strategy = `Infer Schema`
  - **Enable** it.

- **JsonRecordSetWriter** (`org.apache.nifi.json.JsonRecordSetWriter`)
  - Schema Write Strategy = `Do not write schema`
  - **Enable** it.

(If your Kafka uses SSL/SASL, also add and configure the appropriate Kafka security controller service.)

#### 4. Add & Configure Processors (in suggested left-to-right order)

1. **ConsumeKafkaRecord** (`ConsumeKafkaRecord_2_6`)
   - Kafka Brokers = `#{kafka_brokers}`
   - Topic Name = `#{input_topic}`
   - Group ID = `#{consumer_group}`
   - Offset Reset = `latest` (or `earliest` depending on needs)
   - Record Reader = `JsonTreeReader`
   - Record Writer = `JsonRecordSetWriter` (used if you split later; optional here)
   - Scheduling → Run Schedule = `1 sec`

2. **ReplaceText** – Build vLLM request body (`ReplaceText`)
   - Replacement Strategy = `Literal Replace`
   - Replacement Value = (paste exactly — adjust `"content"` field name if your events use different key e.g. `message` or `text`)
     ```json
     {
       "model": "meta-llama/Llama-3.2-3B-Instruct",
       "messages": [
         {"role": "system", "content": "You are a concise security event summarizer. Summarize the event in 1-2 short sentences, highlighting any potential risk or anomaly."},
         {"role": "user", "content": "${field.value:jsonPath('$.content')}"}
       ],
       "temperature": 0.0,
       "max_tokens": 150
     }
     ```
   - Evaluation Mode = `Entire text`
   - **Note**: If your input JSON has no top-level `content`, change the EL expression to match (e.g. `$.message`, `$.event_description`, or `${whole.content}`).

3. **InvokeHTTP** – Call vLLM (`InvokeHTTP`)
   - HTTP Method = `POST`
   - Remote URL = `#{vllm_base_url}/v1/chat/completions`
   - Content-Type = `application/json` (add via **Headers** dynamic property: name=`Content-Type`, value=`application/json`)
   - Send Message Body = `true`
   - Connection Timeout / Read Timeout = `30 sec` (adjust for model speed)
   - Ignore SSL Issues = `true` (only if self-signed cert; better to configure truststore)

4. **EvaluateJsonPath** – Extract LLM response
   - Destination = `flowfile-attribute`
   - Add properties:
     - `summary` → `$.choices[0].message.content`
     - `llm_status` → `$.choices[0].finish_reason` (optional)
   - Return Type = `auto-detect`
   - Auto-terminate `failure` and `unmatched`

5. **PublishKafkaRecord** – Inference results (`PublishKafkaRecord_2_6`)
   - Kafka Brokers = `#{kafka_brokers}`
   - Topic Name = `#{inference_topic}`
   - Record Writer = `JsonRecordSetWriter`
   - Use Kafka Key = `true` (optional)
   - Kafka Key Attribute = `uuid` or `${UUID()}` or existing `${id}` if present
   - Message Key Field = `/id` (if using record path for key)

6. **RouteOnAttribute** – Detect high-risk summaries
   - Routing Strategy = `Route to Property Name`
   - Add property:
     - `high_risk` = `${summary:toString():toLower():contains('attack') || ${summary:toString():toLower():contains('breach') || ${summary:toString():toLower():contains('exploit') || ${summary:toString():toLower():contains('unauthorized') || ${summary:toString():toLower():contains('failed login')}`   (expand regex/keywords as needed)

7. **PublishKafkaRecord** – Alerts only (`PublishKafkaRecord_2_6`)
   - Same as above, but:
     - Topic Name = `#{alerts_topic}`

#### 5. Wire the Relationships (Connections)

- ConsumeKafkaRecord **success** → ReplaceText
- ReplaceText **success** → InvokeHTTP
- InvokeHTTP **response** → EvaluateJsonPath
- EvaluateJsonPath **success** → PublishKafkaRecord (inference-results)
- EvaluateJsonPath **success** → RouteOnAttribute   (use same success twice or clone the connection)
- RouteOnAttribute **high_risk** → PublishKafkaRecord (alerts)
- RouteOnAttribute **unmatched** → PublishKafkaRecord (inference-results)   (so non-alerts still go to main topic)

#### 6. Additional Recommendations

- Add **LogAttribute** or **PutFile** on failure relationships during testing.
- Use **UpdateAttribute** before Publish if you want to add metadata (e.g. `inference_timestamp = ${now():format('yyyy-MM-dd HH:mm:ss')}`).
- Test with small throughput first (right-click ConsumeKafkaRecord → Start, then monitor).
- If vLLM is slow, increase InvokeHTTP timeouts and consider batching (requires more advanced flow).

This corrected flow should now work reliably with vLLM's OpenAI-compatible endpoint and your Kafka setup. Start the flow and monitor the summary & alerts topics. Let me know what your input event JSON structure looks like if you need further tweaks to the ReplaceText EL expression.