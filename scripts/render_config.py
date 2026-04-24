#!/usr/bin/env python3
"""Render the live Xray config from the editable node declaration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from node_config import ConfigError, build_template_context, load_node_config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NODE_CONFIG = Path(
    os.environ.get("NODE_CONFIG_PATH", PROJECT_ROOT / "infra" / "node.yaml")
)
DEFAULT_TEMPLATE = Path(
    os.environ.get(
        "XRAY_TEMPLATE_PATH",
        PROJECT_ROOT / "infra" / "xray.config.template.json",
    )
)
DEFAULT_OUTPUT = Path(
    os.environ.get("RENDERED_CONFIG_PATH", PROJECT_ROOT / "rendered" / "config.json")
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render an Xray config from infra/node.yaml.",
    )
    parser.add_argument(
        "--node-config",
        default=str(DEFAULT_NODE_CONFIG),
        help="Path to the editable node config YAML.",
    )
    parser.add_argument(
        "--template",
        default=str(DEFAULT_TEMPLATE),
        help="Path to the Xray JSON template.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Where to write the rendered Xray JSON config.",
    )
    return parser.parse_args()


def render_template(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: render_template(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [render_template(item, context) for item in value]
    if not isinstance(value, str):
        return value

    if value.startswith("{{") and value.endswith("}}"):
        key = value[2:-2].strip()
        if key not in context:
            raise ConfigError(f"Unknown template placeholder: {key}")
        return context[key]

    output = value
    for key, replacement in context.items():
        token = f"{{{{{key}}}}}"
        if token not in output:
            continue
        if not isinstance(replacement, str):
            raise ConfigError(
                f"Placeholder {key} can only be embedded inside a string when the replacement is also a string."
            )
        output = output.replace(token, replacement)
    return output


def main() -> int:
    args = parse_args()
    node = load_node_config(args.node_config)
    context = build_template_context(node)

    template_path = Path(args.template).expanduser().resolve()
    if not template_path.exists():
        raise ConfigError(f"Template not found: {template_path}")

    template_payload = json.loads(template_path.read_text(encoding="utf-8"))
    rendered = render_template(template_payload, context)

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(rendered, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "rendered",
                "nodeConfig": str(Path(args.node_config).expanduser().resolve()),
                "template": str(template_path),
                "output": str(output_path),
                "serverHost": node["server"]["host"],
                "listenPort": node["server"]["port"],
                "externalPort": node["server"]["external_port"],
                "serverName": node["server"]["primary_server_name"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
