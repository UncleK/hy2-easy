# Architecture

## Goal

Build a single-user, low-maintenance Xray-core line without a web panel. The editable node declaration is the source of truth; generated artifacts are rendered from it and applied to the server.

## Topology

- `xray.service`
- `/usr/local/bin/xray`
- `/usr/local/etc/xray/config.json`
- one dedicated client line, defaulting to `24883/tcp`
- optional existing `Caddy` remains responsible for unrelated `80/443` site traffic

## Port Strategy

- `24883/tcp`
  - default public Xray-core listen port
  - must be allowed by the cloud security group
- `80/443`
  - unrelated to this Xray line
  - keep only if another service, such as `Caddy`, needs them
- `32568/tcp`
  - not used by this project
  - remove it from the cloud security group unless something else needs it
- `3000/tcp`
  - out of scope for this project
  - should be restricted at the cloud security group if not required publicly

## Addressing Rule

- if an existing site domain is fronted by Cloudflare proxy or another CDN proxy, do not reuse that proxied hostname as the Reality ingress
- use either:
  - the server public IP
  - a dedicated DNS-only subdomain that resolves directly to the server

## Config Flow

This project treats the editable node declaration as the source of truth.

1. Edit `infra/node.yaml`
2. Render `rendered/config.json`
3. Validate with `xray -test`
4. Backup current live config
5. Apply to `/usr/local/etc/xray/config.json`
6. Restart `xray.service`
7. Generate `v2rayNG` client artifacts

## Fixed Protocol Choices

- inbound protocol: `vless`
- transport: `tcp`
- transport security: `reality`
- client flow: `xtls-rprx-vision`
- direct outbound: `freedom`
- reserved sink outbound: `blackhole`
- log level: `warning`
- no panel
- no Xray API
- no stats interface
- no Caddy integration
- no Argo / WARP / Psiphon / CDN layering

## Rollback Strategy

Rollback remains simple by design:

1. stop `xray.service`
2. restore the latest config backup from `state/backups/`
3. start `xray.service`

No `x-ui` rollback lane is assumed.

## Future Extension Path

Phase one deliberately leaves room for a simple self-built control plane later:

- edit only `infra/node.yaml`
- reuse the same render/apply scripts
- optional future local admin app on `127.0.0.1:18080`
- optional future `Caddy` reverse-proxy exposure only after the local admin app is proven safe
