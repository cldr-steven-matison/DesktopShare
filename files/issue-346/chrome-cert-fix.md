# Chrome + goes01 CA cert fix (issue #346 Part 3, 2026-09-16)

## Problem
Chrome on Linux (NSS) doesn't inherit system CA trust from `/usr/local/share/ca-certificates/`.
The livelog WebSocket fails with `net::ERR_CERT_AUTHORITY_INVALID` even though the goes01 CA is
system-trusted (verified by `openssl s_client`).

## Fix

```bash
mkdir -p ~/.pki/nssdb
certutil -d sql:$HOME/.pki/nssdb -N --empty-password
certutil -A -n "Cloudera AWC Internal CA" -t "TC,," \
  -i /usr/local/share/ca-certificates/goes01/root-goes01-cai-cluster.crt \
  -d sql:$HOME/.pki/nssdb
```

Verify:
```bash
certutil -d sql:$HOME/.pki/nssdb -L | grep -i cloudera
# Cloudera AWC Internal CA                                     CT,,
```

Restart Chrome.

## Context
The goes01 CA chain is 12 roots installed in `/usr/local/share/ca-certificates/goes01/` via
`update-ca-certificates` (done in #347). OpenSSL and curl use the system trust store — they verify
fine. Chrome uses its own NSS database (`~/.pki/nssdb`). Importing the CA cert into NSS makes
the livelog WebSocket work.

## Alternative
`--ignore-certificate-errors` works but is a blunt instrument (disables all cert checks).

## System-level note (Linux)
On some Linux distros Chrome respects `~/.pki/nssdb` but on others you need to point Chrome at the
system store:
```bash
google-chrome --use-system-ssl-certificate ...
```
If that flag doesn't exist, the certutil approach above is the reliable path.
