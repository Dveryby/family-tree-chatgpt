"""Synthetic images and a mock IIIF/HTTP server; never contact MZA."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image, features

REPO = Path(__file__).resolve().parents[1]
SKILL = Path(os.environ.get("FAMILY_TREE_SKILL", REPO / "skills/family-tree-chatgpt"))
sys.path.insert(0, str(SKILL / "scripts"))
import mza
import research

URL = "https://www.mza.cz/actapublica/matrika/detail/999999?image=synthetic-001.jp2"
BASE = "https://iiif.example.invalid/synthetic"


def metadata(version=3, tiled=True):
    value = {
        "@context": f"http://iiif.io/api/image/{version}/context.json",
        "protocol": "http://iiif.io/api/image", "width": 517, "height": 389,
        "profile": "level1" if version == 3 else ["http://iiif.io/api/image/2/level1.json"],
        "tiles": [{"width": 173, "height": 127, "scaleFactors": [1, 2, 4]}],
        "id" if version == 3 else "@id": BASE,
    }
    if tiled:
        value.update(maxWidth=173, maxHeight=127)
    if version == 3:
        value["type"] = "ImageService3"
    return value


class MockServer:
    """Bounded byte responses, including generated JPEG tiles and HTTP failures."""

    def __init__(self, info=None):
        self.info = info or metadata()
        self.calls = []
        self.responses = []
        self.tiles = []

    def __call__(self, url, *, timeout, max_bytes):
        self.calls.append((url, timeout, max_bytes))
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        if url.endswith("/info.json"):
            return 200, {"Content-Type": "application/json"}, json.dumps(self.info).encode()
        region = url.removeprefix(BASE + "/").split("/")[0]
        if region == "full":
            x, y, w, h = 0, 0, self.info["width"], self.info["height"]
        else:
            x, y, w, h = map(int, region.split(","))
        with Image.new("RGB", (w, h), (x % 256, y % 256, (x + y) % 256)) as tile:
            stream = BytesIO()
            tile.save(stream, format="JPEG")
        payload = stream.getvalue()
        self.tiles.append(((x, y, w, h), payload))
        return 200, {"Content-Type": "image/jpeg"}, payload


class MZAImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "private"
        research.initialize(self.root)
        self.scan = self.base / "synthetic.png"
        Image.new("RGB", (2101, 1703), "white").save(self.scan)

    def cli(self, *args, workspace=True, ok=True):
        command = [sys.executable, str(SKILL / "scripts/family_tree.py")]
        if workspace:
            command += ["--workspace", str(self.root)]
        run = subprocess.run(command + list(map(str, args)), capture_output=True, text=True)
        if ok:
            self.assertEqual(run.returncode, 0, run.stderr)
            return json.loads(run.stdout)
        self.assertNotEqual(run.returncode, 0)
        self.assertNotIn("Traceback", run.stderr)
        return run.stderr

    def test_cli_import_preserves_bytes_metadata_and_unread(self):
        result = self.cli("archive", "mza", "import", self.scan, "--url", URL,
                          "--method", "browser_download", "--reference", "SYNTHETIC",
                          "--image-number", 167, "--acquired-at", "2026-11-14T10:00:00+01:00")
        self.assertTrue(result["imported"])
        stored = self.root / result["file"]
        self.assertEqual(stored.read_bytes(), self.scan.read_bytes())
        self.assertEqual(stat.S_IMODE(stored.stat().st_mode), 0o600)
        acquisition = result["acquisition"]
        self.assertEqual((acquisition["width"], acquisition["height"]), (2101, 1703))
        self.assertEqual(acquisition["format"], "PNG")
        self.assertEqual(acquisition["sha256"], hashlib.sha256(self.scan.read_bytes()).hexdigest())
        self.assertEqual(acquisition["size_bytes"], stored.stat().st_size)
        self.assertEqual(acquisition["image_number"], 167)
        self.assertEqual(acquisition["digital_copy"], "derived")
        record = research.read_state(self.root)["records"][result["record_id"]]
        self.assertEqual(record["reading_status"], "unread")
        self.assertFalse(record["visual_review"])
        self.assertEqual(record["identity"]["status"], "unresolved")
        self.assertFalse(research.read_state(self.root)["claims"])
        self.assertTrue(self.cli("project", "check")["valid"])

    def test_duplicate_is_idempotent_and_does_not_erase_reading(self):
        first = mza.import_image(self.root, self.scan, URL)
        state = research.read_state(self.root)
        record = state["records"][first["record_id"]]
        record["reading_status"] = "draft"
        record["transcription"] = "SYNTHETIC"
        research.update(self.root, 1, record=record, next_step="SYNTHETIC")
        before = (self.root / "research.json").read_bytes()
        result = mza.import_image(self.root, self.scan, URL)
        self.assertTrue(result["duplicate"])
        self.assertFalse(result["imported"])
        self.assertEqual((self.root / "research.json").read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "jinými metadaty"):
            mza.import_image(self.root, self.scan, URL, reference="Changed")

    def test_same_bytes_with_new_url_keep_both_provenances_and_one_file(self):
        first = mza.import_image(self.root, self.scan, URL)
        second = mza.import_image(self.root, self.scan, URL.replace("001.jp2", "002.jp2"))
        self.assertNotEqual(first["record_id"], second["record_id"])
        self.assertEqual(first["file"], second["file"])
        self.assertEqual(len(research.read_state(self.root)["records"]), 2)

    def test_same_url_with_different_bytes_keeps_both_copies(self):
        first = mza.import_image(self.root, self.scan, URL)
        Image.new("RGB", (21, 17), "red").save(self.scan)
        second = mza.import_image(self.root, self.scan, URL)
        self.assertNotEqual(first["file"], second["file"])
        self.assertEqual(len(mza.inspect(URL, self.root)["matches"]), 2)

    def test_supported_formats_preserve_bytes_and_use_real_extension(self):
        formats = ["JPEG", "PNG", "TIFF"]
        if features.check("jpg_2000"):
            formats.append("JPEG2000")
        for fmt in formats:
            with self.subTest(format=fmt):
                # Deliberately misleading input extension, never trust filenames.
                path = self.base / (fmt + ".bin")
                Image.new("RGB", (31, 23), "blue").save(path, format=fmt)
                result = mza.import_image(self.root, path, URL)
                self.assertEqual(result["acquisition"]["format"], fmt)
                self.assertTrue(result["file"].endswith(mza.FORMATS[fmt]))
                self.assertEqual((self.root / result["file"]).read_bytes(), path.read_bytes())
        pages = self.base / "multipage.tif"
        with Image.new("RGB", (31, 23)) as image:
            image.save(pages, save_all=True, append_images=[image])
        with self.assertRaisesRegex(ValueError, "jeden snímek"):
            mza.import_image(self.root, pages, URL)

    def test_record_id_collision_and_import_publication_race(self):
        first = mza.import_image(self.root, self.scan, URL)
        state = research.read_state(self.root)
        state["records"][first["record_id"]]["source"].pop("acquisition")
        research.atomic_json(self.root / "research.json", state)
        with self.assertRaisesRegex(ValueError, "jiný záznam"):
            mza.import_image(self.root, self.scan, URL)
        before = (self.root / "research.json").read_bytes()
        Image.new("RGB", (11, 9), "red").save(self.scan)
        def race(staged, target):
            target.write_bytes(b"racing file")
            os.link(staged, target)
        with patch.object(mza, "publish_new", side_effect=race), self.assertRaises(FileExistsError):
            mza.import_image(self.root, self.scan, URL)
        self.assertEqual((self.root / "research.json").read_bytes(), before)
        digest = research.sha256(self.scan)
        self.assertEqual((self.root / f"sources/mza-{digest}.png").read_bytes(), b"racing file")

    def test_inspect_rejects_plausible_but_false_dimensions(self):
        result = mza.import_image(self.root, self.scan, URL)
        state = research.read_state(self.root)
        state["records"][result["record_id"]]["source"]["acquisition"]["width"] = 2000
        research.atomic_json(self.root / "research.json", state)
        with self.assertRaisesRegex(ValueError, "metadata nesouhlasí"):
            mza.inspect(URL, self.root)

    def test_existing_file_cannot_be_overwritten(self):
        digest = research.sha256(self.scan)
        target = self.root / f"sources/mza-{digest}.png"
        target.write_bytes(b"EXISTING")
        with self.assertRaises(FileExistsError):
            mza.import_image(self.root, self.scan, URL)
        self.assertEqual(target.read_bytes(), b"EXISTING")
        self.assertEqual(research.read_state(self.root)["revision"], 0)
        self.assertFalse(list(self.root.glob("sources/.mza-*")))

    def test_failed_state_write_rolls_back_new_file(self):
        with patch.object(research, "backup_and_write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                mza.import_image(self.root, self.scan, URL)
        self.assertFalse(list((self.root / "sources").iterdir()))
        self.assertEqual(research.read_state(self.root)["revision"], 0)

    def test_changed_source_fails_check_and_inspect(self):
        result = mza.import_image(self.root, self.scan, URL)
        (self.root / result["file"]).write_bytes(b"CHANGED")
        self.assertTrue(research.check_state(research.read_state(self.root), self.root))
        with self.assertRaises(ValueError):
            mza.inspect(URL, self.root)

    def test_inspect_matches_url_and_hash_without_network(self):
        mza.import_image(self.root, self.scan, URL)
        before = (self.root / "research.json").read_bytes()
        with patch("socket.create_connection", side_effect=AssertionError("network")):
            result = mza.inspect(URL, self.root, self.scan)
            other = mza.inspect(URL.replace("001.jp2", "other.jp2"), self.root, self.scan)
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(len(other["matches"]), 1)
        self.assertEqual(result["matches"][0]["width"], 2101)
        self.assertFalse(result["network_accessed"])
        self.assertFalse(result["download_allowed"])
        self.assertEqual((self.root / "research.json").read_bytes(), before)

    def test_no_workspace_inspect_and_disabled_downloader(self):
        result = self.cli("archive", "mza", "inspect", "--url", URL, workspace=False)
        self.assertFalse(result["network_accessed"])
        with patch("socket.create_connection", side_effect=AssertionError("network")):
            with self.assertRaisesRegex(ValueError, "není povoleno"):
                mza.download(URL)
        self.assertIn("není povoleno", self.cli("archive", "mza", "download", "--url", URL, workspace=False, ok=False))
        self.assertIn("unrecognized arguments", self.cli("archive", "mza", "download", "--url", URL,
                                                       "--enable-download", workspace=False, ok=False))

    def test_missing_fields_are_unknown_and_derived_is_never_original(self):
        result = mza.import_image(self.root, self.scan, URL, method="screenshot")
        self.assertEqual(result["acquisition"]["digital_copy"], "derived")
        self.assertIsNone(result["acquisition"]["image_number"])
        self.assertEqual(result["acquisition"]["reference"], "")
        for method in ("screenshot", "iiif_assembled", "manual_import", "browser_download"):
            with self.subTest(method=method), self.assertRaises(ValueError):
                mza.import_image(self.root, self.scan, URL, method=method, digital_copy="original")

    def test_archival_original_requires_evidence(self):
        with self.assertRaises(ValueError):
            mza.import_image(self.root, self.scan, URL, method="archival_copy", digital_copy="original")
        result = mza.import_image(self.root, self.scan, URL, method="archival_copy",
                                  digital_copy="original", provenance_note="SYNTHETIC receipt")
        self.assertEqual(result["acquisition"]["digital_copy"], "original")

    def test_invalid_inputs_stale_revision_and_unsafe_paths(self):
        linked = self.base / "linked.png"
        linked.symlink_to(self.scan)
        corrupt = self.base / "broken.jpg"
        corrupt.write_bytes(b"not an image")
        for path in (linked, corrupt):
            with self.subTest(path=path), self.assertRaises(ValueError):
                mza.import_image(self.root, path, URL)
        for options in ({"image_number": 0}, {"acquired_at": "2026-11-14"}, {"method": "fake"},
                        {"expected_revision": 10}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                mza.import_image(self.root, self.scan, URL, **options)
        with patch.object(mza, "MAX_FILE_BYTES", 10), self.assertRaises(ValueError):
            mza.import_image(self.root, self.scan, URL)
        with patch.object(mza, "MAX_PIXELS", 10), self.assertRaises(ValueError):
            mza.import_image(self.root, self.scan, URL)
        (self.root / "sources").rmdir()
        (self.root / "sources").symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(ValueError):
            mza.import_image(self.root, self.scan, URL)

    def test_git_source_and_destination_rejected(self):
        repo = self.base / "code"
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        copied = repo / "synthetic.png"
        copied.write_bytes(self.scan.read_bytes())
        with self.assertRaises(ValueError):
            mza.import_image(self.root, copied, URL)
        with self.assertRaises(ValueError):
            mza.import_image(repo, self.scan, URL)

    def test_export_restore_and_all_image_commands(self):
        result = self.cli("archive", "mza", "import", self.scan, "--url", URL)
        original = self.root / result["file"]
        self.cli("image", "crop", original, self.root / "crops/crop.png", "--box", "0,0,1,1")
        self.cli("image", "split", original, self.root / "crops/a.png", self.root / "crops/b.png")
        self.cli("image", "mark", original, self.root / "crops/mark.png", "--box", "0.1,0.1,0.9,0.9")
        self.cli("image", "sheet", self.root / "crops/sheet.png", original)
        bundle = self.base / "bundle.zip"
        self.cli("project", "export", bundle)
        restored = self.base / "restored"
        research.restore_bundle(restored, bundle)
        self.assertEqual(research.read_state(restored), research.read_state(self.root))
        self.assertEqual((restored / result["file"]).read_bytes(), self.scan.read_bytes())
        self.assertFalse(research.check_state(research.read_state(restored), restored))
        self.assertEqual(mza.inspect(URL, restored)["matches"][0]["width"], 2101)
        research.update(restored, 1, result="note", scope="SYNTHETIC continuation", next_step="SYNTHETIC")

    def test_schema_one_and_legacy_cli_remain_usable(self):
        state = research.read_state(self.root)
        state["schema_version"] = 1
        for name in research.MODEL_COLLECTIONS:
            state.pop(name)
        research.atomic_json(self.root / "research.json", state)
        self.cli("archive", "mza", "import", self.scan, "--url", URL)
        self.assertEqual(self.cli("project", "check")["schema_version"], 1)
        bundle = self.base / "legacy.zip"
        research.export_bundle(self.root, bundle)
        research.restore_bundle(self.base / "legacy-restored", bundle)
        research.migrate(self.root, 1, "SYNTHETIC migration")
        self.assertTrue(self.cli("project", "check")["valid"])
        self.assertEqual(self.cli("project", "resume")["schema_version"], 2)

    def test_metadata_tampering_is_checked(self):
        result = mza.import_image(self.root, self.scan, URL)
        state = research.read_state(self.root)
        for field, value in (("width", 0), ("size_bytes", 1), ("sha256", "bad"),
                             ("digital_copy", "original"), ("url", "https://evil.invalid/"),
                             ("image_number", -1), ("acquired_at", "bad")):
            broken = deepcopy(state)
            broken["records"][result["record_id"]]["source"]["acquisition"][field] = value
            with self.subTest(field=field):
                self.assertTrue(research.check_state(broken, self.root))


class IIIFTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "assembled.png"

    def test_valid_metadata_v2_v3_and_minimal_full_request(self):
        for version in (2, 3):
            with self.subTest(version=version):
                server = MockServer(metadata(version, tiled=False))
                client = mza.OfflineIIIF(server, sleep=Mock())
                result = client.acquire(BASE + "/info.json", self.output)
                self.assertEqual(result["image_requests"], 1)
                self.assertEqual(result["format"], "PNG")
                self.assertEqual(len(server.calls), 2)
                size = "full" if version == 2 else "max"
                self.assertIn(f"/full/{size}/", server.calls[-1][0])
                self.output.unlink()

    def test_nonstandard_tiles_edges_and_exact_decoded_pixels(self):
        for version in (2, 3):
            with self.subTest(version=version):
                server = MockServer(metadata(version))
                result = mza.OfflineIIIF(server, sleep=Mock()).acquire(BASE + "/info.json", self.output)
                self.assertEqual((result["width"], result["height"]), (517, 389))
                self.assertEqual(result["image_requests"], 12)
                self.assertEqual(server.tiles[-1][0], (346, 381, 171, 8))
                with Image.open(self.output) as assembled:
                    for (x, y, w, h), payload in server.tiles:
                        with Image.open(BytesIO(payload)) as decoded:
                            self.assertEqual(assembled.crop((x, y, x+w, y+h)).tobytes(), decoded.convert("RGB").tobytes())
                self.assertFalse(result["live_mza_verified"])
                self.assertEqual(result["digital_copy"], "derived")
                self.output.unlink()

    def test_missing_height_defaults_to_declared_width_and_v2_profile_limits(self):
        info = metadata(2)
        info["tiles"][0].pop("height")
        info.pop("maxWidth")
        info.pop("maxHeight")
        info["profile"].append({"maxArea": 173 * 173})
        plan = mza.parse_info(info)
        self.assertEqual(len(plan["requests"]), 9)
        self.assertEqual(plan["requests"][-1][2], (346, 346, 171, 43))

    def test_invalid_incomplete_oversized_metadata(self):
        variants = [None, [], {}, {**metadata(), "width": True}, {**metadata(), "height": -1},
                    {**metadata(), "width": 99999999}, {**metadata(), "profile": []},
                    {**metadata(), "@context": "unknown"}, {**metadata(), "tiles": None},
                    {**metadata(), "tiles": [{"width": 173, "scaleFactors": [2]}]},
                    {**metadata(), "maxWidth": -1}, {**metadata(), "tiles": [{"width": 0}]},
                    {**metadata(), "tiles": [{"width": 173, "scaleFactors": [True]}]}]
        for info in variants:
            with self.subTest(info=info), self.assertRaises(ValueError):
                mza.parse_info(info)

    def test_inferred_max_height_and_level0_limited_sizes(self):
        info = metadata()
        info.update(width=100, height=389, maxWidth=173)
        info.pop("maxHeight")
        plan = mza.parse_info(info)
        self.assertEqual(len(plan["requests"]), 4)
        info = metadata(tiled=False)
        info.update(profile="level0", sizes=[{"width": 100, "height": 75}], tiles=[])
        with self.assertRaises(ValueError):
            mza.parse_info(info)
        info["sizes"].append({"width": 517, "height": 389})
        self.assertEqual(len(mza.parse_info(info)["requests"]), 1)

    def test_missing_corrupt_and_wrong_size_tile_never_publish(self):
        for response in ((404, {}, b"missing"), (200, {}, b"bad jpeg")):
            server = MockServer()
            server.responses = [(200, {}, json.dumps(server.info).encode()), response]
            with self.subTest(response=response[0]), self.assertRaises(ValueError):
                mza.OfflineIIIF(server, sleep=Mock()).acquire(BASE + "/info.json", self.output)
            self.assertFalse(self.output.exists())
        server = MockServer()
        tiny = BytesIO()
        Image.new("RGB", (2, 2)).save(tiny, format="JPEG")
        server.responses = [(200, {}, json.dumps(server.info).encode()), (200, {}, tiny.getvalue())]
        with self.assertRaisesRegex(ValueError, "rozměry"):
            mza.OfflineIIIF(server, sleep=Mock()).acquire(BASE + "/info.json", self.output)
        self.assertFalse(self.output.exists())

    def test_403_404_429_and_challenges_stop_without_retry(self):
        for status, body in ((403, b"denied"), (404, b"missing"), (429, b"rate limit"),
                             (401, b"auth"), (200, b"<html>Altcha</html>")):
            server = MockServer()
            server.responses = [(status, {"Retry-After": "1"}, body)]
            client = mza.OfflineIIIF(server, sleep=Mock())
            with self.subTest(status=status), self.assertRaises(ValueError):
                client.get(BASE + "/info.json", 1024)
            self.assertEqual(len(server.calls), 1)
            with self.assertRaises(ValueError):
                client.get(BASE + "/info.json", 1024)
            self.assertEqual(len(server.calls), 1)

    def test_transient_500_and_timeout_retry_once_and_retry_after(self):
        for error in ((500, {"Retry-After": "7"}, b"temporary"), TimeoutError()):
            server, sleeper = MockServer(), Mock()
            server.responses = [error]
            body = mza.OfflineIIIF(server, sleep=sleeper).get(BASE + "/info.json", 4096)
            self.assertEqual(json.loads(body)["width"], 517)
            self.assertEqual(len(server.calls), 2)
            self.assertEqual(server.calls[0][1], 15)
            if not isinstance(error, Exception):
                self.assertIn(unittest.mock.call(7), sleeper.call_args_list)
        for responses in ([(500, {}, b"temporary")] * 2, [TimeoutError()] * 2):
            server = MockServer()
            server.responses = responses
            with self.assertRaises(ValueError):
                mza.OfflineIIIF(server, sleep=Mock()).get(BASE + "/info.json", 1024)
            self.assertEqual(len(server.calls), 2)

    def test_retry_after_date_invalid_or_long_delay(self):
        for retry in ("9999", "invalid", format_datetime(datetime.now(timezone.utc) + timedelta(days=1))):
            server, sleeper = MockServer(), Mock()
            server.responses = [(503, {"Retry-After": retry}, b"busy")]
            with self.assertRaises(ValueError):
                mza.OfflineIIIF(server, sleep=sleeper).get(BASE + "/info.json", 1024)
            self.assertEqual(len(server.calls), 1)
            sleeper.assert_not_called()
        server, sleeper = MockServer(), Mock()
        server.responses = [(503, {"Retry-After": format_datetime(datetime.now(timezone.utc) + timedelta(seconds=20))}, b"busy")]
        mza.OfflineIIIF(server, sleep=sleeper).get(BASE + "/info.json", 4096)
        self.assertEqual(len(server.calls), 2)
        self.assertTrue(18 <= sleeper.call_args_list[0].args[0] <= 20)

    def test_domains_paths_and_redirects_rejected_before_followup(self):
        for url in ("http://iiif.example.invalid/a", "https://127.0.0.1/a", "https://www.mza.cz/a",
                    "https://iiif.example.invalid.evil.test/a", "https://user@iiif.example.invalid/a",
                    "https://iiif.example.invalid/a/%2e%2e/b", "https://iiif.example.invalid:443/a"):
            server = MockServer()
            with self.subTest(url=url), self.assertRaises(ValueError):
                mza.OfflineIIIF(server).get(url, 1024)
            self.assertFalse(server.calls)
        for location in ("https://127.0.0.1/private", BASE + "/other"):
            server = MockServer()
            server.responses = [(302, {"Location": location}, b"")]
            with self.assertRaises(ValueError):
                mza.OfflineIIIF(server).get(BASE + "/info.json", 1024)
            self.assertEqual(len(server.calls), 1)

    def test_metadata_cannot_switch_image_identity(self):
        for base in ("https://www.mza.cz/private", "https://iiif.example.invalid/other"):
            server = MockServer({**metadata(), "id": base})
            with self.assertRaises(ValueError):
                mza.OfflineIIIF(server).acquire(BASE + "/info.json", self.output)
            self.assertEqual(len(server.calls), 1)

    def test_limits_and_atomic_no_overwrite_even_racing(self):
        server = MockServer()
        with self.assertRaises(ValueError):
            mza.OfflineIIIF(server).get(BASE + "/info.json", 1)
        server = MockServer()
        with patch.object(mza, "MAX_REQUESTS", 2), self.assertRaises(ValueError):
            mza.OfflineIIIF(server, sleep=Mock()).acquire(BASE + "/info.json", self.output)
        self.assertFalse(self.output.exists())
        with patch.object(mza, "MAX_TRANSFER_BYTES", 10), self.assertRaises(ValueError):
            mza.OfflineIIIF(MockServer()).get(BASE + "/info.json", 4096)
        self.output.write_bytes(b"existing")
        server = MockServer()
        with self.assertRaises(ValueError):
            mza.OfflineIIIF(server).acquire(BASE + "/info.json", self.output)
        self.assertFalse(server.calls)
        self.output.unlink()
        def race(staged, target):
            target.write_bytes(b"race")
            os.link(staged, target)
        with patch.object(mza, "publish_new", side_effect=race), self.assertRaises(FileExistsError):
            mza.OfflineIIIF(MockServer(), sleep=Mock()).acquire(BASE + "/info.json", self.output)
        self.assertEqual(self.output.read_bytes(), b"race")
        self.assertFalse(list(self.output.parent.glob(".iiif-*")))

    def test_archive_urls_reject_ssrf_and_path_traversal(self):
        for url in (URL.replace("https:", "http:"), URL.replace("www.mza.cz", "localhost"),
                    URL + "&image=second.jp2", URL.replace("synthetic-001", "../secret"),
                    URL.replace("synthetic-001", "%2e%2e%2fsecret"), URL + "#fragment",
                    URL.replace("www.mza.cz", "www.mza.cz@evil.invalid")):
            with self.subTest(url=url), self.assertRaises(ValueError):
                mza.archive_url(url)


if __name__ == "__main__":
    unittest.main()
