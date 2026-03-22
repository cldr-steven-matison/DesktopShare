### Managing Multiple Port-Forwards Efficiently in Minikube/kubectl
Running tons of `kubectl port-forward` commands manually gets painful fast (one terminal per forward, easy to lose, conflicts, etc.). Here are practical ways to handle many at once without going insane:

1. **Run them in background with &** (quick & dirty)  
   In one terminal:
   ```bash
   kubectl port-forward svc/qdrant 6333:6333 &
   kubectl port-forward svc/vllm-service 8000:8000 &
   kubectl port-forward svc/embedding-service 8080:8080 &
   kubectl port-forward svc/mynifi-web 8443:443 &   # or whatever ports
   ```
   - Add `disown` after each to detach completely: `& disown`
   - Check running: `ps aux | grep port-forward`
   - Kill: `pkill -f "port-forward.*qdrant"` (or by PID)

2. **Single kubectl with multiple mappings** (if same resource)  
   ```bash
   kubectl port-forward svc/my-service 8000:8000 8080:8081 9000:8082
   ```
   Works great when forwarding several ports from **one** pod/service.

3. **Use a simple bash script or multiplexer**  
   Create a file like `port-forwards.sh`:
   ```bash
   #!/usr/bin/env bash
   forwards=(
     "svc/qdrant 6333:6333"
     "svc/vllm-service 8000:8000"
     "svc/embedding-service 8080:8080"
     "svc/mynifi-web 8443:443"
     # add more
   )

   case $1 in
     start)
       for f in "${forwards[@]}"; do
         kubectl port-forward $f &> /dev/null &
         echo "Started: $f"
       done
       ;;
     stop)
       pkill -f "kubectl port-forward"
       ;;
     status)
       ps aux | grep port-forward | grep -v grep
       ;;
   esac
   ```
   Then: `./port-forwards.sh start` / `stop` / `status`
