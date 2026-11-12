"""Offline tests with generated images and synthetic evidence only."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
SKILL = Path(os.environ.get("FAMILY_TREE_SKILL", REPO / "skills/family-tree-chatgpt"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SKILL / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


research, crop = load("research"), load("crop")


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private"
        research.initialize(self.root)
        self.record = json.loads((SKILL / "assets/record.json").read_text())
        self.record["id"] = "synthetic_001"

    def reviewed(self):
        Image.new("RGB", (100, 80), "white").save(self.root / "sources/scan.png")
        crop.crop_scan(self.root / "sources/scan.png", self.root / "crops/record.png", (0, 0, 1, 1))
        self.record.update(reading_status="reviewed", visual_review=True, transcription="SYNTHETIC: Joannes Test.")
        self.record["source"].update(archive="Syntetický archiv", reference="TEST-001", page="folio 1, snímek 1", url="https://example.invalid/test", accessed_on="2026-11-10", file="sources/scan.png", crop="crops/record.png")
        return self.record

    def test_cli_roundtrip_separate_processes(self):
        input_file = self.root / "input.json"
        input_file.write_text(json.dumps(self.reviewed()), encoding="utf-8")
        base = [sys.executable, str(SKILL / "scripts/research.py"), "--workspace", str(self.root)]
        subprocess.run(base + ["put", str(input_file), "--expected-revision", "0", "--next-step", "Porovnat druhého kandidáta."], check=True, capture_output=True, text=True)
        state = json.loads(subprocess.run(base + ["resume"], check=True, capture_output=True, text=True).stdout)
        self.assertEqual(state["revision"], 1)
        self.assertEqual(state["records"]["synthetic_001"]["identity"]["status"], "unresolved")
        self.assertEqual(state["next_step"], "Porovnat druhého kandidáta.")
        self.assertEqual(state["events"][0]["result"], "record_saved")
        self.assertEqual(json.loads(subprocess.run(base + ["check"], check=True, capture_output=True, text=True).stdout)["valid"], True)

    def test_other_records_history_and_negative_search_survive(self):
        research.update(self.root, 0, record=self.record, next_step="Další nález.")
        other = deepcopy(self.record)
        other["id"] = "synthetic_002"
        research.update(self.root, 1, record=other, next_step="Kontrola.")
        self.record["transcription"] = "Opravený syntetický text."
        research.update(self.root, 2, record=self.record, next_step="Rejstřík.")
        state = research.update(self.root, 3, result="not_found", scope="TEST-001, snímky 2–4, Test", next_step="Jiná kniha.")
        self.assertEqual(len(state["records"]), 2)
        self.assertEqual(state["records"]["synthetic_002"], other)
        self.assertEqual(state["events"][-1]["scope"], "TEST-001, snímky 2–4, Test")
        backup = json.loads((self.root / "history/revision-000002.json").read_text())
        self.assertEqual(backup["records"]["synthetic_001"]["transcription"], "")

    def test_stale_revision_cannot_overwrite(self):
        research.update(self.root, 0, record=self.record, next_step="A")
        before = (self.root / "research.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "mezitím"):
            research.update(self.root, 0, record=self.record, next_step="B")
        self.assertEqual((self.root / "research.json").read_bytes(), before)

    def test_review_requires_source_and_visual_review(self):
        self.record["reading_status"] = "reviewed"
        self.assertTrue(research.validate_record(self.record, self.root))

    def test_identity_cannot_be_asserted_without_reasons(self):
        self.record["identity"]["status"] = "supported"
        self.assertTrue(research.validate_record(self.record, self.root))

    def test_audit_reports_quality_warnings_without_invalidating_state(self):
        record = self.reviewed()
        record["uncertainties"] = ["Synteticky nejisté čtení."]
        research.update(self.root, 0, record=record, next_step="Zkontrolovat nejistotu.")
        second = deepcopy(record)
        second["id"] = "synthetic_002"
        research.update(self.root, 1, record=second, next_step="Rozlišit dva zápisy.")
        state = research.read_state(self.root)
        self.assertFalse(research.check_state(state, self.root))
        audit = research.audit_state(state)
        codes = [item["code"] for item in audit["warnings"]]
        self.assertEqual(audit["reading_status"]["reviewed"], 2)
        self.assertIn("reviewed_without_translation", codes)
        self.assertIn("reviewed_without_interpretation", codes)
        self.assertIn("open_reading_uncertainties", codes)
        self.assertIn("duplicate_source_locator", codes)

    def test_audit_flags_identity_conclusion_before_review(self):
        self.record["identity"] = {
            "status": "supported",
            "rationale": "Syntetické zdůvodnění.",
            "evidence": ["Syntetická citace."],
        }
        research.update(self.root, 0, record=self.record, next_step="Vizuálně ověřit.")
        audit = research.audit_state(research.read_state(self.root))
        self.assertIn("identity_before_review", [item["code"] for item in audit["warnings"]])

    def test_cli_audit_is_read_only(self):
        script = str(SKILL / "scripts/research.py")
        before = (self.root / "research.json").read_bytes()
        completed = subprocess.run(
            [sys.executable, script, "--workspace", str(self.root), "audit"],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        self.assertIn("no_records", [item["code"] for item in result["warnings"]])
        self.assertEqual((self.root / "research.json").read_bytes(), before)

    def test_changed_scan_is_detected_and_blocks_update(self):
        research.update(self.root, 0, record=self.reviewed(), next_step="Ověřit.")
        Image.new("RGB", (100, 80), "black").save(self.root / "sources/scan.png")
        self.assertTrue(research.check_state(research.read_state(self.root), self.root))
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            research.update(self.root, 1, result="note", scope="test", next_step="Další.")

    def test_path_traversal_and_symlink_escape_are_rejected(self):
        external = Path(self.temp.name) / "outside.png"
        Image.new("RGB", (2, 2)).save(external)
        self.record["source"]["file"] = "../outside.png"
        self.assertTrue(research.validate_record(self.record, self.root))
        (self.root / "sources/link.png").symlink_to(external)
        self.record["source"]["file"] = "sources/link.png"
        self.assertTrue(research.validate_record(self.record, self.root))

    def test_reinitialize_and_git_workspace_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "existuje"):
            research.initialize(self.root)
        subprocess.run(["git", "init", str(Path(self.temp.name))], check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, "mimo git"):
            research.private_workspace(self.root)

    def test_empty_git_named_directory_is_not_a_repository(self):
        (Path(self.temp.name) / ".git").mkdir()
        self.assertEqual(research.private_workspace(self.root), self.root)

    def test_failed_atomic_replace_keeps_previous_state(self):
        before = (self.root / "research.json").read_bytes()
        with patch.object(research.os, "replace", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                research.update(self.root, 0, record=self.record, next_step="Další.")
        self.assertEqual((self.root / "research.json").read_bytes(), before)
        self.assertFalse((self.root / ".research.lock").exists())
        research.update(self.root, 0, record=self.record, next_step="Opakovat.")

    def test_lock_prevents_second_writer(self):
        with research.locked(self.root):
            with self.assertRaisesRegex(ValueError, "zamčená"):
                research.update(self.root, 0, record=self.record, next_step="A")

    def test_malformed_fields_report_errors(self):
        for field, value in (("source", []), ("identity", None), ("uncertainties", None), ("transcription", {})):
            with self.subTest(field=field):
                broken = deepcopy(self.record)
                broken[field] = value
                self.assertTrue(research.validate_record(broken, self.root))

    def test_cli_export_restore_roundtrip_and_continuation(self):
        research.update(self.root, 0, record=self.reviewed(), next_step="Ověřit přenos.")
        research.update(self.root, 1, result="note", scope="Syntetický přenosový test", next_step="Obnovit stav.")
        bundle = Path(self.temp.name) / "research-transfer.zip"
        script = str(SKILL / "scripts/research.py")
        export = subprocess.run(
            [sys.executable, script, "--workspace", str(self.root), "export", str(bundle)],
            check=True,
            capture_output=True,
            text=True,
        )
        export_result = json.loads(export.stdout)
        self.assertTrue(export_result["exported"])
        self.assertEqual(export_result["revision"], 2)
        self.assertEqual(export_result["bundle_sha256"], research.sha256(bundle))
        with self.assertRaises(FileExistsError):
            research.export_bundle(self.root, bundle)
        restored = Path(self.temp.name) / "restored"
        restore = subprocess.run(
            [sys.executable, script, "--workspace", str(restored), "restore", str(bundle)],
            check=True,
            capture_output=True,
            text=True,
        )
        restore_result = json.loads(restore.stdout)
        self.assertTrue(restore_result["restored"])
        self.assertEqual(restore_result["revision"], 2)
        self.assertEqual(research.read_state(restored), research.read_state(self.root))
        self.assertEqual((restored / "sources/scan.png").read_bytes(), (self.root / "sources/scan.png").read_bytes())
        self.assertEqual((restored / "crops/record.png").read_bytes(), (self.root / "crops/record.png").read_bytes())
        self.assertEqual(
            [path.read_bytes() for path in sorted((restored / "history").iterdir())],
            [path.read_bytes() for path in sorted((self.root / "history").iterdir())],
        )
        self.assertFalse((restored / ".research.lock").exists())
        continued = research.update(restored, 2, result="note", scope="Pokračování po obnově", next_step="Další revize.")
        self.assertEqual(continued["revision"], 3)

    def test_restore_rejects_changed_content_and_cleans_staging(self):
        research.update(self.root, 0, record=self.reviewed(), next_step="Export.")
        bundle = Path(self.temp.name) / "valid.zip"
        research.export_bundle(self.root, bundle)
        with zipfile.ZipFile(bundle, "r") as source:
            contents = [(info, source.read(info)) for info in source.infolist()]
        by_name = {info.filename: data for info, data in contents}
        changed = bytearray(by_name["sources/scan.png"])
        changed[-1] ^= 1
        by_name["sources/scan.png"] = bytes(changed)
        tampered = Path(self.temp.name) / "tampered.zip"
        with zipfile.ZipFile(tampered, "w") as target:
            for original, _ in contents:
                copied = zipfile.ZipInfo(original.filename, date_time=original.date_time)
                copied.compress_type = original.compress_type
                copied.create_system = original.create_system
                copied.external_attr = original.external_attr
                target.writestr(copied, by_name[original.filename])
        restored = Path(self.temp.name) / "restored"
        with self.assertRaisesRegex(ValueError, "Kontrolní součet"):
            research.restore_bundle(restored, tampered)
        self.assertFalse(restored.exists())
        self.assertFalse(list(Path(self.temp.name).glob(".research-restore-*")))

    def test_restore_rejects_path_traversal_and_existing_destination(self):
        malicious = Path(self.temp.name) / "malicious.zip"
        payload = b"x"
        manifest = {
            "bundle_schema_version": 1,
            "research_schema_version": 1,
            "revision": 0,
            "created_at": "2026-11-12T00:00:00+00:00",
            "files": [{"path": "../escape", "size": 1, "sha256": hashlib.sha256(payload).hexdigest()}],
        }
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr("../escape", payload)
            archive.writestr("manifest.json", json.dumps(manifest))
        restored = Path(self.temp.name) / "restored"
        with self.assertRaisesRegex(ValueError, "nebezpečnou cestu"):
            research.restore_bundle(restored, malicious)
        self.assertFalse((Path(self.temp.name) / "escape").exists())

        bundle = Path(self.temp.name) / "valid.zip"
        research.export_bundle(self.root, bundle)
        symlink_bundle = Path(self.temp.name) / "symlink-entry.zip"
        with zipfile.ZipFile(bundle, "r") as source, zipfile.ZipFile(symlink_bundle, "w") as target:
            for original in source.infolist():
                copied = zipfile.ZipInfo(original.filename, date_time=original.date_time)
                copied.compress_type = original.compress_type
                copied.create_system = original.create_system
                copied.external_attr = original.external_attr
                if original.filename == "research.json":
                    copied.create_system = 3
                    copied.external_attr = (stat.S_IFLNK | 0o777) << 16
                target.writestr(copied, source.read(original))
        with self.assertRaisesRegex(ValueError, "nepodporovanou položku"):
            research.restore_bundle(restored, symlink_bundle)
        self.assertFalse(restored.exists())

        research.initialize(restored)
        before = (restored / "research.json").read_bytes()
        with self.assertRaisesRegex(FileExistsError, "nepřepíše"):
            research.restore_bundle(restored, bundle)
        self.assertEqual((restored / "research.json").read_bytes(), before)

    def test_export_rejects_symlinks_and_git_destination(self):
        external = Path(self.temp.name) / "external.txt"
        external.write_text("synthetic", encoding="utf-8")
        (self.root / "sources/link.txt").symlink_to(external)
        bundle = Path(self.temp.name) / "symlink.zip"
        with self.assertRaisesRegex(ValueError, "symlink"):
            research.export_bundle(self.root, bundle)
        self.assertFalse(bundle.exists())
        self.assertFalse((self.root / ".research.lock").exists())
        (self.root / "sources/link.txt").unlink()

        failed = Path(self.temp.name) / "failed.zip"
        with patch.object(research.os, "link", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                research.export_bundle(self.root, failed)
        self.assertFalse(failed.exists())
        self.assertFalse(list(Path(self.temp.name).glob(".failed.zip.*.tmp")))
        self.assertFalse((self.root / ".research.lock").exists())

        repository = Path(self.temp.name) / "code"
        subprocess.run(["git", "init", str(repository)], check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, "mimo git"):
            research.export_bundle(self.root, repository / "private.zip")


class CropTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.png"
        self.output = self.root / "crop.png"
        image = Image.new("RGB", (100, 80))
        image.putdata([(x % 256, y % 256, (x + y) % 256) for y in range(80) for x in range(100)])
        image.save(self.source)

    def test_exact_pixels_original_and_metadata(self):
        original = self.source.read_bytes()
        metadata = crop.crop_scan(self.source, self.output, (0.1, 0.25, 0.9, 0.75))
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(metadata["crop_size"], [80, 40])
        with Image.open(self.source) as source, Image.open(self.output) as output:
            self.assertEqual(output.tobytes(), source.crop((10, 20, 90, 60)).tobytes())
            self.assertFalse(output.getexif())

    def test_exif_orientation_applied_without_rewriting_original(self):
        image = Image.new("RGB", (100, 80), "white")
        exif = Image.Exif()
        exif[274] = 6
        image.save(self.source, exif=exif)
        original = self.source.read_bytes()
        metadata = crop.crop_scan(self.source, self.output, (0, 0, 1, 1))
        self.assertEqual(metadata["crop_size"], [80, 100])
        self.assertEqual(self.source.read_bytes(), original)

    def test_reject_invalid_boxes_and_overwriting(self):
        for box in ((0, 0, 100, 80), (0, 0, float("nan"), 1), (0, 0, 0, 1), (0, 0, 0.0001, 0.0001)):
            with self.subTest(box=box), self.assertRaises(ValueError):
                crop.crop_scan(self.source, self.output, box)
        crop.crop_scan(self.source, self.output, (0, 0, 1, 1))
        with self.assertRaises(FileExistsError):
            crop.crop_scan(self.source, self.output, (0, 0, 1, 1))
        with self.assertRaises(ValueError):
            crop.crop_scan(self.source, self.source, (0, 0, 1, 1))

    def test_crop_rejects_real_repository_output(self):
        target = self.root / "code"
        subprocess.run(["git", "init", str(target)], check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, "mimo git"):
            crop.crop_scan(self.source, target / "crop.png", (0, 0, 1, 1))


if __name__ == "__main__":
    unittest.main()
