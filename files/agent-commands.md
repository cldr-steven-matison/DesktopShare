# Agent Commands (OpenClaw Telegram bot)

**Core finding:** OpenClaw's `/bash` needs a `bash -c "..."` wrapper for anything
beyond a single bare command — `&&` chains, `source`, and backgrounding (`&`)
don't reliably run (the bot sometimes just chats back instead of executing)
without it. Bare single commands with no chaining may work unwrapped, but wrap
everything for consistency. Format:
```
/bash bash -c "command"
```

## Confirmed tested and working

Live-tested end-to-end against the real cluster/app — see
`cso-operator-app-streamers.md` Session 14 for test details.

post now with user
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-PostNow.sh xqc"
```

start fetch clips
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-fetchClips.sh start"
```

stop fetch clips
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-fetchClips.sh stop"
```

approve posts
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-approvePosts.sh"
```

update watch list
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-watchList.sh t:extremely k:deenthegreat"
```

## Rewritten with the working pattern — not yet re-tested, verify via Telegram

These previously failed (or the bot hallucinated a chat reply instead of
running them) as plain `/bash <cmd>`. Same commands, now wrapped — confirm
each one via Telegram before trusting it.

vllm port-forward (do this first on a new/restarted cluster)
```bash
/bash bash -c "kubectl port-forward svc/vllm-service 8000:8000 &"
```

pull DesktopShare
```bash
/bash bash -c "cd DesktopShare && git pull"
```

install CSO operators (long-running — logs to deploy.log)
```bash
/bash bash -c "source .env && nohup sh ./DesktopShare/files/agent-install-operators.sh > deploy.log 2>&1 &"
```

apply Kafka + NiFi resources (after operators are installed; windows NiFi yaml variant)
```bash
/bash bash -c "source .env && cd ClouderaStreamingOperators && kubectl apply --filename kafka-eval.yaml,kafka-nodepool.yaml --namespace cld-streaming && kubectl apply -f cluster-issuer.yaml && kubectl apply -f nifi-cluster-30-nifi2x-windows.yaml -n cfm-streaming && kubectl apply -f nifi-combined.yaml"
```

commit + push DesktopShare (template — swap the commit message)
```bash
/bash bash -c "cd DesktopShare && git add . && git commit -m 'your commit message' && git push"
```

get all pods
```bash
/bash bash -c "kubectl get pods --all-namespaces"
```

pull cso-operator-app
```bash
/bash bash -c "cd ~/cso-operator-app && git pull"
```

full minikube reset (destructive — deletes and recreates the cluster; see `agent-minikube-reset.sh`)
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-minikube-reset.sh"
```

---

Dropped as one-off/historical, not reusable patterns: the zellij layout file
copy, the EFM yaml persisted-rename workflow, and the vLLM model yaml
`git add` batch — real things that happened in a past session, but not
commands worth re-running verbatim. See git history (`09f90b4`, `df93a8a`,
prior root `agent-commands.md`) if the exact steps are needed again.
