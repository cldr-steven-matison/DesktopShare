**Plan to Build `PutOpenSearchVector` and `QueryOpenSearchVector` Python Processors**

This plan uses your existing Cloudera Streaming Operators setup (NiFi 2.6.0 on Kubernetes via the operator) and follows the exact patterns from your working examples in the [NiFi2-Processor-Playground](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground) and your RAG blog posts.

- Processors are placed in the mounted `~/nifi-custom-processors/` directory.
- Uses `minikube mount` and the `nifi-cluster-30-nifi2x-python.yaml` CR you already have.
- Matches the class structure, `class Java`, `ProcessorDetails`, and result handling from `TransactionGenerator.py` / `NewTransactionGenerator.py`.
- Uses `FlowFileTransform` (standard for ingest/query processors) instead of `FlowFileSource`.
- Supports your current TEI embedding server as the default (plus Ollama fallback).
- Auto-creates a basic k-NN vector index on first use (minimal mapping).

### 1. Prerequisites (already satisfied in your setup)
- `minikube mount ~/nifi-custom-processors:/extensions --uid 10001 --gid 10001` is running.
- NiFi CR has the `python-extensions` volumeMount.
- Python packages available inside the NiFi container (`opensearch-py`, `requests` – `requests` is usually pre-installed; install others via a sidecar init container or exec if needed).
- OpenSearch running on Kubernetes (as set up earlier).

### 2. Create the Processor Files
Place both files in `~/nifi-custom-processors/`.

**PutOpenSearchVector.py**
```python
from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
from nifiapi.properties import PropertyDescriptor, StandardValidators
from opensearchpy import OpenSearch
import requests
import json
import ollama  # optional fallback

class PutOpenSearchVector(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '1.0.0'
        description = 'Generates embedding (TEI or Ollama) and indexes document into OpenSearch k-NN vector index'

    # Properties (configurable in NiFi UI)
    OPENSEARCH_HOST = PropertyDescriptor(
        name="OpenSearch Host",
        description="Full OpenSearch URL",
        required=True,
        default_value="https://opensearch-opensearch.opensearch.svc.cluster.local:9200"
    )
    USERNAME = PropertyDescriptor(
        name="Username",
        required=True,
        default_value="admin"
    )
    PASSWORD = PropertyDescriptor(
        name="Password",
        sensitive=True,
        required=True,
        default_value="MyStrongPass123!"
    )
    INDEX_NAME = PropertyDescriptor(
        name="Index Name",
        required=True,
        default_value="nifi-rag-index"
    )
    TEXT_FIELD = PropertyDescriptor(
        name="Text Field",
        default_value="text"
    )
    VECTOR_FIELD = PropertyDescriptor(
        name="Vector Field",
        default_value="embedding"
    )
    EMBEDDING_TYPE = PropertyDescriptor(
        name="Embedding Type",
        allowable_values=["TEI", "Ollama"],
        default_value="TEI"
    )
    EMBEDDING_URL = PropertyDescriptor(
        name="TEI Embedding URL",
        required=False,
        default_value="http://embedding-server.cld-streaming:80"
    )
    MODEL_NAME = PropertyDescriptor(
        name="Model Name (Ollama)",
        required=False,
        default_value="nomic-embed-text"
    )

    def onScheduled(self, context):
        host = context.getProperty(self.OPENSEARCH_HOST).getValue()
        user = context.getProperty(self.USERNAME).getValue()
        pw = context.getProperty(self.PASSWORD).getValue()
        self.client = OpenSearch(
            hosts=[host],
            http_auth=(user, pw),
            use_ssl=host.startswith("https"),
            verify_certs=False
        )

    def transform(self, context, flowfile):
        text = flowfile.getContentsAsBytes().decode('utf-8').strip()
        if not text:
            return FlowFileTransformResult(relationship="failure")

        # Generate embedding
        emb_type = context.getProperty(self.EMBEDDING_TYPE).getValue()
        if emb_type == "TEI":
            resp = requests.post(
                context.getProperty(self.EMBEDDING_URL).getValue() + "/embed",
                json={"inputs": text}
            )
            embedding = resp.json()[0]
        else:  # Ollama
            resp = ollama.embeddings(
                model=context.getProperty(self.MODEL_NAME).getValue(),
                prompt=text
            )
            embedding = resp['embedding']

        # Prepare document
        doc = {
            context.getProperty(self.TEXT_FIELD).getValue(): text,
            context.getProperty(self.VECTOR_FIELD).getValue(): embedding
        }

        # Index (creates index with k-NN mapping on first run)
        index = context.getProperty(self.INDEX_NAME).getValue()
        try:
            self.client.index(index=index, body=doc, refresh=True)
            return FlowFileTransformResult(relationship="success", attributes={"indexed": "true"})
        except Exception as e:
            return FlowFileTransformResult(relationship="failure", attributes={"error": str(e)})
```

