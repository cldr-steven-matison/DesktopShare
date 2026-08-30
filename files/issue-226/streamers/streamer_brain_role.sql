-- #276 — the DGX Spark caption brain's read-only door into the streamers roster.
-- Run once on ssb-postgresql (cld-streaming, minikube profile cso-prod-1), database
-- `streamers`, as the superuser through the pod's local trust socket:
--   kubectl exec -i -n cld-streaming deploy/ssb-postgresql -- psql -U postgres -d streamers < this
-- The password is NOT here: substitute it at run time and hand it to spark-dd06
-- out of band (~/.env on the box as STREAMER_BRAIN_DB_PASSWORD).
--
-- The role can SELECT the `streamer_brain` VIEW only — never the raw `streamer`
-- table — so it can never read an unconfirmed pronoun or an internal column.
-- The view (and the identity columns it reads) is created by the app itself at
-- startup: backend/services/roster_store.py `_MIGRATIONS`, idempotent.

CREATE ROLE streamer_brain LOGIN PASSWORD ':PASSWORD';
GRANT CONNECT ON DATABASE streamers TO streamer_brain;
GRANT USAGE ON SCHEMA public TO streamer_brain;
GRANT SELECT ON streamer_brain TO streamer_brain;
