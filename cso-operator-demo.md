# cso-operator-demo — new prod cluster with Site-to-Site from day one (#116)

The production NiFi on WindowsDesktop (`mynifi-0`, `cfm-streaming`) has zero Site-to-Site configuration, and retrofitting it live means an operator-managed restart of the pod every prod flow depends on. So I'm not retrofitting it. I'm stopping the default minikube profile — which *is* the prod cluster on this host: `cfm-streaming`, `cld-streaming`, `mqtt`, and the `default`-namespace app stack all live inside it — and rebuilding everything in a fresh minikube profile named `cso-operator-demo`, with S2S enabled at NiFi creation using the recipe already proven in the Ch10/11 S2S lab. The old profile stays stopped, intact, as a cold rollback image. This doc is the working plan; issue #116 is the tracker.

## Decisions (locked 2026-08-12)

1. **Full parity.** Everything in the default profile moves: NiFi, Kafka/Strimzi, EFM, Mosquitto, cso-operator-app + vLLM/Whisper/qdrant/embedding-server, Flink/SSB, Prometheus/Grafana, Surveyor, cert-manager, ingress-nginx.
2. **The old profile is stopped, never deleted, for the life of this project.** `minikube stop` only. It is the rollback path. Deleting it to reclaim disk is a separate later decision.
3. **The cso-operator-app mTLS auth fix is in scope.** The new NiFi runs `userCertAuth`, which kills the app's `POST /nifi-api/access/token` username/password login. Cutover is not done until the app authenticates to the new NiFi.
4. **Port continuity is a hard requirement.** Kafka external NodePorts `31623/31850/31935/30336`, EFM `10090`, MQTT `1883` — identical on the new cluster. Same zellij panes (`~/.config/zellij/layouts/kube-service-ports-efm.kdl`), same Windows firewall rules. MicroFi-1/2/3, NvidiaNano, and StarlinkAI never learn the cluster changed.
5. **Names are preserved.** Namespaces, the `Nifi` CR name `mynifi`, secret names — everything keeps its name so committed exports, scripts, panes, and docs keep working. The only new name is the minikube profile.

Why this shape beats the issue's original in-place `kubectl delete nifi`: the old world survives untouched until the new world is verified, and the new cluster is built clean instead of inside a half-torn-down environment. The cost is that 32GB of host RAM means the two profiles cannot run at once — this is genuinely sequential, old world down before new world up, and the whole edge fleet is dark in between.

## What the profile swap adds beyond #116's strike list

- **EFM state does not ride along.** A fresh EFM has an empty registry — no classes, no published flows. Every agent-class flow (NvidiaNano, NvidiaNanoJava, StarlinkAI, KubernetesPod, the MicroFi class, and whatever else the live EFM enumerates) must be re-exported and verified current *before* the old EFM goes down, and re-published after. Agents re-associate by class name on heartbeat; each one gets verified ONLINE with a clean c2-ack.
- **GPU and sizing are create-time decisions.** vLLM runs on the RTX 4060, so the new profile needs GPU passthrough at `minikube start`, and CPU/memory sized to match the old profile. Painful to retrofit — capture the old profile's config first.
- **The backup surface is the whole profile**, not just NiFi: helm releases, every CR, PVCs, the NodePort map, and the app credentials injected via `kubectl set env` (never in the YAML).

## Phase 1 — Inventory & Backup (old cluster running; nothing stops until every box is checked)

- [ ] Dump the live flow and resolve the root-PG naming (`CSOOperatorAppWindows` in the issue vs `CSOOperatorApp` in the docs — the dump is authoritative):

```bash
kubectl exec mynifi-0 -n cfm-streaming -- gunzip -c /opt/nifi/nifi-current/conf/flow.json.gz \
  | jq '.rootGroup.processGroups[].name'
```

