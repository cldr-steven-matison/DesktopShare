🚀 **Just launched StreamToWhisper** — the missing audio layer for my fully local Cloudera Streaming Operators stack!

I’ve wired **insanely-fast-whisper** (Whisper large-v3 + Flash Attention 2) directly into my RTX 4060 Minikube cluster. Now audio files, podcasts, meeting recordings, or live streams flow through:

- Apache NiFi → Kafka (`new_audio` topic)  
- GPU-powered transcription server (150+ minutes in <90 seconds)  
- Clean transcripts land in Kafka (`transcribed_text`)  
- Automatically chunked, embedded, and upserted into the existing **StreamToVLLM** Qdrant collection  

Result? I can now ask my local vLLM Qwen2.5-3B model questions about *spoken* content with perfect context.

Full end-to-end pipeline built on the same Cloudera Streaming Operators (CSM + CFM) + NiFi + Kafka foundation I already had running.

📝 **Complete technical guide + all YAMLs, Dockerfile, and ready-to-import NiFi flows** are in the new blog post.

👉 **StreamToWhisper: Insanely Fast Audio Transcription with Cloudera Streaming Operators**  
(link in first comment)

#Cloudera #StreamingOperators #NiFi #Kafka #Whisper #RAG #LocalAI #GPU #DataEngineering #AI #Kubernetes

Would love to hear how you’re handling audio ingestion in your streaming stacks — drop a comment or DM! 🔥