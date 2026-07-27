## How To Install Cloudera Edge Flow Manager Agent Binaries

We need **MiNiFi Java** binaries, **MiNiFi C++ Windows** binaries (`.msi`), **MiNiFi C++ Linux x86_64** binaries, and now **MiNiFi C++ Linux ARM64 (aarch64)** binaries for Edge Flow Manager (EFM). As EFM is a multi-tenant agent manager; it evaluates the incoming agent heartbeats using a strict coordinate layout: `${agentType}/${osArch}/${agentVersion}`.  This markdown is a side quest I took while installing EFM in a kubernetes ecosystem.  I aimed to tackle agents working on mac minikube pod, windows minikube pod, windows desktop native .exe, windows WSL2 ubuntu, and last but not least ubuntu on nvidia jetson.

**Critical Lessons Applied:**

1. EFM's UI validator rejects hyphens in the `osArch` name. We must use `linux` for x86_64 and `linuxaarch64` for ARM64.
2. EFM's backend validator will throw a `400 BAD_REQUEST` if there is more than exactly *one* archive file in a `binaries` leaf directory. All extensions must be isolated into the `extensions` directory path.

---

### Step 1: Deep Breakdown of Your Local Files to EFM Mappings

| Local File Name | Agent Type | OS Arch | Expected EFM Path | Target Version | Final EFM File Name |
| --- | --- | --- | --- | --- | --- |
| `nifi-minifi-cpp-...-bin-linux.tar.gz` | `cpp` | `linux` | `binaries` | `1.26.02` | `minifi.tar.gz` |
| `nifi-minifi-cpp-...-bin-linux-arm64.tar.gz` | `cpp` | `linuxaarch64` | `binaries` | `1.26.02` | `minifi.tar.gz` |
| `nifi-minifi-cpp-...-extra-extensions-linux.tar.gz` | `cpp` | `linux` | `extensions` | `1.26.02` | `extra-extensions.tar.gz` |
| `nifi-minifi-cpp-...-extra-extensions-linux-arm64.tar.gz` | `cpp` | `linuxaarch64` | `extensions` | `1.26.02` | `extra-extensions.tar.gz` |
| `nifi-minifi-cpp-...-extra-python-components.zip` | `cpp` | `linux` | `extensions` | `1.26.02` | `extra-python-components.zip` |
| `nifi-minifi-cpp-...-x64.msi` | `cpp` | `windows` | `binaries` | `1.26.02` | `minifi.msi` |
| `minifi-2.24.08.0-19-bin.tar.gz` | `java` | `linux` | `binaries` | `2.24.08.0-19` | `minifi.tar.gz` |
| `minifi-2.24.08.0-19-bin.tar.gz` (same file) | `java` | `windows` | `binaries` | `2.24.08.0-19` | `minifi.tar.gz` |

---

### Step 2: Build the Full Local Staging Tree

