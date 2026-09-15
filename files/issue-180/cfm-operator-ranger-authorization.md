<!-- Source: cfm-operator/docs/ranger-authorization.md (Cloudera-internal github.infra.cloudera.com/CDF/cfm-operator, master) — fetched 2026-09-15 for #180. Committed to this private repo as the authoritative operator reference. -->

# Apache Ranger Authorization for NiFi

## Overview

By default, NiFi manages access policies in a local `authorizations.xml` file via
`FileAccessPolicyProvider` backed by `StandardManagedAuthorizer`. The cfm-operator drives
that model through its `User` and `UserGroup` controllers, which call the NiFi REST API to
keep policy assignments in sync with the desired state declared in Kubernetes.

For organizations running Cloudera Data Platform (CDP) or any deployment where Apache Ranger
is the central policy engine, that file-based model is redundant and conflicts with Ranger.
Policies set in NiFi's own file would silently diverge from what Ranger intends; access
decisions would be made by NiFi rather than by Ranger, defeating the purpose of a central
policy store.

When the `ranger` field is set on a `Nifi` resource's `spec.security`, the operator switches
to a fully Ranger-delegated authorization mode:

- `authorizers.xml` is rendered with `RangerNiFiAuthorizer` instead of
  `FileAccessPolicyProvider` + `StandardManagedAuthorizer`.
- `nifi.properties` sets `nifi.security.user.authorizer=ranger-nifi-authorizer`.
- Three XML configuration files consumed by the Ranger NiFi plugin —
  `ranger-nifi-security.xml`, `ranger-nifi-audit.xml`, and `ranger-policymgr-ssl.xml` — are
  generated from the structured fields below and mounted into the NiFi pods at
  `/opt/nifi/nifi-current/conf/`. `ranger-policymgr-ssl.xml` is always generated: it contains
  TLS keystore and truststore properties when `tls.secretName` is set, and is empty otherwise.
  When TLS is configured, `ranger-nifi-security.xml` also sets
  `ranger.plugin.nifi.policy.rest.ssl.config.file` to point at that file.
- The `User` and `UserGroup` controllers still create NiFi tenants (users and groups) so that
  Ranger-issued identities are recognized by NiFi, but they skip access policy management
  entirely. Policy enforcement is now Ranger's responsibility.

> The Apache Ranger NiFi plugin documentation is the authoritative reference for the
> underlying XML property names used here:
> https://ranger.apache.org/quick_start_guide.html and the NiFi Ranger plugin source at
> https://github.com/apache/ranger/tree/master/plugin-nifi.

---

## API versions

The `ranger` field is available in both the `cfm.cloudera.com/v1alpha1` and `cfm.cloudera.com/v1` API versions. The field structure is identical in both; examples in this document use `v1alpha1`.

---

## Interaction with other security fields

`spec.security.ranger` is an **authorizer** configuration and is orthogonal to
**authentication** configuration. It can be combined with any authentication method
(`kerberos`, LDAP, OIDC, SAML, certificate-based, single user). The authorizer determines
*what an authenticated user may do*; the authenticator determines *who the user is*.

`spec.security.customAuthorizer` must not be set when `ranger` is set. They are mutually
exclusive authorizer configurations.

---

## Spec

```
spec:
  security:
    ranger:
      serviceName: <string>           # required
      adminURL: <string>              # required
      adminIdentity: <string>         # required
      policyPollIntervalMs: <int>     # optional, default 30000
      audit:                          # optional
        solr:
          url: <string>               # optional
          zookeepersURL: <string>     # optional
          async: <bool>               # optional, default true
          maxQueueSize: <int>         # optional, default 10240
          maxFlushIntervalMs: <int>   # optional, default 30000
      tls:                            # optional
        secretName: <string>
      configSecretName: <string>      # optional escape hatch
```

---

## Field Reference

### `serviceName` (string, **required**)

The name of the NiFi service as registered in Ranger Admin's service repository. Ranger uses
this name to look up the applicable policies when a request arrives. It must exactly match the
service name shown on the Ranger Admin "Service Manager" page under the NiFi service type.

Stored in `ranger-nifi-security.xml` as `ranger.plugin.nifi.service.name`.

**Example:** `nifi-production`

---

### `adminURL` (string, **required**)

The base REST API URL of the Ranger Admin server. The Ranger NiFi plugin contacts this
endpoint to download the policy set on startup and on each poll cycle. The URL must be
reachable from inside the NiFi pods; include the port and scheme.

Stored in `ranger-nifi-security.xml` as `ranger.plugin.nifi.policy.rest.url`.

