# MiNiFi C++ Windows: ListenHTTP to PutFile Integration

This setup replicates the `ListenHTTP` → `PutFile` pattern from the **MiNiFi-Kubernetes-Playground** repository to enable real-time MIDI triggering via an HTTP API.

---

## 1. MiNiFi Configuration (`conf.yml`)
The agent listens on a dedicated port and writes the received payload (the MIDI note) directly to the local filesystem for a watchdog script to consume.

```yaml
MiNiFi Config Version: 3
Flow Controller:
  name: MiNiFi Music Edge
Processors:
  - name: ListenForNotes
    class: org.apache.nifi.minifi.processors.ListenHTTP
    Properties:
      Listening Port: 9998
      Listening IP: 0.0.0.0
      # Note: C++ agent often defaults to /contentListener regardless of this value
      HTTP Rest URL: midi

  - name: WriteToInbox
    class: org.apache.nifi.minifi.processors.PutFile
    scheduling strategy: EVENT_DRIVEN
    Properties:
      Directory: C:\midi\inbox
      Conflict Resolution Strategy: replace

Connections:
  - name: HttpToDisk
    source name: ListenForNotes
    destination name: WriteToInbox
    source relationship name: success