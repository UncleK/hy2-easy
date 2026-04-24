# v2rayNG Client Guide

## Target Client

Phase one supports `v2rayNG` as the primary Android client.

Official project:

- [2dust/v2rayNG](https://github.com/2dust/v2rayNG)

## Generated Artifacts

This project generates two files for the client:

- `rendered/v2rayng-uri.txt`
  - the direct import URI
- `rendered/v2rayng-profile.json`
  - a readable JSON backup of the connection fields

## Import Steps

1. Open `rendered/v2rayng-uri.txt`
2. Copy the full `vless://...` link
3. In `v2rayNG`, choose import from clipboard or import by URI
4. Save the imported node

## Expected Connection Shape

The generated profile is fixed to:

- protocol: `VLESS`
- transport: `TCP`
- security: `Reality`
- flow: `xtls-rprx-vision`
- fingerprint: `chrome`
- SNI: `www.cloudflare.com`

The import URI uses the public client-facing port from `server.external_port`.

## Recommended Client Mode

For normal day-to-day use:

- prefer `VPN mode` if you want most apps to use the line automatically
- use the generated URI as the canonical source of truth

## Quick Validation Checklist

After import:

1. connect successfully
2. open `https://x.com`
3. open `https://www.youtube.com`
4. open one ordinary HTTPS site like `https://www.cloudflare.com`

## Troubleshooting

If import succeeds but traffic fails:

- confirm the server is listening on the configured TCP port, defaulting to `24883/tcp`
- confirm the cloud security group allows the configured public TCP port
- confirm `pbk`, `sid`, `sni`, and `flow` match the server config exactly
- confirm the server host in `infra/node.yaml` is the real reachable public IP or domain
- if your site domain is proxied by Cloudflare, do not use that proxied hostname as the Reality server address; use the server IP or a DNS-only subdomain instead
- re-run `bash scripts/healthcheck.sh` on the server

If connection worked before but stops after a config change:

- check `state/backups/` for the last known-good config
- compare the new `v2rayng-uri.txt` against the old one
- verify that the Reality private/public key pair still matches
