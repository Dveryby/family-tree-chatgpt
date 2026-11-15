-- Core relational evidence model for Family Tree 2.0.
-- The migration runner supplies the transaction, migration ledger row and
-- PRAGMA user_version. Keep this file deterministic and free of private data.

CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY CHECK (version > 0),
    name TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
    applied_at TEXT NOT NULL
);

CREATE TABLE projects (
    id TEXT PRIMARY KEY
        CHECK (length(id) BETWEEN 1 AND 96
               AND id NOT GLOB '*[^a-z0-9_-]*'
               AND substr(id, 1, 1) GLOB '[a-z0-9]'),
    name TEXT NOT NULL CHECK (trim(name) <> ''),
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE import_branches (
    id TEXT PRIMARY KEY
        CHECK (length(id) BETWEEN 1 AND 96
               AND id NOT GLOB '*[^a-z0-9_-]*'
               AND substr(id, 1, 1) GLOB '[a-z0-9]'),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    branch_key TEXT NOT NULL
        CHECK (length(branch_key) BETWEEN 1 AND 96
               AND branch_key NOT GLOB '*[^a-z0-9_-]*'),
    label TEXT NOT NULL CHECK (trim(label) <> ''),
    history_kind TEXT NOT NULL
        CHECK (history_kind IN ('native', 'json_v1', 'json_v2', 'gedcom', 'other')),
    source_revision TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(metadata_json) AND json_type(metadata_json) = 'object'),
    created_at TEXT NOT NULL,
    UNIQUE (project_id, branch_key),
    UNIQUE (id, project_id)
);