The plugin always uses the `RangerAdminRESTClient` implementation
(`ranger.plugin.nifi.policy.source.impl`); that value is hardcoded by the operator and does
not need to be set by the user.

**Example:** `https://ranger-admin.example.com:6182`

---

### `adminIdentity` (string, **required**)

The TLS distinguished name (DN) of the Ranger Admin server's certificate. NiFi's security
model identifies all principals — including services — by their certificate DN. NiFi must
recognize the Ranger Admin identity in order to trust policy download responses signed by that
server.

This value is written into `authorizers.xml` as the `Ranger Admin Identity` property on the
`RangerNiFiAuthorizer` block.

See the NiFi Administration Guide section on authorizers:
https://nifi.apache.org/docs/nifi-docs/html/administration-guide.html#authorizers-setup

**Example:** `CN=ranger-admin.example.com, OU=Security, O=Acme, L=San Jose, ST=CA, C=US`

---

### `policyPollIntervalMs` (integer, optional, default `30000`)

How frequently (in milliseconds) the Ranger NiFi plugin polls Ranger Admin for policy
updates. Lower values reduce the lag between a policy change in Ranger and its effect in NiFi
at the cost of more frequent HTTP calls to Ranger Admin. The default of 30 000 ms (30 seconds)
is the Ranger plugin default and is appropriate for most deployments.

A local policy cache is written to `/tmp/ranger-nifi-security-cache` and is used as a
fallback if Ranger Admin is temporarily unreachable.

Stored in `ranger-nifi-security.xml` as `ranger.plugin.nifi.policy.pollIntervalMs`.

**Example:** `15000` (poll every 15 seconds)

---

### `audit` (object, optional)

Configures where the Ranger NiFi plugin writes access audit events. Audit records capture
every authorization decision — allowed or denied — including the user identity, resource path,
and action. When this section is omitted, Solr auditing is disabled (`xasecure.audit.solr.enable=false`).

Currently the only supported destination is Apache Solr.

---

#### `audit.solr` (object, optional)

Configures Apache Solr as the audit event destination.

Ranger's audit framework uses the `xasecure.audit.*` property namespace, inherited from the
original XASecure project that became Ranger. Full Solr audit configuration reference:
https://ranger.apache.org/quick_start_guide.html

---

##### `audit.solr.url` (string, optional)

A direct HTTP/HTTPS URL pointing to the Solr collection that receives audit events. This is
the simplest connectivity option when Solr is accessible at a known stable address.

Stored in `ranger-nifi-audit.xml` as `xasecure.audit.solr.url`.

Mutually exclusive with `zookeepersURL`: set one or the other, not both.

**Example:** `http://solr.example.com:6083/solr/ranger_audits`

---

##### `audit.solr.zookeepersURL` (string, optional)

A ZooKeeper connection string used for Solr service discovery. When the Solr cluster uses
SolrCloud mode with ZooKeeper-based routing, this is the preferred option because it
accommodates Solr node additions and removals without reconfiguring NiFi.

Stored in `ranger-nifi-audit.xml` as `xasecure.audit.solr.zookeepers`.

**Example:** `zk1.example.com:2181,zk2.example.com:2181/solr`

---

##### `audit.solr.async` (bool, optional, default `true`)

When `true`, audit events are written to an in-memory queue and flushed to Solr in batches.
Asynchronous mode prevents a slow or temporarily unavailable Solr from adding latency to NiFi
request processing. When `false`, each audit write blocks until Solr acknowledges receipt,
providing stronger durability guarantees at the cost of throughput.

Stored in `ranger-nifi-audit.xml` as `xasecure.audit.solr.async`.

---

##### `audit.solr.maxQueueSize` (integer, optional, default `10240`)

The maximum number of audit events held in the asynchronous buffer before the oldest events
are dropped to make room for new ones. Applies only when `async` is `true`. Increase this
value if audit events are being dropped during bursty authorization activity (e.g., large
batch jobs that touch many NiFi resources rapidly).

Stored in `ranger-nifi-audit.xml` as `xasecure.audit.solr.async.max.queue.size`.

---

##### `audit.solr.maxFlushIntervalMs` (integer, optional, default `30000`)

The maximum time in milliseconds between forced flushes of the asynchronous audit queue to
Solr. Even if the queue has not reached `maxQueueSize`, a flush is triggered once this
interval elapses. Lower values reduce audit event lag at the cost of more frequent Solr
writes. Applies only when `async` is `true`.

Stored in `ranger-nifi-audit.xml` as `xasecure.audit.solr.async.max.flush.interval.ms`.

---

### `tls` (object, optional)