- [ ] Export all 7 root PGs fresh via the flow-download API — `TwitchChatBot`, `TopStreamerJoiner`, `WatchlistChatSnapshotPoller`, `WatchlistChatJoiner`, `StreamersApp` (+ children `FetchClips`/`ProcessClips`/`PublishClip`/`PublishClipPeakTimeCron`/`LiveStreamerAlert`/`TunaStarLinkFlows`), `SparkPlug`, and the resolved seventh — pretty-printed, committed to their proper homes (`cso-operator-app/streamers/`, `cso-operator-app/flows/`, or DesktopShare `files/`). This closes the stale-`StreamersApp.json` / missing-export gap the issue found. Mechanics: `nifi-and-ai` skill, `references/flow-api.md` §4.
- [ ] Get `nifi-custom-processors` under version control — `TwitchChatListenerProcessor`, `TwitchChatReplyProcessor`, `WatchlistChatJoinerProcessor.py`, `XLivePostProcessor` currently have no VCS safety net at all.
- [ ] Enumerate every Parameter Context and its parameter names; sensitive values never export, so this becomes the manual re-entry checklist (Twitch/Kick/X client IDs, secrets, refresh tokens).
- [ ] Re-export every EFM agent-class flow and diff against the committed `files/efm*` exports (EdgeFlowManager repo); enumerate the live class list from `GET /efm/api/designer/flows` rather than trusting this doc's list.
- [ ] Snapshot the cluster shape:

```bash
kubectl get nifi mynifi -n cfm-streaming -o yaml > backup/mynifi-cr-live.yaml
helm list -A > backup/helm-releases.txt
kubectl get crd,pvc,svc -A -o wide > backup/cluster-inventory.txt
kubectl get svc -A -o json | jq '..|.nodePort? //empty' > backup/nodeport-map.txt
cat ~/.minikube/profiles/minikube/config.json > backup/minikube-profile-config.json
```

- [ ] Record every secret by name/namespace (`nifi-admin-creds`, `mynifi-cfm-operator-user-cert`, the `kubectl set env`-injected cso-operator-app credentials) — names only, never values, per `agent/incident-rules.md`.
- [ ] Pull the CR baseline for the diff: `~/ClouderaStreamingOperators/nifi-cluster-30-nifi2x-windows.yaml`. The new CR is a diff against this, not hand-written. Same for `kafka-nodeport.yaml`, `efm-deployment-persisted.yaml` + `efm-pvc.yaml` + `efm-configMap.yaml`, and the app-stack yamls.
- [ ] Read the running cso-operator-app pod's actual `MODULES` env and per-processor flow state (the mandatory pre-deploy check) so the restore target is what's really live, not what the docs say.

## Phase 2 — Stop the world