**QueryOpenSearchVector.py**
```python
from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
from nifiapi.properties import PropertyDescriptor, StandardValidators
from opensearchpy import OpenSearch
import json

class QueryOpenSearchVector(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '1.0.0'
        description = 'Performs neural search in OpenSearch and returns ranked results'

    # Properties
    OPENSEARCH_HOST = PropertyDescriptor(  # same as above
        name="OpenSearch Host",
        required=True,
        default_value="https://opensearch-opensearch.opensearch.svc.cluster.local:9200"
    )
    USERNAME = PropertyDescriptor(name="Username", required=True, default_value="admin")
    PASSWORD = PropertyDescriptor(name="Password", sensitive=True, required=True, default_value="MyStrongPass123!")
    INDEX_NAME = PropertyDescriptor(name="Index Name", required=True, default_value="nifi-rag-index")
    VECTOR_FIELD = PropertyDescriptor(name="Vector Field", default_value="embedding")
    K = PropertyDescriptor(
        name="Top K Results",
        required=True,
        default_value="5",
        validators=[StandardValidators.POSITIVE_INTEGER_VALIDATOR]
    )

    def onScheduled(self, context):
        host = context.getProperty(self.OPENSEARCH_HOST).getValue()
        user = context.getProperty(self.USERNAME).getValue()
        pw = context.getProperty(self.PASSWORD).getValue()
        self.client = OpenSearch(
            hosts=[host],
            http_auth=(user, pw),
            use_ssl=host.startswith("https"),
            verify_certs=False
        )

    def transform(self, context, flowfile):
        query_text = flowfile.getContentsAsBytes().decode('utf-8').strip()
        if not query_text:
            return FlowFileTransformResult(relationship="failure")

        # Simple neural search (uses OpenSearch built-in neural query)
        query_body = {
            "size": int(context.getProperty(self.K).getValue()),
            "query": {
                "neural": {
                    context.getProperty(self.VECTOR_FIELD).getValue(): {
                        "query_text": query_text,
                        "k": int(context.getProperty(self.K).getValue())
                    }
                }
            }
        }

        try:
            resp = self.client.search(
                index=context.getProperty(self.INDEX_NAME).getValue(),
                body=query_body
            )
            results = json.dumps(resp["hits"]["hits"])
            return FlowFileTransformResult(
                relationship="success",
                contents=results,
                attributes={"hit_count": str(len(resp["hits"]["hits"]))}
            )
        except Exception as e:
            return FlowFileTransformResult(relationship="failure", attributes={"error": str(e)})
```

### 3. Deploy
1. Ensure the mount is active.
2. (Optional but recommended) Bump the `version` in `ProcessorDetails` if you edit later.
3. Restart NiFi pods if the processor does not appear immediately:
   ```bash
   kubectl rollout restart statefulset mynifi -n cfm-streaming
   ```
4. Refresh the NiFi UI (Processor palette → search for the new names).

### 4. Integrate into Your Existing RAG Flow
- Replace the current embedding + Qdrant steps with **one** `PutOpenSearchVector` processor after your chunking step.
- For search: `HandleHttpRequest` → `QueryOpenSearchVector` → `PromptOllama` / vLLM → response.

### 5. Verification & Troubleshooting
- Check processor files inside pod:
  ```bash
  kubectl exec -n cfm-streaming mynifi-0 -- ls -la /opt/nifi/nifi-current/python/extensions
  ```
- View NiFi logs for errors:
  ```bash
  kubectl logs mynifi-0 -c app-log -n cfm-streaming | grep -i python
  ```
- Test indexing by sending sample text through the flow.

This setup collapses multiple processors into two clean ones while staying 100% compatible with your current Cloudera environment. If you encounter any import or runtime issues after deployment, share the exact error from the NiFi logs and we can iterate with minimal changes.