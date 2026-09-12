# Personal Hysteria 2 gateway

This repository reconstructs the current Hetzner VPN deployment from a read-only
server inspection on 2026-09-13. The GitHub repository retains its original
`xray-personal-gateway` name, but now targets **Hysteria 2 v2.12.1 on UDP 24443**.
Obsolete Xray code has been removed.

The server uses password authentication, a self-signed TLS certificate, and an
HTTP proxy masquerade. No control panel is involved.

## Quick start

```powershell
python -m pip install -r requirements-hysteria.txt
python scripts/audit_hysteria.py root@YOUR_SERVER --identity C:\path\to\ssh-key
```

To render a config, supply the existing password via `HYSTERIA_PASSWORD` in a
private environment and run `python scripts/render_hysteria.py`. Output stays in
Git-ignored `rendered/`. This command does not deploy anything.

See [operations and recovery](docs/hysteria-operations.md) for observed server
paths, file permissions, backup requirements and deliberate deployment steps.

## Files

- `infra/hysteria.config.template.yaml`: live configuration with a password placeholder.
- `infra/hysteria-server.service`: observed production systemd unit.
- `scripts/audit_hysteria.py`: read-only remote drift and service checks.
- `scripts/render_hysteria.py`: private local config rendering.
- `tests/test_hysteria.py`: credential substitution and rejection checks.
- `state/`: local private backup notes; backup contents are ignored.

Run tests with `python -m unittest discover -s tests -v`.

Passwords, TLS keys, client artifacts and local backups are excluded from Git.
The repository alone cannot restore the existing TLS identity; retain encrypted
private backups of the live configuration, certificate and key.
