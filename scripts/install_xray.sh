#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTALL_SCRIPT_URL="${XRAY_INSTALL_SCRIPT_URL:-https://github.com/XTLS/Xray-install/raw/main/install-release.sh}"
XRAY_SERVICE_NAME="${XRAY_SERVICE_NAME:-xray}"

run_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

echo "[xray-install] project root: ${PROJECT_ROOT}"

if ! command -v curl >/dev/null 2>&1; then
  echo "[xray-install] error: curl is required." >&2
  exit 1
fi

if command -v xray >/dev/null 2>&1; then
  echo "[xray-install] detected xray binary: $(command -v xray)"
  xray version | head -n 1
else
  echo "[xray-install] xray binary not found; installing via official Xray-install script."
  run_root bash -c "$(curl -fsSL --proto '=https' --tlsv1.2 "${INSTALL_SCRIPT_URL}")" @ install
fi

if systemctl list-unit-files | grep -qw "${XRAY_SERVICE_NAME}.service"; then
  echo "[xray-install] ${XRAY_SERVICE_NAME}.service is present."
  run_root systemctl enable "${XRAY_SERVICE_NAME}" >/dev/null 2>&1 || true
  run_root systemctl start "${XRAY_SERVICE_NAME}" >/dev/null 2>&1 || true
  run_root systemctl --no-pager --full status "${XRAY_SERVICE_NAME}" --lines=0 || true
else
  echo "[xray-install] error: ${XRAY_SERVICE_NAME}.service was not installed." >&2
  exit 1
fi