CREATE TABLE original_files (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    sha256 TEXT NOT NULL
        CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
    byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
    original_name TEXT NOT NULL CHECK (trim(original_name) <> ''),
    media_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    storage_path TEXT NOT NULL CHECK (trim(storage_path) <> ''),
    provenance_key TEXT NOT NULL CHECK (trim(provenance_key) <> ''),
    provenance_json TEXT NOT NULL
        CHECK (json_valid(provenance_json) AND json_type(provenance_json) = 'object'),
    acquired_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    UNIQUE (branch_id, sha256, provenance_key),
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TABLE import_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    original_file_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL CHECK (trim(idempotency_key) <> ''),
    importer TEXT NOT NULL CHECK (trim(importer) <> ''),
    importer_version TEXT NOT NULL,
    source_schema_version INTEGER CHECK (source_schema_version IS NULL OR source_schema_version > 0),
    status TEXT NOT NULL CHECK (status IN ('staged', 'validated', 'committed', 'failed')),
    summary_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(summary_json) AND json_type(summary_json) = 'object'),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (original_file_id, branch_id)
        REFERENCES original_files(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (branch_id, idempotency_key),
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TABLE persons (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    import_run_id TEXT,
    label TEXT NOT NULL CHECK (trim(label) <> ''),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (import_run_id, branch_id)
        REFERENCES import_runs(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TABLE sources (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    import_run_id TEXT,
    kind TEXT NOT NULL CHECK (trim(kind) <> ''),
    title TEXT NOT NULL CHECK (trim(title) <> ''),
    citation TEXT NOT NULL DEFAULT '',
    repository TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (import_run_id, branch_id)
        REFERENCES import_runs(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TABLE research_records (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    import_run_id TEXT,
    source_id TEXT,
    record_kind TEXT NOT NULL
        CHECK (record_kind IN ('vital_register', 'research_note', 'index', 'other')),
    title TEXT NOT NULL CHECK (trim(title) <> ''),
    original_language TEXT NOT NULL DEFAULT '',
    reading_status TEXT NOT NULL CHECK (reading_status IN ('unread', 'draft', 'reviewed')),
    visual_reviewed_at TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    CHECK (reading_status <> 'reviewed'
           OR (visual_reviewed_at IS NOT NULL AND source_id IS NOT NULL)),
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (import_run_id, branch_id)
        REFERENCES import_runs(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_id, branch_id)
        REFERENCES sources(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TABLE transcription_segments (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    segment_key TEXT NOT NULL CHECK (trim(segment_key) <> ''),
    sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
    region_json TEXT
        CHECK (region_json IS NULL OR (json_valid(region_json) AND json_type(region_json) = 'object')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (record_id, branch_id)
        REFERENCES research_records(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    UNIQUE (record_id, segment_key),
    UNIQUE (record_id, sequence_no),
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TABLE transcription_variants (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    supersedes_variant_id TEXT,
    authored_by TEXT NOT NULL CHECK (authored_by IN ('user', 'chatgpt', 'gemini')),
    author_label TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL CHECK (trim(language) <> ''),
    text TEXT NOT NULL,
    reading_confidence REAL NOT NULL CHECK (reading_confidence BETWEEN 0.0 AND 1.0),
    reading_state TEXT NOT NULL CHECK (reading_state IN ('clear', 'uncertain', 'unreadable')),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (segment_id, branch_id)
        REFERENCES transcription_segments(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (supersedes_variant_id, branch_id)
        REFERENCES transcription_variants(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TABLE events (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    import_run_id TEXT,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'birth', 'baptism', 'death', 'burial', 'marriage', 'banns',
        'residence', 'occupation', 'immigration', 'emigration', 'military', 'other'
    )),
    date_text TEXT NOT NULL DEFAULT '',
    place_text TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (import_run_id, branch_id)
        REFERENCES import_runs(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TABLE event_participants (
    event_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (trim(role) <> ''),
    PRIMARY KEY (event_id, person_id, role),
    FOREIGN KEY (event_id, branch_id)
        REFERENCES events(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (person_id, branch_id)
        REFERENCES persons(id, branch_id) ON DELETE RESTRICT
);

CREATE TABLE relationships (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    import_run_id TEXT,
    relationship_type TEXT NOT NULL CHECK (trim(relationship_type) <> ''),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (import_run_id, branch_id)
        REFERENCES import_runs(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TABLE relationship_participants (
    relationship_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (trim(role) <> ''),
    PRIMARY KEY (relationship_id, person_id, role),
    FOREIGN KEY (relationship_id, branch_id)
        REFERENCES relationships(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (person_id, branch_id)
        REFERENCES persons(id, branch_id) ON DELETE RESTRICT
);

CREATE TABLE claims (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    import_run_id TEXT,
    subject_kind TEXT NOT NULL CHECK (subject_kind IN ('person', 'relationship', 'event', 'record')),
    person_id TEXT,
    relationship_id TEXT,
    event_id TEXT,
    record_id TEXT,
    predicate TEXT NOT NULL
        CHECK (length(predicate) BETWEEN 1 AND 96
               AND predicate NOT GLOB '*[^a-z0-9_.-]*'
               AND substr(predicate, 1, 1) GLOB '[a-z]'),
    value_json TEXT NOT NULL CHECK (json_valid(value_json)),
    status TEXT NOT NULL DEFAULT 'unverified'
        CHECK (status IN ('unverified', 'supported', 'rejected')),
    evidence_level TEXT NOT NULL DEFAULT 'none'
        CHECK (evidence_level IN ('none', 'lead', 'indirect', 'direct', 'corroborated')),
    rationale TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    CHECK (
        (subject_kind = 'person' AND person_id IS NOT NULL
         AND relationship_id IS NULL AND event_id IS NULL AND record_id IS NULL)
        OR
        (subject_kind = 'relationship' AND relationship_id IS NOT NULL
         AND person_id IS NULL AND event_id IS NULL AND record_id IS NULL)
        OR
        (subject_kind = 'event' AND event_id IS NOT NULL
         AND person_id IS NULL AND relationship_id IS NULL AND record_id IS NULL)
        OR
        (subject_kind = 'record' AND record_id IS NOT NULL
         AND person_id IS NULL AND relationship_id IS NULL AND event_id IS NULL)
    ),
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (import_run_id, branch_id)
        REFERENCES import_runs(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (person_id, branch_id)
        REFERENCES persons(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (relationship_id, branch_id)
        REFERENCES relationships(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (event_id, branch_id)
        REFERENCES events(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (record_id, branch_id)
        REFERENCES research_records(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TABLE citations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    record_id TEXT,
    locator TEXT NOT NULL DEFAULT '',
    quotation TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (claim_id, branch_id)
        REFERENCES claims(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_id, branch_id)
        REFERENCES sources(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (record_id, branch_id)
        REFERENCES research_records(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TRIGGER claims_must_begin_unverified
BEFORE INSERT ON claims
WHEN NEW.status <> 'unverified'
BEGIN
    SELECT RAISE(ABORT, 'claim must begin unverified and be reviewed explicitly');
END;

CREATE TRIGGER claim_review_requires_citation_and_rationale
BEFORE UPDATE OF status ON claims
WHEN NEW.status <> OLD.status
BEGIN
    SELECT CASE
        WHEN OLD.status <> 'unverified' OR NEW.status NOT IN ('supported', 'rejected')
            THEN RAISE(ABORT, 'claim status transition is not allowed')
        WHEN trim(NEW.rationale) = '' OR NEW.evidence_level = 'none' OR NEW.reviewed_at IS NULL
            THEN RAISE(ABORT, 'reviewed claim needs rationale, evidence level and review time')
        WHEN NOT EXISTS (SELECT 1 FROM citations WHERE claim_id = OLD.id)
            THEN RAISE(ABORT, 'supported or rejected claim needs a citation')
    END;
END;

CREATE TABLE identity_assessments (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    left_person_id TEXT NOT NULL,
    right_person_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unresolved'
        CHECK (status IN ('unresolved', 'supported', 'rejected')),
    evidence_level TEXT NOT NULL DEFAULT 'none'
        CHECK (evidence_level IN ('none', 'lead', 'indirect', 'direct', 'corroborated')),
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    decided_at TEXT,
    CHECK (left_person_id <> right_person_id),
    FOREIGN KEY (left_person_id, project_id)
        REFERENCES persons(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (right_person_id, project_id)
        REFERENCES persons(id, project_id) ON DELETE RESTRICT,
    UNIQUE (id, project_id)
);

CREATE TABLE identity_assessment_evidence (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    assessment_id TEXT NOT NULL,
    citation_id TEXT NOT NULL,
    polarity TEXT NOT NULL CHECK (polarity IN ('support', 'counter')),
    explanation TEXT NOT NULL CHECK (trim(explanation) <> ''),
    created_at TEXT NOT NULL,
    FOREIGN KEY (assessment_id, project_id)
        REFERENCES identity_assessments(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (citation_id, project_id)
        REFERENCES citations(id, project_id) ON DELETE RESTRICT
);

CREATE TRIGGER identity_assessments_must_begin_unresolved
BEFORE INSERT ON identity_assessments
WHEN NEW.status <> 'unresolved'
BEGIN
    SELECT RAISE(ABORT, 'identity assessment must begin unresolved');
END;

CREATE TRIGGER identity_decision_requires_cited_evidence
BEFORE UPDATE OF status ON identity_assessments
WHEN NEW.status <> OLD.status
BEGIN
    SELECT CASE
        WHEN OLD.status <> 'unresolved' OR NEW.status NOT IN ('supported', 'rejected')
            THEN RAISE(ABORT, 'identity status transition is not allowed')
        WHEN trim(NEW.rationale) = '' OR NEW.evidence_level = 'none' OR NEW.decided_at IS NULL
            THEN RAISE(ABORT, 'identity decision needs rationale, evidence level and decision time')
        WHEN NOT EXISTS (
            SELECT 1 FROM identity_assessment_evidence
            WHERE assessment_id = OLD.id
        )
            THEN RAISE(ABORT, 'identity decision needs cited evidence')
    END;
END;

CREATE TABLE conflicts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    code TEXT NOT NULL CHECK (trim(code) <> ''),
    label TEXT NOT NULL CHECK (trim(label) <> ''),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    UNIQUE (project_id, code),
    UNIQUE (id, project_id)
);

CREATE TABLE conflict_claims (
    conflict_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    PRIMARY KEY (conflict_id, claim_id),
    FOREIGN KEY (conflict_id, project_id)
        REFERENCES conflicts(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (claim_id, project_id)
        REFERENCES claims(id, project_id) ON DELETE RESTRICT,
    UNIQUE (conflict_id, project_id, claim_id)
);

CREATE TABLE conflict_decisions (
    id TEXT PRIMARY KEY,
    conflict_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    rationale TEXT NOT NULL CHECK (trim(rationale) <> ''),
    decided_by TEXT NOT NULL CHECK (trim(decided_by) <> ''),
    decided_at TEXT NOT NULL,
    FOREIGN KEY (conflict_id, project_id)
        REFERENCES conflicts(id, project_id) ON DELETE RESTRICT,
    UNIQUE (id, conflict_id, project_id)
);

CREATE TABLE conflict_decision_claims (
    decision_id TEXT NOT NULL,
    conflict_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK (disposition IN ('preferred', 'not_preferred', 'rejected')),
    PRIMARY KEY (decision_id, claim_id),
    FOREIGN KEY (decision_id, conflict_id, project_id)
        REFERENCES conflict_decisions(id, conflict_id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (conflict_id, project_id, claim_id)
        REFERENCES conflict_claims(conflict_id, project_id, claim_id) ON DELETE RESTRICT
);

CREATE TRIGGER conflict_resolution_requires_decision
BEFORE UPDATE OF status ON conflicts
WHEN NEW.status <> OLD.status
BEGIN
    SELECT CASE
        WHEN OLD.status <> 'open' OR NEW.status <> 'resolved' OR NEW.resolved_at IS NULL
            THEN RAISE(ABORT, 'conflict status transition is not allowed')
        WHEN NOT EXISTS (SELECT 1 FROM conflict_decisions WHERE conflict_id = OLD.id)
            THEN RAISE(ABORT, 'resolved conflict needs an append-only decision')
    END;
END;

CREATE TABLE media_objects (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    original_file_id TEXT,
    source_id TEXT,
    record_id TEXT,
    media_kind TEXT NOT NULL CHECK (media_kind IN ('original', 'derivative')),
    sha256 TEXT NOT NULL
        CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
    byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
    media_type TEXT NOT NULL CHECK (trim(media_type) <> ''),
    storage_path TEXT NOT NULL CHECK (trim(storage_path) <> ''),
    provenance_json TEXT NOT NULL
        CHECK (json_valid(provenance_json) AND json_type(provenance_json) = 'object'),
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (original_file_id, branch_id)
        REFERENCES original_files(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_id, branch_id)
        REFERENCES sources(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (record_id, branch_id)
        REFERENCES research_records(id, branch_id) ON DELETE RESTRICT,
    UNIQUE (id, branch_id),
    UNIQUE (id, project_id)
);

CREATE TABLE image_crops (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    parent_media_id TEXT NOT NULL,
    output_media_id TEXT NOT NULL,
    x0 REAL NOT NULL CHECK (x0 >= 0.0 AND x0 < 1.0),
    y0 REAL NOT NULL CHECK (y0 >= 0.0 AND y0 < 1.0),
    x1 REAL NOT NULL CHECK (x1 > 0.0 AND x1 <= 1.0),
    y1 REAL NOT NULL CHECK (y1 > 0.0 AND y1 <= 1.0),
    operation_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(operation_json) AND json_type(operation_json) = 'object'),
    created_at TEXT NOT NULL,
    CHECK (x1 > x0 AND y1 > y0 AND parent_media_id <> output_media_id),
    FOREIGN KEY (parent_media_id, branch_id)
        REFERENCES media_objects(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (output_media_id, branch_id)
        REFERENCES media_objects(id, branch_id) ON DELETE RESTRICT,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT
);

CREATE TABLE research_tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    branch_id TEXT,
    title TEXT NOT NULL CHECK (trim(title) <> ''),
    question TEXT NOT NULL CHECK (trim(question) <> ''),
    status TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'done', 'blocked', 'cancelled')),
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
    next_step TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    closed_at TEXT,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    UNIQUE (id, project_id)
);

CREATE TABLE negative_searches (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    branch_id TEXT,
    task_id TEXT,
    searched_at TEXT NOT NULL,
    query TEXT NOT NULL CHECK (trim(query) <> ''),
    scope TEXT NOT NULL CHECK (trim(scope) <> ''),
    result_detail TEXT NOT NULL CHECK (trim(result_detail) <> ''),
    researcher TEXT NOT NULL CHECK (trim(researcher) <> ''),
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (task_id, project_id)
        REFERENCES research_tasks(id, project_id) ON DELETE RESTRICT,
    UNIQUE (id, project_id)
);

CREATE TABLE negative_search_sources (
    search_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    PRIMARY KEY (search_id, source_id),
    FOREIGN KEY (search_id, project_id)
        REFERENCES negative_searches(id, project_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_id, project_id)
        REFERENCES sources(id, project_id) ON DELETE RESTRICT
);

CREATE INDEX import_runs_branch_idx ON import_runs(branch_id, started_at);
CREATE INDEX persons_branch_idx ON persons(branch_id);
CREATE INDEX records_branch_idx ON research_records(branch_id, reading_status);
CREATE INDEX claims_subject_person_idx ON claims(person_id) WHERE person_id IS NOT NULL;
CREATE INDEX claims_subject_relationship_idx ON claims(relationship_id) WHERE relationship_id IS NOT NULL;
CREATE INDEX claims_subject_event_idx ON claims(event_id) WHERE event_id IS NOT NULL;
CREATE INDEX citations_claim_idx ON citations(claim_id);
CREATE INDEX identity_pair_idx ON identity_assessments(project_id, left_person_id, right_person_id);
CREATE INDEX conflicts_status_idx ON conflicts(project_id, status);
CREATE INDEX tasks_status_idx ON research_tasks(project_id, status);
