"""SQLite Family Tree 2.0 migrations and evidence semantics on synthetic data."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills/family-tree-chatgpt"
CLI = SKILL / "scripts/family_tree.py"
FIXTURE = REPO / "tests/fixtures/etapa_0b_branch_metadata.json"


def load_store_module():
    spec = importlib.util.spec_from_file_location(
        "family_tree_sqlite_store", SKILL / "scripts/sqlite_store.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sqlite_store = load_store_module()


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "family-tree.sqlite"

    def test_empty_database_runs_real_migrations_and_records_checksums(self):
        result = sqlite_store.initialize_database(self.database)
        self.assertEqual(result["schema_version"], 2)
        with sqlite3.connect(self.database) as connection:
            rows = connection.execute(
                "SELECT version, name, sha256 FROM schema_migrations ORDER BY version"
            ).fetchall()
            self.assertEqual([row[0] for row in rows], [1, 2])
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
            for version, name, digest in rows:
                migration = sqlite_store.migrations()[version - 1]
                self.assertEqual(name, migration.name)
                self.assertEqual(digest, migration.sha256)
        self.assertEqual(sqlite_store.validate_database(self.database), [])
        self.assertEqual(self.database.stat().st_mode & 0o777, 0o600)

    def test_migration_one_to_two_preserves_existing_rows(self):
        sqlite_store.initialize_database(self.database, target_version=1)
        status = sqlite_store.database_status(self.database)
        self.assertTrue(status["needs_migration"])
        self.assertIsNone(status["counts"]["sync_outbox"])
        self.assertTrue(any("není aktuální" in item for item in sqlite_store.validate_database(self.database)))
        with sqlite3.connect(self.database) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "INSERT INTO projects(id, name, description, created_at) VALUES ('project', 'Synthetic', '', '2026-11-15T00:00:00+00:00')"
            )
            connection.execute(
                "INSERT INTO import_branches "
                "(id, project_id, branch_key, label, history_kind, source_revision, metadata_json, created_at) "
                "VALUES ('branch', 'project', 'branch', 'Synthetic branch', 'native', '', '{}', '2026-11-15T00:00:00+00:00')"
            )
            connection.execute(
                "INSERT INTO persons(id, project_id, branch_id, label, notes, created_at) "
                "VALUES ('person', 'project', 'branch', 'Identity container', '', '2026-11-15T00:00:00+00:00')"
            )
        result = sqlite_store.migrate_database(self.database)
        self.assertTrue(result["migrated"])
        self.assertEqual(result["from_schema_version"], 1)
        self.assertEqual(result["schema_version"], 2)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT label FROM persons").fetchone()[0], "Identity container")
            self.assertIsNotNone(connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sync_outbox'"
            ).fetchone())

    def test_migration_checksum_tampering_is_rejected(self):
        sqlite_store.initialize_database(self.database)
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE schema_migrations SET sha256 = ? WHERE version = 2", ("0" * 64,))
        with self.assertRaisesRegex(ValueError, "Kontrolní součet migrace 2"):
            sqlite_store.database_status(self.database)

    def test_database_cli_init_status_and_check(self):
        initialized = subprocess.run(
            [sys.executable, str(CLI), "database", "init", str(self.database)],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual(json.loads(initialized.stdout)["schema_version"], 2)
        status = subprocess.run(
            [sys.executable, str(CLI), "database", "status", str(self.database)],
            check=True, capture_output=True, text=True,
        )
        self.assertFalse(json.loads(status.stdout)["network_writes"])
        checked = subprocess.run(
            [sys.executable, str(CLI), "database", "check", str(self.database)],
            check=True, capture_output=True, text=True,
        )
        self.assertTrue(json.loads(checked.stdout)["valid"])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "family-tree.sqlite"
        sqlite_store.initialize_database(self.database)
        self.store = sqlite_store.GenealogyStore(self.database)
        self.addCleanup(self.store.close)
        self.store.create_project("project", "Synthetic project", actor="test-user")
        self.store.create_import_branch(
            "branch", "project", "native", "Synthetic native branch", "native",
            actor="test-user",
        )

    def add_person_source_claim(self, suffix="one", *, value="synthetic"):
        person_id = f"person_{suffix}"
        source_id = f"source_{suffix}"
        claim_id = f"claim_{suffix}"
        citation_id = f"citation_{suffix}"
        self.store.create_person(person_id, "project", "branch", f"Person {suffix}", actor="test-user")
        self.store.create_source(
            source_id, "project", "branch", "synthetic", f"Source {suffix}",
            citation=f"Synthetic citation {suffix}.", actor="test-user",
        )
        self.store.create_claim(
            claim_id, "project", "branch", "person", person_id,
            "name.birth", value, actor="test-user",
        )
        self.store.add_citation(
            citation_id, "project", "branch", claim_id, source_id,
            locator="synthetic locator", actor="test-user",
        )
        return person_id, source_id, claim_id, citation_id

    def test_metadata_only_fixture_keeps_revision_13_branches_separate_and_idempotent(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["fixture_scope"], "metadata_only")
        self.assertTrue(all(not item["content_in_fixture"] for item in fixture["branches"]))
        for index, item in enumerate(fixture["branches"], start=1):
            branch_id = f"branch_{index}"
            file_id = f"file_{index}"
            run_id = f"run_{index}"
            self.store.create_import_branch(
                branch_id, "project", item["key"], item["label"], item["history_kind"],
                source_revision="13",
                metadata={"known_counts": item["counts"], "metadata_only": True},
                actor="test-user",
            )
            registered = self.store.register_original_file(
                file_id, "project", branch_id,
                sha256=item["artifact_sha256"], byte_size=0,
                original_name=f"metadata-only-{index}.archive",
                storage_path=f"private://unavailable/{item['artifact_sha256']}",
                provenance_key=f"etapa-0b-{item['key']}",
                provenance={"content_available": False, "fixture_scope": "metadata_only"},
                actor="test-user",
            )
            self.assertTrue(registered["created"])
            run = self.store.start_import_run(
                run_id, "project", branch_id, file_id,
                idempotency_key=f"sha256:{item['artifact_sha256']}",
                importer="family-tree-2-metadata-stage",
                source_schema_version=item["schema_version"],
                summary={"known_counts": item["counts"], "content_imported": False},
                actor="test-user",
            )
            self.assertTrue(run["created"])
            repeated = self.store.start_import_run(
                run_id, "project", branch_id, file_id,
                idempotency_key=f"sha256:{item['artifact_sha256']}",
                importer="family-tree-2-metadata-stage",
                source_schema_version=item["schema_version"],
                summary={"known_counts": item["counts"], "content_imported": False},
                actor="test-user",
            )
            self.assertFalse(repeated["created"])
            self.store.create_person(
                f"person_branch_{index}", "project", branch_id,
                "Synthetic branch-local identity", import_run_id=run_id, actor="test-user",
            )

        branches = self.store.connection.execute(
            "SELECT branch_key, history_kind FROM import_branches "
            "WHERE branch_key LIKE 'revision_13_%' ORDER BY branch_key"
        ).fetchall()
        self.assertEqual([tuple(row) for row in branches], [
            ("revision_13_a", "json_v2"), ("revision_13_b", "json_v1")
        ])
        persons = self.store.connection.execute(
            "SELECT branch_id, count(*) FROM persons WHERE branch_id LIKE 'branch_%' GROUP BY branch_id ORDER BY branch_id"
        ).fetchall()
        self.assertEqual([tuple(row) for row in persons], [("branch_1", 1), ("branch_2", 1)])
        with self.assertRaisesRegex(ValueError, "Idempotency klíč importu"):
            self.store.start_import_run(
                "different_run", "project", "branch_1", "file_1",
                idempotency_key=f"sha256:{fixture['branches'][0]['artifact_sha256']}",
                importer="different-importer", summary={}, actor="test-user",
            )

    def test_claim_identity_reading_and_event_semantics_are_independent(self):
        person_a, source_id, claim_id, citation_id = self.add_person_source_claim()
        self.store.create_person("person_two", "project", "branch", "Person two", actor="test-user")
        self.store.create_record(
            "record", "project", "branch", "vital_register", "Synthetic record",
            source_id=source_id, reading_status="reviewed",
            visual_reviewed_at="2026-11-15T10:00:00+01:00", actor="test-user",
        )
        self.store.create_identity_assessment(
            "identity", "project", person_a, "person_two", actor="test-user"
        )
        statuses = self.store.connection.execute(
            "SELECT r.reading_status, a.status FROM research_records r CROSS JOIN identity_assessments a "
            "WHERE r.id = 'record' AND a.id = 'identity'"
        ).fetchone()
        self.assertEqual(tuple(statuses), ("reviewed", "unresolved"))

        self.store.create_event(
            "event_birth", "project", "branch", "birth",
            participants=[{"person_id": person_a, "role": "child"}], actor="test-user",
        )
        self.store.create_event(
            "event_baptism", "project", "branch", "baptism",
            participants=[{"person_id": person_a, "role": "child"}], actor="test-user",
        )
        self.store.create_event("event_death", "project", "branch", "death", actor="test-user")
        self.store.create_event("event_burial", "project", "branch", "burial", actor="test-user")
        event_types = {
            row[0] for row in self.store.connection.execute(
                "SELECT event_type FROM events WHERE id LIKE 'event_%'"
            )
        }
        self.assertEqual(event_types, {"birth", "baptism", "death", "burial"})

        self.store.create_claim(
            "uncited_claim", "project", "branch", "person", person_a,
            "occupation", "synthetic occupation", actor="test-user",
        )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "needs a citation"):
            self.store.review_claim(
                "uncited_claim", "supported", "direct", "Synthetic rationale.", actor="test-user"
            )
        self.store.review_claim(
            claim_id, "supported", "direct", "Synthetic cited rationale.", actor="test-user"
        )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "decision is immutable"):
            self.store.connection.execute(
                "UPDATE claims SET rationale = 'later overwrite' WHERE id = ?", (claim_id,)
            )
        self.store.connection.rollback()
        self.store.create_claim(
            "rejected_claim", "project", "branch", "person", person_a,
            "birth.date", "impossible synthetic alternative", actor="test-user",
        )
        self.store.add_citation(
            "rejected_citation", "project", "branch", "rejected_claim", source_id,
            locator="synthetic counter-locator", actor="test-user",
        )
        self.store.review_claim(
            "rejected_claim", "rejected", "direct",
            "The cited synthetic source contradicts this alternative.", actor="test-user",
        )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "needs cited evidence"):
            self.store.decide_identity(
                "identity", "supported", "corroborated", "Synthetic identity rationale.", actor="test-user"
            )
        self.store.add_identity_evidence(
            "identity_support", "project", "identity", citation_id,
            "support", "Synthetic positive evidence.", actor="test-user",
        )
        self.store.add_identity_evidence(
            "identity_counter", "project", "identity", citation_id,
            "counter", "Synthetic counterevidence retained for review.", actor="test-user",
        )
        self.store.decide_identity(
            "identity", "supported", "corroborated", "Both evidence polarities were assessed.",
            actor="test-user",
        )
        evidence = self.store.connection.execute(
            "SELECT polarity FROM identity_assessment_evidence ORDER BY polarity"
        ).fetchall()
        self.assertEqual([row[0] for row in evidence], ["counter", "support"])
        self.assertEqual(self.store.validate(), [])

    def test_relationship_is_only_a_container_until_explicit_claim_is_reviewed(self):
        self.store.create_person("parent", "project", "branch", "Parent", actor="test-user")
        self.store.create_person("child", "project", "branch", "Child", actor="test-user")
        self.store.create_relationship(
            "parent_child", "project", "branch", "parent_child",
            [
                {"person_id": "parent", "role": "parent"},
                {"person_id": "child", "role": "child"},
            ],
            actor="test-user",
        )
        columns = {
            row[1] for row in self.store.connection.execute("PRAGMA table_info(relationships)")
        }
        self.assertNotIn("status", columns)
        self.store.create_claim(
            "relationship_claim", "project", "branch", "relationship", "parent_child",
            "relationship.parent_child", True, actor="test-user",
        )
        self.assertEqual(
            self.store.connection.execute(
                "SELECT status FROM claims WHERE id = 'relationship_claim'"
            ).fetchone()[0],
            "unverified",
        )

    def test_conflict_resolution_preserves_all_variants_and_decision(self):
        person_id, source_id, first, _ = self.add_person_source_claim("first", value="1900-01-01")
        self.store.create_claim(
            "claim_second", "project", "branch", "person", person_id,
            "birth.date", "1901-01-01", actor="test-user",
        )
        self.store.add_citation(
            "citation_second", "project", "branch", "claim_second", source_id,
            locator="second synthetic locator", actor="test-user",
        )
        self.store.create_conflict(
            "conflict", "project", "K01", "Synthetic date conflict",
            [first, "claim_second"], actor="test-user",
        )
        self.store.resolve_conflict(
            "decision", "conflict", "project", "Synthetic comparative rationale.",
            {first: "preferred", "claim_second": "not_preferred"},
            decided_by="test-user", actor="test-user",
        )
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM conflict_claims WHERE conflict_id = 'conflict'"
        ).fetchone()[0], 2)
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM claims WHERE id IN (?, ?)", (first, "claim_second")
        ).fetchone()[0], 2)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "claims are preserved"):
            self.store.connection.execute("DELETE FROM claims WHERE id = ?", (first,))
        self.store.connection.rollback()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "claim statement is immutable"):
            self.store.connection.execute(
                "UPDATE claims SET value_json = '\"overwritten\"' WHERE id = ?", (first,)
            )
        self.store.connection.rollback()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
            self.store.connection.execute(
                "UPDATE conflict_decisions SET rationale = 'changed' WHERE id = 'decision'"
            )
        self.store.connection.rollback()

    def test_audit_chain_is_valid_and_append_only(self):
        self.store.append_audit_revision(
            "project", "test-user", "synthetic.note", {"scope": "audit test"}
        )
        self.assertEqual(self.store.validate(), [])
        revisions = self.store.connection.execute(
            "SELECT revision_no, previous_hash, revision_hash FROM audit_revisions ORDER BY revision_no"
        ).fetchall()
        self.assertEqual([row[0] for row in revisions], list(range(1, len(revisions) + 1)))
        self.assertIsNone(revisions[0][1])
        self.assertEqual(revisions[-1][1], revisions[-2][2])
        with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
            self.store.connection.execute(
                "UPDATE audit_revisions SET action = 'changed' WHERE revision_no = 1"
            )
        self.store.connection.rollback()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
            self.store.connection.execute("DELETE FROM audit_revisions WHERE revision_no = 1")
        self.store.connection.rollback()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "extend the chain"):
            self.store.connection.execute(
                "INSERT INTO audit_revisions "
                "(id, project_id, revision_no, previous_hash, revision_hash, actor, action, payload_json, created_at) "
                "VALUES ('gap', 'project', 999, NULL, ?, 'test-user', 'gap', '{}', ?)",
                ("0" * 64, "2026-11-15T00:00:00+00:00"),
            )
        self.store.connection.rollback()

    def test_outbox_is_approved_idempotent_immutable_and_never_sent(self):
        first = self.store.enqueue_outbox(
            "outbox_one", "project", "gramps:create:person:one", "create_person",
            "person", "person_one", {"name": "Synthetic"},
            approved_by="test-user", approved_at="2026-11-15T12:00:00+01:00",
            branch_id="branch",
        )
        self.assertEqual(first, {"id": "outbox_one", "created": True, "sent": False})
        repeated = self.store.enqueue_outbox(
            "outbox_one", "project", "gramps:create:person:one", "create_person",
            "person", "person_one", {"name": "Synthetic"},
            approved_by="test-user", approved_at="2026-11-15T12:00:00+01:00",
            branch_id="branch",
        )
        self.assertFalse(repeated["created"])
        with self.assertRaisesRegex(ValueError, "jinou operaci"):
            self.store.enqueue_outbox(
                "outbox_two", "project", "gramps:create:person:one", "create_person",
                "person", "person_two", {"name": "Different"},
                approved_by="test-user", approved_at="2026-11-15T12:00:00+01:00",
            )
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM sync_outbox_attempts"
        ).fetchone()[0], 0)
        self.assertFalse(self.store.status()["network_writes"])
        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
            self.store.connection.execute(
                "UPDATE sync_outbox SET aggregate_id = 'changed' WHERE id = 'outbox_one'"
            )
        self.store.connection.rollback()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
            self.store.connection.execute("DELETE FROM sync_outbox WHERE id = 'outbox_one'")
        self.store.connection.rollback()
        self.assertEqual(self.store.validate(), [])

    def test_transcription_variants_media_crops_and_negative_searches_are_preserved(self):
        person_id, source_id, _, _ = self.add_person_source_claim("transcription")
        self.store.create_record(
            "record_transcription", "project", "branch", "vital_register", "Synthetic entry",
            source_id=source_id, actor="test-user",
        )
        connection = self.store.connection
        stamp = "2026-11-15T00:00:00+00:00"
        self.store.add_transcription_segment(
            "segment", "project", "branch", "record_transcription", "name", 0,
            actor="test-user",
        )
        for variant_id, author, state, text in (
            ("variant_user", "user", "clear", "Synthetic"),
            ("variant_chatgpt", "chatgpt", "uncertain", "Synthet(?)ic"),
            ("variant_gemini", "gemini", "unreadable", "[…]"),
        ):
            self.store.add_transcription_variant(
                variant_id, "project", "branch", "segment", author, "la", text,
                0.5, state, actor="test-user",
            )
        self.assertEqual(connection.execute(
            "SELECT count(DISTINCT authored_by) FROM transcription_variants"
        ).fetchone()[0], 3)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "superseding variant"):
            connection.execute(
                "UPDATE transcription_variants SET text = 'changed' WHERE id = 'variant_user'"
            )
        connection.rollback()

        digest = "1" * 64
        self.store.add_media_object(
            "media_original", "project", "branch", "original", digest, 1,
            "image/png", "private://original.png", {"kind": "original"},
            source_id=source_id, actor="test-user",
        )
        self.store.add_media_object(
            "media_crop", "project", "branch", "derivative", "2" * 64, 1,
            "image/png", "private://crop.png", {"kind": "crop"},
            source_id=source_id, actor="test-user",
        )
        self.store.add_image_crop(
            "crop", "project", "branch", "media_original", "media_crop",
            (0.1, 0.2, 0.9, 0.8), actor="test-user",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO image_crops "
                "(id, project_id, branch_id, parent_media_id, output_media_id, x0, y0, x1, y1, created_at) "
                "VALUES ('bad_crop', 'project', 'branch', 'media_original', 'media_crop', 0.9, 0.2, 0.1, 0.8, ?)",
                (stamp,),
            )
        connection.rollback()
        self.store.create_research_task(
            "task", "project", "Synthetic task", "What was searched?",
            branch_id="branch", actor="test-user",
        )
        self.store.log_negative_search(
            "negative", "project", "Synthetic query",
            "Register X, years 1900–1901, pages 1–2", "No matching entry found.",
            researcher="test-user", searched_at=stamp, branch_id="branch", task_id="task",
            source_ids=[source_id], actor="test-user",
        )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
            connection.execute(
                "UPDATE negative_searches SET scope = 'changed' WHERE id = 'negative'"
            )
        connection.rollback()
        self.assertEqual(person_id, "person_transcription")
        self.assertEqual(self.store.validate(), [])


if __name__ == "__main__":
    unittest.main()
