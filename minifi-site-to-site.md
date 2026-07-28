# MiNiFi Site-to-Site: the full transport matrix

**Subplan of the Complete Guide to Edge Flow Management. Status: 🔲 not started (greenfield — nothing exists yet).**

Site-to-Site (S2S) is how flow files move between MiNiFi, NiFi, and Cloudera's cloud
products. Five paths, built local-first then cloud. CDP DataFlow + Data Hub access is
confirmed, so all five are field-validatable.

## Reference

- Apache `nifi-minifi-cpp` `SITE_TO_SITE.md`
- Apache `nifi-minifi-cpp` `extensions/python/PYTHON.md` (where a path carries Python logic)

## The five paths

| # | Path | Environment | Prereqs |
|----|------|-------------|---------|
| 1 | MiNiFi Java → NiFi K8s | local minikube | Java MiNiFi agent, NiFi Remote Process Group + input port |
| 2 | MiNiFi C++ → NiFi K8s | local minikube | C++ MiNiFi agent, same RPG/input port |
| 3 | NiFi K8s → Cloudera DataFlow | local → CDP cloud | CDF endpoint, S2S over HTTPS, cloud creds |
| 4 | NiFi K8s → Cloudera Data Hub | local → CDP cloud | Data Hub NiFi, remote input port, cloud creds |
| 5 | Cloudera DataFlow → Cloudera Data Hub | CDP → CDP | both provisioned, network path between them |

## Build order

Local first (paths 1, 2) to nail the RPG/input-port mechanics and the transport protocol
(RAW vs HTTP) with no cloud variables. Then the cloud paths (3, 4) which add HTTPS, auth,
and network reachability. Finish with CDF→Data Hub (path 5).

## Per-path deliverable

Each path gets: the source-side config (MiNiFi `config.yml` RPG block or NiFi RPG),
the target-side input port, the transport protocol choice with rationale, and a
copy-paste verification (send a flow file, confirm arrival on the target).

## Traps to watch (carry forward from prior work)

- MiNiFi C++ strict YAML: every component needs an explicit UUID `id`; `Remote Processing Groups: []` must be present even when empty.
- Cloud paths: S2S over HTTPS needs the transport protocol set correctly and the remote URL reachable — expect the same "unexpected end of stream" class of failure if a target restarts mid-transfer.

## When this ships

Add a `site-to-site/` section to the MiNiFi Playground (one subdir per path), flip the
Site-to-Site rows in the master guide as each path is field-validated, and feed the resulting
flows into the Sample Gallery.
