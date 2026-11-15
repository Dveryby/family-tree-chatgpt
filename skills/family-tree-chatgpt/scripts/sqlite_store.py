#!/usr/bin/env python3
"""Versioned SQLite evidence store for Family Tree 2.0.

The existing research.json workflow remains supported.  This module is an
opt-in relational store for explicit imports and future approved Gramps
operations; it performs no network access and never sends outbox rows.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
MIGRATION_RE = re.compile(r"(?P<version>[0-9]{4})_(?P<name>[a-z0-9_]+)\.sql")
ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,95}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_json(value):
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Hodnota musí být konečný JSON.") from exc


def digest_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_id(value, field="id"):
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ValueError(
            f"{field}: použij 1–96 malých ASCII písmen, číslic, pomlček či podtržítek."
        )
    return value


def validate_sha256(value, field="sha256"):
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{field}: očekáván SHA-256 malými hex znaky.")
    return value


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    sql: str
    sha256: str


def migrations(directory=MIGRATIONS_DIR):
    directory = Path(directory)
    found = []
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_RE.fullmatch(path.name)
        if not match:
            raise ValueError(f"Neplatný název migračního souboru: {path.name}")
        sql = path.read_text(encoding="utf-8")
        found.append(Migration(
            version=int(match.group("version")),
            name=path.name,
            path=path,
            sql=sql,
            sha256=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        ))
    if not found:
        raise ValueError("Nebyly nalezeny žádné SQLite migrace.")
    versions = [item.version for item in found]
    expected = list(range(1, len(found) + 1))
    if versions != expected:
        raise ValueError(f"SQLite migrace musí být souvislé 1..N; nalezeno {versions}.")
    return tuple(found)


CURRENT_SCHEMA_VERSION = len(migrations())


def _sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _configure(connection, *, query_only=False):
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    if query_only:
        connection.execute("PRAGMA query_only = ON")


def _user_version(connection):
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _verify_migration_ledger(connection, available=None):
    available = migrations() if available is None else available
    current = _user_version(connection)
    if current > len(available):
        raise ValueError(
            f"Databáze používá novější SQLite schéma {current}; tento kód podporuje {len(available)}."
        )
    has_ledger = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if current == 0:
        if has_ledger:
            raise ValueError("Databáze má migrační tabulku, ale PRAGMA user_version je 0.")
        return
    if not has_ledger:
        raise ValueError("Databázi chybí tabulka schema_migrations.")
    rows = connection.execute(
        "SELECT version, name, sha256 FROM schema_migrations ORDER BY version"
    ).fetchall()
    if [row["version"] for row in rows] != list(range(1, current + 1)):
        raise ValueError("Historie SQLite migrací není souvislá.")
    for row in rows:
        expected = available[row["version"] - 1]
        if row["name"] != expected.name or row["sha256"] != expected.sha256:
            raise ValueError(
                f"Kontrolní součet migrace {row['version']} neodpovídá zdrojovému souboru."
            )


def apply_migrations(connection, target_version=None, directory=MIGRATIONS_DIR):
    available = migrations(directory)
    target = len(available) if target_version is None else target_version
    if type(target) is not int or target < 0 or target > len(available):
        raise ValueError(f"Cílová verze migrace musí být 0 až {len(available)}.")
    current = _user_version(connection)
    if target < current:
        raise ValueError("Automatický downgrade SQLite schématu není podporován.")
    _verify_migration_ledger(connection, available)
    for migration in available[current:target]:
        applied_at = now()
        script = (
            "BEGIN IMMEDIATE;\n"
            + migration.sql
            + "\nINSERT INTO schema_migrations(version, name, sha256, applied_at) VALUES ("
            + str(migration.version)
            + ", " + _sql_literal(migration.name)
            + ", " + _sql_literal(migration.sha256)
            + ", " + _sql_literal(applied_at) + ");\n"
            + f"PRAGMA user_version = {migration.version};\n"
            + "COMMIT;\n"
        )
        try:
            connection.executescript(script)
        except sqlite3.Error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
    _verify_migration_ledger(connection, available)
    return _user_version(connection)


def _private_database_path(path, *, must_exist=False):
    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise ValueError("SQLite databáze nesmí být symlink.")
    resolved = candidate.resolve()
    if must_exist and not resolved.is_file():
        raise ValueError("SQLite databáze neexistuje nebo není běžný soubor.")
    for parent in (resolved.parent, *resolved.parent.parents):
        marker = parent / ".git"
        is_repository = marker.is_dir() and (marker / "HEAD").is_file()
        if marker.is_file():
            try:
                is_repository = marker.read_text(encoding="utf-8").startswith("gitdir:")
            except (OSError, UnicodeError):
                is_repository = True
        if is_repository:
            raise ValueError("Soukromou SQLite databázi ulož mimo git repozitář.")
    return resolved


def initialize_database(path, target_version=None):
    path = _private_database_path(path)
    if path.exists():
        raise FileExistsError("SQLite databáze už existuje; init ji nepřepíše.")
    if not path.parent.is_dir():
        raise ValueError("Nadřazený adresář SQLite databáze neexistuje.")
    connection = sqlite3.connect(path)
    try:
        _configure(connection)
        version = apply_migrations(connection, target_version)
    except Exception:
        connection.close()
        path.unlink(missing_ok=True)
        raise
    else:
        connection.close()
        path.chmod(0o600)
    return {"initialized": True, "database": str(path), "schema_version": version}


def migrate_database(path, target_version=None):
    path = _private_database_path(path, must_exist=True)
    connection = sqlite3.connect(path)
    try:
        _configure(connection)
        before = _user_version(connection)
        after = apply_migrations(connection, target_version)
    finally:
        connection.close()
    return {
        "migrated": after != before,
        "database": str(path),
        "from_schema_version": before,
        "schema_version": after,
    }


@contextmanager
def transaction(connection):
    if connection.in_transaction:
        yield
        return
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        connection.execute("ROLLBACK")
        raise
    else:
        connection.execute("COMMIT")


class GenealogyStore:
    """Small explicit API over the migrated schema.

    Every method is local and transactional. Imported entity writers should
    call ``start_import_run`` first and skip the mapping when it returns
    ``created=False``.
    """

    def __init__(self, path, *, migrate=True, read_only=False):
        self.path = _private_database_path(path, must_exist=True)
        if read_only:
            uri = self.path.as_uri() + "?mode=ro"
            self.connection = sqlite3.connect(uri, uri=True)
        else:
            self.connection = sqlite3.connect(self.path)
        _configure(self.connection, query_only=read_only)
        if migrate and not read_only:
            apply_migrations(self.connection)
        else:
            _verify_migration_ledger(self.connection)

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def _append_audit(self, project_id, actor, action, payload, created_at=None):
        if not actor or not str(actor).strip() or not action or not str(action).strip():
            raise ValueError("Audit vyžaduje aktéra a akci.")
        payload_json = canonical_json(payload)
        previous = self.connection.execute(
            "SELECT revision_no, revision_hash FROM audit_revisions "
            "WHERE project_id = ? ORDER BY revision_no DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        revision_no = 1 if previous is None else previous["revision_no"] + 1
        previous_hash = None if previous is None else previous["revision_hash"]
        created_at = created_at or now()
        material = canonical_json({
            "project_id": project_id,
            "revision_no": revision_no,
            "previous_hash": previous_hash,
            "actor": actor,
            "action": action,
            "payload": json.loads(payload_json),
            "created_at": created_at,
        })
        revision_hash = digest_text(material)
        audit_id = f"{project_id}:{revision_no}"
        self.connection.execute(
            "INSERT INTO audit_revisions "
            "(id, project_id, revision_no, previous_hash, revision_hash, actor, action, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                audit_id, project_id, revision_no, previous_hash, revision_hash,
                actor, action, payload_json, created_at,
            ),
        )
        return revision_hash

    def append_audit_revision(self, project_id, actor, action, payload):
        with transaction(self.connection):
            return self._append_audit(project_id, actor, action, payload)

    def create_project(self, project_id, name, *, description="", actor):
        validate_id(project_id, "project_id")
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO projects(id, name, description, created_at) VALUES (?, ?, ?, ?)",
                (project_id, name, description, created_at),
            )
            self._append_audit(
                project_id, actor, "project.created",
                {"project_id": project_id, "name": name}, created_at,
            )
        return project_id

    def create_import_branch(
        self, branch_id, project_id, branch_key, label, history_kind,
        *, source_revision="", metadata=None, actor,
    ):
        validate_id(branch_id, "branch_id")
        validate_id(project_id, "project_id")
        validate_id(branch_key, "branch_key")
        metadata_json = canonical_json({} if metadata is None else metadata)
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO import_branches "
                "(id, project_id, branch_key, label, history_kind, source_revision, metadata_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    branch_id, project_id, branch_key, label, history_kind,
                    source_revision, metadata_json, created_at,
                ),
            )
            self._append_audit(
                project_id, actor, "import_branch.created",
                {"branch_id": branch_id, "branch_key": branch_key, "history_kind": history_kind},
                created_at,
            )
        return branch_id

    def register_original_file(
        self, file_id, project_id, branch_id, *, sha256, byte_size,
        original_name, storage_path, provenance_key, provenance,
        media_type="application/octet-stream", acquired_at=None, actor,
    ):
        validate_sha256(sha256)
        provenance_json = canonical_json(provenance)
        values = (
            file_id, project_id, branch_id, sha256, byte_size, original_name,
            media_type, storage_path, provenance_key, provenance_json, acquired_at,
        )
        created_at = now()
        with transaction(self.connection):
            existing = self.connection.execute(
                "SELECT id, project_id, branch_id, sha256, byte_size, original_name, media_type, "
                "storage_path, provenance_key, provenance_json, acquired_at FROM original_files "
                "WHERE branch_id = ? AND sha256 = ? AND provenance_key = ?",
                (branch_id, sha256, provenance_key),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != values:
                    raise ValueError("Stejný původ souboru už existuje s jinými metadata.")
                return {"id": existing["id"], "created": False}
            self.connection.execute(
                "INSERT INTO original_files "
                "(id, project_id, branch_id, sha256, byte_size, original_name, media_type, "
                "storage_path, provenance_key, provenance_json, acquired_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                values + (created_at,),
            )
            self._append_audit(
                project_id, actor, "original_file.registered",
                {"file_id": file_id, "branch_id": branch_id, "sha256": sha256},
                created_at,
            )
        return {"id": file_id, "created": True}

    def start_import_run(
        self, run_id, project_id, branch_id, original_file_id, *,
        idempotency_key, importer, importer_version="",
        source_schema_version=None, summary=None, actor,
    ):
        summary_json = canonical_json({} if summary is None else summary)
        comparison = (
            run_id, project_id, branch_id, original_file_id, idempotency_key,
            importer, importer_version, source_schema_version, summary_json,
        )
        started_at = now()
        with transaction(self.connection):
            existing = self.connection.execute(
                "SELECT id, project_id, branch_id, original_file_id, idempotency_key, importer, "
                "importer_version, source_schema_version, summary_json FROM import_runs "
                "WHERE branch_id = ? AND idempotency_key = ?",
                (branch_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != comparison:
                    raise ValueError("Idempotency klíč importu už označuje jiný obsah.")
                return {"id": existing["id"], "created": False}
            self.connection.execute(
                "INSERT INTO import_runs "
                "(id, project_id, branch_id, original_file_id, idempotency_key, importer, "
                "importer_version, source_schema_version, status, summary_json, started_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'staged', ?, ?)",
                comparison[:8] + (summary_json, started_at),
            )
            self._append_audit(
                project_id, actor, "import.started",
                {"run_id": run_id, "branch_id": branch_id, "idempotency_key": idempotency_key},
                started_at,
            )
        return {"id": run_id, "created": True}

    def finish_import_run(self, run_id, *, status, actor):
        if status not in ("validated", "committed", "failed"):
            raise ValueError("Import lze dokončit jako validated, committed nebo failed.")
        row = self.connection.execute(
            "SELECT project_id, status FROM import_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Importní běh neexistuje.")
        allowed = {
            "staged": {"validated", "failed"},
            "validated": {"committed", "failed"},
        }
        if status not in allowed.get(row["status"], set()):
            raise ValueError("Neplatný přechod stavu importu.")
        completed_at = now() if status in ("committed", "failed") else None
        with transaction(self.connection):
            self.connection.execute(
                "UPDATE import_runs SET status = ?, completed_at = ? WHERE id = ?",
                (status, completed_at, run_id),
            )
            self._append_audit(
                row["project_id"], actor, "import.status_changed",
                {"run_id": run_id, "from": row["status"], "to": status},
            )

    def add_import_snapshot(
        self, snapshot_id, project_id, branch_id, import_run_id,
        original_file_id, snapshot_kind, source_schema_version,
        source_revision, payload, *, actor,
    ):
        payload_json = canonical_json(payload)
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO import_state_snapshots "
                "(id, project_id, branch_id, import_run_id, original_file_id, snapshot_kind, "
                "source_schema_version, source_revision, payload_json, payload_sha256, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot_id, project_id, branch_id, import_run_id,
                    original_file_id, snapshot_kind, source_schema_version,
                    source_revision, payload_json, digest_text(payload_json), created_at,
                ),
            )
            self._append_audit(
                project_id, actor, "import.snapshot_preserved",
                {
                    "snapshot_id": snapshot_id,
                    "kind": snapshot_kind,
                    "source_revision": source_revision,
                },
                created_at,
            )

    def add_import_history_event(
        self, event_id, project_id, branch_id, import_run_id,
        event_index, payload, *, source_revision=None, actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO import_history_events "
                "(id, project_id, branch_id, import_run_id, event_index, source_revision, "
                "payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id, project_id, branch_id, import_run_id, event_index,
                    source_revision, canonical_json(payload), created_at,
                ),
            )

    def add_imported_record_text(
        self, text_id, project_id, branch_id, import_run_id, record_id,
        text_kind, text_value, provenance, *, actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO imported_record_texts "
                "(id, project_id, branch_id, import_run_id, record_id, text_kind, "
                "text_value, provenance_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    text_id, project_id, branch_id, import_run_id, record_id,
                    text_kind, text_value, canonical_json(provenance), created_at,
                ),
            )

    def add_imported_uncertainty(
        self, uncertainty_id, project_id, branch_id, import_run_id,
        record_id, sequence_no, text, *, actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO imported_record_uncertainties "
                "(id, project_id, branch_id, import_run_id, record_id, sequence_no, "
                "uncertainty_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    uncertainty_id, project_id, branch_id, import_run_id,
                    record_id, sequence_no, text, created_at,
                ),
            )

    def create_person(
        self, person_id, project_id, branch_id, label, *, import_run_id=None,
        notes="", source_identifier="", source_json=None, actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO persons(id, project_id, branch_id, import_run_id, label, notes, created_at, "
                "source_identifier, source_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    person_id, project_id, branch_id, import_run_id, label, notes, created_at,
                    source_identifier, canonical_json({} if source_json is None else source_json),
                ),
            )
            self._append_audit(
                project_id, actor, "person.container_created",
                {"person_id": person_id, "branch_id": branch_id}, created_at,
            )

    def create_source(
        self, source_id, project_id, branch_id, kind, title, *, citation="",
        repository="", url="", notes="", import_run_id=None,
        source_identifier="", source_json=None, actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO sources "
                "(id, project_id, branch_id, import_run_id, kind, title, citation, repository, url, notes, "
                "created_at, source_identifier, source_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source_id, project_id, branch_id, import_run_id, kind, title,
                    citation, repository, url, notes, created_at, source_identifier,
                    canonical_json({} if source_json is None else source_json),
                ),
            )
            self._append_audit(
                project_id, actor, "source.created",
                {"source_id": source_id, "branch_id": branch_id}, created_at,
            )

    def create_record(
        self, record_id, project_id, branch_id, record_kind, title, *,
        source_id=None, reading_status="unread", visual_reviewed_at=None,
        original_language="", notes="", import_run_id=None,
        source_identifier="", source_json=None, actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO research_records "
                "(id, project_id, branch_id, import_run_id, source_id, record_kind, title, "
                "original_language, reading_status, visual_reviewed_at, notes, created_at, "
                "source_identifier, source_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_id, project_id, branch_id, import_run_id, source_id,
                    record_kind, title, original_language, reading_status,
                    visual_reviewed_at, notes, created_at, source_identifier,
                    canonical_json({} if source_json is None else source_json),
                ),
            )
            self._append_audit(
                project_id, actor, "record.created",
                {"record_id": record_id, "reading_status": reading_status}, created_at,
            )

    def add_transcription_segment(
        self, segment_id, project_id, branch_id, record_id, segment_key,
        sequence_no, *, region=None, actor,
    ):
        created_at = now()
        region_json = None if region is None else canonical_json(region)
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO transcription_segments "
                "(id, project_id, branch_id, record_id, segment_key, sequence_no, region_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    segment_id, project_id, branch_id, record_id, segment_key,
                    sequence_no, region_json, created_at,
                ),
            )
            self._append_audit(
                project_id, actor, "transcription_segment.created",
                {"segment_id": segment_id, "record_id": record_id}, created_at,
            )

    def add_transcription_variant(
        self, variant_id, project_id, branch_id, segment_id, authored_by,
        language, text, reading_confidence, reading_state, *,
        author_label="", notes="", supersedes_variant_id=None, actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO transcription_variants "
                "(id, project_id, branch_id, segment_id, supersedes_variant_id, authored_by, "
                "author_label, language, text, reading_confidence, reading_state, notes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    variant_id, project_id, branch_id, segment_id, supersedes_variant_id,
                    authored_by, author_label, language, text, reading_confidence,
                    reading_state, notes, created_at,
                ),
            )
            self._append_audit(
                project_id, actor, "transcription_variant.added",
                {
                    "variant_id": variant_id,
                    "segment_id": segment_id,
                    "authored_by": authored_by,
                    "supersedes_variant_id": supersedes_variant_id,
                },
                created_at,
            )

    def create_relationship(
        self, relationship_id, project_id, branch_id, relationship_type,
        participants, *, import_run_id=None, notes="", source_identifier="",
        source_json=None, actor,
    ):
        if not isinstance(participants, list) or len(participants) < 2:
            raise ValueError("Vztah vyžaduje alespoň dva účastníky.")
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO relationships "
                "(id, project_id, branch_id, import_run_id, relationship_type, notes, created_at, "
                "source_identifier, source_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    relationship_id, project_id, branch_id, import_run_id,
                    relationship_type, notes, created_at, source_identifier,
                    canonical_json({} if source_json is None else source_json),
                ),
            )
            for participant in participants:
                self.connection.execute(
                    "INSERT INTO relationship_participants(relationship_id, branch_id, person_id, role) "
                    "VALUES (?, ?, ?, ?)",
                    (relationship_id, branch_id, participant["person_id"], participant["role"]),
                )
            self._append_audit(
                project_id, actor, "relationship.container_created",
                {"relationship_id": relationship_id, "branch_id": branch_id}, created_at,
            )

    def create_event(
        self, event_id, project_id, branch_id, event_type, *, participants=None,
        date_text="", place_text="", description="", import_run_id=None, actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO events "
                "(id, project_id, branch_id, import_run_id, event_type, date_text, place_text, description, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id, project_id, branch_id, import_run_id, event_type,
                    date_text, place_text, description, created_at,
                ),
            )
            for participant in participants or []:
                self.connection.execute(
                    "INSERT INTO event_participants(event_id, branch_id, person_id, role) VALUES (?, ?, ?, ?)",
                    (event_id, branch_id, participant["person_id"], participant["role"]),
                )
            self._append_audit(
                project_id, actor, "event.container_created",
                {"event_id": event_id, "event_type": event_type}, created_at,
            )

    def create_claim(
        self, claim_id, project_id, branch_id, subject_kind, subject_id,
        predicate, value, *, evidence_level="none", notes="",
        import_run_id=None, source_identifier="", source_json=None, actor,
    ):
        subject_columns = {
            "person": (subject_id, None, None, None),
            "relationship": (None, subject_id, None, None),
            "event": (None, None, subject_id, None),
            "record": (None, None, None, subject_id),
        }
        if subject_kind not in subject_columns:
            raise ValueError("Neznámý typ subjektu tvrzení.")
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO claims "
                "(id, project_id, branch_id, import_run_id, subject_kind, person_id, relationship_id, "
                "event_id, record_id, predicate, value_json, status, evidence_level, rationale, notes, "
                "created_at, source_identifier, source_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unverified', ?, '', ?, ?, ?, ?)",
                (
                    claim_id, project_id, branch_id, import_run_id, subject_kind,
                    *subject_columns[subject_kind], predicate, canonical_json(value),
                    evidence_level, notes, created_at, source_identifier,
                    canonical_json({} if source_json is None else source_json),
                ),
            )
            self._append_audit(
                project_id, actor, "claim.created",
                {"claim_id": claim_id, "subject_kind": subject_kind, "predicate": predicate},
                created_at,
            )

    def add_citation(
        self, citation_id, project_id, branch_id, claim_id, source_id, *,
        record_id=None, locator="", quotation="", note="",
        source_identifier="", source_json=None, actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO citations "
                "(id, project_id, branch_id, claim_id, source_id, record_id, locator, quotation, note, "
                "created_at, source_identifier, source_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    citation_id, project_id, branch_id, claim_id, source_id,
                    record_id, locator, quotation, note, created_at, source_identifier,
                    canonical_json({} if source_json is None else source_json),
                ),
            )
            self._append_audit(
                project_id, actor, "citation.added",
                {"citation_id": citation_id, "claim_id": claim_id}, created_at,
            )

    def review_claim(self, claim_id, status, evidence_level, rationale, *, actor):
        if status not in ("supported", "rejected"):
            raise ValueError("Tvrzení lze posoudit jako supported nebo rejected.")
        row = self.connection.execute(
            "SELECT project_id, status FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Tvrzení neexistuje.")
        reviewed_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "UPDATE claims SET status = ?, evidence_level = ?, rationale = ?, reviewed_at = ? WHERE id = ?",
                (status, evidence_level, rationale, reviewed_at, claim_id),
            )
            self._append_audit(
                row["project_id"], actor, "claim.reviewed",
                {"claim_id": claim_id, "status": status, "evidence_level": evidence_level},
                reviewed_at,
            )

    def create_identity_assessment(
        self, assessment_id, project_id, left_person_id, right_person_id, *, actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO identity_assessments "
                "(id, project_id, left_person_id, right_person_id, status, evidence_level, rationale, created_at) "
                "VALUES (?, ?, ?, ?, 'unresolved', 'none', '', ?)",
                (assessment_id, project_id, left_person_id, right_person_id, created_at),
            )
            self._append_audit(
                project_id, actor, "identity_assessment.created",
                {"assessment_id": assessment_id, "persons": [left_person_id, right_person_id]},
                created_at,
            )

    def add_identity_evidence(
        self, evidence_id, project_id, assessment_id, citation_id,
        polarity, explanation, *, actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO identity_assessment_evidence "
                "(id, project_id, assessment_id, citation_id, polarity, explanation, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    evidence_id, project_id, assessment_id, citation_id,
                    polarity, explanation, created_at,
                ),
            )
            self._append_audit(
                project_id, actor, "identity_evidence.added",
                {"assessment_id": assessment_id, "evidence_id": evidence_id, "polarity": polarity},
                created_at,
            )

    def decide_identity(self, assessment_id, status, evidence_level, rationale, *, actor):
        if status not in ("supported", "rejected"):
            raise ValueError("Totožnost lze uzavřít jako supported nebo rejected.")
        row = self.connection.execute(
            "SELECT project_id FROM identity_assessments WHERE id = ?", (assessment_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Posouzení totožnosti neexistuje.")
        decided_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "UPDATE identity_assessments "
                "SET status = ?, evidence_level = ?, rationale = ?, decided_at = ? WHERE id = ?",
                (status, evidence_level, rationale, decided_at, assessment_id),
            )
            self._append_audit(
                row["project_id"], actor, "identity_assessment.decided",
                {"assessment_id": assessment_id, "status": status}, decided_at,
            )

    def create_conflict(
        self, conflict_id, project_id, code, label, claim_ids, *,
        source_identifier="", source_json=None, source_branch_id=None, actor,
    ):
        if not isinstance(claim_ids, list) or len(set(claim_ids)) < 2:
            raise ValueError("Konflikt vyžaduje nejméně dvě různá tvrzení.")
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO conflicts(id, project_id, code, label, status, created_at, "
                "source_identifier, source_json, source_branch_id) "
                "VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?)",
                (
                    conflict_id, project_id, code, label, created_at, source_identifier,
                    canonical_json({} if source_json is None else source_json), source_branch_id,
                ),
            )
            for claim_id in claim_ids:
                self.connection.execute(
                    "INSERT INTO conflict_claims(conflict_id, project_id, claim_id) VALUES (?, ?, ?)",
                    (conflict_id, project_id, claim_id),
                )
            self._append_audit(
                project_id, actor, "conflict.created",
                {"conflict_id": conflict_id, "claim_ids": claim_ids}, created_at,
            )

    def resolve_conflict(
        self, decision_id, conflict_id, project_id, rationale, dispositions, *, decided_by, actor,
    ):
        if not isinstance(dispositions, dict) or not dispositions:
            raise ValueError("Rozhodnutí konfliktu vyžaduje dispozici alespoň jednoho tvrzení.")
        decided_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO conflict_decisions "
                "(id, conflict_id, project_id, rationale, decided_by, decided_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (decision_id, conflict_id, project_id, rationale, decided_by, decided_at),
            )
            for claim_id, disposition in dispositions.items():
                self.connection.execute(
                    "INSERT INTO conflict_decision_claims "
                    "(decision_id, conflict_id, project_id, claim_id, disposition) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (decision_id, conflict_id, project_id, claim_id, disposition),
                )
            self.connection.execute(
                "UPDATE conflicts SET status = 'resolved', resolved_at = ? WHERE id = ? AND project_id = ?",
                (decided_at, conflict_id, project_id),
            )
            self._append_audit(
                project_id, actor, "conflict.resolved",
                {"conflict_id": conflict_id, "decision_id": decision_id}, decided_at,
            )

    def add_media_object(
        self, media_id, project_id, branch_id, media_kind, sha256, byte_size,
        media_type, storage_path, provenance, *, original_file_id=None,
        source_id=None, record_id=None, source_identifier="", source_json=None, actor,
    ):
        validate_sha256(sha256)
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO media_objects "
                "(id, project_id, branch_id, original_file_id, source_id, record_id, media_kind, "
                "sha256, byte_size, media_type, storage_path, provenance_json, created_at, "
                "source_identifier, source_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    media_id, project_id, branch_id, original_file_id, source_id,
                    record_id, media_kind, sha256, byte_size, media_type,
                    storage_path, canonical_json(provenance), created_at, source_identifier,
                    canonical_json({} if source_json is None else source_json),
                ),
            )
            self._append_audit(
                project_id, actor, "media.registered",
                {"media_id": media_id, "media_kind": media_kind, "sha256": sha256},
                created_at,
            )

    def add_image_crop(
        self, crop_id, project_id, branch_id, parent_media_id, output_media_id,
        box, *, operation=None, actor,
    ):
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            raise ValueError("Výřez vyžaduje čtyři relativní souřadnice x0,y0,x1,y1.")
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO image_crops "
                "(id, project_id, branch_id, parent_media_id, output_media_id, "
                "x0, y0, x1, y1, operation_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    crop_id, project_id, branch_id, parent_media_id, output_media_id,
                    *box, canonical_json({} if operation is None else operation), created_at,
                ),
            )
            self._append_audit(
                project_id, actor, "image_crop.registered",
                {
                    "crop_id": crop_id,
                    "parent_media_id": parent_media_id,
                    "output_media_id": output_media_id,
                },
                created_at,
            )

    def create_research_task(
        self, task_id, project_id, title, question, *, branch_id=None,
        priority="normal", next_step="", actor,
    ):
        created_at = now()
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO research_tasks "
                "(id, project_id, branch_id, title, question, status, priority, next_step, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)",
                (
                    task_id, project_id, branch_id, title, question,
                    priority, next_step, created_at,
                ),
            )
            self._append_audit(
                project_id, actor, "research_task.created",
                {"task_id": task_id, "branch_id": branch_id}, created_at,
            )

    def log_negative_search(
        self, search_id, project_id, query, scope, result_detail, *,
        researcher, searched_at, branch_id=None, task_id=None,
        source_ids=None, actor,
    ):
        with transaction(self.connection):
            self.connection.execute(
                "INSERT INTO negative_searches "
                "(id, project_id, branch_id, task_id, searched_at, query, scope, result_detail, researcher) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    search_id, project_id, branch_id, task_id, searched_at,
                    query, scope, result_detail, researcher,
                ),
            )
            for source_id in source_ids or []:
                self.connection.execute(
                    "INSERT INTO negative_search_sources(search_id, project_id, source_id) VALUES (?, ?, ?)",
                    (search_id, project_id, source_id),
                )
            self._append_audit(
                project_id, actor, "negative_search.logged",
                {"search_id": search_id, "scope": scope}, searched_at,
            )

    def enqueue_outbox(
        self, outbox_id, project_id, idempotency_key, operation_type,
        aggregate_type, aggregate_id, payload, *, approved_by,
        approved_at, branch_id=None,
    ):
        payload_json = canonical_json(payload)
        payload_sha256 = digest_text(payload_json)
        comparison = (
            outbox_id, project_id, branch_id, idempotency_key, "gramps_web",
            operation_type, aggregate_type, aggregate_id, payload_json,
            payload_sha256, approved_by, approved_at,
        )
        created_at = now()
        with transaction(self.connection):
            existing = self.connection.execute(
                "SELECT id, project_id, branch_id, idempotency_key, destination, operation_type, "
                "aggregate_type, aggregate_id, payload_json, payload_sha256, approved_by, approved_at "
                "FROM sync_outbox WHERE project_id = ? AND idempotency_key = ?",
                (project_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != comparison:
                    raise ValueError("Idempotency klíč outboxu už označuje jinou operaci.")
                return {"id": existing["id"], "created": False, "sent": False}
            self.connection.execute(
                "INSERT INTO sync_outbox "
                "(id, project_id, branch_id, idempotency_key, destination, operation_type, "
                "aggregate_type, aggregate_id, payload_json, payload_sha256, approved_by, approved_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                comparison + (created_at,),
            )
            self._append_audit(
                project_id, approved_by, "outbox.enqueued",
                {"outbox_id": outbox_id, "idempotency_key": idempotency_key}, created_at,
            )
        return {"id": outbox_id, "created": True, "sent": False}

    def status(self):
        return database_status(self.connection)

    def validate(self):
        return validate_database(self.connection)


def _table_count(connection, table):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    if exists is None:
        return None
    return int(connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])


def database_status(database):
    close = False
    if isinstance(database, sqlite3.Connection):
        connection = database
    else:
        path = _private_database_path(database, must_exist=True)
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        _configure(connection, query_only=True)
        close = True
    try:
        _verify_migration_ledger(connection)
        tables = (
            "projects", "import_branches", "original_files", "import_runs", "persons",
            "sources", "research_records", "events", "relationships", "claims",
            "citations", "identity_assessments", "conflicts", "audit_revisions", "sync_outbox",
            "import_state_snapshots", "import_history_events", "imported_record_texts",
            "imported_record_uncertainties",
        )
        return {
            "schema_version": _user_version(connection),
            "current_schema_version": CURRENT_SCHEMA_VERSION,
            "needs_migration": _user_version(connection) != CURRENT_SCHEMA_VERSION,
            "counts": {table: _table_count(connection, table) for table in tables},
            "network_writes": False,
        }
    finally:
        if close:
            connection.close()


def validate_database(database):
    close = False
    if isinstance(database, sqlite3.Connection):
        connection = database
    else:
        path = _private_database_path(database, must_exist=True)
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        _configure(connection, query_only=True)
        close = True
    errors = []
    try:
        schema_version = _user_version(connection)
        try:
            _verify_migration_ledger(connection)
        except ValueError as exc:
            errors.append(str(exc))
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        if [row[0] for row in integrity] != ["ok"]:
            errors.extend(f"SQLite integrity_check: {row[0]}" for row in integrity)
        for row in connection.execute("PRAGMA foreign_key_check"):
            errors.append(f"Cizí klíč porušen: tabulka {row[0]}, rowid {row[1]}.")
        if schema_version != CURRENT_SCHEMA_VERSION:
            errors.append(
                f"SQLite schéma {schema_version} není aktuální; očekáváno {CURRENT_SCHEMA_VERSION}."
            )
            return errors
        bad_claims = connection.execute(
            "SELECT id FROM claims c WHERE status IN ('supported', 'rejected') "
            "AND (trim(rationale) = '' OR evidence_level = 'none' OR reviewed_at IS NULL "
            "OR NOT EXISTS (SELECT 1 FROM citations x WHERE x.claim_id = c.id))"
        ).fetchall()
        errors.extend(f"Posouzené tvrzení bez úplné opory: {row['id']}" for row in bad_claims)
        bad_identity = connection.execute(
            "SELECT id FROM identity_assessments a WHERE status IN ('supported', 'rejected') "
            "AND (trim(rationale) = '' OR evidence_level = 'none' OR decided_at IS NULL "
            "OR NOT EXISTS (SELECT 1 FROM identity_assessment_evidence e WHERE e.assessment_id = a.id))"
        ).fetchall()
        errors.extend(f"Závěr totožnosti bez citované opory: {row['id']}" for row in bad_identity)
        for project in connection.execute("SELECT id FROM projects ORDER BY id"):
            previous_hash = None
            expected_revision = 1
            rows = connection.execute(
                "SELECT * FROM audit_revisions WHERE project_id = ? ORDER BY revision_no",
                (project["id"],),
            ).fetchall()
            for row in rows:
                material = canonical_json({
                    "project_id": row["project_id"],
                    "revision_no": row["revision_no"],
                    "previous_hash": row["previous_hash"],
                    "actor": row["actor"],
                    "action": row["action"],
                    "payload": json.loads(row["payload_json"]),
                    "created_at": row["created_at"],
                })
                if row["revision_no"] != expected_revision or row["previous_hash"] != previous_hash:
                    errors.append(f"Auditní řetězec projektu {project['id']} není souvislý.")
                    break
                if digest_text(material) != row["revision_hash"]:
                    errors.append(f"Auditní hash projektu {project['id']} nesouhlasí.")
                    break
                previous_hash = row["revision_hash"]
                expected_revision += 1
        for row in connection.execute("SELECT id, payload_json, payload_sha256 FROM sync_outbox"):
            if digest_text(row["payload_json"]) != row["payload_sha256"]:
                errors.append(f"Outbox {row['id']} má chybný hash payloadu.")
        for row in connection.execute(
            "SELECT id, payload_json, payload_sha256 FROM import_state_snapshots"
        ):
            if digest_text(row["payload_json"]) != row["payload_sha256"]:
                errors.append(f"Importní snapshot {row['id']} má chybný hash payloadu.")
        return errors
    finally:
        if close:
            connection.close()