Configures mutual TLS (mTLS) between the Ranger NiFi plugin running inside NiFi pods and the
Ranger Admin server. When the Ranger Admin endpoint is TLS-protected — which is strongly
recommended in production — both a keystore (client certificate for NiFi to authenticate to
Ranger Admin) and a truststore (CA certificate to verify Ranger Admin's server certificate)
are typically required.

If this section is omitted entirely, the plugin will use Java's default truststore and will
not present a client certificate. This is acceptable when Ranger Admin is configured to not
require mutual TLS and uses a publicly trusted certificate, but is **not recommended** for
production environments.

The underlying XML property namespace is `xasecure.policymgr.clientssl.*`.

---

#### `tls.secretName` (string, optional)

The name of a Kubernetes `Secret` in the same namespace that contains the keystore and truststore NiFi uses
for mTLS with Ranger Admin. The operator mounts the same Secret at two separate paths and expects the
following keys:

| Secret key            | Mount path                          | Description                               |
|-----------------------|-------------------------------------|-------------------------------------------|
| `keystore.jks`        | `/home/nifi/ranger-tls-keystore/`   | The JKS-format keystore file (binary)     |
| `keystore.password`   | `/home/nifi/ranger-tls-keystore/`   | The plaintext password for the keystore   |
| `truststore.jks`      | `/home/nifi/ranger-tls-truststore/` | The JKS-format truststore file (binary)   |
| `truststore.password` | `/home/nifi/ranger-tls-truststore/` | The plaintext password for the truststore |

Passwords are injected at runtime via JCEKS credential files (`ranger-keystore.jceks` and
`ranger-truststore.jceks`) created by `start.sh` from the password files above. They do not
appear in cleartext in the generated XML.

The truststore limits CA trust to the Ranger Admin connection only — the Ranger CA is not
added to the JVM-wide truststore and cannot be inadvertently trusted by LDAP, OIDC, or other
NiFi TLS connections. As an alternative, `spec.security.additionalCABundlesRef` adds the CA
JVM-wide; use the explicit truststore in production to minimize the trust surface.

---

### `configSecretName` (string, optional)

An escape hatch for advanced Ranger configurations not expressible through the structured
fields above. When set, the operator **skips all XML generation** and instead mounts only the
keys present in this Kubernetes `Secret` directly into `/opt/nifi/nifi-current/conf/`. The
`tls` block is ignored entirely and no TLS Secret volumes are mounted.

The Secret must be in the same namespace as the `Nifi` resource. The operator validates it at
reconcile time and returns an error (surfaced as a Kubernetes Event on the `Nifi` resource) if
either required key is absent. The three supported keys are:

| Secret key                  | Mount path                                                     | Required |
|-----------------------------|----------------------------------------------------------------|----------|
| `ranger-nifi-security.xml`  | `/opt/nifi/nifi-current/conf/ranger-nifi-security.xml`         | yes      |
| `ranger-nifi-audit.xml`     | `/opt/nifi/nifi-current/conf/ranger-nifi-audit.xml`            | yes      |
| `ranger-policymgr-ssl.xml`  | `/opt/nifi/nifi-current/conf/ranger-policymgr-ssl.xml`         | no       |

`ranger-policymgr-ssl.xml` is only needed when Ranger TLS is configured; if absent from the
Secret it is neither mounted nor generated.

Use cases include:
- Properties not yet modeled in the operator schema (e.g., Kafka or HDFS audit destinations).
- Ranger plugin versions with non-standard property names.
- Environments requiring credential provider integration (`jceks://` URIs for passwords).
- mTLS with Ranger Admin using custom keystore/truststore paths or formats.

When `configSecretName` is set, all structured fields under `audit` and `tls` are still
validated by the API server but their values are **not used** — the Secret contents take
complete precedence.

---

## Behavior under Ranger mode

### User and UserGroup controllers

When `ranger` is configured, `User` and `UserGroup` resources still create and update NiFi
tenant identities (users and groups) via the NiFi REST API. This is necessary so that NiFi
can resolve identity strings returned from Ranger policy checks to internal user objects.

However, the controllers **skip all access policy operations** — they do not call
`CreateAccessPolicy`, `UpdateAccessPolicy`, or add users to policy resource entries. The
`accessPolicies` and `accessPolicyProfileRef` fields on `User` and `UserGroup` resources are
accepted by the API server but have no effect when Ranger is enabled. Policy management is
Ranger's responsibility.

### Authorizer selection

The `nifi.security.user.authorizer` property in `nifi.properties` is set based on the
following precedence:

1. `single-user-authorizer` — when Single User Auth is enabled.
2. `ranger-nifi-authorizer` — when `spec.security.ranger` is set.
3. `managed-authorizer` — the default file-based authorizer.

Consider the following three configuration scenarios:

1. security.singleUserAuth and security.ranger
2. security.ldap and security.ranger
3. security.ldap

For case 1, single user auth will configure NiFi to ignore all authorizations because there's only the single super user.

For case 2, user authentication is handled by LDAP and authorization handled by ranger.

For case 3, user authentication is handled by LDAP and authorization handled by managed-authorizer (what we know as access policies).

---

## Examples

### Minimal configuration (no TLS, no audit)

```yaml
apiVersion: cfm.cloudera.com/v1alpha1
kind: Nifi
metadata:
  name: nifi-prod
  namespace: nifi
spec:
  security:
    ranger:
      serviceName: nifi-prod
      adminURL: https://ranger-admin.example.com:6182
      adminIdentity: "CN=ranger-admin.example.com, OU=Security, O=Acme, L=San Jose, ST=CA, C=US"
```

### Production configuration (mTLS + Solr audit)

```yaml
apiVersion: cfm.cloudera.com/v1alpha1
kind: Nifi
metadata:
  name: nifi-prod
  namespace: nifi
spec:
  security:
    ranger:
      serviceName: nifi-prod
      adminURL: https://ranger-admin.example.com:6182
      adminIdentity: "CN=ranger-admin.example.com, OU=Security, O=Acme, L=San Jose, ST=CA, C=US"
      policyPollIntervalMs: 15000
      audit:
        solr:
          url: http://solr.example.com:6083/solr/ranger_audits
          async: true
          maxQueueSize: 20480
          maxFlushIntervalMs: 10000
      tls:
        secretName: nifi-ranger-tls
```

### ZooKeeper-based Solr discovery

```yaml
spec:
  security:
    ranger:
      serviceName: nifi-prod
      adminURL: https://ranger-admin.example.com:6182
      adminIdentity: "CN=ranger-admin.example.com, OU=Security, O=Acme, L=San Jose, ST=CA, C=US"
      audit:
        solr:
          zookeepersURL: "zk1.example.com:2181,zk2.example.com:2181/solr"
```

### Override with custom XML (escape hatch)

```yaml
spec:
  security:
    ranger:
      serviceName: nifi-prod
      adminURL: https://ranger-admin.example.com:6182
      adminIdentity: "CN=ranger-admin.example.com, OU=Security, O=Acme, L=San Jose, ST=CA, C=US"
      configSecretName: nifi-ranger-custom-config
```

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: nifi-ranger-custom-config
  namespace: nifi
stringData:
  ranger-nifi-security.xml: |
    <?xml version="1.0"?>
    <configuration>
      <property>
        <name>ranger.plugin.nifi.service.name</name>
        <value>nifi-prod</value>
      </property>
      <property>
        <name>ranger.plugin.nifi.policy.source.impl</name>
        <value>org.apache.ranger.admin.client.RangerAdminRESTClient</value>
      </property>
      <property>
        <name>ranger.plugin.nifi.policy.rest.url</name>
        <value>https://ranger-admin.example.com:6182</value>
      </property>
      <property>
        <name>ranger.plugin.nifi.policy.pollIntervalMs</name>
        <value>30000</value>
      </property>
      <property>
        <name>ranger.plugin.nifi.policy.cache.dir</name>
        <value>/tmp/ranger-nifi-security-cache</value>
      </property>
    </configuration>
  ranger-nifi-audit.xml: |
    <?xml version="1.0"?>
    <configuration>
      <property>
        <name>xasecure.audit.solr.enable</name>
        <value>true</value>
      </property>
      <property>
        <name>xasecure.audit.solr.async</name>
        <value>true</value>
      </property>
      <property>
        <name>xasecure.audit.solr.url</name>
        <value>http://solr.example.com:6083/solr/ranger_audits</value>
      </property>
      <property>
        <name>xasecure.audit.solr.async.max.queue.size</name>
        <value>10240</value>
      </property>
      <property>
        <name>xasecure.audit.solr.async.max.flush.interval.ms</name>
        <value>30000</value>
      </property>
    </configuration>
  ranger-policymgr-ssl.xml: |
    <?xml version="1.0"?>
    <configuration>
      <property>
        <name>xasecure.policymgr.clientssl.keystore</name>
        <value>/home/nifi/ranger-tls-keystore/keystore.jks</value>
      </property>
      <property>
        <name>xasecure.policymgr.clientssl.keystore.credential.file</name>
        <value>jceks://file/opt/nifi/nifi-current/conf/ranger-keystore.jceks</value>
      </property>
      <property>
        <name>xasecure.policymgr.clientssl.truststore</name>
        <value>/home/nifi/ranger-tls-truststore/truststore.jks</value>
      </property>
      <property>
        <name>xasecure.policymgr.clientssl.truststore.credential.file</name>
        <value>jceks://file/opt/nifi/nifi-current/conf/ranger-truststore.jceks</value>
      </property>
    </configuration>
```

---

## Generated XML files

When `configSecretName` is **not** set, the operator generates three XML configuration files
from the structured spec fields. The following examples show what the operator produces for a
production configuration.

### `ranger-nifi-security.xml` (generated)

```xml
<?xml version="1.0"?>
<configuration>
  <property>
    <name>ranger.plugin.nifi.service.name</name>
    <value>nifi-prod</value>
  </property>
  <property>
    <name>ranger.plugin.nifi.policy.source.impl</name>
    <value>org.apache.ranger.admin.client.RangerAdminRESTClient</value>
  </property>
  <property>
    <name>ranger.plugin.nifi.policy.rest.url</name>
    <value>https://ranger-admin.example.com:6182</value>
  </property>
  <property>
    <name>ranger.plugin.nifi.policy.pollIntervalMs</name>
    <value>15000</value>
  </property>
  <property>
    <name>ranger.plugin.nifi.policy.cache.dir</name>
    <value>/tmp/ranger-nifi-security-cache</value>
  </property>
  <!-- present only when tls.secretName is set -->
  <property>
    <name>ranger.plugin.nifi.policy.rest.ssl.config.file</name>
    <value>/opt/nifi/nifi-current/conf/ranger-policymgr-ssl.xml</value>
  </property>
</configuration>
```

### `ranger-policymgr-ssl.xml` (For mTLS communication with Ranger)

Contains the keystore and truststore configuration for the NiFi → Ranger Admin mTLS
connection. When `tls.secretName` is set the file contains the four TLS properties shown
below; when TLS is not configured the file renders as an empty `<configuration/>` element.

The Ranger NiFi plugin reads credentials via Hadoop `CredentialProvider` from JCEKS files
created by `start.sh` at pod startup; the plaintext `.password` properties in this file are
not used by the plugin and are omitted.

```xml
<?xml version="1.0"?>
<configuration>
  <property>
    <name>xasecure.policymgr.clientssl.keystore</name>
    <value>/home/nifi/ranger-tls-keystore/keystore.jks</value>
  </property>
  <property>
    <name>xasecure.policymgr.clientssl.keystore.credential.file</name>
    <value>jceks://file/opt/nifi/nifi-current/conf/ranger-keystore.jceks</value>
  </property>
  <property>
    <name>xasecure.policymgr.clientssl.truststore</name>
    <value>/home/nifi/ranger-tls-truststore/truststore.jks</value>
  </property>
  <property>
    <name>xasecure.policymgr.clientssl.truststore.credential.file</name>
    <value>jceks://file/opt/nifi/nifi-current/conf/ranger-truststore.jceks</value>
  </property>
</configuration>
```

### `ranger-nifi-audit.xml` (generated, Solr enabled)

```xml
<?xml version="1.0"?>
<configuration>
  <property>
    <name>xasecure.audit.solr.enable</name>
    <value>true</value>
  </property>
  <property>
    <name>xasecure.audit.solr.async</name>
    <value>true</value>
  </property>
  <property>
    <name>xasecure.audit.solr.url</name>
    <value>http://solr.example.com:6083/solr/ranger_audits</value>
  </property>
  <property>
    <name>xasecure.audit.solr.async.max.queue.size</name>
    <value>20480</value>
  </property>
  <property>
    <name>xasecure.audit.solr.async.max.flush.interval.ms</name>
    <value>10000</value>
  </property>
</configuration>
```

### `ranger-nifi-audit.xml` (generated, Solr disabled)

When `spec.security.ranger.audit` is omitted:

```xml
<?xml version="1.0"?>
<configuration>
  <property>
    <name>xasecure.audit.solr.enable</name>
    <value>false</value>
  </property>
</configuration>
```

---

## TLS Secret format

### Keystore Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: nifi-ranger-keystore
  namespace: nifi
type: Opaque
data:
  # base64-encoded JKS keystore file
  keystore.jks: <base64>
  # base64-encoded plaintext password string
  keystore.password: <base64>
  # base64-encoded JKS truststore file
  truststore.jks: <base64>
  # base64-encoded plaintext password string
  truststore.password: <base64>
```
