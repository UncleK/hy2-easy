#!/usr/bin/env python3
"""hy2-easy: a small, single-server Hysteria 2 installer and local manager."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote, urlencode

VERSION = "0.1.1"
CORE_VERSION = "2.12.2"
CORE_HASHES = {
    "x86_64": ("amd64", "6493dfffd55b5883f64c76c63880ecc32988f0c568c9ca9014907877b4d55f94"),
    "aarch64": ("arm64", "ebfacc1ec3a0edfd742cd68ce17f292a6092e606b9d11f99b035c1d888f3d709"),
}
ETC = Path("/etc/hy2-easy")
LIB = Path("/usr/local/lib/hy2-easy")
CLI = Path("/usr/local/bin/hy2-easy")
UNIT = Path("/etc/systemd/system/hy2-easy.service")
SERVICE = "hy2-easy.service"
USER = "hy2-easy"
SNI = "hy2-easy.local"

UNIT_TEXT = """[Unit]
Description=hy2-easy personal Hysteria 2 gateway
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=hy2-easy
Group=hy2-easy
ExecStart=/usr/local/lib/hy2-easy/hysteria server --disable-update-check --config /etc/hy2-easy/server.json
Restart=on-failure
RestartSec=3
Environment=HYSTERIA_LOG_LEVEL=warn
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
CapabilityBoundingSet=
AmbientCapabilities=
UMask=0077

[Install]
WantedBy=multi-user.target
"""


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def host_name(value):
    """Accept only a bare IP or DNS name, never a URL or shell fragment."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if "%" in value:
        raise ValueError("地址不能包含 IPv6 zone ID")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        pass
    if re.fullmatch(r"[0-9.]+", value):
        raise ValueError("IP 地址无效")
    value = value.rstrip(".").encode("idna").decode("ascii").lower()
    if len(value) > 253 or not value or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
        for part in value.split(".")
    ):
        raise ValueError("请输入公网 IP 或域名，不含 https://、端口或路径")
    return value


def endpoint(host, port):
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"


def certificate_pin(cert):
    der = ssl.PEM_cert_to_DER_cert(cert.read_text(encoding="ascii"))
    return hashlib.sha256(der).hexdigest()


def share_uri(host, port, password, pin):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", pin):
        raise ValueError("证书指纹无效")
    query = urlencode({"sni": SNI, "insecure": "1", "pinSHA256": pin})
    return f"hysteria2://{quote(password, safe='')}@{endpoint(host, port)}/?{query}#hy2-easy"


def client_config(host, port, password, pin):
    return {
        "server": endpoint(host, port), "auth": password,
        "tls": {"sni": SNI, "insecure": True, "pinSHA256": pin},
        "socks5": {"listen": "127.0.0.1:1080"},
        "http": {"listen": "127.0.0.1:8080"},
    }


def write_private(path, content, mode=0o600):
    # Exclusive creation also refuses existing symlinks.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        os.fchmod(handle.fileno(), mode)
        handle.write(content)


def write_json(path, value, mode=0o600):
    write_private(path, json.dumps(value, indent=2) + "\n", mode)


def core_download(target):
    arch, expected = CORE_HASHES[platform.machine()]
    url = f"https://github.com/HyNetworks/hysteria/releases/download/app/v{CORE_VERSION}/hysteria-linux-{arch}"
    run("curl", "--fail", "--location", "--silent", "--show-error", "--proto", "=https",
        "--proto-redir", "=https", "--connect-timeout", "15", "--max-time", "300",
        "--retry", "2", "--output", str(target), url)
    if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        target.unlink()
        raise ValueError("Hysteria 下载校验失败，未安装")
    target.chmod(0o755)


def validate_platform():
    if platform.system() != "Linux" or platform.machine() not in CORE_HASHES:
        raise ValueError("支持 Debian 12/13、Ubuntu 22.04/24.04 的 amd64/arm64")
    release = platform.freedesktop_os_release()
    if (release.get("ID"), release.get("VERSION_ID")) not in {
        ("debian", "12"), ("debian", "13"), ("ubuntu", "22.04"), ("ubuntu", "24.04")
    }:
        raise ValueError("当前系统不在支持列表中")
    if not Path("/run/systemd/system").is_dir():
        raise ValueError("需要正在运行的 systemd；普通 Docker 容器不适用")


def prompt_host(given):
    if given:
        return host_name(given)
    parts = os.environ.get("SSH_CONNECTION", "").split()
    default = parts[2] if len(parts) == 4 else ""
    if default:
        try:
            if not ipaddress.ip_address(default).is_global:
                default = ""
        except ValueError:
            default = ""
    with open("/dev/tty", "r+", encoding="utf-8", buffering=1) as tty:
        tty.write("\n  请复制云服务器页面上的「公网 IP」并粘贴到这里。\n")
        if default:
            tty.write("  如果下面的地址正确，直接按回车即可。\n")
        tty.write(f"  服务器地址{f' [{default}]' if default else ''}: ")
        answer = tty.readline()
    if not answer:
        raise ValueError("未输入服务器地址；也可以使用 --host 指定")
    return host_name(answer.strip() or default)


