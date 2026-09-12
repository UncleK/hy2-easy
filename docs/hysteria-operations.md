# Current Hysteria deployment

## Evidence captured on 2026-09-13

Read-only SSH inspection of the current Hetzner host established:

| Item | Observed value |
| --- | --- |
| Binary | `/usr/local/bin/hysteria`, v2.12.1, linux/amd64 |
| Unit | `/etc/systemd/system/hysteria-server.service` |
| Runtime identity | `hysteria:hysteria` |
| Config | `/etc/hysteria/config.yaml`, `root:hysteria`, mode `0640` |
| Certificate | `/etc/hysteria/server.crt`, `root:hysteria`, mode `0644` |
| Private key | `/etc/hysteria/server.key`, `root:hysteria`, mode `0640` |
| Ingress | UDP 24443, wildcard listen |
| Auth | Password; value deliberately excluded from Git |
| Masquerade | Proxy to `https://www.cloudflare.com/`, rewriteHost enabled |
| Service | active, enabled; NRestarts=0 |
| Active since | 2026-08-21 07:40:18 UTC |
| Certificate validity | 2026-08-21 to 2036-08-18 UTC |
| Socket buffers | rmem_max and wmem_max both 4194304 |
| UFW | inactive; Hetzner firewall rules were not inspected |
| Xray | No binary or installed unit found |

A live HTTPS request through the existing local proxy at `127.0.0.1:10809`
returned the inspected Hetzner server's public IP. This confirms that request's
proxy exit at inspection time; no throughput or long-duration stability test was run.

The live YAML does not explicitly configure congestion, speedTest or disableUDP.
`/etc/sysctl.d/90-hysteria2.conf` is absent. The tracked unit is a copy of the observed unit, not
a proposed service-hardening change.

## Read-only drift check

Install `requirements-hysteria.txt` in a Python environment. The remote host also
needs Python 3 and PyYAML (both were present at inspection time).

```powershell
python -m pip install -r requirements-hysteria.txt
python scripts/audit_hysteria.py root@YOUR_SERVER --identity C:\path\to\ssh-key
```

The audit removes the password on the server before comparison, compares the
unit by hash, and checks active/enabled state, version and UDP listener. Unknown
configuration structure fails closed for manual review. Exit 0 means all these
checks match; exit 1 means drift; exit 2 means the remote read failed. This is
not a client throughput or end-to-end tunnel test.

## Render configuration

Supply the existing password through `HYSTERIA_PASSWORD` in a private local
environment, then run:

```powershell
python scripts/render_hysteria.py
```

This creates `rendered/hysteria/config.yaml`, which Git ignores. Existing output
is not overwritten. Windows users must protect the output directory with their
local NTFS ACLs; POSIX mode 0600 alone does not establish a Windows DACL.
No passwords, client URIs, private keys or actual server address are tracked.

## Restore or deploy deliberately

This reconciliation did not change the server. A fresh machine still requires
the verified Hysteria v2.12.1 binary from the upstream release, a `hysteria` system
account, and UDP 24443 allowed in the relevant cloud/host firewall. Installation
and firewall changes are separate from the read-only audit.

Preserve `/etc/hysteria/config.yaml`, `server.crt`, and `server.key` in an encrypted
private backup. Git contains neither the password nor the TLS identity and is
therefore not a complete disaster-recovery backup. Restore the same certificate
and key to preserve existing client certificate pins. Generating a replacement
certificate requires updating and verifying each client's pin.

On an already prepared Linux host, after privately restoring the certificate/key
and rendering the configuration, these are the explicit deployment steps:

```bash
sudo install -d -o root -g hysteria -m 0750 /etc/hysteria
# Back up an existing config/unit privately before replacing either file.
sudo install -o root -g hysteria -m 0640 rendered/hysteria/config.yaml /etc/hysteria/config.yaml
sudo install -o root -g root -m 0644 infra/hysteria-server.service /etc/systemd/system/hysteria-server.service
sudo systemctl daemon-reload
sudo systemctl enable hysteria-server
sudo systemctl restart hysteria-server
sudo systemctl is-active hysteria-server
sudo ss -lunp
```

Hysteria's observed server CLI has no config-test flag. A successful YAML render
does not establish that a replacement server starts or accepts clients. If the
service or client check fails, restore the private config/unit backup, reload
systemd and restart. Verify the certificate pin and a real client request before
accepting a future deployment.

## Repository migration

The obsolete Xray implementation and experimental Hysteria installer were removed
at the owner's request. Previously committed Xray code remains in Git history.
Existing ignored private files and backups remain local and are not inputs to
the current Hysteria scripts. No remote VPN settings were modified during recovery.
