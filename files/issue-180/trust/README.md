# trust/ — plugin client trust material (NOT in git)

Emptied 2026-09-15: the enforcement proof was deferred (see ../FACTS.md "BLOCKING FINDING"),
so the host private-key material pulled here was deleted for hygiene. Everything is gitignored.

To rebuild for a follow-on:
- keystore: reuse an AutoTLS host keystore from any CM-managed node —
  `/var/lib/cloudera-scm-agent/agent-cert/cm-auto-host_keystore.jks` + `cm-auto-host_key.pw`.
- truststore: `keytool -importcert -alias scm-local-ca -file ../scm-local-ca.pem -keystore truststore.jks -storepass changeit`.
- The keystore cert's CN/SAN **is** the plugin's identity on the plain download endpoint the operator
  uses (`/service/plugins/policies/download/`): Ranger matches it against the service config
  `commonNameForCertificate` once `ranger.service.http.enabled=false`. The earlier note here ("a keystore
  alone will NOT authenticate") was about the `/secure/` (SPNEGO) endpoint, which the plugin never calls —
  see `../RUNBOOK-spark.md`. Also keep `plugin.crt` / `plugin.key` (PEM export) here for the Phase 1.5 curl gate.
