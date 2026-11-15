-- Lossless research.json import metadata and local-only Gramps approval support.
-- Imported identifiers remain available in source_identifier while database
-- primary keys are branch-scoped deterministic identifiers.

ALTER TABLE persons ADD COLUMN source_identifier TEXT NOT NULL DEFAULT '';
ALTER TABLE persons ADD COLUMN source_json TEXT NOT NULL DEFAULT '{}'
    CHECK (json_valid(source_json) AND json_type(source_json) = 'object');

ALTER TABLE sources ADD COLUMN source_identifier TEXT NOT NULL DEFAULT '';
ALTER TABLE sources ADD COLUMN source_json TEXT NOT NULL DEFAULT '{}'
    CHECK (json_valid(source_json) AND json_type(source_json) = 'object');

ALTER TABLE research_records ADD COLUMN source_identifier TEXT NOT NULL DEFAULT '';
ALTER TABLE research_records ADD COLUMN source_json TEXT NOT NULL DEFAULT '{}'
    CHECK (json_valid(source_json) AND json_type(source_json) = 'object');

ALTER TABLE relationships ADD COLUMN source_identifier TEXT NOT NULL DEFAULT '';
ALTER TABLE relationships ADD COLUMN source_json TEXT NOT NULL DEFAULT '{}'
    CHECK (json_valid(source_json) AND json_type(source_json) = 'object');

ALTER TABLE claims ADD COLUMN source_identifier TEXT NOT NULL DEFAULT '';
ALTER TABLE claims ADD COLUMN source_json TEXT NOT NULL DEFAULT '{}'
    CHECK (json_valid(source_json) AND json_type(source_json) = 'object');

ALTER TABLE citations ADD COLUMN source_identifier TEXT NOT NULL DEFAULT '';
ALTER TABLE citations ADD COLUMN source_json TEXT NOT NULL DEFAULT '{}'
    CHECK (json_valid(source_json) AND json_type(source_json) = 'object');

ALTER TABLE conflicts ADD COLUMN source_identifier TEXT NOT NULL DEFAULT '';
ALTER TABLE conflicts ADD COLUMN source_json TEXT NOT NULL DEFAULT '{}'
    CHECK (json_valid(source_json) AND json_type(source_json) = 'object');
ALTER TABLE conflicts ADD COLUMN source_branch_id TEXT REFERENCES import_branches(id) ON DELETE RESTRICT;

ALTER TABLE media_objects ADD COLUMN source_identifier TEXT NOT NULL DEFAULT '';
ALTER TABLE media_objects ADD COLUMN source_json TEXT NOT NULL DEFAULT '{}'
    CHECK (json_valid(source_json) AND json_type(source_json) = 'object');

CREATE UNIQUE INDEX persons_source_identifier_idx
    ON persons(branch_id, source_identifier) WHERE source_identifier <> '';
CREATE UNIQUE INDEX sources_source_identifier_idx
    ON sources(branch_id, source_identifier) WHERE source_identifier <> '';
CREATE UNIQUE INDEX records_source_identifier_idx
    ON research_records(branch_id, source_identifier) WHERE source_identifier <> '';
CREATE UNIQUE INDEX relationships_source_identifier_idx
    ON relationships(branch_id, source_identifier) WHERE source_identifier <> '';
CREATE UNIQUE INDEX claims_source_identifier_idx
    ON claims(branch_id, source_identifier) WHERE source_identifier <> '';
CREATE UNIQUE INDEX citations_source_identifier_idx
    ON citations(branch_id, source_identifier) WHERE source_identifier <> '';
CREATE UNIQUE INDEX conflicts_source_identifier_idx
    ON conflicts(source_branch_id, source_identifier)
    WHERE source_branch_id IS NOT NULL AND source_identifier <> '';
CREATE UNIQUE INDEX media_source_identifier_idx
    ON media_objects(branch_id, source_identifier) WHERE source_identifier <> '';

