#!/usr/bin/env python3
"""Destructive test: run ONLY in a fresh disposable Linux/systemd container."""
import argparse
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from unittest import mock
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
ETC = Path("/etc/hy2-easy")
CORE = Path("/usr/local/lib/hy2-easy/hysteria")
TOKEN = b"hy2-easy-real-quic-end-to-end"


def command(*args, ok=True):
    result = subprocess.run(args, capture_output=True, text=True, timeout=420)
    if ok and result.returncode:
        # Installation stdout contains an ephemeral password, so never dump it.
        raise AssertionError(f"Command failed: {args[0]} (exit {result.returncode}); private output withheld")
    return result


class Target(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(TOKEN)))
        self.end_headers()
        self.wfile.write(TOKEN)

    def log_message(self, *_):
        pass


def client_probe(config, temp, target_port, success):
    cfg = temp / "client.json"
    cfg.write_text(json.dumps(config))
    cfg.chmod(0o600)
    with open(temp / "client.log", "w") as logs:
        client = subprocess.Popen([str(CORE), "client", "--disable-update-check", "--config", str(cfg)], stdout=logs, stderr=logs)
        try:
            result = None
            for _ in range(30):
                result = subprocess.run([
                    "curl", "--silent", "--show-error", "--max-time", "1", "--noproxy", "",
                    "--proxy", "http://127.0.0.1:18080", f"http://127.0.0.1:{target_port}/",
                ], capture_output=True)
                if result.returncode == 0 and result.stdout == TOKEN:
                    break
                if client.poll() is not None:
                    break
                time.sleep(0.1)
            if success:
                assert result and result.returncode == 0 and result.stdout == TOKEN, "Real QUIC proxy request failed"
            else:
                assert not (result and result.returncode == 0 and result.stdout == TOKEN), "Invalid identity was accepted"
                assert client.wait(timeout=15) != 0, "Invalid client did not fail closed"
        finally:
            if client.poll() is None:
                client.terminate()
            client.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disposable-container", action="store_true", required=True)
    args = parser.parse_args()
    assert args.disposable_container and Path("/.dockerenv").exists(), "Fresh Docker container required"
    assert not ETC.exists(), "Refusing to test an existing installation"
    os.umask(0o077)
    spec = importlib.util.spec_from_file_location("hy2_easy", ROOT / "scripts/hy2_easy.py")
    hy2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hy2)
    target = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Target)
    threading.Thread(target=target.serve_forever, daemon=True).start()
    try:
        # systemd-tmpfiles may still be cleaning /tmp just after container boot.
        with tempfile.TemporaryDirectory(prefix="hy2-easy-e2e-", dir="/root") as directory:
            temp = Path(directory)
            # Exercise the standalone download path before publishing a tag.
            # Only the fixed-tag source fetch is served locally; core downloads
            # still use the real HTTPS endpoint and the pinned digest.
            bootstrap = temp / "install.sh"
            shutil.copyfile(ROOT / "install.sh", bootstrap)
            shim = temp / "bin"
            shim.mkdir()
            expected_url = f"https://raw.githubusercontent.com/UncleK/hy2-easy/v{hy2.VERSION}/scripts/hy2_easy.py"
            wrapper = shim / "curl"
            wrapper.write_text(
                "#!/usr/bin/python3\nimport os,sys,shutil\n"
                "args=sys.argv[1:]\n"
                "urls=[a for a in args if a.startswith('https://raw.githubusercontent.com/')]\n"
                "if urls:\n"
                f" assert urls == [{expected_url!r}], 'Wrong release URL after OS detection'\n"
                f" shutil.copyfile({str(ROOT / 'scripts/hy2_easy.py')!r}, args[args.index('-o')+1])\n"
                "else:\n os.execv('/usr/bin/curl', ['/usr/bin/curl', *args])\n"
            )
            wrapper.chmod(0o755)
            old_path = os.environ["PATH"]
            try:
                os.environ["PATH"] = str(shim) + ":" + old_path
                command("bash", str(bootstrap), "--host", "127.0.0.1")
            finally:
                os.environ["PATH"] = old_path
            print("PASS: standalone bootstrap URL + checksum + real systemd start", flush=True)
            command("systemctl", "is-enabled", "hy2-easy")
            command("systemctl", "is-active", "hy2-easy")
            for name in ("share.txt", "share.png", "client.json", "state.json"):
                assert (ETC / name).stat().st_mode & 0o777 == 0o600, name
            for name in ("server.key", "server.json", "server.crt"):
                assert (ETC / name).stat().st_mode & 0o777 == 0o640, name
            assert ETC.stat().st_mode & 0o777 == 0o750
            assert command("runuser", "-u", "hy2-easy", "--", "cat", str(ETC / "share.txt"), ok=False).returncode != 0
            pid = int(command("systemctl", "show", "hy2-easy", "-p", "MainPID", "--value").stdout)
            status = Path(f"/proc/{pid}/status").read_text()
            assert "CapEff:\t0000000000000000" in status
            print("PASS: private credentials + non-root service without capabilities", flush=True)
            uri = (ETC / "share.txt").read_text().strip()
            decoded = command("zbarimg", "--quiet", "--raw", str(ETC / "share.png")).stdout.strip()
            assert decoded == uri
            print("PASS: QR decoded to the exact connection URI", flush=True)
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ETC.iterdir()}
            assert command("bash", str(ROOT / "install.sh"), "--host", "127.0.0.2", ok=False).returncode != 0
            after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ETC.iterdir()}
            assert before == after
            command("hy2-easy", "status")
            command("hy2-easy", "logs")
            assert uri in command("hy2-easy", "share").stdout
            print("PASS: repeat install preserves all files; management commands work", flush=True)
            config = json.loads((ETC / "client.json").read_text())
            config["http"]["listen"] = "127.0.0.1:18080"
            config.pop("socks5")
            client_probe(config, temp, target.server_port, True)
            print("PASS: generated client config -> QUIC -> HTTP target", flush=True)
            link_config = {"server": uri, "http": {"listen": "127.0.0.1:18080"}}
            client_probe(link_config, temp, target.server_port, True)
            print("PASS: share URI consumed by official core -> QUIC -> HTTP target", flush=True)
            parsed = urlsplit(uri)
            query = parse_qs(parsed.query)
            query["pinSHA256"] = ["0" * 64]
            bad_pin = urlunsplit(parsed._replace(query=urlencode(query, doseq=True)))
            client_probe({**link_config, "server": bad_pin}, temp, target.server_port, False)
            bad_auth = urlunsplit(parsed._replace(netloc="invalid-test-password@" + parsed.netloc.split("@", 1)[1]))
            client_probe({**link_config, "server": bad_auth}, temp, target.server_port, False)
            print("PASS: wrong certificate pin and wrong password both rejected", flush=True)
            command("systemctl", "restart", "hy2-easy")
            time.sleep(1)
            client_probe(link_config, temp, target.server_port, True)
            print("PASS: restart retains a working client identity", flush=True)
            saved_core = temp / "hysteria"
            shutil.copy2(CORE, saved_core)
            command("hy2-easy", "uninstall", "--yes")
            for path in (hy2.ETC, hy2.LIB, hy2.CLI, hy2.UNIT):
                assert not path.exists(), path
            assert command("getent", "passwd", "hy2-easy", ok=False).returncode != 0
            assert command("getent", "group", "hy2-easy", ok=False).returncode != 0
            print("PASS: uninstall removes only the managed service/files/account", flush=True)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as occupied:
                occupied.bind(("0.0.0.0", 24443))
                try:
                    hy2.install(argparse.Namespace(host="127.0.0.1", port=24443))
                except ValueError:
                    pass
                else:
                    raise AssertionError("Occupied port accepted")
            assert not hy2.ETC.exists()
            print("PASS: port conflict refused before installation", flush=True)
            with mock.patch.object(hy2, "core_download", side_effect=lambda dest: shutil.copy2(saved_core, dest)), \
                    mock.patch.object(hy2, "service_ready", return_value=False):
                try:
                    hy2.install(argparse.Namespace(host="127.0.0.1", port=24443))
                except ValueError:
                    pass
                else:
                    raise AssertionError("Injected startup failure accepted")
            for path in (hy2.ETC, hy2.LIB, hy2.CLI, hy2.UNIT):
                assert not path.exists(), path
            assert command("getent", "passwd", "hy2-easy", ok=False).returncode != 0
            print("PASS: injected startup failure rolls back files/service/account", flush=True)
    finally:
        target.shutdown()


if __name__ == "__main__":
    main()