- [ ] Fresh go-ahead from Steven — an earlier "ok" never covers this window.
- [ ] Stop all root PGs top-down (`StreamersApp`'s shared `Trigger`/`RouteOnAttribute` fans out to three children — stopping it pauses all three). Let in-flight FlowFiles drain; confirm every connection queue is empty.
- [ ] Re-dump `flow.json.gz` and confirm everything `STOPPED`, queues empty — this dump is the final pre-migration archive.
- [ ] `minikube stop`. The old world is now cold and intact. Expected while it's down: all agents (MicroFi-1/2/3, NvidiaNano C++/Java, StarlinkAI, the k8s pods) fail heartbeats and retry harmlessly; MicroFi MQTT/Kafka publishes drop on the floor for the duration. Schedule the window accordingly.

## Phase 3 — Stand up cso-operator-demo

- [ ] Create the profile with the old profile's captured sizing plus GPU:

```bash
# cpus/memory from backup/minikube-profile-config.json — match, don't guess
minikube start -p cso-operator-demo --driver=docker --gpus=all \
  --cpus=<matched> --memory=<matched> --addons=ingress
```

- [ ] Install in dependency order: cert-manager → CFM operator → Strimzi + CSA operators → Kafka CR **with the pinned external NodePorts** (`31623/31850/31935/30336` in the listener config — this is what makes decision 4 real) → EFM (persisted deployment + PVC + configMap) → Mosquitto → Prometheus/Grafana stack → Flink/SSB → Surveyor → app stack (`default` ns yamls, then `kubectl set env` the credentials back in).
- [ ] Create the new `Nifi` CR as a diff of `nifi-cluster-30-nifi2x-windows.yaml`: `userCertAuth`, `initialAdminIdentity` set correctly **at creation** (the mapped identity/SAN, not the subject DN — it's immutable once persistence is on; the lab burned a full delete+recreate on this), and S2S enabled from day one (`nifi.remote.input.host`/`.secure`/`.http.enabled` in `configOverride.nifiProperties.upsert`). Plus nar-loader/python-extensions-loader for the custom processors.
- [ ] Declare the operator-managed identities per the Ch10/11 recipe: a flow-author `User` CR (read/write on `/flow`, `/controller`, `/process-groups/root`), Steven's day-to-day UI login identity, and the `User`/`AccessPolicyProfile` CRs S2S peers will need. Hand-POSTed policies 409 under the operator — CRs only.
- [ ] Confirm the pod is healthy before importing anything, then bring up the same port-forward panes from `kube-service-ports-efm.kdl` (the kubectl context is now `cso-operator-demo` — verify each pane targets it) and confirm reachability from LAN + Tailscale. Same ports, so the existing Windows firewall rules already cover them — verify, don't assume, from a real external client.

## Phase 4 — Restore & Verify

- [ ] Import the root PGs from the Phase-1 exports via the multipart upload endpoint, `StreamersApp` first (most children).
- [ ] Recreate every Parameter Context and re-enter sensitive values from the Phase-1 checklist.
- [ ] Reinstall the custom processors from the now-version-controlled `nifi-custom-processors` source.
- [ ] Rebuild referenced controller services — `LiveStreamerAlert`'s `MapCacheServer`, the `StandardHttpContextMap` behind the `TwitchChatBot`/`PublishClip` Handle-HTTP pairs.
- [ ] Republish every agent-class flow to the new EFM from the Phase-1 exports; watch each agent re-associate by class and verify ONLINE + clean c2-ack: MicroFi-1/2/3, NvidiaNano (C++ and Java), StarlinkAI, the k8s pod agents.
- [ ] Wire cso-operator-app to the new NiFi with mTLS client-cert auth (bearer-token login is gone under `userCertAuth`) and prove the app can actually drive a flow — in scope, per decision 3.
- [ ] Verify each PG `VALID`, no bulletins, wiring matching the Phase-1 dump; first pass with the existing `DRY_RUN` flags (`TwitchChatBot` reply, `WatchlistChatJoiner`, `TopStreamerJoiner`) before anything goes live.
- [ ] Prove S2S itself — an input port with S2S HTTP input enabled and the same FlowFile-transit verification Ch10/11 used. This is the actual #116 deliverable, even with no real MiNiFi peer wired yet.
- [ ] Flip every PG back to its pre-migration run state; confirm the external Kafka/MQTT clients reconnect for real (MicroFi camera → Kafka bridge, MQTT teardown telemetry, NvidiaNano, StarlinkAI).
- [ ] Re-export every migrated PG fresh from the new cluster and commit; then the doc updates listed at the bottom.

## Rollback

At any point before Phase-4 sign-off:

```bash
minikube stop -p cso-operator-demo
minikube start   # the default profile, untouched since Phase 2
```

then flip the PGs back to their run states from the Phase-2 archive. Nothing in the old world was modified, so rollback is a restart, not a restore.

## What NOT to do

- **Don't GET-then-PUT any processor with sensitive properties** during verification — the masked `********` writes back as a literal and destroys the credential. Parameter Contexts or narrow-scope endpoints only.
- **Don't hand-build an agent-deployer command or reuse an `agentIdentifier`** if any agent needs re-enrolling — server-minted commands from EFM only.
- **Don't delete the old profile.** Stop is the ceiling for this project.
- **Don't let any port renumber.** A "close enough" NodePort means reflashing XIAO units and editing three devices' hosts files.
- **Don't start ad-hoc port-forwards.** The canonical set is the zellij layout; fix the pane, not around it.
- **Don't skip the fresh go-ahead** before Phase 2 — an earlier approval never covers a later stop.

## When this ships, update

- `minifi-site-to-site.md` + the master guide tracker — S2S flips from lab-only to adopted-on-production.
- `CLAUDE-CHECKIN.md` WindowsDesktop block — the cluster is `cso-operator-demo`, not the default profile.
- `reference_app_url.md` / app docs — if the app URL mechanics change under the new profile.
- This doc — fold in whatever the build actually taught us, per the plan-doc rule.