CREATE TABLE import_state_snapshots (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    import_run_id TEXT NOT NULL,
    original_file_id TEXT NOT NULL,
    snapshot_kind TEXT NOT NULL CHECK (snapshot_kind IN ('history', 'current')),
    source_schema_version INTEGER NOT NULL CHECK (source_schema_version IN (1, 2)),
    source_revision INTEGER NOT NULL CHECK (source_revision >= 0),
    payload_json TEXT NOT NULL
        CHECK (json_valid(payload_json) AND json_type(payload_json) = 'object'),
    payload_sha256 TEXT NOT NULL
        CHECK (length(payload_sha256) = 64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'),
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (import_run_id, branch_id)
        REFERENCES import_runs(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (original_file_id, branch_id)
        REFERENCES original_files(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (import_run_id, snapshot_kind, source_revision),
    UNIQUE (id, project_id)
);

CREATE TABLE import_history_events (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    import_run_id TEXT NOT NULL,
    event_index INTEGER NOT NULL CHECK (event_index >= 0),
    source_revision INTEGER,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (import_run_id, branch_id)
        REFERENCES import_runs(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (import_run_id, event_index)
);

CREATE TABLE imported_record_texts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    import_run_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    text_kind TEXT NOT NULL
        CHECK (text_kind IN ('transcription', 'translation', 'interpretation')),
    text_value TEXT NOT NULL,
    provenance_json TEXT NOT NULL
        CHECK (json_valid(provenance_json) AND json_type(provenance_json) = 'object'),
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (import_run_id, branch_id)
        REFERENCES import_runs(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (record_id, branch_id)
        REFERENCES research_records(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (record_id, text_kind)
);

CREATE TABLE imported_record_uncertainties (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    import_run_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
    uncertainty_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (import_run_id, branch_id)
        REFERENCES import_runs(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (record_id, branch_id)
        REFERENCES research_records(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (record_id, sequence_no)
);

CREATE TRIGGER import_state_snapshots_no_update
BEFORE UPDATE ON import_state_snapshots
BEGIN
    SELECT RAISE(ABORT, 'import snapshots are immutable');
END;

CREATE TRIGGER import_state_snapshots_no_delete
BEFORE DELETE ON import_state_snapshots
BEGIN
    SELECT RAISE(ABORT, 'import snapshots are immutable');
END;

CREATE TRIGGER import_history_events_no_update
BEFORE UPDATE ON import_history_events
BEGIN
    SELECT RAISE(ABORT, 'import history is append-only');
END;

CREATE TRIGGER import_history_events_no_delete
BEFORE DELETE ON import_history_events
BEGIN
    SELECT RAISE(ABORT, 'import history is append-only');
END;

CREATE TRIGGER imported_record_texts_no_update
BEFORE UPDATE ON imported_record_texts
BEGIN
    SELECT RAISE(ABORT, 'imported record texts are immutable');
END;

CREATE TRIGGER imported_record_texts_no_delete
BEFORE DELETE ON imported_record_texts
BEGIN
    SELECT RAISE(ABORT, 'imported record texts are immutable');
END;

CREATE TRIGGER imported_record_uncertainties_no_update
BEFORE UPDATE ON imported_record_uncertainties
BEGIN
    SELECT RAISE(ABORT, 'imported uncertainties are immutable');
END;

CREATE TRIGGER imported_record_uncertainties_no_delete
BEFORE DELETE ON imported_record_uncertainties
BEGIN
    SELECT RAISE(ABORT, 'imported uncertainties are immutable');
END;

CREATE TRIGGER persons_import_source_no_update
BEFORE UPDATE OF source_identifier, source_json ON persons
WHEN OLD.import_run_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'import provenance is immutable');
END;

CREATE TRIGGER persons_import_no_delete
BEFORE DELETE ON persons
WHEN OLD.import_run_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'imported persons are preserved');
END;

CREATE TRIGGER sources_import_source_no_update
BEFORE UPDATE OF source_identifier, source_json ON sources
WHEN OLD.import_run_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'import provenance is immutable');
END;

CREATE TRIGGER sources_import_no_delete
BEFORE DELETE ON sources
WHEN OLD.import_run_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'imported sources are preserved');
END;

CREATE TRIGGER records_import_source_no_update
BEFORE UPDATE OF source_identifier, source_json ON research_records
WHEN OLD.import_run_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'import provenance is immutable');
END;

CREATE TRIGGER records_import_no_delete
BEFORE DELETE ON research_records
WHEN OLD.import_run_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'imported records are preserved');
END;

CREATE TRIGGER relationships_import_source_no_update
BEFORE UPDATE OF source_identifier, source_json ON relationships
WHEN OLD.import_run_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'import provenance is immutable');
END;

CREATE TRIGGER relationships_import_no_delete
BEFORE DELETE ON relationships
WHEN OLD.import_run_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'imported relationships are preserved');
END;

CREATE TRIGGER claims_import_source_no_update
BEFORE UPDATE OF source_identifier, source_json ON claims
WHEN OLD.import_run_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'import provenance is immutable');
END;

CREATE TRIGGER conflicts_import_source_no_update
BEFORE UPDATE OF source_identifier, source_json, source_branch_id ON conflicts
WHEN OLD.source_branch_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'import provenance is immutable');
END;
