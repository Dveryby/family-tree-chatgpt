"""Synthetic tests for schema-1/2 research.json SQLite adapters."""
from copy import deepcopy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills/family-tree-chatgpt/scripts"
FIXTURES = REPO / "tests/fixtures"
import sys
sys.path.insert(0, str(SCRIPTS))
import research
import research_import
import sqlite_store


def source(source_id):
    return {
        "id": source_id,
        "kind": "synthetic_register",
        "title": "Synthetic register",
        "citation": "Synthetic archive, TEST 1.",
        "repository": "Synthetic archive",
        "url": "https://example.invalid/test",
        "accessed_on": "2026-11-15",
        "files": [],
        "record_ids": [],
        "notes": "",
        "extensions": {},
    }


def claim(claim_id, person_id, value, status="unverified"):
    citations = []
    rationale = ""
    if status == "supported":
        citations = [{
            "source_id": "source_a", "locator": "folio 1",
            "quotation": "", "note": "Syntetická citace.",
        }]
        rationale = "Syntetický pramen podporuje tvrzení."
    return {
        "id": claim_id,
        "subject": {"type": "person", "id": person_id},
        "predicate": "name.given",
        "value": value,
        "status": status,
        "citations": citations,
        "rationale": rationale,
        "notes": "",
        "extensions": {},
    }


class ResearchImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "family-tree.sqlite"
        sqlite_store.initialize_database(self.database)

    def workspace(self, name, state, history=None):
        root = self.root / name
        for directory in ("sources", "crops", "history"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        research.atomic_json(root / "research.json", state)
        for snapshot in history or []:
            research.atomic_json(
                root / "history" / f"revision-{snapshot['revision']:06d}.json", snapshot
            )
        return root

    def schema_one(self):
        previous = {
            "schema_version": 1,
            "revision": 0,
            "records": {},
            "events": [],
            "next_step": "Zapsat syntetický záznam.",
        }
        current = json.loads(
            (FIXTURES / "research_v1_synthetic.json").read_text(encoding="utf-8")
        )
        workspace = self.workspace("schema-one", current, [previous])
        (workspace / "sources" / "unreferenced-synthetic.txt").write_text(
            "synthetic source bytes", encoding="utf-8"
        )
        return workspace

    def schema_two(self):
        persons = {
            key: {"id": key, "label": f"Synthetic {key}", "notes": "", "extensions": {}}
            for key in ("person_a", "person_b")
        }
        claims = {
            "claim_supported": claim("claim_supported", "person_a", "Anna", "supported"),
            "claim_a": claim("claim_a", "person_a", "A", "supported"),
            "claim_b": claim("claim_b", "person_a", "B"),
        }
        conflicts = {
            f"k{number:02d}": {
                "id": f"k{number:02d}",
                "claim_ids": ["claim_a", "claim_b"],
                "status": "open",
                "resolution": {"preferred_claim_ids": [], "rationale": ""},
                "notes": "Syntetický otevřený konflikt.",
                "extensions": {},
            }
            for number in range(1, 14)
        }
        state = {
            "schema_version": 2,
            "revision": 13,
            "records": {},
            "persons": persons,
            "relationships": {},
            "claims": claims,
            "sources": {"source_a": source("source_a")},
            "conflicts": conflicts,
            "events": [{"result": "note", "scope": "synthetic", "revision": 13}],
            "next_step": "Ponechat K01–K13 otevřené.",
        }
        return self.workspace("schema-two", state)

    def import_kwargs(self, branch_key, label):
        return {
            "project_id": "project",
            "project_name": "Synthetic project",
            "branch_key": branch_key,
            "branch_label": label,
            "actor": "test-user",
        }

    def test_dry_run_schema_one_is_read_only_then_import_is_idempotent_and_lossless(self):
        workspace = self.schema_one()
        dry = research_import.import_research(
            self.database, workspace,
            dry_run=True, **self.import_kwargs("branch_v1", "Schema 1"),
        )
        self.assertTrue(dry["would_import"])
        self.assertEqual(dry["planned_insert_counts"]["media"], 1)
        self.assertEqual(sqlite_store.database_status(self.database)["counts"]["projects"], 0)

        first = research_import.import_research(
            self.database, workspace, **self.import_kwargs("branch_v1", "Schema 1")
        )
        self.assertTrue(first["imported"])
        self.assertEqual(first["source_schema_version"], 1)
        self.assertEqual(first["inserted_counts"]["record_texts"], 3)
        self.assertEqual(first["inserted_counts"]["media"], 1)
        before = sqlite_store.database_status(self.database)["counts"]
        repeated = research_import.import_research(
            self.database, workspace, **self.import_kwargs("branch_v1", "Schema 1")
        )
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(sqlite_store.database_status(self.database)["counts"], before)
        changed = research.read_state(workspace)
        changed["revision"] = 2
        changed["events"].append({"result": "note", "scope": "changed", "revision": 2})
        changed["next_step"] = "Importovat jako novou větev."
        research.atomic_json(workspace / "research.json", changed)
        with self.assertRaisesRegex(ValueError, "novou branch-key"):
            research_import.import_research(
                self.database, workspace, **self.import_kwargs("branch_v1", "Schema 1")
            )
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM import_state_snapshots"
            ).fetchone()[0], 2)
            self.assertEqual(connection.execute(
                "SELECT source_identifier FROM research_records"
            ).fetchone()[0], "record_v1")
            self.assertEqual(connection.execute(
                "SELECT text_value FROM imported_record_texts WHERE text_kind = 'transcription'"
            ).fetchone()[0], "Syntetický přepis (?)")
            self.assertEqual(connection.execute(
                "SELECT json_extract(payload_json, '$.result') FROM import_history_events"
            ).fetchone()[0], "record_saved")
        self.assertEqual(sqlite_store.validate_database(self.database), [])

    def test_schema_two_keeps_branch_separate_and_preserves_open_k01_to_k13(self):
        research_import.import_research(
            self.database, self.schema_one(), **self.import_kwargs("branch_v1", "Schema 1")
        )
        result = research_import.import_research(
            self.database, self.schema_two(), **self.import_kwargs("branch_v2", "Schema 2")
        )
        self.assertEqual(result["open_conflict_codes"], [f"K{x:02d}" for x in range(1, 14)])
        self.assertIn("claim_status_evidence_level", result["normalizations"])
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            branches = connection.execute(
                "SELECT branch_key, history_kind FROM import_branches ORDER BY branch_key"
            ).fetchall()
            self.assertEqual(
                [tuple(row) for row in branches],
                [("branch_v1", "json_v1"), ("branch_v2", "json_v2")],
            )
            person_counts = connection.execute(
                "SELECT b.branch_key, count(p.id) FROM import_branches b "
                "LEFT JOIN persons p ON p.branch_id = b.id GROUP BY b.id ORDER BY b.branch_key"
            ).fetchall()
            self.assertEqual(
                [tuple(row) for row in person_counts],
                [("branch_v1", 0), ("branch_v2", 2)],
            )
            conflicts = connection.execute(
                "SELECT source_identifier, code, status FROM conflicts ORDER BY source_identifier"
            ).fetchall()
            self.assertEqual(len(conflicts), 13)
            self.assertTrue(all(row["status"] == "open" for row in conflicts))
            self.assertEqual(
                sorted(row["code"] for row in conflicts),
                [f"K{x:02d}" for x in range(1, 14)],
            )
            person = connection.execute(
                "SELECT id, source_identifier FROM persons WHERE source_identifier = 'person_a'"
            ).fetchone()
            self.assertNotEqual(person["id"], "person_a")
            with self.assertRaisesRegex(sqlite3.IntegrityError, "import provenance"):
                connection.execute(
                    "UPDATE persons SET source_json = '{}' WHERE id = ?", (person["id"],)
                )
            connection.rollback()
        self.assertEqual(sqlite_store.validate_database(self.database), [])

    def test_outbox_approval_requires_supported_nonconflicting_claim_and_never_sends(self):
        research_import.import_research(
            self.database, self.schema_two(), **self.import_kwargs("branch_v2", "Schema 2")
        )
        plan = {
            "schema_version": 1,
            "project_id": "project",
            "operations": [{
                "branch_key": "branch_v2",
                "idempotency_key": "gramps:create:person:synthetic-a",
                "operation_type": "create_person",
                "aggregate_type": "person",
                "aggregate_id": "person_a",
                "claim_ids": ["claim_supported"],
                "payload": {"handle": "synthetic-a"},
            }],
        }
        dry = research_import.approve_outbox(
            self.database, plan, approved_by="reviewer", dry_run=True
        )
        self.assertEqual(dry["eligible"], 1)
        approved = research_import.approve_outbox(
            self.database, plan, approved_by="reviewer"
        )
        self.assertEqual(approved["approved"], 1)
        self.assertEqual(approved["sent"], 0)
        repeated = research_import.approve_outbox(
            self.database, plan, approved_by="reviewer"
        )
        self.assertEqual(repeated["unchanged"], 1)
        conflicted = deepcopy(plan)
        conflicted["operations"][0]["idempotency_key"] = "gramps:conflicted"
        conflicted["operations"][0]["claim_ids"] = ["claim_a"]
        with self.assertRaisesRegex(ValueError, "otevřeném konfliktu"):
            research_import.approve_outbox(
                self.database, conflicted, approved_by="reviewer"
            )
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM sync_outbox"
            ).fetchone()[0], 1)
            payload = json.loads(connection.execute(
                "SELECT payload_json FROM sync_outbox"
            ).fetchone()[0])
            self.assertEqual(
                payload["approval_evidence"]["claim_source_identifiers"],
                ["claim_supported"],
            )
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM sync_outbox_attempts"
            ).fetchone()[0], 0)
        self.assertFalse(sqlite_store.database_status(self.database)["network_writes"])

    def test_database_import_cli_reports_dry_run_without_writes(self):
        completed = subprocess.run(
            [
                sys.executable, str(SCRIPTS / "family_tree.py"),
                "database", "import-research", str(self.database), str(self.schema_one()),
                "--project-id", "project", "--project-name", "Synthetic project",
                "--branch-key", "branch_v1", "--branch-label", "Schema 1",
                "--actor", "test-user", "--dry-run",
            ],
            check=True, capture_output=True, text=True,
        )
        report = json.loads(completed.stdout)
        self.assertTrue(report["dry_run"])
        self.assertTrue(report["would_import"])
        self.assertEqual(sqlite_store.database_status(self.database)["counts"]["projects"], 0)


if __name__ == "__main__":
    unittest.main()
