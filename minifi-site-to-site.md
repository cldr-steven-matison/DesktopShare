# MiNiFi Site-to-Site: the full transport matrix

**Subplan — Complete Guide Ch11–15. Status: 🔲 not started (greenfield — nothing exists yet).**

Site-to-Site (S2S) is how flow files move between MiNiFi, NiFi, and Cloudera's cloud
products. Five paths, built local-first then cloud. CDP DataFlow + Data Hub access is
confirmed, so all five are field-validatable.

## Reference

- Apache `nifi-minifi-cpp` `SITE_TO_SITE.md`
- Apache `nifi-minifi-cpp` `extensions/python/PYTHON.md` (where a path carries Python logic)

## The five paths

| Ch | Path | Environment | Prereqs |
|----|------|-------------|---------|
| 11 | MiNiFi Java → NiFi K8s | local minikube | Java agent (Ch9), NiFi Remote Process Group + input port |
| 12 | MiNiFi C++ → NiFi K8s | local minikube | C++ agent (Ch8), same RPG/input port |
| 13 | NiFi K8s → Cloudera DataFlow | local → CDP cloud | CDF endpoint, S2S over HTTPS, cloud creds |
| 14 | NiFi K8s → Cloudera Data Hub | local → CDP cloud | Data Hub NiFi, remote input port, cloud creds |
| 15 | Cloudera DataFlow → Cloudera Data Hub | CDP → CDP | both provisioned, network path between them |

## Build order

Local first (11, 12) to nail the RPG/input-port mechanics and the transport protocol
(RAW vs HTTP) with no cloud variables. Then the cloud paths (13, 14) which add HTTPS, auth,
and network reachability. Finish with CDF→Data Hub (15).

## Per-path deliverable

Each path gets: the source-side config (MiNiFi `config.yml` RPG block or NiFi RPG),
the target-side input port, the transport protocol choice with rationale, and a
copy-paste verification (send a flow file, confirm arrival on the target).

## Traps to watch (carry forward from prior work)

- MiNiFi C++ strict YAML: every component needs an explicit UUID `id`; `Remote Processing Groups: []` must be present even when empty.
- Cloud paths: S2S over HTTPS needs the transport protocol set correctly and the remote URL reachable — expect the same "unexpected end of stream" class of failure if a target restarts mid-transfer.

## When this ships

Add a `site-to-site/` section to the MiNiFi Playground (one subdir per path), flip Ch11–15
in the master guide as each path is field-validated, and feed the resulting flows into the
Sample Gallery (Ch19).
