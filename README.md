# xray-personal-gateway

Single-user Xray-core deployment scaffold for a stable `VLESS + REALITY + xtls-rprx-vision` line, managed with "config as source" and rendered deployment artifacts.

## What This Project Does

- manages one dedicated Xray-core line, defaulting to `24883/tcp`
- treats `infra/node.yaml` as the only editable source of truth
- renders a production-ready `config.json`
- generates `v2rayNG` import artifacts
- keeps secrets and rendered output out of Git by default

## Quick Start

1. Copy [`infra/node.example.yaml`](./infra/node.example.yaml) to `infra/node.yaml`.
2. Fill in the real server host, UUID, Reality keys, and short ID.
3. Install or verify Xray on the server:

```bash
bash scripts/install_xray.sh
```

4. Render and apply the config:

```bash
bash scripts/apply_config.sh
```

5. Generate client artifacts:

```bash
python3 scripts/generate_v2rayng_profile.py
```

6. Import `rendered/v2rayng-uri.txt` into `v2rayNG`.

## Layout

- `docs/`: architecture, operations, and client instructions
- `infra/`: source config, JSON template, and security-group checklist
- `scripts/`: installation, rendering, apply, artifact generation, health checks
- `state/`: local notes and backups only

## Safety Notes

- Do not commit `infra/node.yaml`.
- Do not commit real UUIDs, private keys, public keys, or short IDs.
- Do not commit `rendered/`; it contains client-ready artifacts derived from live secrets.
- This project is intended to run without `x-ui` or any panel.
