"""Authorized live path exercised with synthetic HTML and mocked HTTPS only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import socket
import ssl
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/family-tree-chatgpt/scripts"))
import mza
import mza_live
import research
from test_mza import BASE, URL, MockServer, metadata

LIVE_BASE = "https://iipserver.mza.cz/iipsrv//iipsrv.fcgi?IIIF=/srv/SYNTHETIC/synthetic-001.jp2"


class LiveMock:
    def __init__(self, *, tiled=False, version=3):
        info = metadata(version, tiled)
        info["id" if version == 3 else "@id"] = LIVE_BASE
        self.server = MockServer(info)
        self.calls = []

    def __call__(self, url, **options):
        self.calls.append(url)
        if url == URL:
            html = '<html><script>source="' + LIVE_BASE.replace("?IIIF=", "?Deepzoom=") + '";</script></html>'
            return 200, {"Content-Type": "text/html"}, html.encode()
        return self.server(url.replace(LIVE_BASE, BASE), **options)


class LiveMZATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        lock_patch = patch.object(mza_live, "LOCK_FILE", self.base / "global-mza.lock")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)
        self.root = self.base / "private"
        research.initialize(self.root)
        self.permission = self.base / "permission.json"
        self.declaration = {
            "schema_version": 1, "archive": "mza", "basis": "user_attestation",
            "scope": "single_image", "statement": "SYNTHETIC consent for IIIF",
            "evidence_reference": "SYNTHETIC test declaration", "recorded_at": research.now(),
            "min_interval_seconds": 2,
        }
        self.write_permission()

    def write_permission(self):
        self.permission.write_text(json.dumps(self.declaration))
        self.permission.chmod(0o600)

    def acquire(self, server=None, **options):
        return mza.download(URL, self.root, permission_file=self.permission,
                            transport=server or LiveMock(), sleep=Mock(), **options)

    def test_live_full_and_tiles_api2_api3_import_and_transfer(self):
        for version in (2, 3):
            for tiled in (False, True):
                with self.subTest(version=version, tiled=tiled):
                    root = self.base / f"project-{version}-{tiled}"
                    research.initialize(root)
                    server = LiveMock(version=version, tiled=tiled)
                    result = mza.download(URL, root, permission_file=self.permission,
                                          transport=server, sleep=Mock(), image_number=167)
                    self.assertTrue(result["downloaded"])
                    self.assertEqual(result["request_count"], 14 if tiled else 3)
                    self.assertEqual((result["acquisition"]["width"], result["acquisition"]["height"]), (517, 389))
                    acquisition = research.read_state(root)["records"][result["record_id"]]["source"]["acquisition"]
                    self.assertEqual(acquisition["permission"]["sha256"], research.sha256(self.permission))
                    self.assertEqual(acquisition["permission"]["basis"], "user_attestation")
                    self.assertEqual(acquisition["iiif"]["info_url"], LIVE_BASE + "/info.json")
                    self.assertFalse(acquisition["iiif"]["live_access_verified"])
                    self.assertFalse(result["iiif"]["live_mza_verified"])
                    self.assertEqual(acquisition["method"], "iiif_assembled")
                    bundle = self.base / f"bundle-{version}-{tiled}.zip"
                    research.export_bundle(root, bundle)
                    restored = self.base / f"restored-{version}-{tiled}"
                    research.restore_bundle(restored, bundle)
                    self.assertEqual(research.read_state(restored), research.read_state(root))
                    self.assertFalse(list(root.glob(".mza-acquisition-*")))

    def test_duplicate_download_uses_local_copy_without_network(self):
        self.acquire()
        transport = Mock(side_effect=AssertionError("network"))
        result = self.acquire(transport)
        self.assertFalse(result["network_accessed"])
        self.assertTrue(result["already_stored"])
        transport.assert_not_called()

    def test_missing_expired_insecure_and_invalid_permission_fail_before_network(self):
        original = deepcopy(self.declaration)
        for changes in ({"scope": "all_books"}, {"basis": "flag"}, {"statement": ""},
                        {"evidence_reference": ""}, {"min_interval_seconds": 0},
                        {"min_interval_seconds": float("nan")},
                        {"expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}):
            self.declaration = {**original, **changes}
            self.write_permission()
            server = Mock(side_effect=AssertionError("network"))
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.acquire(server)
            server.assert_not_called()
        self.declaration = original
        self.write_permission()
        self.permission.chmod(0o644)
        with self.assertRaises(ValueError):
            self.acquire(Mock(side_effect=AssertionError("network")))
        self.permission.unlink()
        with self.assertRaises(ValueError):
            self.acquire(Mock(side_effect=AssertionError("network")))

    def test_permission_symlink_and_git_file_rejected(self):
        linked = self.base / "linked.json"
        linked.symlink_to(self.permission)
        with self.assertRaises(ValueError):
            mza_live.load_permission(linked)
        with patch.object(research, "in_git_tree", return_value=True), self.assertRaises(ValueError):
            mza_live.load_permission(self.permission)

    def test_forbidden_status_and_challenge_never_query_image_service(self):
        for response in ((403, {}, b""), (429, {}, b""), (302, {"location": LIVE_BASE}, b""),
                         (200, {"content-type": "text/html"}, b"<html><altcha-widget></altcha-widget></html>")):
            server = Mock(return_value=response)
            with self.subTest(status=response[0]), self.assertRaises(ValueError):
                self.acquire(server)
            self.assertEqual(server.call_count, 1)
            self.assertFalse(list((self.root / "sources").iterdir()))

    def test_discovery_exact_match_escaping_and_no_filename_substitution(self):
        html = '<script>source="' + LIVE_BASE.replace("IIIF=", "Deepzoom=").replace("/", "\\/") + '";</script>'
        self.assertEqual(mza_live.discover_service(html, URL), LIVE_BASE)
        for text in (html.replace("synthetic-001", "other"), "<html>no source</html>",
                     html.replace("iipserver.mza.cz", "localhost"), html + html.replace("SYNTHETIC", "OTHER")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                mza_live.discover_service(text, URL)

    def test_bad_url_stale_revision_and_invalid_workspace_fail_before_network(self):
        server = Mock(side_effect=AssertionError("network"))
        with self.assertRaises(ValueError):
            self.acquire(server, expected_revision=42)
        with self.assertRaises(ValueError):
            self.acquire(server, image_number=0)
        with self.assertRaises(ValueError):
            mza.download(URL.split("?")[0], self.root, permission_file=self.permission, transport=server)
        with self.assertRaises(ValueError):
            mza.download(URL.replace("www.mza.cz", "localhost"), self.root,
                         permission_file=self.permission, transport=server)
        server.assert_not_called()

    def test_complete_copy_survives_failed_import(self):
        with patch.object(mza, "import_image", side_effect=ValueError("state changed")):
            with self.assertRaisesRegex(ValueError, "úplná kopie zůstává"):
                self.acquire()
        copies = list(self.root.glob(".mza-acquisition-*/scan.png"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(mza.image_info(copies[0])["width"], 517)
        self.assertEqual(research.read_state(self.root)["revision"], 0)

    def test_permission_and_iiif_metadata_corruption_is_rejected(self):
        result = self.acquire()
        state = research.read_state(self.root)
        for field, value in (("permission", {}), ("iiif", {}), ("iiif", {"info_url": "https://localhost/info.json"})):
            broken = deepcopy(state)
            broken["records"][result["record_id"]]["source"]["acquisition"][field] = value
            with self.subTest(field=field, value=value):
                self.assertTrue(research.check_state(broken, self.root))

    def test_challenge_late_in_html_stops_before_image_discovery(self):
        server = Mock(return_value=(200, {"Content-Type": "text/html"}, b"x" * 70000 + b"<altcha-widget></altcha-widget>"))
        with self.assertRaises(ValueError):
            self.acquire(server)
        self.assertEqual(server.call_count, 1)

    def test_global_lock_prevents_parallel_downloads_and_cleans_after_error(self):
        server = Mock(side_effect=AssertionError("network"))
        with mza_live.acquisition_lock(), self.assertRaisesRegex(ValueError, "zámek"):
            self.acquire(server)
        server.assert_not_called()
        self.assertFalse(mza_live.LOCK_FILE.exists())
        self.acquire()
        self.assertFalse(mza_live.LOCK_FILE.exists())

    def test_download_continues_past_benign_captcha_script_references(self):
        original = LiveMock()
        def server(url, **options):
            status, headers, body = original(url, **options)
            if url == URL:
                body += b'<script src="/js/altcha.js"></script><script>var captcha = true;</script>'
            return status, headers, body
        self.assertTrue(self.acquire(server)["downloaded"])
        self.assertEqual(len(original.calls), 3)

    def test_diagnostics_saved_before_block_without_credential_headers(self):
        directory = self.base / "diagnostics"
        server = Mock(return_value=(200, {
            "Content-Type": "text/html", "Set-Cookie": "secret-session", "Authorization": "secret-auth",
        }, b'<html><meta name="csrf-token" content="secret-meta"><input value="secret-csrf" name="csrf_token"><altcha-widget></altcha-widget></html>'))
        with self.assertRaisesRegex(ValueError, "active_challenge.*Diagnostika"):
            self.acquire(server, diagnostics_dir=directory)
        self.assertEqual(server.call_count, 1)
        metadata = json.loads((directory / "response-0001.metadata.json").read_text())
        self.assertEqual(metadata["diagnosis"]["signals"], ["altcha_widget"])
        self.assertEqual(metadata["status"], 200)
        self.assertTrue(metadata["redacted"])
        contents = b"\n".join(path.read_bytes() for path in directory.iterdir())
        for secret in (b"secret-session", b"secret-auth", b"secret-csrf", b"secret-meta"):
            self.assertNotIn(secret, contents)
        self.assertIn(b"[REDACTED]", contents)
        for path in directory.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads((directory / "attempt.json").read_text())["responses"], 1)

    def test_successful_diagnostics_capture_all_responses_and_never_overwrite(self):
        directory = self.base / "diagnostics"
        result = self.acquire(diagnostics_dir=directory)
        self.assertEqual(result["diagnostics_dir"], str(directory))
        self.assertEqual(len(list(directory.glob("*.metadata.json"))), 3)
        self.assertEqual(json.loads((directory / "attempt.json").read_text())["error"], None)
        with self.assertRaises(FileExistsError):
            mza_live.ResponseDiagnostics(directory)
        with patch.object(research, "in_git_tree", return_value=True), self.assertRaises(ValueError):
            mza_live.ResponseDiagnostics(self.base / "repo-diagnostics")

    def test_malformed_deep_html_is_saved_without_claiming_a_challenge(self):
        directory = self.base / "deep-html"
        server = Mock(return_value=(200, {"Content-Type": "text/html"}, b"<div>" * 513))
        with self.assertRaisesRegex(ValueError, "vnoření.*Diagnostika"):
            self.acquire(server, diagnostics_dir=directory)
        metadata = json.loads((directory / "response-0001.metadata.json").read_text())
        self.assertEqual(metadata["diagnosis"]["classification"], "html_parse_error")
        self.assertEqual(metadata["diagnosis"]["signals"], [])
        self.assertEqual(server.call_count, 1)

    def test_diagnostic_mode_reads_block_body_but_does_not_follow_redirect(self):
        connection = Mock()
        response = connection.getresponse.return_value
        response.status = 403
        response.getheaders.return_value = [("Content-Type", "text/html"), ("Content-Length", "4")]
        response.read.side_effect = [b"deny", b""]
        with patch.object(mza_live, "public_addresses", return_value=["8.8.8.8"]), \
                patch("http.client.HTTPSConnection", return_value=connection) as factory:
            result = mza_live.HTTPSTransport(capture_error_body=True)(URL, timeout=15, max_bytes=4096)
        self.assertEqual(result, (403, {"content-type": "text/html", "content-length": "4"}, b"deny"))
        self.assertEqual(factory.call_count, 1)

    def test_revocation_between_requests_stops_before_image_service(self):
        original = LiveMock()
        def revoke(url, **options):
            result = original(url, **options)
            self.permission.unlink()
            return result
        with self.assertRaises(ValueError):
            self.acquire(revoke)
        self.assertEqual(len(original.calls), 1)

    def test_transfer_budget_counts_bytes_before_timeout(self):
        connection = Mock()
        response = connection.getresponse.return_value
        response.status = 200
        response.getheaders.return_value = []
        response.read.side_effect = [b"123", TimeoutError()]
        client = mza_live.HTTPSTransport()
        with patch.object(mza_live, "public_addresses", return_value=["8.8.8.8"]), \
                patch("http.client.HTTPSConnection", return_value=connection), self.assertRaises(TimeoutError):
            client(URL, timeout=15, max_bytes=10)
        self.assertEqual(client.transferred, 3)
        response.getheaders.return_value = [("Content-Length", "3")]
        response.read.reset_mock()
        with patch.object(mza, "MAX_TRANSFER_BYTES", 5), \
                patch.object(mza_live, "public_addresses", return_value=["8.8.8.8"]), \
                patch("http.client.HTTPSConnection", return_value=connection), self.assertRaises(ValueError):
            client(URL, timeout=15, max_bytes=10)
        response.read.assert_not_called()

    def test_dns_and_domain_policy_rejects_ssrf(self):
        for ip in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:8.8.8.8"):
            answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]
            with self.subTest(ip=ip), patch("socket.getaddrinfo", return_value=answers), self.assertRaises(ValueError):
                mza_live.public_addresses("iipserver.mza.cz")
        for url in (LIVE_BASE.replace("https:", "http:"), LIVE_BASE + "&token=secret",
                    LIVE_BASE.replace("/SYNTHETIC/", "/../"), LIVE_BASE.replace(".mza.cz", ".mza.cz.evil.test"),
                    LIVE_BASE.replace("/SYNTHETIC/", "/%252e%252e/"), "https://www.mza.cz/admin"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                mza_live.live_url(url)

    def test_https_pins_ip_preserves_tls_hostname_and_limits_response(self):
        response = Mock(status=200)
        response.getheaders.return_value = [("Content-Length", "2")]
        response.read.side_effect = [b"OK", b""]
        connection = Mock()
        connection.getresponse.return_value = response
        connection.sock.fileno.return_value = 3
        def request(*args, **kwargs):
            connection._create_connection(("www.mza.cz", 443), 15)
        connection.request.side_effect = request
        with patch.object(mza_live, "public_addresses", return_value=["8.8.8.8"]), \
                patch("http.client.HTTPSConnection", return_value=connection) as factory, \
                patch("socket.create_connection") as tcp:
            result = mza_live.HTTPSTransport()(URL, timeout=15, max_bytes=10)
        self.assertEqual(result[2], b"OK")
        self.assertEqual(factory.call_args.args[0], "www.mza.cz")
        context = factory.call_args.kwargs["context"]
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(tcp.call_args.args[0], ("8.8.8.8", 443))
        connection.close.assert_called_once()

    def test_https_never_reads_block_response_or_disables_tls(self):
        connection = Mock()
        response = connection.getresponse.return_value
        response.status = 403
        response.getheaders.return_value = []
        with patch.object(mza_live, "public_addresses", return_value=["8.8.8.8"]), \
                patch("http.client.HTTPSConnection", return_value=connection):
            self.assertEqual(mza_live.HTTPSTransport()(URL, timeout=15, max_bytes=10)[0], 403)
        response.read.assert_not_called()
        connection.request.side_effect = ssl.SSLCertVerificationError("untrusted")
        with patch.object(mza_live, "public_addresses", return_value=["8.8.8.8"]), \
                patch("http.client.HTTPSConnection", return_value=connection), self.assertRaisesRegex(ValueError, "TLS"):
            mza_live.HTTPSTransport()(URL, timeout=15, max_bytes=10)

    def test_https_declared_and_streamed_limits_truncation(self):
        for headers, chunks in (([("Content-Length", "999")], []), ([], [b"12345"]),
                                ([("Content-Length", "4")], [b"x", b""])):
            connection = Mock()
            response = connection.getresponse.return_value
            response.status = 200
            response.getheaders.return_value = headers
            response.read.side_effect = chunks
            with self.subTest(headers=headers), patch.object(mza_live, "public_addresses", return_value=["8.8.8.8"]), \
                    patch("http.client.HTTPSConnection", return_value=connection), self.assertRaises(ValueError):
                mza_live.HTTPSTransport()(URL, timeout=15, max_bytes=4)


if __name__ == "__main__":
    unittest.main()
