#!/usr/bin/env python3
"""Compare tracked Hysteria artifacts with a read-only, redacted SSH snapshot."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]

# Fail closed on unfamiliar config fields rather than accidentally exporting
# credentials from a new authentication, outbound, or masquerade configuration.
REMOTE = r'''
import json, pathlib, subprocess, yaml
c = yaml.safe_load(pathlib.Path('/etc/hysteria/config.yaml').read_text())
shape = {
 'listen': None,
 'tls': {'cert': None, 'key': None},
 'auth': {'type': None, 'password': None},
 'masquerade': {'type': None, 'proxy': {'url': None, 'rewriteHost': None}},
}
def check(value, spec):
 if isinstance(spec, dict):
  if not isinstance(value, dict) or set(value) != set(spec):
   raise SystemExit('Unsupported config structure; manual private review required')
  for k in spec: check(value[k], spec[k])
 elif not isinstance(value, (str, bool, int)):
  raise SystemExit('Unsupported config value')
check(c, shape)
if c['auth']['type'] != 'password':
 raise SystemExit('Unsupported authentication type')
c['auth']['password'] = 'REPLACE_WITH_HYSTERIA_PASSWORD'
# Only emit a comparison result for the unit; unit environment may contain secrets.
unit = pathlib.Path('/etc/systemd/system/hysteria-server.service').read_text()
import hashlib
def run(*args):
 p = subprocess.run(args, capture_output=True, text=True)
 return p.stdout.strip()
print(json.dumps({
 'config': c,
 'unit_sha256': hashlib.sha256(unit.strip().encode()).hexdigest(),
 'active': run('systemctl', 'is-active', 'hysteria-server'),
 'enabled': run('systemctl', 'is-enabled', 'hysteria-server'),
 'restarts': run('systemctl', 'show', 'hysteria-server', '-p', 'NRestarts', '--value'),
 'version': run('/usr/local/bin/hysteria', 'version'),
 'udp_listener': ':24443' in run('ss', '-H', '-lun'),
}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', help='SSH destination, e.g. root@your-server')
    parser.add_argument('--identity', type=Path)
    args = parser.parse_args()
    if args.host.startswith('-'):
        parser.error('host must not be an SSH option')
    command = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
               '-o', 'ConnectTimeout=15']
    if args.identity:
        command += ['-i', str(args.identity.expanduser())]
    command += [args.host, 'python3 -']
    result = subprocess.run(command, input=REMOTE, text=True,
                            capture_output=True, timeout=45)
    if result.returncode:
        # Do not echo remote stderr, which might include config/credential values.
        print('Remote audit failed; check SSH access and supported config schema.', file=sys.stderr)
        return 2
    snapshot = json.loads(result.stdout)
    expected = yaml.safe_load((ROOT / 'infra/hysteria.config.template.yaml').read_text())
    import hashlib
    unit = (ROOT / 'infra/hysteria-server.service').read_text().strip()
    checks = {
        'config_matches': snapshot['config'] == expected,
        'unit_matches': snapshot['unit_sha256'] == hashlib.sha256(unit.encode()).hexdigest(),
        'active': snapshot['active'] == 'active',
        'enabled': snapshot['enabled'] == 'enabled',
        'udp_24443_listening': snapshot['udp_listener'],
        'version_matches': 'Version:\tv2.12.1' in snapshot['version'],
    }
    print(json.dumps({'checks': checks, 'restarts': snapshot['restarts']}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