```bash
# ==========================================
# 0. Clean the Staging Area
# ==========================================
rm -rf ~/efm-binaries/staging/
mkdir -p ~/efm-binaries/staging/binaries/cpp/linux/1.26.02
mkdir -p ~/efm-binaries/staging/binaries/cpp/linuxaarch64/1.26.02
mkdir -p ~/efm-binaries/staging/binaries/cpp/windows/1.26.02
mkdir -p ~/efm-binaries/staging/binaries/java/linux/2.24.08.0-19
mkdir -p ~/efm-binaries/staging/binaries/java/windows/2.24.08.0-19

# ==========================================
# 1. C++ LINUX (x86_64) - Unpack, Inject, Repack
# ==========================================
# Unpack base
tar -xf ~/efm-binaries/nifi-minifi-cpp-1.26.02-b30-bin-linux.tar.gz -C ~/efm-binaries/staging/binaries/cpp/linux/1.26.02/

# Unpack and inject .so extensions
mkdir -p /tmp/efm-ext-linux
tar -xf ~/efm-binaries/nifi-minifi-cpp-1.26.02-b30-extra-extensions-linux.tar.gz -C /tmp/efm-ext-linux
find /tmp/efm-ext-linux -name "*.so" -exec cp {} ~/efm-binaries/staging/binaries/cpp/linux/1.26.02/nifi-minifi-cpp-1.26.02/extensions/ \;

# Unpack and inject Python components
unzip -o ~/efm-binaries/nifi-minifi-cpp-1.26.02-b30-extra-python-components.zip -d ~/efm-binaries/staging/binaries/cpp/linux/1.26.02/nifi-minifi-cpp-1.26.02/

# Re-package and clean up
cd ~/efm-binaries/staging/binaries/cpp/linux/1.26.02/
tar -czf minifi.tar.gz nifi-minifi-cpp-1.26.02/
rm -rf nifi-minifi-cpp-1.26.02/ /tmp/efm-ext-linux

# ==========================================
# 2. C++ LINUX ARM64 (aarch64) - Unpack, Inject, Repack
# ==========================================
# Unpack base
tar -xf ~/efm-binaries/nifi-minifi-cpp-1.26.02-b30-bin-linux-arm64.tar.gz -C ~/efm-binaries/staging/binaries/cpp/linuxaarch64/1.26.02/

# Unpack and inject .so extensions
mkdir -p /tmp/efm-ext-arm64
tar -xf ~/efm-binaries/nifi-minifi-cpp-1.26.02-b30-extra-extensions-linux-arm64.tar.gz -C /tmp/efm-ext-arm64
find /tmp/efm-ext-arm64 -name "*.so" -exec cp {} ~/efm-binaries/staging/binaries/cpp/linuxaarch64/1.26.02/nifi-minifi-cpp-1.26.02/extensions/ \;

# Unpack and inject Python components
unzip -o ~/efm-binaries/nifi-minifi-cpp-1.26.02-b30-extra-python-components.zip -d ~/efm-binaries/staging/binaries/cpp/linuxaarch64/1.26.02/nifi-minifi-cpp-1.26.02/

# Re-package and clean up
cd ~/efm-binaries/staging/binaries/cpp/linuxaarch64/1.26.02/
tar -czf minifi.tar.gz nifi-minifi-cpp-1.26.02/
rm -rf nifi-minifi-cpp-1.26.02/ /tmp/efm-ext-arm64

# ==========================================
# 3. C++ WINDOWS (x64) - Direct Copy
# ==========================================
cp ~/efm-binaries/nifi-minifi-cpp-1.26.02-b30-x64.msi ~/efm-binaries/staging/binaries/cpp/windows/1.26.02/minifi.msi

# ==========================================
# 4. JAVA LINUX - Direct Copy
# ==========================================
cp ~/efm-binaries/minifi-2.24.08.0-19-bin.tar.gz ~/efm-binaries/staging/binaries/java/linux/2.24.08.0-19/minifi.tar.gz

# ==========================================
# 5. JAVA WINDOWS - Same platform-agnostic tarball
# ==========================================
# Field-verified 2026-07-25: without this leaf, osArch=windows deployer returns 400.
cp ~/efm-binaries/minifi-2.24.08.0-19-bin.tar.gz ~/efm-binaries/staging/binaries/java/windows/2.24.08.0-19/minifi.tar.gz
```

---

### Step 3: Stream via Tar Pipe

```bash
# ==========================================
# Phase A: Push Binaries to EFM Server
# ==========================================

# 1. Get the CURRENT running EFM pod
EFM_POD=$(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}')

# 2. Stream the completed binaries directory directly into the EFM pod
cd ~/efm-binaries/staging/
tar -cf - binaries/ | kubectl exec -i $EFM_POD -n cld-streaming -- tar -xf - -C /opt/efm/efm-2.3.1.0-2/agent-deployer/

# 3. Restart the deployment so EFM indexes the newly staged binaries
kubectl rollout restart deployment/efm -n cld-streaming

# 4. Wait for the new pod to report ready
kubectl wait --for=condition=ready pod -l app=efm -n cld-streaming --timeout=120s

# 5. Secure the NEW pod identifier for verification
EFM_POD=$(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}')

# 6. Verify the files arrived safely on the EFM server (Notice: No '-t' flag!)
kubectl exec -i $EFM_POD -n cld-streaming -- sh -c 'find /opt/efm/efm-2.3.1.0-2/agent-deployer/ -type f | grep -E "binaries" | sort'

```

---

### Step 4: The Ultimate Verification Routine

Don't guess if it worked—verify it. Run this command to trace every file sitting inside the EFM deployment structure:

```bash
kubectl exec -it $EFM_POD -n cld-streaming -- find /opt/efm/efm-2.3.1.0-2/agent-deployer/ -type f | grep -E "binaries|extensions" | sort

```

#### Your output must match this exact tree:

```text
/opt/efm/efm-2.3.1.0-2/agent-deployer/binaries/cpp/linux/1.26.02/minifi.tar.gz
/opt/efm/efm-2.3.1.0-2/agent-deployer/binaries/cpp/linuxaarch64/1.26.02/minifi.tar.gz
/opt/efm/efm-2.3.1.0-2/agent-deployer/binaries/cpp/windows/1.26.02/minifi.msi
/opt/efm/efm-2.3.1.0-2/agent-deployer/binaries/java/linux/2.24.08.0-19/minifi.tar.gz
/opt/efm/efm-2.3.1.0-2/agent-deployer/binaries/java/windows/2.24.08.0-19/minifi.tar.gz
```

> **2026-07-25:** Java on Windows + k8s is field-documented in `efm-windows-java-minifi.md` (processor catalog, C++-vs-Java class-manifest trap, k8s `sudo` deployer trap).

---

### Step 5: Force EFM to Re-index the World

Bounce the deployment tracking layout so that the Spring Boot context wakes up and registers the clean, validated configurations:

```bash
kubectl rollout restart deployment/efm -n cld-streaming
kubectl wait --for=condition=ready pod -l app=efm -n cld-streaming --timeout=120s

```

Go open or refresh your browser tab at `http://localhost:10090/efm/ui` (or your proxy interface address). The UI dropdown will now cleanly display **`v1.26.02 - linux`**, **`v1.26.02 - windows`**, and **`v2.24.08.0-19 - linux`**. Clicking them to generate the scripts will successfully pass both UI and Backend validation.

### Working Edge Flow Manager Deploy Agent CLI Command Samples

`java` MiNiFi Agent

```
curl -L \
 -d agentClass=test \
 -d agentIdentifier=e9faec53-6301-4ba1-a9e9-2403674ccdb2 \
 -d agentType=java \
 -d agentVersion=2.24.08.0-19 \
 -d autoConfigureSecurity=false \
 -d baseUrl=http%3A%2F%2F127.0.0.1%3A46663%2Fefm%2Fapi \
 -d hbPeriod=5000 \
 -d osArch=linux \
 -d serviceName=minifi \
 -d serviceUser=minifi \
 -d trustSelfSignedCertificates=false \
 http://127.0.0.1:46663/efm/api/agent-deployer/script | bash -
```

`cpp linux` MiNiFi Agent

```
curl -L \
 -d agentClass=test \
 -d agentIdentifier=54be1fee-9f21-4328-8b86-3b1c5a822b0b \
 -d agentType=cpp \
 -d agentVersion=1.26.02 \
 -d autoConfigureSecurity=false \
 -d baseUrl=http%3A%2F%2F127.0.0.1%3A46663%2Fefm%2Fapi \
 -d hbPeriod=5000 \
 -d osArch=linux \
 -d serviceName=minifi \
 -d serviceUser=minifi \
 -d trustSelfSignedCertificates=false \
 http://127.0.0.1:46663/efm/api/agent-deployer/script | bash -
```

`cpp linuxaarch64` MiNiFi Agent

```
curl -L \
 -d agentClass=NvidiaNano \
 -d agentIdentifier=$(cat /proc/sys/kernel/random/uuid) \
 -d agentType=cpp \
 -d agentVersion=1.26.02 \
 -d autoConfigureSecurity=false \
 -d baseUrl=http%3A%2F%2F127.0.0.1%3A46663%2Fefm%2Fapi \
 -d hbPeriod=5000 \
 -d osArch=linuxaarch64 \
 -d serviceName=minifi \
 -d serviceUser=minifi \
 -d trustSelfSignedCertificates=false \
 http://127.0.0.1:46663/efm/api/agent-deployer/script | bash -
```

`cpp windows` MiNiFi Agent

```bash
Set-ExecutionPolicy Bypass -Scope Process -Force;`
Invoke-WebRequest `
 -Uri http://127.0.0.1:46663/efm/api/agent-deployer/script `
 -Method Post `
 -Body ("agentClass=test" + `
       "&agentIdentifier=a66d299f-e7a3-42ea-84cf-3669009e4596" + `
       "&agentType=cpp" + `
       "&agentVersion=1.26.02" + `
       "&autoConfigureSecurity=false" + `
       "&baseUrl=http%3A%2F%2F127.0.0.1%3A46663%2Fefm%2Fapi" + `
       "&hbPeriod=5000" + `
       "&osArch=windows" + `
       "&serviceName=minifi" + `
       "&serviceUser=minifi" + `
       "&trustSelfSignedCertificates=false") `
 -UseBasicParsing `
 -ContentType "application/x-www-form-urlencoded" `
 | Invoke-Expression
