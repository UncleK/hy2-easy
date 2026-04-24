#!/usr/bin/env python3
"""Generate v2rayNG import artifacts for the phase-one Xray line."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from node_config import load_node_config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NODE_CONFIG = Path(
    os.environ.get("NODE_CONFIG_PATH", PROJECT_ROOT / "infra" / "node.yaml")
)
DEFAULT_URI_OUTPUT = Path(
    os.environ.get("V2RAYNG_URI_PATH", PROJECT_ROOT / "rendered" / "v2rayng-uri.txt")
)
DEFAULT_PROFILE_OUTPUT = Path(
    os.environ.get(
        "V2RAYNG_PROFILE_PATH",
        PROJECT_ROOT / "rendered" / "v2rayng-profile.json",
    )
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate v2rayNG artifacts from infra/node.yaml.",
    )
    parser.add_argument(
        "--node-config",
        default=str(DEFAULT_NODE_CONFIG),
        help="Path to the editable node config YAML.",
    )
    parser.add_argument(
        "--uri-output",
        default=str(DEFAULT_URI_OUTPUT),
        help="Path for the generated vless:// share URI.",
    )
    parser.add_argument(
        "--profile-output",
        default=str(DEFAULT_PROFILE_OUTPUT),
        help="Path for the readable JSON backup profile.",
    )
    return parser.parse_args()


def format_authority_host(host: str) -> str:
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def build_vless_uri(node: dict[str, object]) -> str:
    server = node["server"]
    client = node["client"]
    auth = node["auth"]

    host = format_authority_host(server["host"])
    query = urlencode(
        [
            ("encryption", "none"),
            ("flow", client["flow"]),
            ("security", "reality"),
            ("sni", server["primary_server_name"]),
            ("fp", client["fingerprint"]),
            ("pbk", server["reality_public_key"]),
            ("sid", server["short_id"]),
            ("type", "tcp"),
        ],
        quote_via=quote,
        safe="",
    )
    fragment = quote(client["remark"], safe="")
    return f"vless://{auth['uuid']}@{host}:{server['external_port']}?{query}#{fragment}"


def main() -> int:
    args = parse_args()
    node = load_node_config(args.node_config)
    uri = build_vless_uri(node)

    uri_path = Path(args.uri_output).expanduser().resolve()
    profile_path = Path(args.profile_output).expanduser().resolve()
    uri_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.parent.mkdir(parents=True, exist_ok=True)

    profile_payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "client": {
            "target": "v2rayNG",
            "remark": node["client"]["remark"],
            "uri": uri,
        },
        "server": {
            "host": node["server"]["host"],
            "port": node["server"]["external_port"],
            "listenPort": node["server"]["port"],
            "serverName": node["server"]["primary_server_name"],
            "realityDest": node["server"]["reality_dest"],
            "realityPublicKey": node["server"]["reality_public_key"],
            "shortId": node["server"]["short_id"],
        },
        "auth": {
            "uuid": node["auth"]["uuid"],
            "flow": node["client"]["flow"],
            "fingerprint": node["client"]["fingerprint"],
        },
    }

    uri_path.write_text(uri + "\n", encoding="utf-8")
    profile_path.write_text(
        json.dumps(profile_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "generated",
                "uriOutput": str(uri_path),
                "profileOutput": str(profile_path),
                "remark": node["client"]["remark"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
