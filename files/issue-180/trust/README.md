# trust/ — plugin client trust material (NOT in git)

Emptied 2026-09-15: the enforcement proof was deferred (see ../FACTS.md "BLOCKING FINDING"),
so the host private-key material pulled here was deleted for hygiene. Everything is gitignored.

To rebuild for a follow-on:
- keystore: reuse an AutoTLS host keystore from any CM-managed node —
  `/var/lib/cloudera-scm-agent/agent-cert/cm-auto-host_keystore.jks` + `cm-auto-host_key.pw`.
- truststore: `keytool -importcert -alias scm-local-ca -file ../scm-local-ca.pem -keystore truststore.jks -storepass changeit`.
- BUT note: on this Kerberized Base cluster the mTLS cert only secures the channel; policy download
  authenticates via Kerberos/SPNEGO. A keystore alone will NOT authenticate the plugin.
