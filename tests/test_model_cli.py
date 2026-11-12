"""General evidence model and unified CLI tests use synthetic data only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image


REPO = Path(__file__).resolve().parents[1]
SKILL = Path(os.environ.get("FAMILY_TREE_SKILL", REPO / "skills/family-tree-chatgpt"))
CLI = SKILL / "scripts/family_tree.py"


def load_research():
    spec = importlib.util.spec_from_file_location("research_model", SKILL / "scripts/research.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


research = load_research()


def entity_patch():
    return {
        "persons": [
            {"id": "person_a", "label": "Synthetic A", "notes": "", "extensions": {}},
            {"id": "person_b", "label": "Synthetic B", "notes": "", "extensions": {}},
        ],
        "relationships": [{
            "id": "relation_parent_child",
            "type": "parent_child",
            "participants": [
                {"person_id": "person_a", "role": "parent"},
                {"person_id": "person_b", "role": "child"},
            ],
            "notes": "",
            "extensions": {},
        }],
        "sources": [
            {
                "id": "source_one", "kind": "synthetic_register", "title": "Synthetic source 1",
                "citation": "Synthetic archive, TEST-1, page 1.", "repository": "Synthetic archive",
                "url": "https://example.invalid/1", "accessed_on": "2026-11-12", "files": [],
                "record_ids": [], "notes": "", "extensions": {},
            },
            {
                "id": "source_two", "kind": "synthetic_register", "title": "Synthetic source 2",
                "citation": "Synthetic archive, TEST-2, page 2.", "repository": "Synthetic archive",
                "url": "", "accessed_on": "", "files": [], "record_ids": [],
                "notes": "", "extensions": {},
            },
        ],
        "claims": [
            {
                "id": "claim_birth_1900", "subject": {"type": "person", "id": "person_b"},
                "predicate": "birth.date", "value": "1900-01-01", "status": "supported",
                "citations": [{"source_id": "source_one", "locator": "page 1", "quotation": "", "note": ""}],
                "rationale": "Synthetic source explicitly states the date.", "notes": "", "extensions": {},
            },
            {
                "id": "claim_birth_1901", "subject": {"type": "person", "id": "person_b"},
                "predicate": "birth.date", "value": "1901-01-01", "status": "unverified",
                "citations": [{"source_id": "source_two", "locator": "page 2", "quotation": "", "note": ""}],
                "rationale": "", "notes": "", "extensions": {},
            },
            {
                "id": "claim_parent", "subject": {"type": "relationship", "id": "relation_parent_child"},
                "predicate": "relationship.parent_child", "value": True, "status": "unverified",
                "citations": [{"source_id": "source_one", "locator": "page 1", "quotation": "", "note": ""}],
                "rationale": "", "notes": "", "extensions": {},
            },
        ],
        "conflicts": [{
            "id": "conflict_birth_date", "claim_ids": ["claim_birth_1900", "claim_birth_1901"],
            "status": "open", "resolution": {"preferred_claim_ids": [], "rationale": ""},
            "notes": "", "extensions": {},
        }],
    }


class GeneralModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private"
        research.initialize(self.root)

    def test_atomic_model_apply_conflict_and_resolution(self):
        state = research.apply_model(self.root, 0, entity_patch(), "Resolve the synthetic date conflict.")
        self.assertEqual(state["revision"], 1)
        self.assertEqual(state["schema_version"], 2)
        self.assertFalse(research.check_state(state, self.root))
        audit = research.audit_state(state)
        self.assertEqual(audit["model_counts"]["persons"], 2)
        self.assertIn("open_conflict", [item["code"] for item in audit["warnings"]])

        resolved = entity_patch()["conflicts"][0]
        resolved["status"] = "resolved"
        resolved["resolution"] = {
            "preferred_claim_ids": ["claim_birth_1900"],
            "rationale": "Synthetic comparison prefers the explicitly cited claim.",
        }
        state = research.apply_model(
            self.root, 1, {"conflicts": [resolved]}, "Continue with another synthetic claim."
        )
        self.assertEqual(state["revision"], 2)
        self.assertNotIn("open_conflict", [item["code"] for item in research.audit_state(state)["warnings"]])

    def test_invalid_reference_does_not_change_state(self):
        before = (self.root / "research.json").read_bytes()
        invalid = {
            "relationships": [{
                "id": "bad_relation", "type": "parent_child",
                "participants": [
                    {"person_id": "missing_a", "role": "parent"},
                    {"person_id": "missing_b", "role": "child"},
                ],
                "notes": "", "extensions": {},
            }]
        }
        with self.assertRaisesRegex(ValueError, "neznámá osoba"):
            research.apply_model(self.root, 0, invalid, "Do not save.")
        self.assertEqual((self.root / "research.json").read_bytes(), before)
        self.assertFalse((self.root / ".research.lock").exists())

    def test_model_source_hash_is_checked(self):
        path = self.root / "sources/synthetic.txt"
        path.write_text("synthetic source", encoding="utf-8")
        source = {
            "id": "source_file", "kind": "synthetic", "title": "Synthetic file",
            "citation": "Synthetic citation.", "repository": "", "url": "", "accessed_on": "",
            "files": [{"path": "sources/synthetic.txt", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}],
            "record_ids": [], "notes": "", "extensions": {},
        }
        research.apply_model(self.root, 0, {"sources": [source]}, "Check the file.")
        path.write_text("changed", encoding="utf-8")
        self.assertTrue(any("SHA-256" in item for item in research.check_state(research.read_state(self.root), self.root)))

    def test_explicit_schema_one_migration_preserves_data(self):
        legacy = Path(self.temp.name) / "legacy"
        for name in ("sources", "crops", "history"):
            (legacy / name).mkdir(parents=True, exist_ok=True)
        original = {
            "schema_version": 1,
            "revision": 4,
            "records": {},
            "events": [{"result": "note", "scope": "synthetic"}],
            "next_step": "Synthetic legacy step.",
        }
        research.atomic_json(legacy / "research.json", original)
        bundle = Path(self.temp.name) / "legacy.zip"
        research.export_bundle(legacy, bundle)
        restored = Path(self.temp.name) / "legacy-restored"
        research.restore_bundle(restored, bundle)
        self.assertEqual(research.read_state(restored), original)
        migrated = research.migrate(legacy, 4, "Create the first explicit claim.")
        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual(migrated["revision"], 5)
        self.assertEqual(migrated["events"][0], original["events"][0])
        self.assertEqual(json.loads((legacy / "history/revision-000004.json").read_text()), original)
        self.assertTrue(all(not migrated[name] for name in research.MODEL_COLLECTIONS))


class UnifiedCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private"
        self.base = [sys.executable, str(CLI), "--workspace", str(self.root)]

    def run_json(self, arguments):
        completed = subprocess.run(
            self.base + arguments, check=True, capture_output=True, text=True
        )
        return json.loads(completed.stdout)

    def test_project_model_and_record_commands_share_one_cli(self):
        initialized = self.run_json(["project", "init"])
        self.assertEqual(initialized["schema_version"], 2)
        patch = Path(self.temp.name) / "patch.json"
        patch.write_text(json.dumps(entity_patch()), encoding="utf-8")
        applied = self.run_json([
            "model", "apply", str(patch), "--expected-revision", "0",
            "--next-step", "Review the synthetic conflict.",
        ])
        self.assertEqual(applied["claims"], 3)
        shown = self.run_json([
            "model", "show", "--collection", "conflicts", "--id", "conflict_birth_date"
        ])
        self.assertEqual(shown["status"], "open")

        record = json.loads((SKILL / "assets/record.json").read_text(encoding="utf-8"))
        record["id"] = "synthetic_cli_record"
        record_path = Path(self.temp.name) / "record.json"
        record_path.write_text(json.dumps(record), encoding="utf-8")
        saved = self.run_json([
            "record", "put", str(record_path), "--expected-revision", "1",
            "--next-step", "Read the synthetic record.",
        ])
        self.assertEqual(saved["revision"], 2)
        self.assertTrue(self.run_json(["project", "check"])["valid"])

    def test_gedcom_and_image_commands_are_routed(self):
        gedcom_path = Path(self.temp.name) / "synthetic.ged"
        gedcom_path.write_text(
            "0 HEAD\n1 SOUR SyntheticCLI\n1 GEDC\n2 VERS 5.5.1\n1 CHAR UTF-8\n"
            "0 @I1@ INDI\n1 NAME Synthetic /Person/\n0 TRLR\n",
            encoding="utf-8",
        )
        imported_path = Path(self.temp.name) / "import.json"
        imported = subprocess.run(
            [sys.executable, str(CLI), "gedcom", "import", str(gedcom_path), str(imported_path)],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual(json.loads(imported.stdout)["persons"], 1)

        image_path = Path(self.temp.name) / "source.png"
        crop_path = Path(self.temp.name) / "crop.png"
        Image.new("RGB", (20, 10), "white").save(image_path)
        cropped = subprocess.run(
            [sys.executable, str(CLI), "image", "crop", str(image_path), str(crop_path), "--box", "0,0,0.5,1"],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual(json.loads(cropped.stdout)["crop_size"], [10, 10])


if __name__ == "__main__":
    unittest.main()