```

---

## Windows Desktop Agent — Full Install with Python Support

> **Field-verified 2026-07-27 on MINI-Gaming-G1** under class **`WindowsDesktopCpp`** (parallel to Java `WindowsDesktop`). Full write-up: `efm-binaries-windows-python.md` + `efm-executescript.md` Path D.
>
> **Key insight:** The EFM deployer runs `msiexec` without selecting Feature Level 2 packages. Python (`CM_C_python_script_extension`) is Level 2. Prefer **administrative extract** (`msiexec /a`) when you lack elevation, or `ADDLOCAL=ALL` when you can elevate. Never install from `C:\WINDOWS\system32`.

### Preferred path A — no elevation (verified)

```powershell
New-Item C:\minifi -ItemType Directory -Force | Out-Null
Invoke-WebRequest "http://127.0.0.1:10090/efm/api/agent-deployer/binary?agentType=cpp&agentVersion=1.26.02&osArch=windows" `
  -OutFile C:\minifi\minifi.msi -UseBasicParsing

# Unpack ALL MSI payload (including python DLL) without registering a service
Start-Process msiexec -ArgumentList `
  "/a `"C:\minifi\minifi.msi`" TARGETDIR=`"C:\minifi\extract`" /quiet /L*v C:\minifi\msi_extract.log" -Wait

Copy-Item C:\minifi\extract\ApacheNiFiMiNiFi\nifi-minifi-cpp C:\minifi\nifi-minifi-cpp -Recurse -Force
# MSI CustomAction would mklink this; copy is fine:
Copy-Item C:\minifi\nifi-minifi-cpp\extensions\minifi-python-script-extension.dll `
          C:\minifi\nifi-minifi-cpp\extensions\minifi_native.pyd -Force

# Wire C2: nifi.c2.agent.class=WindowsDesktopCpp, fresh agentIdentifier, EFM base URLs
# Start process mode (not service):
Start-Process C:\minifi\nifi-minifi-cpp\bin\minifi.exe -WorkingDirectory C:\minifi\nifi-minifi-cpp\bin
```

Map the class after first heartbeat:

```bash
curl -X POST http://127.0.0.1:10090/efm/api/agent-class-manifest-config \
  -H 'Content-Type: application/json' \
  -d '{"agentClassName":"WindowsDesktopCpp","agentManifestId":"<id-from-GET-/agents/{id}>"}'
```

### Preferred path B — elevated service install with ADDLOCAL=ALL

When you have an elevated PowerShell (Administrators High integrity):

```powershell
cd C:\minifi   # NOT system32
# Download MSI as above, then:
Start-Process msiexec.exe -ArgumentList `
  "/i `"C:\minifi\minifi.msi`" ADDLOCAL=ALL AUTOSTART=0 INSTALL_ROOT=`"C:\minifi`" INSTALLPYTHONDIR=`"C:\Python314`" /quiet /L*v C:\minifi\msi_install.log" `
  -PassThru -Wait
# Configure C2 on the installed tree, then Start-Service "Apache NiFi MiNiFi"
```

### Why ADDLOCAL=ALL / extract is required

EFM deployer msiexec line (Level 1 only):
```
msiexec.exe /i minifi.msi AUTOSTART=0 INSTALL_ROOT=$PWD /quiet
```
`minifi_native.pyd` is **not** a separate archive file — it is created at install time as a link/copy of `minifi-python-script-extension.dll`.

### Smoke Test — Minimal Python Flow via EFM

Use class **`WindowsDesktopCpp`** (not the Java `WindowsDesktop` class):

1. **ListenHTTP** — port **18080**, path `contentListener`
2. **ExecuteScript** — Script Engine: `python`, Script Body with `onTrigger` / `REL_SUCCESS`
3. **LogAttribute** — Log Payload = true

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:18080/contentListener -Method Post `
  -Body '{"test":"hello from windows cpp"}' -ContentType "application/json"
```

Expect LogAttribute lines with your script's attributes and the JSON payload.

---

## Kafka + scripting NARs on the CEM Java agent — SOLVED 2026-07-27 (field-verified, MINI-Gaming-G1)

