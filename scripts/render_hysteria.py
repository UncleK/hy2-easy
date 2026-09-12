#!/usr/bin/env python3
"""Render the recovered Hysteria config locally; never deploy or restart."""
import argparse
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def render(password):
    if not password or password == 'REPLACE_WITH_HYSTERIA_PASSWORD':
        raise ValueError('Set a non-placeholder HYSTERIA_PASSWORD')
    config = yaml.safe_load((ROOT / 'infra/hysteria.config.template.yaml').read_text())
    config['auth']['password'] = password
    return yaml.safe_dump(config, sort_keys=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'rendered/hysteria/config.yaml')
    args = parser.parse_args()
    try:
        content = render(os.environ.get('HYSTERIA_PASSWORD'))
    except ValueError as exc:
        parser.error(str(exc))
    output = args.output.resolve()
    # Restrict secret-bearing outputs to the Git-ignored artifact directory.
    if not output.is_relative_to((ROOT / 'rendered').resolve()):
        parser.error('output must be inside rendered/')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Do not overwrite an existing artifact or follow a final-path symlink.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(content)
    print('Rendered private config under rendered/; no server changes performed.')


if __name__ == '__main__':
    main()
