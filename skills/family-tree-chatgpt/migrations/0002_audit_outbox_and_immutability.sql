-- Append-only revision audit, future Gramps outbox and immutability guards.
-- ETAPA 1 only enqueues approved operations; it does not transmit them.

CREATE TABLE audit_revisions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    revision_no INTEGER NOT NULL CHECK (revision_no > 0),
    previous_hash TEXT
        CHECK (previous_hash IS NULL
               OR (length(previous_hash) = 64 AND previous_hash NOT GLOB '*[^0-9a-f]*')),
    revision_hash TEXT NOT NULL
        CHECK (length(revision_hash) = 64 AND revision_hash NOT GLOB '*[^0-9a-f]*'),
    actor TEXT NOT NULL CHECK (trim(actor) <> ''),
    action TEXT NOT NULL CHECK (trim(action) <> ''),
    payload_json TEXT NOT NULL
        CHECK (json_valid(payload_json) AND json_type(payload_json) = 'object'),
    created_at TEXT NOT NULL,
    UNIQUE (project_id, revision_no),
    UNIQUE (project_id, revision_hash)
);

CREATE TABLE sync_outbox (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    branch_id TEXT,
    idempotency_key TEXT NOT NULL CHECK (trim(idempotency_key) <> ''),
    destination TEXT NOT NULL DEFAULT 'gramps_web' CHECK (destination = 'gramps_web'),
    operation_type TEXT NOT NULL CHECK (trim(operation_type) <> ''),
    aggregate_type TEXT NOT NULL CHECK (trim(aggregate_type) <> ''),
    aggregate_id TEXT NOT NULL CHECK (trim(aggregate_id) <> ''),
    payload_json TEXT NOT NULL
        CHECK (json_valid(payload_json) AND json_type(payload_json) = 'object'),
    payload_sha256 TEXT NOT NULL
        CHECK (length(payload_sha256) = 64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'),
    approved_by TEXT NOT NULL CHECK (trim(approved_by) <> ''),
    approved_at TEXT NOT NULL CHECK (trim(approved_at) <> ''),
    created_at TEXT NOT NULL,
    FOREIGN KEY (branch_id, project_id)
        REFERENCES import_branches(id, project_id) ON DELETE RESTRICT,
    UNIQUE (project_id, idempotency_key),
    UNIQUE (id, project_id)
);

CREATE TABLE sync_outbox_attempts (
    id TEXT PRIMARY KEY,
    outbox_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    attempt_no INTEGER NOT NULL CHECK (attempt_no > 0),
    state TEXT NOT NULL CHECK (state IN ('planned', 'sent', 'failed', 'confirmed')),
    remote_key TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (outbox_id, project_id)
        REFERENCES sync_outbox(id, project_id) ON DELETE RESTRICT,
    UNIQUE (outbox_id, attempt_no)
);

CREATE INDEX audit_revision_order_idx ON audit_revisions(project_id, revision_no);
CREATE INDEX outbox_project_idx ON sync_outbox(project_id, created_at);
CREATE INDEX outbox_attempt_idx ON sync_outbox_attempts(outbox_id, attempt_no);

CREATE TRIGGER audit_revisions_require_continuous_chain
BEFORE INSERT ON audit_revisions
BEGIN
    SELECT CASE
        WHEN NEW.revision_no <> COALESCE((
            SELECT max(revision_no) + 1 FROM audit_revisions WHERE project_id = NEW.project_id
        ), 1)
            THEN RAISE(ABORT, 'audit revision number must extend the chain')
        WHEN NOT (NEW.previous_hash IS (
            SELECT revision_hash FROM audit_revisions
            WHERE project_id = NEW.project_id ORDER BY revision_no DESC LIMIT 1
        ))
            THEN RAISE(ABORT, 'audit previous hash must extend the chain')
    END;
END;

CREATE TRIGGER audit_revisions_no_update
BEFORE UPDATE ON audit_revisions
BEGIN
    SELECT RAISE(ABORT, 'audit revisions are append-only');
END;

CREATE TRIGGER audit_revisions_no_delete
BEFORE DELETE ON audit_revisions
BEGIN
    SELECT RAISE(ABORT, 'audit revisions are append-only');
END;

CREATE TRIGGER outbox_no_update
BEFORE UPDATE ON sync_outbox
BEGIN
    SELECT RAISE(ABORT, 'outbox operations are immutable');
END;

CREATE TRIGGER outbox_no_delete
BEFORE DELETE ON sync_outbox
BEGIN
    SELECT RAISE(ABORT, 'outbox operations are immutable');
END;

CREATE TRIGGER outbox_attempts_no_update
BEFORE UPDATE ON sync_outbox_attempts
BEGIN
    SELECT RAISE(ABORT, 'outbox attempts are append-only');
END;

CREATE TRIGGER outbox_attempts_no_delete
BEFORE DELETE ON sync_outbox_attempts
BEGIN
    SELECT RAISE(ABORT, 'outbox attempts are append-only');
END;

CREATE TRIGGER original_files_no_update
BEFORE UPDATE ON original_files
BEGIN
    SELECT RAISE(ABORT, 'original files and provenance are immutable');
END;

CREATE TRIGGER original_files_no_delete
BEFORE DELETE ON original_files
BEGIN
    SELECT RAISE(ABORT, 'original files and provenance are immutable');
END;

CREATE TRIGGER transcription_variants_no_update
BEFORE UPDATE ON transcription_variants
BEGIN
    SELECT RAISE(ABORT, 'transcription variants are immutable; add a superseding variant');
END;

CREATE TRIGGER transcription_segments_no_update
BEFORE UPDATE ON transcription_segments
BEGIN
    SELECT RAISE(ABORT, 'transcription segments are immutable');
END;

CREATE TRIGGER transcription_segments_no_delete
BEFORE DELETE ON transcription_segments
BEGIN
    SELECT RAISE(ABORT, 'transcription segments are preserved');
END;

CREATE TRIGGER transcription_variants_no_delete
BEFORE DELETE ON transcription_variants
BEGIN
    SELECT RAISE(ABORT, 'transcription variants are immutable');
END;

CREATE TRIGGER claim_statement_no_update
BEFORE UPDATE OF project_id, branch_id, import_run_id, subject_kind,
                 person_id, relationship_id, event_id, record_id,
                 predicate, value_json, created_at
ON claims
BEGIN
    SELECT RAISE(ABORT, 'claim statement is immutable; add a conflicting claim');
END;

CREATE TRIGGER claims_no_delete
BEFORE DELETE ON claims
BEGIN
    SELECT RAISE(ABORT, 'claims are preserved; reject or conflict them instead');
END;

CREATE TRIGGER claim_decision_no_second_edit
BEFORE UPDATE OF status, evidence_level, rationale, reviewed_at ON claims
WHEN OLD.status IN ('supported', 'rejected')
BEGIN
    SELECT RAISE(ABORT, 'claim decision is immutable; add a new claim and conflict');
END;

CREATE TRIGGER citations_no_update
BEFORE UPDATE ON citations
BEGIN
    SELECT RAISE(ABORT, 'citations are immutable');
END;

CREATE TRIGGER citations_no_delete
BEFORE DELETE ON citations
BEGIN
    SELECT RAISE(ABORT, 'citations are preserved with the claim');
END;

CREATE TRIGGER identity_pair_no_update
BEFORE UPDATE OF project_id, left_person_id, right_person_id, created_at
ON identity_assessments
BEGIN
    SELECT RAISE(ABORT, 'identity assessment subjects are immutable');
END;

CREATE TRIGGER identity_decision_no_second_edit
BEFORE UPDATE OF status, evidence_level, rationale, decided_at ON identity_assessments
WHEN OLD.status IN ('supported', 'rejected')
BEGIN
    SELECT RAISE(ABORT, 'identity decision is immutable; add a new assessment');
END;

CREATE TRIGGER identity_assessments_no_delete
BEFORE DELETE ON identity_assessments
BEGIN
    SELECT RAISE(ABORT, 'identity assessments are preserved');
END;

CREATE TRIGGER identity_evidence_no_update
BEFORE UPDATE ON identity_assessment_evidence
BEGIN
    SELECT RAISE(ABORT, 'identity evidence is immutable');
END;

CREATE TRIGGER identity_evidence_no_delete
BEFORE DELETE ON identity_assessment_evidence
BEGIN
    SELECT RAISE(ABORT, 'identity evidence is preserved');
END;

CREATE TRIGGER conflict_claims_no_update
BEFORE UPDATE ON conflict_claims
BEGIN
    SELECT RAISE(ABORT, 'conflict variants are immutable');
END;

CREATE TRIGGER conflicts_core_no_update
BEFORE UPDATE OF project_id, code, label, created_at ON conflicts
BEGIN
    SELECT RAISE(ABORT, 'conflict identity is immutable');
END;

CREATE TRIGGER conflicts_no_delete
BEFORE DELETE ON conflicts
BEGIN
    SELECT RAISE(ABORT, 'conflicts are preserved');
END;

CREATE TRIGGER conflict_claims_no_delete
BEFORE DELETE ON conflict_claims
BEGIN
    SELECT RAISE(ABORT, 'conflict variants are preserved');
END;

CREATE TRIGGER conflict_decisions_no_update
BEFORE UPDATE ON conflict_decisions
BEGIN
    SELECT RAISE(ABORT, 'conflict decisions are append-only');
END;

CREATE TRIGGER conflict_decisions_no_delete
BEFORE DELETE ON conflict_decisions
BEGIN
    SELECT RAISE(ABORT, 'conflict decisions are append-only');
END;

CREATE TRIGGER conflict_decision_claims_no_update
BEFORE UPDATE ON conflict_decision_claims
BEGIN
    SELECT RAISE(ABORT, 'conflict decision details are append-only');
END;

CREATE TRIGGER conflict_decision_claims_no_delete
BEFORE DELETE ON conflict_decision_claims
BEGIN
    SELECT RAISE(ABORT, 'conflict decision details are append-only');
END;

CREATE TRIGGER media_objects_no_update
BEFORE UPDATE ON media_objects
BEGIN
    SELECT RAISE(ABORT, 'media provenance is immutable');
END;

CREATE TRIGGER media_objects_no_delete
BEFORE DELETE ON media_objects
BEGIN
    SELECT RAISE(ABORT, 'media provenance is immutable');
END;

CREATE TRIGGER image_crops_no_update
BEFORE UPDATE ON image_crops
BEGIN
    SELECT RAISE(ABORT, 'crop provenance is immutable');
END;

CREATE TRIGGER image_crops_no_delete
BEFORE DELETE ON image_crops
BEGIN
    SELECT RAISE(ABORT, 'crop provenance is immutable');
END;

CREATE TRIGGER negative_searches_no_update
BEFORE UPDATE ON negative_searches
BEGIN
    SELECT RAISE(ABORT, 'negative searches are append-only');
END;

CREATE TRIGGER negative_searches_no_delete
BEFORE DELETE ON negative_searches
BEGIN
    SELECT RAISE(ABORT, 'negative searches are append-only');
END;

CREATE TRIGGER negative_search_sources_no_update
BEFORE UPDATE ON negative_search_sources
BEGIN
    SELECT RAISE(ABORT, 'negative search sources are append-only');
END;

CREATE TRIGGER negative_search_sources_no_delete
BEFORE DELETE ON negative_search_sources
BEGIN
    SELECT RAISE(ABORT, 'negative search sources are append-only');
END;
