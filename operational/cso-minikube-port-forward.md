## Managing Multiple Services & Port-Forwards Efficiently in Minikube
Running tons of `kubectl port-forward` or `minikube service` commands manually gets painful fast (one terminal per forward, easy to lose, conflicts, etc.). Here are practical ways to handle many at once without going insane:


## Using minikube service list
Before you start working with services, it is helpful to see the state of all your services in one view. You don't need to run a command for each just to check the status:

```Bash
minikube service list --namespace cld-streaming
```

Notice the following output:

```terminal
┌───────────────┬────────────────────────────────┬──────────────────┬─────┐
│   NAMESPACE   │              NAME              │   TARGET PORT    │ URL │
├───────────────┼────────────────────────────────┼──────────────────┼─────┤
│ cld-streaming │ cloudera-surveyor-service      │ http/8080        │     │
│ cld-streaming │ flink-operator-webhook-service │ No node port     │     │
│ cld-streaming │ my-cluster-kafka-bootstrap     │ No node port     │     │
│ cld-streaming │ my-cluster-kafka-brokers       │ No node port     │     │
│ cld-streaming │ schema-registry-service        │ application/9090 │     │
│ cld-streaming │ ssb-mve                        │ No node port     │     │
│ cld-streaming │ ssb-postgresql                 │ No node port     │     │
│ cld-streaming │ ssb-session-admin              │ No node port     │     │
│ cld-streaming │ ssb-session-admin-rest         │ No node port     │     │
│ cld-streaming │ ssb-sse                        │ No node port     │     │
└───────────────┴────────────────────────────────┴──────────────────┴─────┘
```

This generates a clean table showing the current running services.


## **Run them in background with &** 

   For `minikube service`:

   ```bash
minikube service cloudera-surveyor-service -n cld-streaming --url &
minikube service schema-registry-service -n cld-streaming --url & minikube service ssb-sse -n cld-streaming --url &
   ```
   - use `&` to chain multiple commands
   - use `&` on end to run in the background
   - use `--url` to just return the url w/o opening the browser


   For `kubectl port-forward`:

   ```bash
   kubectl port-forward svc/qdrant 6333:6333 &
   kubectl port-forward svc/vllm-service 8000:8000 &
   kubectl port-forward svc/embedding-service 8080:8080 &
   kubectl port-forward svc/mynifi-web 8443:443 &
   ```
   - Add `disown` after each to detach completely: `& disown`
   - Check running: `ps aux | grep port-forward`
   - Kill: `pkill -f "port-forward.*qdrant"` (or by PID)


## **Use a simple bash script**  

  Create a file like `minikube-services.sh`:

```bash
#!/usr/bin/env bash

# List your services here
SERVICES=(
  "cloudera-surveyor-service"
  "schema-registry-service"
  "ssb-sse"
)
NAMESPACE="cld-streaming"

case $1 in
  start)
    for svc in "${SERVICES[@]}"; do
      # Use --url to prevent browser pop-up spam if preferred
      minikube service $svc --namespace $NAMESPACE & 
      echo "Starting tunnel for: $svc"
    done
    ;;
  stop)
    echo "Stopping all minikube service tunnels..."
    pkill -f "minikube service"
    ;;
  list)
    minikube service list -n $NAMESPACE
    ;;
  *)
    echo "Usage: ./streaming-ui.sh {start|stop|list}"
    ;;
esac
```

Then: `./minikube-services.sh start` / `stop` / `status`

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