def port_available(port):
    # Probe both families, without changing firewall or any existing service.
    for family, address in ((socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::")):
        if family == socket.AF_INET6 and not socket.has_ipv6:
            continue
        try:
            with socket.socket(family, socket.SOCK_DGRAM) as sock:
                sock.bind((address, port))
        except OSError as exc:
            import errno
            if exc.errno in (errno.EAFNOSUPPORT, errno.EADDRNOTAVAIL):
                continue
            raise ValueError(f"UDP {port} 无法使用，请通过 --port 指定空闲端口") from exc


def service_ready():
    for _ in range(15):
        if subprocess.run(["systemctl", "is-active", "--quiet", SERVICE]).returncode == 0:
            time.sleep(1)
            return subprocess.run(["systemctl", "is-active", "--quiet", SERVICE]).returncode == 0
        time.sleep(1)
    return False


def install(args):
    validate_platform()
    if any(p.exists() or p.is_symlink() for p in (ETC, LIB, CLI, UNIT, Path(str(UNIT) + ".d"))):
        raise ValueError("检测到已有 hy2-easy 文件，未覆盖。已安装请运行 sudo hy2-easy share")
    host = prompt_host(args.host)
    if not 1024 <= args.port <= 65535:
        raise ValueError("端口范围为 1024–65535")
    port_available(args.port)
    import grp
    import pwd
    try:
        pwd.getpwnam(USER)
    except KeyError:
        pass
    else:
        raise ValueError("hy2-easy 系统用户已存在，未接管该用户")
    try:
        grp.getgrnam(USER)
    except KeyError:
        pass
    else:
        raise ValueError("hy2-easy 系统组已存在，未接管该组")
    print("\n  [2/3] 正在安装连接服务，自动生成密码和二维码…", flush=True)
    account_created = False
    created = []
    with tempfile.TemporaryDirectory(prefix="hy2-easy-") as temp:
        binary = Path(temp) / "hysteria"
        core_download(binary)
        try:
            run("useradd", "--system", "--user-group", "--no-create-home", "--home-dir", str(ETC),
                "--shell", "/usr/sbin/nologin", USER)
            account_created = True
            gid = grp.getgrnam(USER).gr_gid
            ETC.mkdir(mode=0o750)
            created.append(ETC)
            ETC.chmod(0o750)
            os.chown(ETC, 0, gid)
            LIB.mkdir(mode=0o755)
            created.append(LIB)
            LIB.chmod(0o755)
            shutil.copyfile(binary, LIB / "hysteria")
            (LIB / "hysteria").chmod(0o755)
            run("openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
                "-sha256", "-days", "3650", "-nodes", "-subj", f"/CN={SNI}",
                "-addext", f"subjectAltName=DNS:{SNI}", "-keyout", str(ETC / "server.key"),
                "-out", str(ETC / "server.crt"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            password = secrets.token_urlsafe(32)
            server = {
                "listen": f":{args.port}",
                "tls": {"cert": str(ETC / "server.crt"), "key": str(ETC / "server.key")},
                "auth": {"type": "password", "password": password},
                "masquerade": {"type": "string", "string": {"content": "Not Found", "statusCode": 404}},
            }
            write_json(ETC / "server.json", server, 0o640)
            for name in ("server.json", "server.key", "server.crt"):
                path = ETC / name
                path.chmod(0o640)
                os.chown(path, 0, gid)
            write_json(ETC / "state.json", {"owner": "hy2-easy", "version": VERSION, "host": host, "port": args.port})
            export_files()
            write_private(UNIT, UNIT_TEXT, 0o644)
            created.append(UNIT)
            write_private(CLI, Path(__file__).read_text(encoding="utf-8"), 0o755)
            created.append(CLI)
            run("systemctl", "daemon-reload")
            run("systemctl", "enable", "--now", SERVICE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if not service_ready():
                raise ValueError("服务启动失败，已回滚本次安装")
        except BaseException:
            if UNIT in created:
                subprocess.run(["systemctl", "disable", "--now", SERVICE], capture_output=True)
            for path in reversed(created):
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
            if account_created:
                subprocess.run(["userdel", USER], capture_output=True)
            raise
    print("\n  [3/3] 安装完成 ✓\n")
    print(f"  请确认云服务器已放行 UDP {args.port}。")
    print("  接下来：打开客户端 → 扫码或粘贴下面的链接 → 开启连接。")
    print("  Windows 用户：导入 v2rayN 后，开启「系统代理」。\n")
    share()


def installed_state():
    state = json.loads((ETC / "state.json").read_text())
    if state.get("owner") != "hy2-easy":
        raise ValueError("配置不属于 hy2-easy")
    return state


def export_files():
    state = installed_state()
    server = json.loads((ETC / "server.json").read_text())
    pin = certificate_pin(ETC / "server.crt")
    password = server["auth"]["password"]
    uri = share_uri(state["host"], state["port"], password, pin)
    write_private(ETC / "share.txt", uri + "\n")
    write_json(ETC / "client.json", client_config(state["host"], state["port"], password, pin))
    # QR encoding is entirely local. Credentials never go to an image service.
    png = ETC / "share.png"
    with open(png, "xb") as handle:
        run("qrencode", "-t", "PNG", "-o", "-", input=uri.encode(), stdout=handle)
    png.chmod(0o600)


def share():
    installed_state()
    uri = (ETC / "share.txt").read_text().strip()
    if sys.stdout.isatty():
        run("qrencode", "-t", "ANSIUTF8", input=uri, text=True)
    print("  ── 复制下面这一整行，从 hysteria2:// 开始 ──\n")
    print(uri)
    print("\n  扫不了二维码？复制上面的链接同样可以。")
    print("  以后查看连接信息：sudo hy2-easy")
    print("  使用教程：https://github.com/UncleK/hy2-easy#开始使用")
    print("  请保管好链接和二维码，它们就是你的连接凭据。")


def menu():
    print("\n  hy2-easy · 自己的 VPN，简单连接\n")
    print("  1  连接新设备（显示二维码和链接）")
    print("  2  看看服务是否正常")
    print("  3  查看最近的错误信息")
    print("  4  卸载 hy2-easy")
    print("  0  退出\n")
    choices = {"1": "share", "2": "status", "3": "logs", "4": "uninstall", "0": "exit"}
    while True:
        choice = input("  输入数字并按回车 [1]: ").strip() or "1"
        if choice in choices:
            return choices[choice]
        print("  请输入 0、1、2、3 或 4。")


def uninstall(args):
    installed_state()
    if UNIT.read_text() != UNIT_TEXT or LIB.is_symlink() or ETC.is_symlink():
        raise ValueError("安装文件已被外部修改，停止自动卸载")
    if not args.yes and input("删除 hy2-easy 服务、密码和证书？输入 DELETE 确认: ") != "DELETE":
        print("已取消")
        return
    run("systemctl", "disable", "--now", SERVICE)
    UNIT.unlink()
    run("systemctl", "daemon-reload")
    shutil.rmtree(LIB)
    shutil.rmtree(ETC)
    CLI.unlink()
    run("userdel", USER)
    print("hy2-easy 已卸载。系统依赖和防火墙规则保持原样。")


def main():
    parser = argparse.ArgumentParser(description="hy2-easy · 自己的 VPN，简单连接")
    parser.add_argument("--version", action="version", version=f"hy2-easy {VERSION} / Hysteria {CORE_VERSION}")
    commands = parser.add_subparsers(dest="command")
    setup = commands.add_parser("install", help="安装到一台新的 Linux 服务器")
    setup.add_argument("--host", help="服务器公网 IP 或域名")
    setup.add_argument("--port", type=int, default=24443, help="UDP 端口，默认 24443")
    commands.add_parser("share", help="显示二维码和连接链接")
    commands.add_parser("status", help="查看服务状态")
    commands.add_parser("logs", help="查看最近的本地服务日志")
    remove = commands.add_parser("uninstall", help="卸载服务并删除连接凭据")
    remove.add_argument("--yes", action="store_true", help="确认卸载并删除密码和证书")
    args = parser.parse_args()
    if platform.system() != "Linux" or os.geteuid() != 0:
        parser.error("请在 Linux 服务器上通过 sudo 运行")
    if args.command is None:
        if not sys.stdin.isatty():
            parser.print_help()
            return 0
        args.command = menu()
        args.yes = False
        if args.command == "exit":
            return 0
    os.umask(0o077)
    import fcntl
    # Serialize install/share/removal so partially generated credentials are never read.
    fd = os.open("/run/lock/hy2-easy.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == "install":
            install(args)
        elif args.command == "share":
            share()
        elif args.command == "status":
            return subprocess.run(["systemctl", "status", "--no-pager", SERVICE]).returncode
        elif args.command == "logs":
            return subprocess.run(["journalctl", "-u", SERVICE, "-n", "50", "--no-pager"]).returncode
        elif args.command == "uninstall":
            uninstall(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"hy2-easy: {exc}", file=sys.stderr)
        raise SystemExit(1)
