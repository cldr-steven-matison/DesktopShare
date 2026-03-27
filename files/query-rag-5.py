import requests

def ask(question):
    # 1. Embed
    emb = requests.post("http://localhost:8080/embed", json={"inputs": question}).json()[0]

    # 2. Search Qdrant
    search = requests.post("http://localhost:6333/collections/my-rag-collection/points/search", 
                           json={"vector": emb, "limit": 1, "with_payload": True}).json()
    
    results = search.get("result", [])
    raw_text = results[0]["payload"].get("text", "") if results else "No context."

    # --- THE ESCAPE HATCH ---
    # If the text starts with '[', it's a vector. We don't want it.
    if str(raw_text).startswith("["):
        print("[!] Warning: Found vector trash in text field. Ignoring it.")
        context = "Reference data is currently being re-indexed."
    else:
        # Force the context to be tiny (500 chars) to guarantee we stay under 4096 tokens
        context = str(raw_text)[:500] 

    # 3. vLLM Call
    payload = {
        "model": "Qwen/Qwen2.5-3B-Instruct",
        "messages": [
            {"role": "system", "content": "Briefly answer using this context."},
            {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
        ],
        "max_tokens": 100
    }

    resp = requests.post("http://localhost:8000/v1/chat/completions", json=payload)
    
    if resp.status_code == 200:
        print("\n=== ANSWER ===")
        print(resp.json()["choices"][0]["message"]["content"])
    else:
        print(f"Error: {resp.text}")

ask("What is StreamToVLLM?")
