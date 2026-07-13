**SIDE QUEST: MiNiFi In-Memory Tuning (Zero-Disk, Ultra-Low-Latency MIDI Pipeline)**

**Master Plan Context**  
This side quest directly supports **PHASE 6** of the MIDIFI plan (the Windows-hosted MiNiFi C++ agent that consumes from Kafka and drops notes into `C:\midi\inbox`).  

The current bottleneck: even though the end-to-end flow is simple (`ConsumeKafka` → `PutFile`), the default **persistent repositories** (RocksDB + file-system content repo) introduce disk I/O and queuing latency. This creates the “clumping” you hear versus the direct `yyd.py` script.  

**Goal of this side quest**  
Switch the agent to a **pure in-memory (volatile) configuration** so MIDI notes fly through the internal pipeline with zero disk touches until the final `PutFile` write to the inbox folder. This should make MiNiFi feel as tight (or tighter) than the Python watchdog script while keeping the full NiFi/Kafka architecture intact.

### 1. Repository Swap (In-Memory Only)

Edit `C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\conf\minifi.properties`

**Change these three lines** (they are the core of the performance win):

```properties
# In-Memory Repositories (Zero Disk I/O)
nifi.flowfile.repository.class.name=VolatileFlowFileRepository
nifi.content.repository.class.name=VolatileContentRepository
nifi.provenance.repository.class.name=NoOpRepository
```

**Why these exact classes?**  
- `VolatileFlowFileRepository` → flow-file metadata lives only in RAM (official alias for NoOp-style behavior in C++).  
- `VolatileContentRepository` → actual MIDI note payloads stay in RAM.  
- `NoOpRepository` for provenance → we don’t need provenance events for a live MIDI stream (saves CPU and memory).

### 2. Eliminate Directory Bloat (Prevent Startup Conflicts)

**Comment out** all the disk directory properties so MiNiFi never tries to initialize or lock persistent folders:

```properties
# COMMENT THESE OUT — Volatile repos do not use disk
# nifi.flowfile.repository.directory.default=${MINIFI_HOME}/flowfile_repository
# nifi.database.content.repository.directory.default=${MINIFI_HOME}/content_repository
# nifi.provenance.repository.directory.default=${MINIFI_HOME}/provenance_repository
```

### 3. Threading & Yield Tuning (Make the Agent Hyper-Responsive)

Add or update these lines in the same `minifi.properties` file:

```properties
# Core Engine Tuning
nifi.flow.engine.threads=4
nifi.administrative.yield.duration=1 sec
nifi.bored.yield.duration=10 millis
```

- `nifi.flow.engine.threads=4` → enough threads for `ListenHTTP`/`ConsumeKafka` + `PutFile` without contention.  
- `nifi.administrative.yield.duration=1 sec` → the agent wakes up much faster when your Python scripts start/stop.  
- `nifi.bored.yield.duration=10 millis` → already excellent; keeps the polling loop extremely tight.

### 4. Safety-First Rollout Plan (One Change at a Time)

Do **not** apply everything at once. Follow this exact order and test after each step:

1. **Backup** your current `minifi.properties` (and `config.yml`).
2. Apply **only the three repository class names** + comment out the directories.
3. Restart the MiNiFi service and verify it starts cleanly (check logs for any repository init errors).
4. Run your test MIDI stream (send a few notes via the K8s NiFi flow) and listen for clumping.
5. Add the threading/yield settings.
6. Restart and re-test.

**Expected outcome**  
Notes should now arrive with the same crisp, non-clumped timing as your direct Python script, but still routed through the full Kafka/NiFi architecture.

### Risk Assessment (Same as Master Plan Philosophy)

| Risk | Impact | Mitigation / Acceptance |
|------|--------|-------------------------|
| MiNiFi crash or restart | In-flight notes are lost | Acceptable — live Strudel stream; old notes dumping is worse |
| Memory pressure | Very low (MIDI notes are tiny) | Monitor RAM; volatile repos only hold transient data |
| Provenance UI | Disabled | Not used in this setup anyway |
| Directory lock errors on startup | Prevented by commenting out paths | — |

### Verification Checklist (After Each Restart)

- MiNiFi service starts without errors.  
- `ConsumeKafka` → `PutFile` flow processes notes.  
- Watchdog still receives files in `C:\midi\inbox`.  
- Audible latency matches (or beats) the `yyd.py` baseline.  
- No unexpected disk activity in the old repository folders.