**The gap (historical):** the EFM-staged CEM Java tarball `minifi-2.24.08.0-19-bin.tar.gz` is field-verified (2026-07-25, `efm-windows-java-minifi.md`) to ship **114 processors with no `ExecuteScript` and no `PublishKafka`/`ConsumeKafka` NAR**. C++ has both (Kafka via `libminifi-rdkafka-extensions.so` in the stock set; scripting via extra-extensions / `ADDLOCAL=ALL`) — so this was a **Java-only** shortfall.

**The mistake that would have wasted a session:** `mynifi` (the full NiFi instance already running in `cfm-streaming`, CFM `2.6.0.4.3.4.0-234`) already has both NARs (`nifi-kafka-nar`, `nifi-scripting-nar`) unpacked under `work/nar/extensions/`. Copying them straight into the MiNiFi Java agent's `extensions/` autoload dir **will not work** — checked their `META-INF/MANIFEST.MF` first and both declare `Nar-Dependency-Version: 2.6.0.4.3.4.0-234`, pointing at sibling framework NARs of that exact version. The MiNiFi Java agent's own framework NARs are all versioned `2.24.08.0-19` (confirmed by unzipping an installed NAR's manifest) — a completely different Cloudera build/version line, with no `nifi-kafka-service-api-nar` present at all. NiFi's NAR loader matches dependencies by **exact** group+id+version string, no fallback — a straight copy fails to resolve.

**The real fix — build from the exact matching source.** `~/efm-binaries/nifi-minifi-java-2.0.0.2.24.08.0-19-source.tar.gz` was already sitting on this box — the full Apache NiFi monorepo source for the *exact* installed build, including complete `nifi-extension-bundles/nifi-kafka-bundle/` and `nifi-extension-bundles/nifi-scripting-bundle/` modules. Recipe (JDK 21 + the tarball's own `mvnw`, both already present/bootstrapped without any extra install):

```bash
tar -xzf ~/efm-binaries/nifi-minifi-java-2.0.0.2.24.08.0-19-source.tar.gz -C /some/scratch/dir
cd /some/scratch/dir/nifi-minifi-java-2.0.0.2.24.08.0-19

# Rewrite every module's version to match the already-installed agent framework —
# this is what makes the built NARs' Nar-Dependency-Version strings line up.
./mvnw -q -N org.codehaus.mojo:versions-maven-plugin:2.17.1:set \
  -DnewVersion=2.24.08.0-19 -DgenerateBackupPoms=false -DprocessAllModules=true

# Build just the 3 NARs actually needed (and their reactor deps, via -am):
./mvnw -pl nifi-extension-bundles/nifi-kafka-bundle/nifi-kafka-nar,nifi-extension-bundles/nifi-kafka-bundle/nifi-kafka-3-service-nar,nifi-extension-bundles/nifi-scripting-bundle/nifi-scripting-nar \
  -am -DskipTests -Dcheckstyle.skip=true -Drat.skip=true -Dlicense.skip=true -Dspotbugs.skip=true \
  clean install
```

~3 minutes total for both builds. Produces, all correctly versioned `2.24.08.0-19` with dependency chains matching what's already installed:
- `nifi-kafka-service-api-nar` (dependency of kafka-nar; not present in stock tarball at all)
- `nifi-kafka-nar` (`PublishKafka`/`ConsumeKafka` processors)
- `nifi-kafka-3-service-nar` (`Kafka3ConnectionService` — the controller service `PublishKafka` requires; **easy to miss**, it's a separate module from `nifi-kafka-nar`)
- `nifi-scripting-nar` (`ExecuteScript`, Groovy 4.0.23 + Clojure 1.8.0 engines — **no Jython/Python** in this build, unlike C++)

**Drop-in mechanism confirmed live, no restart needed:** `nifi.nar.library.autoload.directory=./extensions` (in `conf/minifi.properties`) is watched continuously by a running agent — `kubectl cp` (or copy on Windows) the 3 `.nar` files into `<MINIFI_AGENT_HOME>/extensions/` and the `NAR Auto-Loader` thread picks them up within ~5-10s, no process restart. Confirmed clean loads with `[0] skipped` in `minifi-app.log` for all three.

**Field-certified on `KubernetesPodJava` (2026-07-27):**
- Live manifest: 114 → **122 processors**, `ExecuteScript`/`ConsumeKafka`/`PublishKafka` all present.
- **ExecuteScript really executes**: a Groovy script inserted into the live smoke flow (`GenerateFlowFile → ExecuteScript → LogAttribute`) set a custom attribute that showed up on every flowfile reaching `LogAttribute` — not just class-loaded, actually ran.
- **PublishKafka is a real, working transactional producer**: wired to a `Kafka3ConnectionService` pointed at the in-cluster bootstrap (`my-cluster-kafka-bootstrap.cld-streaming.svc:9092` — no hairpin-NAT issue since this agent runs inside the cluster, unlike the Windows-native C++ test in `efm-validation-agent.md`). Log shows a real Kafka 3.9.0 client connecting, discovering the cluster ID, negotiating a transaction coordinator, and getting a producer ID assigned. The only remaining snag is `UNKNOWN_TOPIC_OR_PARTITION` because the test topic was never created — that's expected, not a NAR problem, and topic creation goes through Surveyor per `[[reference_kafka_ops]]`, not left as CLI cruft here.
- **Gotcha hit along the way — the class-manifest trap applies to newly-autoloaded processors too**: after the NARs loaded, the Designer still rejected `ExecuteScript`/`PublishKafka` as "not an available Processor type" until the agent class's manifest mapping was explicitly refreshed (`PUT /efm/api/agent-class-manifest-config` to the agent's *new* `agentManifestId`) — same trap `efm-windows-java-minifi.md` documented for C++-vs-Java flows, but it also fires on a same-runtime manifest change.

**Built artifacts persisted** (not committed to this repo — binaries live alongside the other staged agent binaries, not in DesktopShare's docs tree): `~/efm-binaries/java-nar-drop-in-2.24.08.0-19/` on MINI-Gaming-G1 holds all 4 built NARs, ready to copy anywhere without rebuilding:
```
nifi-kafka-service-api-nar-2.24.08.0-19.nar   (26 KB)
nifi-kafka-nar-2.24.08.0-19.nar               (752 KB)
nifi-kafka-3-service-nar-2.24.08.0-19.nar     (18.8 MB)
nifi-scripting-nar-2.24.08.0-19.nar           (21.2 MB)
```

**Also field-certified on the real `WindowsDesktop` Java agent (2026-07-27, same day)** — not just the throwaway K8s pod. Same 4 NARs, copied straight onto `C:\Users\tunas\minifi-java\minifi-2.24.08.0-19\extensions\` via the WSL2 `/mnt/c` mount (no `kubectl cp` needed, native filesystem access), autoloaded clean with `[0] skipped`, same as the K8s pod.

- Manifest count 114 → 122, same as K8s.
- `ExecuteScript` Groovy really executed on the live agent, same pattern as before — attribute `nar.groovy.smoke=windows-java-nar-drop-in-ok` showed up on every flowfile through the existing smoke flow.
- `PublishKafka` + `Kafka3ConnectionService` instantiated a real Kafka 3.9.0 transactional producer, attempted a real TCP connect to `192.168.1.121:31623`, and failed with a real `TimeoutException: Timeout expired after 5000ms while awaiting InitProducerId` — the same hairpin-NAT limitation hit in the C++ test (`efm-validation-agent.md` Task 3), not a processor-availability problem. Confirms the NAR is functionally real on native Windows too.
- **Side gotcha hit and cleared:** the live `WindowsDesktop` designer canvas had two pre-existing orphaned processors (`ExecuteStreamCommand`, `ExecuteProcess` — disconnected, never configured, unrelated to this work) that blocked `/publish` with a 409 until deleted. EFM's Designer has no disable/inert state for a processor — a canvas won't publish until every processor on it, connected or not, passes validation.
- Agent's C2 heartbeat briefly looked stalled (`lastSeen` ~25h old) before this work started; turned out to be a stale single read, not a real problem — the very next NAR-triggered manifest change ticked `lastSeen` forward within ~13s. Worth knowing this can look alarming without actually being one.

- Cloudera CEM 2.4.0 MiNiFi Java processor support: `docs.cloudera.com/cem/2.4.0/release-notes-minifi-java/topics/cem-java-agent-processors.html`

> Field validation of the C++ side (live Windows manifest, live Kafka smoke) is tracked in `efm-validation-agent.md`.

---

## Appendix


### Expose EFM 

Port Forward to expose EFM to world, then use minikube `hostip:10090` in agent curls.

```bash
kubectl port-forward --address 0.0.0.0 service/efm 10090:10090 -n cld-streaming
```

### Minikube Service for Windows

```bash
tunas@MINI-Gaming-G1:~$ minikube service efm -n cld-streaming
┌───────────────┬──────┬──────────────┬───────────────────────────┐
│   NAMESPACE   │ NAME │ TARGET PORT  │            URL            │
├───────────────┼──────┼──────────────┼───────────────────────────┤
│ cld-streaming │ efm  │ efm-ui/10090 │ http://192.168.49.2:30517 │
│               │      │ metrics/9092 │ http://192.168.49.2:30608 │
└───────────────┴──────┴──────────────┴───────────────────────────┘
🔗  Starting tunnel for service efm.
┌───────────────┬──────┬─────────────┬────────────────────────┐
│   NAMESPACE   │ NAME │ TARGET PORT │          URL           │
├───────────────┼──────┼─────────────┼────────────────────────┤
│ cld-streaming │ efm  │             │ http://127.0.0.1:43431 │
│               │      │             │ http://127.0.0.1:41909 │
└───────────────┴──────┴─────────────┴────────────────────────┘
[cld-streaming efm  http://127.0.0.1:43431
http://127.0.0.1:41909]
❗  Because you are using a Docker driver on linux, the terminal needs to be open to run it.
```

**Notice** With `minikube service` control click the :43431 url (2nd to last), then append `/efm/ui/` to get to the EFM UI.

### PowerShell History

```bash
PS C:\Users\tunas> history

  Id CommandLine
  -- -----------
   1 # 1. Allow the port through Windows Firewall
   2 New-NetFirewallRule -DisplayName "EFM-Bridge-46663" -Di...
   3 # 2. Map the traffic from your Windows LAN IP to your W...
   4 # Replace '172.26.201.5' with your WSL Ubuntu IP (that'...
   5 netsh interface portproxy add v4tov4 listenport=46663 l...
   6 ipconfig
   7 cd ..\..\Users\tunas
   8 nano .\.wslconfig
   9 edit .\.wslconfig
  10 wsl --shutdown
  11 New-NetFirewallRule -DisplayName "Allow ICMPv4-In" -Pro...
  12 New-NetFirewallRule -DisplayName "Allow EFM Port 10090"...
```

### Check Pod for Python Extensions


```bash
# ==========================================
# Phase B: Deploy & Verify the MiNiFi Agent
# ==========================================

# 7. Delete the old agent pod so it forgets the previous installation
kubectl delete pod minifi-agent-k8s -n cld-streaming

# 8. Spin up a fresh agent pod
kubectl apply -f minifi-agent-pod.yaml

# 9. Tail the logs to watch the fresh download and installation succeed
kubectl logs minifi-agent-k8s -n cld-streaming -f

# 10. Once running, verify all extensions (including Python) exist on the agent
kubectl exec minifi-agent-k8s -n cld-streaming -- ls -al nifi-minifi-cpp-1.26.02/extensions
```

```bash
kubectl exec minifi-agent-k8s -n cld-streaming -- ls -al nifi-minifi-cpp-1.26.02/extensions
total 86368
drwxr-xr-x  2 501 staff     4096 Jun  9 12:41 .
drwxr-xr-x 10 501 staff     4096 Jun  9 12:41 ..
-rwxr-xr-x  1 501 staff  1637704 Mar  2 23:08 libminifi-archive-extensions.so
-rwxr-xr-x  1 501 staff 10235592 Mar  2 23:08 libminifi-aws.so
-rwxr-xr-x  1 501 staff  5144176 Mar  2 23:08 libminifi-azure.so
-rwxr-xr-x  1 501 staff   468304 Mar  2 23:08 libminifi-civet-extensions.so
-rwxr-xr-x  1 501 staff 15514168 Mar  2 23:08 libminifi-couchbase.so
-rwxr-xr-x  1 501 staff   265584 Mar  2 23:08 libminifi-elasticsearch.so
-rwxr-xr-x  1 501 staff   142656 Jun  9 12:34 libminifi-execute-process.so
-rwxr-xr-x  1 501 staff  5534672 Mar  2 23:08 libminifi-gcp.so
-rwxr-xr-x  1 501 staff 14477400 Mar  2 23:08 libminifi-grafana-loki.so
-rwxr-xr-x  1 501 staff  1130832 Mar  2 23:08 libminifi-kubernetes-extensions.so
-rwxr-xr-x  1 501 staff  3943480 Jun  9 12:34 libminifi-llamacpp.so
-rwxr-xr-x  1 501 staff  1002288 Jun  9 12:34 libminifi-lua-script-extension.so
-rwxr-xr-x  1 501 staff   588224 Mar  2 23:08 libminifi-mqtt-extensions.so
-rwxr-xr-x  1 501 staff  2826680 Jun  9 12:34 libminifi-opc-extensions.so
-rwxr-xr-x  1 501 staff   225000 Mar  2 23:08 libminifi-procfs.so
-rwxr-xr-x  1 501 staff   682736 Mar  2 23:08 libminifi-prometheus.so
-rwxr-xr-x  1 501 staff    27056 Jun  9 12:34 libminifi-python-lib-loader-extension.so
-rwxr-xr-x  1 501 staff   727816 Jun  9 12:34 libminifi-python-script-extension.so
-rwxr-xr-x  1 501 staff  4097624 Mar  2 23:08 libminifi-rdkafka-extensions.so
-rwxr-xr-x  1 501 staff 12408408 Mar  2 23:08 libminifi-rocksdb-repos.so
-rwxr-xr-x  1 501 staff    84680 Jun  9 12:34 libminifi-script-extension.so
-rwxr-xr-x  1 501 staff   241088 Mar  2 23:08 libminifi-splunk.so
-rwxr-xr-x  1 501 staff  1152352 Mar  2 23:08 libminifi-sql.so
-rwxr-xr-x  1 501 staff  4859776 Mar  2 23:08 libminifi-standard-processors.so
-rwxr-xr-x  1 501 staff   245488 Mar  2 23:08 libminifi-systemd.so
-rwxr-xr-x  1 501 staff   727816 Jun  9 12:34 minifi_native.so
```

### EFM Startup

```bash
The following environment configuration was determined:                                                                  │
│                                                                                                                          │
│ APP_NAME=efm                                                                                                             │
│ APP_HOME=/opt/efm/efm-2.3.1.0-2                                                                                          │
│ APP_BIN_DIR=/opt/efm/efm-2.3.1.0-2/bin                                                                                   │
│ APP_CONF_DIR=/opt/efm/efm-2.3.1.0-2/conf                                                                                 │
│ APP_LIB_DIR=/opt/efm/efm-2.3.1.0-2/lib                                                                                   │
│ APP_LOG_DIR=                                                                                                             │
│ APP_RUN_DIR=/opt/efm/efm-2.3.1.0-2/run                                                                                   │
│ APP_BIN_FILE=/opt/efm/efm-current/bin/efm.sh                                                                             │
│ APP_CONF_FILE=/opt/efm/efm-2.3.1.0-2/conf/efm.conf                                                                       │
│ APP_PROPS_FILE=/opt/efm/efm-2.3.1.0-2/conf/efm.properties                                                                │
│ APP_JAR_FILE=/opt/efm/efm-2.3.1.0-2/lib/efm.jar                                                                          │
│ APP_CLASSPATH=/opt/efm/efm-2.3.1.0-2/conf:/opt/efm/efm-2.3.1.0-2/lib                                                     │
│ JAVA_OPTS=-Xms2048m -Xmx2048m -XX:+UseG1GC                                                                               │
│ RUN_ARGS=                                                                                                                │
│ STOP_WAIT_TIME=20                                                                                                        │
│ USE_START_STOP_DAEMON=true                              


│   ______    ______   __    __ 
│  /\  ___\  /\  ___\ /\ '-./  \
│  \ \  __\  \ \  __\ \ \ \-./\ \ 
│   \ \_____\ \ \_\    \ \_\ \ \_\   
│    \/_____/  \/_/     \/_/  \/_/ 
│
│  (v2.3.1.0-2)
│ >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
│ Cloudera | CEM | Edge Flow Manager



 _______ __ _______ __ _______ __      __             __         __ __
|   |   |__|    |  |__|    ___|__|    |__.-----.-----|  |_.---.-|  |  .-----.----.
|       |  |       |  |    ___|  |    |  |     |__ --|   _|  _  |  |  |  -__|   _|
|__|_|__|__|__|____|__|___|   |__|    |__|__|__|_____|____|___._|__|__|_____|__|




```