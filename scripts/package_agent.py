#!/usr/bin/env python3
"""Build the offline-dependency Agent zip from explicit public input directories."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist'
def main():
    assert (ROOT/'agent/node_modules/@modelcontextprotocol/sdk/package.json').is_file(), 'Run npm ci --ignore-scripts --omit=optional in agent first'
    OUT.mkdir(exist_ok=True)
    version = json.loads((ROOT/'agent/package.json').read_text())['version']
    archive = OUT/f'hy2-easy-agent-v{version}.zip'
    paths = [ROOT/'LICENSE', ROOT/'README.md', ROOT/'install.sh', ROOT/'scripts/hy2_easy.py', ROOT/'docs/agent.md',
             ROOT/'agent/package.json', ROOT/'agent/package-lock.json', ROOT/'agent/configure.mjs']
    for directory in ['docs', 'agent/src', 'agent/ui', 'agent/adapters', 'agent/node_modules']:
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file())
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for p in sorted(set(paths)):
            relative = p.relative_to(ROOT)
            assert '.env' not in p.name and 'configured' not in relative.parts
            output.write(p, 'hy2-easy/'+relative.as_posix())
    print(f'{archive.name}: {archive.stat().st_size} bytes; SHA256 {hashlib.sha256(archive.read_bytes()).hexdigest()}')
if __name__ == '__main__': main()
