# Operations

## Server Assumptions

- Ubuntu host
- `systemd` is available
- root or `sudo` access is available
- cloud security group changes are handled outside this repo
- no `x-ui` panel is required or managed by this project

## Prepare the Editable Node Config

Copy the example file:

```bash
cp infra/node.example.yaml infra/node.yaml
```

Fill in these real values:

- `server.host`
- `server.port`
- `server.external_port`
- `auth.uuid`
- `server.reality_private_key`
- `server.reality_public_key`
- `server.short_id`

## Generate Required Secrets

After Xray is installed, generate a UUID:

```bash
xray uuid
```

Generate a Reality key pair:

```bash
xray x25519
```

Choose one short ID:

- hexadecimal only
- keep it short and memorable enough to rotate manually

Example:

```text
0123456789abcdef
```

## Install or Verify Xray

Run:

```bash
bash scripts/install_xray.sh
```

This script:

- checks whether `xray.service` already exists
- installs Xray via the official `XTLS/Xray-install` script when needed

## Render and Apply the Config

```bash
bash scripts/apply_config.sh
```

This script:

- renders `rendered/config.json`
- validates it with `xray -test`
- backs up the current live config
- writes the rendered config to `/usr/local/etc/xray/config.json`
  - installed as `root:nogroup` with `640` permissions so the `xray` service can read it without making the private key world-readable
- restarts `xray.service`
- restores the previous config automatically if restart fails

## Generate Client Artifacts

```bash
python3 scripts/generate_v2rayng_profile.py
```

Generated files:

- `rendered/v2rayng-uri.txt`
- `rendered/v2rayng-profile.json`

## Health Checks

Run:

```bash
bash scripts/healthcheck.sh
```

The checks cover:

- `xray.service` active state
- config syntax validation
- expected listen port from `XRAY_PORT`, defaulting to `24883`
- generated client artifact presence

## Day-Two Maintenance

- rotate UUID or Reality material by editing `infra/node.yaml` and re-running `apply_config.sh`
- keep backups under `state/backups/`
- do not use `x-ui` or another panel to mutate this line
- verify the live port with `ss -lntp` on the server instead of relying on external port probes
