#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
NODE_CONFIG_PATH="${NODE_CONFIG_PATH:-${PROJECT_ROOT}/infra/node.yaml}"
XRAY_TEMPLATE_PATH="${XRAY_TEMPLATE_PATH:-${PROJECT_ROOT}/infra/xray.config.template.json}"
RENDERED_CONFIG_PATH="${RENDERED_CONFIG_PATH:-${PROJECT_ROOT}/rendered/config.json}"
XRAY_CONFIG_PATH="${XRAY_CONFIG_PATH:-/usr/local/etc/xray/config.json}"
XRAY_SERVICE_NAME="${XRAY_SERVICE_NAME:-xray}"
XRAY_BACKUP_DIR="${XRAY_BACKUP_DIR:-${PROJECT_ROOT}/state/backups}"
V2RAYNG_URI_PATH="${V2RAYNG_URI_PATH:-${PROJECT_ROOT}/rendered/v2rayng-uri.txt}"
V2RAYNG_PROFILE_PATH="${V2RAYNG_PROFILE_PATH:-${PROJECT_ROOT}/rendered/v2rayng-profile.json}"

run_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

timestamp() {
  date -u +"%Y%m%dT%H%M%SZ"
}

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "[apply-config] error: ${PYTHON_BIN} is required." >&2
  exit 1
fi

if ! command -v xray >/dev/null 2>&1; then
  echo "[apply-config] error: xray binary not found. Run scripts/install_xray.sh first." >&2
  exit 1
fi

mkdir -p "${XRAY_BACKUP_DIR}"

echo "[apply-config] rendering ${NODE_CONFIG_PATH}"
"${PYTHON_BIN}" "${SCRIPT_DIR}/render_config.py" \
  --node-config "${NODE_CONFIG_PATH}" \
  --template "${XRAY_TEMPLATE_PATH}" \
  --output "${RENDERED_CONFIG_PATH}"

echo "[apply-config] generating v2rayNG artifacts"
"${PYTHON_BIN}" "${SCRIPT_DIR}/generate_v2rayng_profile.py" \
  --node-config "${NODE_CONFIG_PATH}" \
  --uri-output "${V2RAYNG_URI_PATH}" \
  --profile-output "${V2RAYNG_PROFILE_PATH}"

echo "[apply-config] validating rendered config"
xray -test -config "${RENDERED_CONFIG_PATH}"

backup_path=""
if run_root test -f "${XRAY_CONFIG_PATH}"; then
  backup_path="${XRAY_BACKUP_DIR}/config.$(timestamp).json"
  echo "[apply-config] backing up current live config to ${backup_path}"
  run_root cp "${XRAY_CONFIG_PATH}" "${backup_path}"
fi

echo "[apply-config] installing rendered config to ${XRAY_CONFIG_PATH}"
run_root install -D -o root -g nogroup -m 640 "${RENDERED_CONFIG_PATH}" "${XRAY_CONFIG_PATH}"

echo "[apply-config] restarting ${XRAY_SERVICE_NAME}.service"
if ! run_root systemctl restart "${XRAY_SERVICE_NAME}"; then
  echo "[apply-config] restart failed." >&2
  if [[ -n "${backup_path}" ]]; then
    echo "[apply-config] restoring previous live config from ${backup_path}" >&2
    run_root cp "${backup_path}" "${XRAY_CONFIG_PATH}"
    run_root systemctl restart "${XRAY_SERVICE_NAME}" || true
  fi
  exit 1
fi

echo "[apply-config] post-restart validation"
run_root systemctl --no-pager --full status "${XRAY_SERVICE_NAME}" --lines=0
run_root xray -test -config "${XRAY_CONFIG_PATH}"

echo "[apply-config] done"
