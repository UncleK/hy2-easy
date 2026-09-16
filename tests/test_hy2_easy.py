import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hy2_easy", ROOT / "scripts/hy2_easy.py")
hy2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hy2)


class ConnectionTests(unittest.TestCase):
    def test_link_roundtrip_ipv6_and_special_password(self):
        password = 'test-only:@/# ?雪'
        pin = "ab" * 32
        parsed = urlsplit(hy2.share_uri("2001:db8::1", 24443, password, pin))
        self.assertEqual(parsed.hostname, "2001:db8::1")
        self.assertEqual(parsed.port, 24443)
        self.assertEqual(unquote(parsed.username), password)
        query = parse_qs(parsed.query)
        self.assertEqual(query["pinSHA256"], [pin])
        self.assertEqual(query["insecure"], ["1"])
        self.assertNotIn("bandwidth", query)

    def test_host_validation(self):
        for bad in ("", "https://example.com", "a/b", "a@b", "example.com:443", "a;id", "a\nb", "999.1.1.1", "fe80::1%eth0", "-example.com"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                hy2.host_name(bad)
        self.assertEqual(hy2.host_name("EXAMPLE.com."), "example.com")
        self.assertEqual(hy2.host_name("[2001:db8::1]"), "2001:db8::1")

    def test_no_unpinned_self_signed_profile(self):
        for pin in ("", "a" * 63, "z" * 64):
            with self.assertRaises(ValueError):
                hy2.share_uri("example.com", 24443, "test-only", pin)

    def test_bad_download_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "hysteria"
            target.write_bytes(b"not-an-upstream-binary")
            with mock.patch.object(hy2, "run"), mock.patch.object(hy2.platform, "machine", return_value="x86_64"):
                with self.assertRaises(ValueError):
                    hy2.core_download(target)
            self.assertFalse(target.exists())

    @unittest.skipUnless(hy2.os.name == "posix", "POSIX permissions")
    def test_private_write_refuses_overwrite_and_has_exact_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "share.txt"
            hy2.write_private(path, "test-only")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                hy2.write_private(path, "other")
            self.assertEqual(path.read_text(), "test-only")

    def test_release_bootstrap_matches_source(self):
        actual = hashlib.sha256((ROOT / "scripts/hy2_easy.py").read_bytes()).hexdigest()
        self.assertIn(f"TOOL_SHA256='{actual}'", (ROOT / "install.sh").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
