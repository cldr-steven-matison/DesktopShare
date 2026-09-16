# Step 2 — Kafka SASL (A4): SOLVED & PROVEN live (2026-09-16, FTF3XR2065 on corp VPN)

Broker: `goes01-csm-kafka.goes01-csm-cluster.demos.cloudera-labs.com:8443` (KRAFT, 3 brokers, HEALTHY).
All probes token-free in transcript; the client secret lived only in `/tmp` (mode 600), never committed.

## What #343 got wrong, corrected by live evidence
1. **The broker does NOT drop the connection.** A raw `SaslHandshake` shows it responds and
   advertises its enabled mechanisms.
2. **Exactly one SASL mechanism is enabled: `OAUTHBEARER`.** PLAIN / SCRAM-256/512 / GSSAPI in #343
   failed because they are **not enabled** — nothing to do with the credential.
3. **The failure with the SSO cookie has one precise cause.** OAUTHBEARER handshake → `error_code=0`;
   `SaslAuthenticate` with the `hadoop-jwt` → `58 SASL_AUTHENTICATION_FAILED`,
   **`Token validation failed: Expiry not set`**. The SSO cookie (`iss:KNOXSSO, managed.token:false`)
   carries **no `exp` claim**; the broker's OAUTHBEARER validator requires one.

## The fix — proven end-to-end from this Mac
The correct credential is an OAuth2 `client_credentials` token (which *does* carry `exp`), minted from
the Console auth API, used as the OAUTHBEARER token:

1. `POST /api/v0/auth/access-keys/credentials` (Bearer hadoop-jwt) → `client_id`/`client_secret`
   bound to `steven.matison` (HTTP 201). *(Provisioned this session — client_id `62b996d8-8680-4c4d-b475-e792c5e60772`; see "Credential housekeeping".)*
2. `POST /api/v0/auth/access-keys/token` (HTTP Basic `client_id:client_secret`,
   `grant_type=client_credentials`) → HTTP 200 `{access_token, token_type:Bearer, expires_in}`.
   Token claims: `iss=…/knox-tokenexchange, sub=steven.matison, exp=1789568004` — **has an expiry.**
3. **SASL auth SUCCEEDS:** OAUTHBEARER handshake `error_code=0`, `SaslAuthenticate error_code=0`
   (empty error message).
4. **Produce→consume round-trip SUCCEEDS** (confluent-kafka / librdkafka 2.15.1, `oauth_cb` returning
   the minted token): produced marker `issue-351-oauthbearer-proof-4ff1bc5f` →
   `test_topic[0]@offset 3988896`, consumed back byte-identical. **✓ A4 PROVEN.**
   Admin `list_topics` also works: cluster `nDT2Sa9oTruJjqgkMrCUmA`, topics
   `dm_topic, sensor_data, test_topic, tt, __surveyor_topic_configs, __transaction_state` — so
   `steven.matison` has Ranger describe + produce + consume authz on `test_topic`.

## Production client config (matches the working AWC Flink-SQL connector example)
```
security.protocol = SASL_SSL
sasl.mechanism    = OAUTHBEARER
# librdkafka native OIDC (or Kafka OAuthBearerLoginModule with the same three values):
sasl.oauthbearer.method            = oidc
sasl.oauthbearer.client.id         = <client_id>
sasl.oauthbearer.client.secret     = <client_secret>
sasl.oauthbearer.token.endpoint.url= https://console.goes01-se-goes.demos.cloudera-labs.com/api/v0/auth/access-keys/token
ssl.truststore.type                = PEM   # trust "Cloudera AWC Internal CA"
```
The Java `OAuthBearerLoginModule` + `OAuthBearerLoginCallbackHandler` form (Flink/NiFi) is identical:
it calls the same token endpoint with the clientId/secret and gets a token with `exp`.

## Remaining, non-blocking notes
- **TLS trust:** this test used `enable.ssl.certificate.verification=false`. Production should trust
  the **Cloudera AWC Internal CA** PEM (the CSM host cert is not in the imported goes01 chain — the
  same `-k` caveat #343 recorded). The CA PEM is in the working Flink example / the goes-certs set.
- **Ranger authz** is per principal: `steven.matison` is authorized on `test_topic`. A machine-user
  demo identity would need its own Ranger Kafka policy.

## Credential housekeeping (action for Steven)
The access key provisioned this session (`client_id 62b996d8-…`, bound to `steven.matison`) is the
exact artifact the demo needs. Its secret was returned once and kept only in `/tmp` — **not committed**.
Keep it (store the secret in `~/.awc.creds` or a NiFi Parameter Context, never in the repo) or revoke
it via the Console/Knox token management surface.

## Raw evidence
`step2-kafka-saslhandshake-*.txt` (mechanisms), `step2-kafka-oauthbearer-*.txt` (SSO cookie → "Expiry
not set"), `step2-kafka-oauthbearer-minted-*.txt` (minted token → error_code 0),
`step2-kafka-admin-listtopics-*.txt`, `step2-kafka-produce-consume-*.txt` (round-trip).
