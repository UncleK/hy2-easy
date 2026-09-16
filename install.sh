#!/usr/bin/env bash
set -euo pipefail
umask 077

VERSION='0.1.0'
TOOL_SHA256='15c75bbe1ce01ac39cee0b5d5b610d414d5682083ada89df481d10f9d92b8be1'

if [[ ${1:-} == '--help' ]]; then
    echo 'Usage: sudo bash install.sh [--host SERVER_IP_OR_DOMAIN] [--port 24443]'
    exit 0
fi
if [[ $(uname -s) != Linux || $EUID -ne 0 ]]; then
    echo '请在 Linux 服务器上运行 sudo bash install.sh' >&2
    exit 1
fi
if [[ ! -d /run/systemd/system ]]; then
    echo '需要正在运行的 systemd。' >&2
    exit 1
fi
# shellcheck source=/dev/null
source /etc/os-release
case "$ID:$VERSION_ID" in
    debian:12|debian:13|ubuntu:22.04|ubuntu:24.04) ;;
    *) echo '支持 Debian 12/13、Ubuntu 22.04/24.04。' >&2; exit 1 ;;
esac
case "$(uname -m)" in
    x86_64|aarch64) ;;
    *) echo '支持 amd64/arm64。' >&2; exit 1 ;;
esac
if [[ -e /etc/hy2-easy || -L /etc/hy2-easy ]]; then
    echo '检测到已有配置，未覆盖。已安装请运行 sudo hy2-easy share' >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
printf '\n  hy2-easy · 自己的 VPN，简单连接\n\n'
printf '  [1/3] 正在准备安装环境，请稍候…\n'
if ! { apt-get update -qq && apt-get install -y --no-install-recommends \
    ca-certificates curl python3 openssl qrencode passwd; } >"$work/packages.log" 2>&1; then
    printf '\n软件依赖安装失败。下面是最后几行错误，修复后重新执行安装命令即可：\n' >&2
    tail -n 12 "$work/packages.log" >&2
    exit 1
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -f "$script_dir/scripts/hy2_easy.py" ]]; then
    cp -- "$script_dir/scripts/hy2_easy.py" "$work/hy2_easy.py"
else
    curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
        --connect-timeout 15 --max-time 120 --retry 2 \
        "https://raw.githubusercontent.com/UncleK/hy2-easy/v$VERSION/scripts/hy2_easy.py" \
        -o "$work/hy2_easy.py"
fi
if ! printf '%s  %s\n' "$TOOL_SHA256" "$work/hy2_easy.py" | sha256sum --check --status; then
    echo '安装文件校验失败，请重新下载当前版本。' >&2
    exit 1
fi
python3 "$work/hy2_easy.py" install "$@"
