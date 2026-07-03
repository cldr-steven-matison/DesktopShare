
Agent Commands all start from this point forward with a new minicube cluster:

```bash
kubectl port-forward svc/vllm-service 8000:8000 &
```

Next the following sample commands I am using to get my Telegram chat started:

```bash


/bash cd DesktopShare && git pull

/bash source .env && nohup sh ./DesktopShare/files/agent-install-operators.sh > deploy.log 2>&1 &

# notice use of -windows yaml for nifi
/bash source .env && cd ClouderaStreamingOperators && kubectl apply --filename kafka-eval.yaml,kafka-nodepool.yaml --namespace cld-streaming && kubectl apply -f cluster-issuer.yaml && kubectl apply -f nifi-cluster-30-nifi2x-windows.yaml -n cfm-streaming && kubectl apply -f nifi-combined.yaml

## a git commit if chat made any repo changes
/bash git add . && git commit -m "your commit message" && git push


/bash cd DesktopShare && git add . && git commit -m "Tuna Street Push Zellij 2" && git push


/bash cd ClouderaStreamingOperators && git status
/bash cd ClouderaStreamingOperators && mv efm-deployment.yaml efm-deployment-persisted.yaml
/bash cd ClouderaStreamingOperators && git restore efm-deployment.yaml
/bash cd ClouderaStreamingOperators && git add efm-deployment-persisted.yaml
/bash cd ClouderaStreamingOperators && git commit -m "EFM Persisted Yaml" && git push


/bash cd ClouderaStreamingOperators && git add vllm-Qwen2.5-1.5B-Instruct.yaml && git add  vllm-Qwen2.5-3B-Instruct.yaml && git add vllm-Qwen2.5-7B-Instruct-AWQ.yaml
/bash cd ClouderaStreamingOperators && git commit -m "vLLM Models" && git push

/bash kubectl get pods --all-namespaces

/bash cd ~/cso-operator-app && git pull



Streamers pipeline — Telegram bot scripts:


/bash source .env && bash ./DesktopShare/files/agent-PostNow.sh

/bash source .env && bash ./DesktopShare/files/agent-approvePosts.sh

# t:username -> Twitch, k:username -> Kick — 1 to 4 args, replaces the whole watch list
/bash source .env && bash ./DesktopShare/files/agent-watchList.sh t:xqc k:adinross

/bash source .env && bash ./DesktopShare/files/agent-minikube-reset.sh

```