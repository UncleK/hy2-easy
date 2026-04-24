# Security Group Checklist

This checklist assumes:

- the Xray-core line uses `24883/tcp` by default
- host firewall rules are managed outside this repo

## Allow Rules

- `22/tcp`
  - management IP only
- `24883/tcp`
  - public
  - Xray-core line
- `80/tcp`
  - keep only if another service, such as `Caddy`, needs it
- `443/tcp`
  - keep only if another service, such as `Caddy`, needs it

## Restrict Or Remove

- `32568/tcp`
  - remove unless a separate management service still requires it
- `3000/tcp`
  - restrict to management IP or remove if no longer needed publicly
- random public UDP ports
  - document first
  - remove if their usage is unclear and no service listens on them

## Verification

After changing the security group:

1. confirm the configured Xray TCP port is reachable from the client network
2. confirm unused management or UDP ports are closed
3. confirm existing `80/443` services still behave as expected if they are in use
