**Here is a complete list Cloudera and Steven Matison Resources:**

### 1. Main GitHub Repository (Core Setup)
- **Repository**: [https://github.com/cldr-steven-matison/ClouderaStreamingOperators](https://github.com/cldr-steven-matison/ClouderaStreamingOperators)  
  Full Cloudera Streaming Operators deployment (NiFi 2.x on Kubernetes).

### 2. Blog Posts
- **How to AI with NiFi and Python**
  []()
  (Explains my approach on how to use AI to build NiFi Python Processors)

- **Observability with Cloudera Streaming Operators**
  []()
  (Wire the entire Cloudera Streaming Operator stack to Prometheus & Grafana)

- **Custom Processors with Cloudera Streaming Operators**  
  [https://cldr-steven-matison.github.io/blog/Custom-Processors-With-Cloudera-Streaming-Operators/](https://cldr-steven-matison.github.io/blog/Custom-Processors-With-Cloudera-Streaming-Operators/)  
  (Explains Python processor deployment, mount setup, and `nifi-cluster-30-nifi2x-python.yaml` pattern.)

- **RAG with Cloudera Streaming Operators**  
  [https://cldr-steven-matison.github.io/blog/RAG-with-Cloudera-Streaming-Operators/](https://cldr-steven-matison.github.io/blog/RAG-with-Cloudera-Streaming-Operators/)  
  (Your existing RAG flow with Kafka → chunking → TEI embedding server → vector DB.)

### 3. Supporting GitHub Repositories
- **NiFi2-Processor-Playground**  
  [https://github.com/cldr-steven-matison/NiFi2-Processor-Playground](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground)  
  (Working Python processor examples from various lessons such as `TransactionGenerator.py` / `NewTransactionGenerator.py` / `FraudModel.py`

- **MiNiFi-Kubernetes-Playground**  
  [https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground](https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground)  
  (A clean-slate playground for experimenting with **Apache MiNiFi C++** on **Minikube** (Kubernetes). Includes a custom `Dockerfile`, strict `config.yml` (ListenHTTP → PublishKafka + PutFile), Kubernetes `Deployment`/`Service` manifests with readiness probe fixes, and a “nuclear” rebuild script for fast iteration without caching issues.)
