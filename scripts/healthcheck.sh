#!/usr/bin/env bash
set -euo pipefail

XRAY_SERVICE_NAME="${XRAY_SERVICE_NAME:-xray}"
XRAY_CONFIG_PATH="${XRAY_CONFIG_PATH:-/usr/local/etc/xray/config.json}"
EXPECTED_PORT="${XRAY_PORT:-24883}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "[healthcheck] error: $*" >&2
  exit 1
}

echo "[healthcheck] checking ${XRAY_SERVICE_NAME}.service"
systemctl is-active --quiet "${XRAY_SERVICE_NAME}" || fail "${XRAY_SERVICE_NAME}.service is not active"

echo "[healthcheck] checking xray binary"
command -v xray >/dev/null 2>&1 || fail "xray binary not found"
xray version | head -n 1

echo "[healthcheck] validating ${XRAY_CONFIG_PATH}"
if [[ "${EUID}" -eq 0 ]]; then
  xray -test -config "${XRAY_CONFIG_PATH}" >/dev/null
else
  sudo xray -test -config "${XRAY_CONFIG_PATH}" >/dev/null
fi

echo "[healthcheck] checking listen port ${EXPECTED_PORT}"
ss -tulpn | grep -Eq "[:.]${EXPECTED_PORT}[[:space:]]" || fail "expected listen port ${EXPECTED_PORT} not found"

URI_PATH="${PROJECT_ROOT}/rendered/v2rayng-uri.txt"
PROFILE_PATH="${PROJECT_ROOT}/rendered/v2rayng-profile.json"
if [[ -f "${URI_PATH}" ]]; then
  echo "[healthcheck] found client URI artifact: ${URI_PATH}"
else
  echo "[healthcheck] warning: missing ${URI_PATH}"
fi
if [[ -f "${PROFILE_PATH}" ]]; then
  echo "[healthcheck] found client JSON artifact: ${PROFILE_PATH}"
else
  echo "[healthcheck] warning: missing ${PROFILE_PATH}"
fi

echo "[healthcheck] all required checks passed"
