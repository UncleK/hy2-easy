#!/usr/bin/env python3
"""Shared node-config parsing and normalization helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


HEX_PATTERN = re.compile(r"^[0-9a-fA-F]+$")
INTEGER_PATTERN = re.compile(r"^-?\d+$")


class ConfigError(RuntimeError):
    """Raised when the editable node config is invalid."""


def load_node_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).expanduser().resolve()
    if not config_path.exists():
        raise ConfigError(f"Node config not found: {config_path}")

    text = config_path.read_text(encoding="utf-8")
    payload = _load_yaml_or_fallback(text)
    return normalize_node_config(payload)


def _load_yaml_or_fallback(text: str) -> Any:
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None

    if yaml is not None:
        parsed = yaml.safe_load(text)
        if parsed is None:
            raise ConfigError("Node config is empty.")
        return parsed

    return _parse_minimal_yaml(text)


def _parse_minimal_yaml(text: str) -> Any:
    cleaned_lines: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        stripped = raw_line.lstrip(" ")
        if stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(stripped)
        if "\t" in raw_line[:indent]:
            raise ConfigError("Tabs are not supported in node.yaml indentation.")
        cleaned_lines.append((indent, stripped))

    if not cleaned_lines:
        raise ConfigError("Node config is empty.")

    parsed, next_index = _parse_block(cleaned_lines, 0, 0)
    if next_index != len(cleaned_lines):
        raise ConfigError("Unexpected trailing content in node config.")
    return parsed


def _parse_block(
    lines: list[tuple[int, str]],
    start_index: int,
    indent: int,
) -> tuple[Any, int]:
    if start_index >= len(lines):
        raise ConfigError("Unexpected end of node config.")

    current_indent, current_text = lines[start_index]
    if current_indent < indent:
        raise ConfigError("Invalid indentation in node config.")
    if current_indent != indent:
        raise ConfigError("Nested blocks must use 2-space indentation steps.")

    if current_text.startswith("- "):
        output: list[Any] = []
        index = start_index
        while index < len(lines):
            line_indent, line_text = lines[index]
            if line_indent < indent:
                break
            if line_indent != indent or not line_text.startswith("- "):
                raise ConfigError("List items must align cleanly in node config.")

            item_text = line_text[2:].strip()
            if not item_text:
                child, index = _parse_block(lines, index + 1, indent + 2)
                output.append(child)
                continue

            output.append(_parse_scalar(item_text))
            index += 1
        return output, index

    output_dict: dict[str, Any] = {}
    index = start_index
    while index < len(lines):
        line_indent, line_text = lines[index]
        if line_indent < indent:
            break
        if line_indent != indent or line_text.startswith("- "):
            raise ConfigError("Mapping keys must align cleanly in node config.")
        if ":" not in line_text:
            raise ConfigError(f"Invalid mapping line: {line_text}")

        key, value_text = line_text.split(":", 1)
        key = key.strip()
        value_text = value_text.strip()
        if not key:
            raise ConfigError("Mapping key cannot be empty.")

        if not value_text:
            child, index = _parse_block(lines, index + 1, indent + 2)
            output_dict[key] = child
            continue

        output_dict[key] = _parse_scalar(value_text)
        index += 1

    return output_dict, index


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "~"}:
        return None
    if INTEGER_PATTERN.fullmatch(value):
        return int(value)
    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value


def normalize_node_config(payload: Any) -> dict[str, Any]:
    root = _as_dict(payload, "root")
    server = _as_dict(root.get("server"), "server")
    auth = _as_dict(root.get("auth"), "auth")
    client = _as_dict(root.get("client"), "client")
    log = _as_dict(root.get("log"), "log")

    host = _require_string(server.get("host"), "server.host")
    port = _require_int(server.get("port", 24883), "server.port")
    if port < 1 or port > 65535:
        raise ConfigError("server.port must be between 1 and 65535.")
    external_port = _require_int(server.get("external_port", port), "server.external_port")
    if external_port < 1 or external_port > 65535:
        raise ConfigError("server.external_port must be between 1 and 65535.")

    listen = _optional_string(server.get("listen")) or "::"
    server_names = _normalize_server_names(server)
    reality_dest = _optional_string(server.get("reality_dest")) or f"{server_names[0]}:443"
    reality_private_key = _require_string(
        server.get("reality_private_key"),
        "server.reality_private_key",
    )
    reality_public_key = _require_string(
        server.get("reality_public_key"),
        "server.reality_public_key",
    )
    short_id = _require_string(server.get("short_id"), "server.short_id")
    if len(short_id) > 16 or not HEX_PATTERN.fullmatch(short_id):
        raise ConfigError("server.short_id must be hexadecimal and at most 16 characters.")

    uuid = _require_string(auth.get("uuid"), "auth.uuid")

    remark = _optional_string(client.get("remark")) or "personal-main"
    email = _optional_string(client.get("email")) or "primary-v2rayng"
    fingerprint = _optional_string(client.get("fingerprint")) or "chrome"
    flow = _optional_string(client.get("flow")) or "xtls-rprx-vision"

    log_level = _optional_string(log.get("level")) or "warning"

    return {
        "server": {
            "host": host,
            "port": port,
            "external_port": external_port,
            "listen": listen,
            "server_names": server_names,
            "primary_server_name": server_names[0],
            "reality_dest": reality_dest,
            "reality_private_key": reality_private_key,
            "reality_public_key": reality_public_key,
            "short_id": short_id.lower(),
        },
        "auth": {
            "uuid": uuid,
        },
        "client": {
            "remark": remark,
            "email": email,
            "fingerprint": fingerprint,
            "flow": flow,
        },
        "log": {
            "level": log_level,
        },
    }


def build_template_context(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "LOG_LEVEL": node["log"]["level"],
        "INBOUND_LISTEN": node["server"]["listen"],
        "INBOUND_PORT": node["server"]["port"],
        "CLIENT_UUID": node["auth"]["uuid"],
        "CLIENT_FLOW": node["client"]["flow"],
        "CLIENT_EMAIL": node["client"]["email"],
        "REALITY_DEST": node["server"]["reality_dest"],
        "REALITY_SERVER_NAMES": node["server"]["server_names"],
        "REALITY_PRIVATE_KEY": node["server"]["reality_private_key"],
        "REALITY_SHORT_IDS": [node["server"]["short_id"]],
    }


def _normalize_server_names(server: dict[str, Any]) -> list[str]:
    if isinstance(server.get("server_names"), list):
        names = [
            entry.strip()
            for entry in server["server_names"]
            if isinstance(entry, str) and entry.strip()
        ]
        if names:
            return names

    fallback = _optional_string(server.get("server_name")) or "www.cloudflare.com"
    return [fallback]


def _as_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a mapping.")
    return value


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _require_string(value: Any, label: str) -> str:
    normalized = _optional_string(value)
    if normalized is None:
        raise ConfigError(f"{label} must be a non-empty string.")
    return normalized


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{label} must be an integer.")
    return value
