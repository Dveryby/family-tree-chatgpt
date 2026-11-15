#!/usr/bin/env python3
"""Lossless, branch-isolated research.json imports into the SQLite store.

This module is offline.  It also records explicitly approved Gramps outbox
operations, but deliberately contains no transport or network client.
"""
import hashlib
import json
import mimetypes
from pathlib import Path
import re

import research
import sqlite_store


IMPORTER = "family-tree-research-json"
IMPORTER_VERSION = "2.0.0"
MAX_INPUT_BYTES = 50 * 1024 * 1024
OUTBOX_APPROVAL_SCHEMA_VERSION = 1
CONFLICT_CODE_RE = re.compile(r"(?:^|[_-])(k(?:0[1-9]|1[0-3]))(?:$|[_-])", re.IGNORECASE)


def _stable_id(kind, branch_id, source_identifier):
    digest = hashlib.sha256(
        f"{branch_id}\0{kind}\0{source_identifier}".encode("utf-8")
    ).hexdigest()[:32]
    return f"ri_{kind}_{digest}"


def _read_json_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Importní vstup musí být běžný soubor: {path}")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError(f"Importní JSON překračuje limit 50 MiB: {path.name}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Importní soubor není platný UTF-8 JSON: {path.name}") from exc
    return value, raw


def _validate_snapshot_shape(state, label):
    if not isinstance(state, dict) or state.get("schema_version") not in (1, 2):
        raise ValueError(f"{label}: nepodporovaná verze research.json.")
    if type(state.get("revision")) is not int or state["revision"] < 0:
        raise ValueError(f"{label}: neplatná revize.")
    if not isinstance(state.get("records"), dict):
        raise ValueError(f"{label}: chybí mapa records.")
    if not isinstance(state.get("events"), list) or not isinstance(state.get("next_step"), str):
        raise ValueError(f"{label}: neplatná historie nebo next_step.")
    if state["schema_version"] == 2 and any(
        not isinstance(state.get(name), dict) for name in research.MODEL_COLLECTIONS
    ):
        raise ValueError(f"{label}: neplatný obecný model formátu 2.")


def load_research_input(input_path):
    candidate = Path(input_path).expanduser()
    if candidate.is_symlink():
        raise ValueError("Importní vstup nesmí být symlink.")
    if candidate.is_dir():
        root = research.private_workspace(candidate)
        current_path = root / "research.json"
    else:
        current_path = candidate.resolve()
        if current_path.name != "research.json":
            raise ValueError("Zadej pracovní složku nebo soubor pojmenovaný research.json.")
        root = research.private_workspace(current_path.parent)
    state, raw = _read_json_file(current_path)
    _validate_snapshot_shape(state, "research.json")
    errors = research.check_state(state, root)
    if errors:
        raise ValueError("\n".join(errors))

    snapshots = []
    history = root / "history"
    if history.exists():
        if history.is_symlink() or not history.is_dir():
            raise ValueError("history/ musí být běžný adresář.")
        for path in sorted(history.glob("revision-*.json")):
            snapshot, snapshot_raw = _read_json_file(path)
            _validate_snapshot_shape(snapshot, path.name)
            snapshots.append({
                "kind": "history",
                "path": path,
                "state": snapshot,
                "raw": snapshot_raw,
            })
    snapshots.append({"kind": "current", "path": current_path, "state": state, "raw": raw})
    seen = set()
    for snapshot in snapshots:
        marker = (snapshot["kind"], snapshot["state"]["revision"])
        if marker in seen:
            raise ValueError(
                f"Duplicitní {snapshot['kind']} snapshot revize {snapshot['state']['revision']}."
            )
        seen.add(marker)
    return root, state, snapshots


def _source_counts(state, snapshots):
    return {
        "records": len(state["records"]),
        "persons": len(state.get("persons", {})),
        "relationships": len(state.get("relationships", {})),
        "claims": len(state.get("claims", {})),
        "citations": sum(len(item.get("citations", [])) for item in state.get("claims", {}).values()),
        "sources": len(state.get("sources", {})),
        "conflicts": len(state.get("conflicts", {})),
        "history_events": len(state["events"]),
        "snapshots": len(snapshots),
    }


def _workspace_media_paths(root):
    paths = []
    for directory_name in ("sources", "crops"):
        directory = root / directory_name
        if not directory.exists():
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"{directory_name}/ musí být běžný adresář.")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Import médií odmítl symlink: {path.relative_to(root)}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(
                    f"Import médií podporuje jen běžné soubory: {path.relative_to(root)}"
                )
            paths.append(path.relative_to(root).as_posix())
    return paths


def _planned_counts(root, state):
    record_links = {
        record_id
        for source in state.get("sources", {}).values()
        for record_id in source.get("record_ids", [])
    }
    referenced_paths = []
    crops = 0
    for record in state["records"].values():
        source = record["source"]
        referenced_paths.extend(
            value for value in (source.get("file", ""), source.get("crop", "")) if value
        )
        metadata = record.get("crop_metadata")
        if (
            source.get("file")
            and source.get("crop")
            and isinstance(metadata, dict)
            and isinstance(metadata.get("box"), list)
            and len(metadata["box"]) == 4
        ):
            crops += 1
    referenced_paths.extend(
        item["path"]
        for source in state.get("sources", {}).values()
        for item in source.get("files", [])
    )
    workspace_paths = _workspace_media_paths(root)
    return {
        "persons": len(state.get("persons", {})),
        "sources": len(state.get("sources", {})) + sum(
            record_id not in record_links for record_id in state["records"]
        ),
        "records": len(state["records"]),
        "record_texts": len(state["records"]) * 3,
        "uncertainties": sum(
            len(record["uncertainties"]) for record in state["records"].values()
        ),
        "relationships": len(state.get("relationships", {})),
        "claims": len(state.get("claims", {})),
        "citations": sum(
            len(claim["citations"]) for claim in state.get("claims", {}).values()
        ),
        "conflicts": len(state.get("conflicts", {})),
        "media": len(referenced_paths) + len(set(workspace_paths) - set(referenced_paths)),
        "crops": crops,
        "history_events": len(state["events"]),
    }


def _conflict_code(source_identifier):
    match = CONFLICT_CODE_RE.search(source_identifier)
    return match.group(1).upper() if match else source_identifier


def _branch_id(project_id, branch_key):
    return _stable_id("branch", project_id, branch_key)


def _existing_context(connection, project_id, branch_key):
    project = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    branch = connection.execute(
        "SELECT * FROM import_branches WHERE project_id = ? AND branch_key = ?",
        (project_id, branch_key),
    ).fetchone()
    return project, branch


def _base_report(state, snapshots, project_id, branch_key, branch_id, source_hash, dry_run):
    open_codes = sorted(
        _conflict_code(key)
        for key, value in state.get("conflicts", {}).items()
        if value.get("status") == "open" and CONFLICT_CODE_RE.search(key)
    )
    return {
        "dry_run": dry_run,
        "imported": False,
        "idempotent": False,
        "network_writes": False,
        "source_schema_version": state["schema_version"],
        "source_revision": state["revision"],
        "source_sha256": source_hash,
        "project_id": project_id,
        "branch_key": branch_key,
        "branch_id": branch_id,
        "source_counts": _source_counts(state, snapshots),
        "open_conflict_codes": open_codes,
        "normalizations": (
            ["claim_status_evidence_level"]
            if any(
                claim.get("status") in ("supported", "rejected")
                for claim in state.get("claims", {}).values()
            )
            else []
        ),
        "warnings": [],
        "outbox_enqueued": 0,
    }


def _register_snapshot_files(store, project_id, branch_id, snapshots, actor):
    registered = []
    for snapshot in snapshots:
        state = snapshot["state"]
        digest = hashlib.sha256(snapshot["raw"]).hexdigest()
        source_key = f"{snapshot['kind']}:revision:{state['revision']}"
        file_id = _stable_id("file", branch_id, source_key + ":" + digest)
        result = store.register_original_file(
            file_id, project_id, branch_id,
            sha256=digest,
            byte_size=len(snapshot["raw"]),
            original_name=snapshot["path"].name,
            storage_path=str(snapshot["path"]),
            provenance_key=source_key,
            provenance={
                "kind": snapshot["kind"],
                "source_schema_version": state["schema_version"],
                "source_revision": state["revision"],
                "path": str(snapshot["path"]),
            },
            media_type="application/json",
            actor=actor,
        )
        registered.append((snapshot, result["id"]))
    return registered


def _create_embedded_source(store, state, project_id, branch_id, run_id, record_key, record, actor):
    source = record["source"]
    source_identifier = f"record:{record_key}:source"
    source_id = _stable_id("source", branch_id, source_identifier)
    title = source.get("reference") or source.get("page") or f"Pramen zápisu {record_key}"
    citation = ", ".join(
        part for part in (source.get("archive"), source.get("reference"), source.get("page"))
        if isinstance(part, str) and part.strip()
    )
    store.create_source(
        source_id, project_id, branch_id, "research_record_source", title,
        citation=citation,
        repository=source.get("archive", ""),
        url=source.get("url", ""),
        notes="Pramen vložený přímo v research.json; nebyl automaticky sloučen s jiným pramenem.",
        import_run_id=run_id,
        source_identifier=source_identifier,
        source_json=source,
        actor=actor,
    )
    return source_id


def _media_type(path):
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def _add_media(
    store, root, project_id, branch_id, run_id, source_identifier,
    relative, media_kind, provenance, *, source_id=None, record_id=None, source_json=None, actor,
):
    if not relative:
        return None
    path = research.asset(root, relative)
    digest = research.sha256(path)
    media_id = _stable_id("media", branch_id, source_identifier)
    store.add_media_object(
        media_id, project_id, branch_id, media_kind, digest, path.stat().st_size,
        _media_type(path), relative, provenance,
        source_id=source_id,
        record_id=record_id,
        source_identifier=source_identifier,
        source_json={} if source_json is None else source_json,
        actor=actor,
    )
    return media_id


def _map_state(store, root, state, project_id, branch_id, run_id, report, actor):
    source_ids = {}
    record_ids = {}
    person_ids = {}
    relationship_ids = {}
    claim_ids = {}
    mapped_media_paths = set()
    created = {name: 0 for name in (
        "persons", "sources", "records", "record_texts", "uncertainties",
        "relationships", "claims", "citations", "conflicts", "media",
        "crops", "history_events",
    )}

    for source_key, source in state.get("sources", {}).items():
        source_id = _stable_id("source", branch_id, source_key)
        source_ids[source_key] = source_id
        store.create_source(
            source_id, project_id, branch_id, source["kind"], source["title"],
            citation=source["citation"], repository=source["repository"],
            url=source["url"], notes=source["notes"], import_run_id=run_id,
            source_identifier=source_key, source_json=source, actor=actor,
        )
        created["sources"] += 1

    records_to_sources = {}
    for source_key, source in state.get("sources", {}).items():
        for record_key in source.get("record_ids", []):
            records_to_sources.setdefault(record_key, []).append(source_key)

    for record_key, record in state["records"].items():
        record_id = _stable_id("record", branch_id, record_key)
        record_ids[record_key] = record_id
        linked = records_to_sources.get(record_key, [])
        if linked:
            source_id = source_ids[linked[0]]
            if len(linked) > 1:
                report["warnings"].append(
                    f"Zápis {record_key} odkazuje na více pramenů; všechny zůstaly zachované v JSON, "
                    f"relační source_id používá {linked[0]}."
                )
        else:
            source_id = _create_embedded_source(
                store, state, project_id, branch_id, run_id, record_key, record, actor
            )
            created["sources"] += 1
        source = record["source"]
        visual_reviewed_at = source.get("accessed_on") if record["reading_status"] == "reviewed" else None
        title = source.get("reference") or source.get("page") or f"Badatelský zápis {record_key}"
        store.create_record(
            record_id, project_id, branch_id, "vital_register", title,
            source_id=source_id, reading_status=record["reading_status"],
            visual_reviewed_at=visual_reviewed_at, notes="",
            import_run_id=run_id, source_identifier=record_key,
            source_json=record, actor=actor,
        )
        created["records"] += 1
        for text_kind in ("transcription", "translation", "interpretation"):
            store.add_imported_record_text(
                _stable_id("text", branch_id, f"{record_key}:{text_kind}"),
                project_id, branch_id, run_id, record_id, text_kind,
                record[text_kind],
                {"source_identifier": record_key, "authorship": "unknown"},
                actor=actor,
            )
            created["record_texts"] += 1
        for index, uncertainty in enumerate(record["uncertainties"]):
            store.add_imported_uncertainty(
                _stable_id("uncertainty", branch_id, f"{record_key}:{index}"),
                project_id, branch_id, run_id, record_id, index, uncertainty,
                actor=actor,
            )
            created["uncertainties"] += 1

        original_media = _add_media(
            store, root, project_id, branch_id, run_id,
            f"record:{record_key}:file", source.get("file", ""), "original",
            {"record_source_identifier": record_key, "field": "source.file"},
            source_id=source_id, record_id=record_id, source_json=source, actor=actor,
        )
        if original_media:
            created["media"] += 1
            mapped_media_paths.add(source["file"])
        crop_media = _add_media(
            store, root, project_id, branch_id, run_id,
            f"record:{record_key}:crop", source.get("crop", ""), "derivative",
            {"record_source_identifier": record_key, "field": "source.crop"},
            source_id=source_id, record_id=record_id, source_json=source, actor=actor,
        )
        if crop_media:
            created["media"] += 1
            mapped_media_paths.add(source["crop"])
        crop_metadata = record.get("crop_metadata")
        if original_media and crop_media and isinstance(crop_metadata, dict):
            box = crop_metadata.get("box")
            if isinstance(box, list) and len(box) == 4:
                store.add_image_crop(
                    _stable_id("crop", branch_id, record_key), project_id, branch_id,
                    original_media, crop_media, box, operation=crop_metadata, actor=actor,
                )
                created["crops"] += 1

    for source_key, source in state.get("sources", {}).items():
        for index, item in enumerate(source.get("files", [])):
            media = _add_media(
                store, root, project_id, branch_id, run_id,
                f"source:{source_key}:file:{index}:{item['path']}", item["path"], "original",
                {"source_identifier": source_key, "field": "sources.files", "index": index},
                source_id=source_ids[source_key], source_json=item, actor=actor,
            )
            if media:
                created["media"] += 1
                mapped_media_paths.add(item["path"])

    for relative in _workspace_media_paths(root):
        if relative in mapped_media_paths:
            continue
        media_kind = "original" if relative.startswith("sources/") else "derivative"
        media = _add_media(
            store, root, project_id, branch_id, run_id,
            f"workspace:{relative}", relative, media_kind,
            {"field": "workspace_file", "referenced_by_current_state": False},
            source_json={"path": relative}, actor=actor,
        )
        if media:
            created["media"] += 1
            mapped_media_paths.add(relative)

    for person_key, person in state.get("persons", {}).items():
        person_id = _stable_id("person", branch_id, person_key)
        person_ids[person_key] = person_id
        store.create_person(
            person_id, project_id, branch_id, person["label"],
            notes=person["notes"], import_run_id=run_id,
            source_identifier=person_key, source_json=person, actor=actor,
        )
        created["persons"] += 1

    for relationship_key, relationship in state.get("relationships", {}).items():
        relationship_id = _stable_id("relationship", branch_id, relationship_key)
        relationship_ids[relationship_key] = relationship_id
        participants = [
            {"person_id": person_ids[item["person_id"]], "role": item["role"]}
            for item in relationship["participants"]
        ]
        store.create_relationship(
            relationship_id, project_id, branch_id, relationship["type"], participants,
            notes=relationship["notes"], import_run_id=run_id,
            source_identifier=relationship_key, source_json=relationship, actor=actor,
        )
        created["relationships"] += 1

    for claim_key, claim in state.get("claims", {}).items():
        claim_id = _stable_id("claim", branch_id, claim_key)
        claim_ids[claim_key] = claim_id
        subject_type = claim["subject"]["type"]
        subject_id = (
            person_ids[claim["subject"]["id"]]
            if subject_type == "person"
            else relationship_ids[claim["subject"]["id"]]
        )
        store.create_claim(
            claim_id, project_id, branch_id, subject_type, subject_id,
            claim["predicate"], claim["value"], notes=claim["notes"],
            import_run_id=run_id, source_identifier=claim_key,
            source_json=claim, actor=actor,
        )
        created["claims"] += 1
        for index, citation in enumerate(claim["citations"]):
            citation_source_key = citation["source_id"]
            source = state["sources"][citation_source_key]
            linked_records = source.get("record_ids", [])
            citation_source_identifier = f"{claim_key}:citation:{index}"
            store.add_citation(
                _stable_id("citation", branch_id, citation_source_identifier),
                project_id, branch_id, claim_id, source_ids[citation_source_key],
                record_id=record_ids.get(linked_records[0]) if len(linked_records) == 1 else None,
                locator=citation["locator"], quotation=citation["quotation"], note=citation["note"],
                source_identifier=citation_source_identifier, source_json=citation, actor=actor,
            )
            created["citations"] += 1
        if claim["status"] in ("supported", "rejected"):
            store.review_claim(
                claim_id, claim["status"], "lead", claim["rationale"], actor=actor
            )

    for conflict_key, conflict in state.get("conflicts", {}).items():
        conflict_id = _stable_id("conflict", branch_id, conflict_key)
        code = _conflict_code(conflict_key)
        existing_code = store.connection.execute(
            "SELECT id FROM conflicts WHERE project_id = ? AND code = ?",
            (project_id, code),
        ).fetchone()
        if existing_code is not None:
            code = f"{branch_id}:{code}"
            report["warnings"].append(
                f"Kód konfliktu {conflict_key} už existoval v jiné větvi; původní ID zůstalo v source_identifier."
            )
        mapped_claims = [claim_ids[item] for item in conflict["claim_ids"]]
        store.create_conflict(
            conflict_id, project_id, code, conflict_key, mapped_claims,
            source_identifier=conflict_key, source_json=conflict,
            source_branch_id=branch_id, actor=actor,
        )
        created["conflicts"] += 1
        if conflict["status"] == "resolved":
            preferred = set(conflict["resolution"]["preferred_claim_ids"])
            dispositions = {
                claim_ids[item]: ("preferred" if item in preferred else "not_preferred")
                for item in conflict["claim_ids"]
            }
            store.resolve_conflict(
                _stable_id("decision", branch_id, conflict_key), conflict_id, project_id,
                conflict["resolution"]["rationale"], dispositions,
                decided_by="research.json import", actor=actor,
            )

    for index, event in enumerate(state["events"]):
        store.add_import_history_event(
            _stable_id("history", branch_id, str(index)), project_id, branch_id,
            run_id, index, event,
            source_revision=event.get("revision") if isinstance(event, dict) else None,
            actor=actor,
        )
        created["history_events"] += 1
    return created


def import_research(
    database, input_path, *, project_id, project_name, branch_key,
    branch_label, actor, dry_run=False,
):
    sqlite_store.validate_id(project_id, "project_id")
    sqlite_store.validate_id(branch_key, "branch_key")
    if not project_name.strip() or not branch_label.strip() or not actor.strip():
        raise ValueError("Název projektu, popisek větve a aktér nesmějí být prázdné.")
    root, state, snapshots = load_research_input(input_path)
    source_hash = hashlib.sha256(snapshots[-1]["raw"]).hexdigest()
    branch_id = _branch_id(project_id, branch_key)
    report = _base_report(
        state, snapshots, project_id, branch_key, branch_id, source_hash, dry_run
    )
    planned_counts = _planned_counts(root, state)
    report["planned_insert_counts"] = planned_counts
    database_errors = sqlite_store.validate_database(database)
    if database_errors:
        raise ValueError("\n".join(database_errors))
    status = sqlite_store.database_status(database)
    if status["schema_version"] != sqlite_store.CURRENT_SCHEMA_VERSION:
        raise ValueError("Před importem spusť database migrate na aktuální schéma.")

    with sqlite_store.GenealogyStore(database, migrate=False, read_only=dry_run) as store:
        project, branch = _existing_context(store.connection, project_id, branch_key)
        if branch is not None:
            branch_id = branch["id"]
            report["branch_id"] = branch_id
            expected_kind = f"json_v{state['schema_version']}"
            if branch["history_kind"] != expected_kind:
                raise ValueError("Existující importní větev má jiný typ historie.")
            existing = store.connection.execute(
                "SELECT id, status FROM import_runs WHERE branch_id = ? AND idempotency_key = ?",
                (branch_id, f"sha256:{source_hash}:{IMPORTER_VERSION}"),
            ).fetchone()
            if existing is not None:
                report.update({
                    "idempotent": True,
                    "import_run_id": existing["id"],
                    "import_status": existing["status"],
                })
                return report
            different = store.connection.execute(
                "SELECT id FROM import_runs WHERE branch_id = ? LIMIT 1", (branch_id,)
            ).fetchone()
            if different is not None:
                raise ValueError(
                    "Importní větev už obsahuje jiný snapshot; pro změněný research.json "
                    "založ novou branch-key, aby se původní historie nepřepsala."
                )
        elif store.connection.execute(
            "SELECT 1 FROM import_branches WHERE id = ?", (branch_id,)
        ).fetchone():
            raise ValueError("Odvozené ID větve už používá jiná větev.")

        if dry_run:
            report.update({
                "would_create_project": project is None,
                "would_create_branch": branch is None,
                "would_import": True,
                "import_run_id": _stable_id("run", branch_id, source_hash),
            })
            return report

        with sqlite_store.transaction(store.connection):
            if project is None:
                store.create_project(project_id, project_name, actor=actor)
            if branch is None:
                store.create_import_branch(
                    branch_id, project_id, branch_key, branch_label,
                    f"json_v{state['schema_version']}",
                    source_revision=str(state["revision"]),
                    metadata={"adapter": IMPORTER, "adapter_version": IMPORTER_VERSION},
                    actor=actor,
                )
            registered = _register_snapshot_files(store, project_id, branch_id, snapshots, actor)
            current_file_id = registered[-1][1]
            run_id = _stable_id("run", branch_id, source_hash)
            run = store.start_import_run(
                run_id, project_id, branch_id, current_file_id,
                idempotency_key=f"sha256:{source_hash}:{IMPORTER_VERSION}",
                importer=IMPORTER, importer_version=IMPORTER_VERSION,
                source_schema_version=state["schema_version"],
                summary={
                    "source_counts": report["source_counts"],
                    "source_revision": state["revision"],
                    "next_step": state["next_step"],
                },
                actor=actor,
            )
            if not run["created"]:
                report.update({"idempotent": True, "import_run_id": run["id"]})
                return report
            for snapshot, original_file_id in registered:
                snapshot_state = snapshot["state"]
                store.add_import_snapshot(
                    _stable_id(
                        "snapshot", branch_id,
                        f"{snapshot['kind']}:{snapshot_state['revision']}",
                    ),
                    project_id, branch_id, run_id, original_file_id,
                    snapshot["kind"], snapshot_state["schema_version"],
                    snapshot_state["revision"], snapshot_state, actor=actor,
                )
            inserted = _map_state(
                store, root, state, project_id, branch_id, run_id, report, actor
            )
            if inserted != planned_counts:
                raise ValueError(
                    "Vložené počty neodpovídají dry-run plánu; import byl vrácen zpět."
                )
            store.finish_import_run(run_id, status="validated", actor=actor)
            errors = store.validate()
            if errors:
                raise ValueError("\n".join(errors))
            store.finish_import_run(run_id, status="committed", actor=actor)

    report.update({
        "imported": True,
        "import_run_id": run_id,
        "import_status": "committed",
        "inserted_counts": inserted,
    })
    return report


def _eligible_claim(connection, project_id, branch_id, source_identifier):
    row = connection.execute(
        "SELECT id, status FROM claims WHERE project_id = ? AND branch_id = ? "
        "AND source_identifier = ?",
        (project_id, branch_id, source_identifier),
    ).fetchone()
    if row is None:
        raise ValueError(f"Outbox odkazuje na neznámé tvrzení {source_identifier!r}.")
    if row["status"] != "supported":
        raise ValueError(f"Tvrzení {source_identifier!r} není supported.")
    conflicts = connection.execute(
        "SELECT f.id, f.status FROM conflicts f "
        "JOIN conflict_claims cc ON cc.conflict_id = f.id WHERE cc.claim_id = ?",
        (row["id"],),
    ).fetchall()
    for conflict in conflicts:
        if conflict["status"] == "open":
            raise ValueError(f"Tvrzení {source_identifier!r} je v otevřeném konfliktu.")
        preferred = connection.execute(
            "SELECT 1 FROM conflict_decision_claims WHERE conflict_id = ? "
            "AND claim_id = ? AND disposition = 'preferred'",
            (conflict["id"], row["id"]),
        ).fetchone()
        if preferred is None:
            raise ValueError(f"Tvrzení {source_identifier!r} není preferovanou variantou konfliktu.")
    return row["id"]


def approve_outbox(database, approval, *, approved_by, dry_run=False):
    if not approved_by.strip():
        raise ValueError("Schvalující osoba nesmí být prázdná.")
    database_errors = sqlite_store.validate_database(database)
    if database_errors:
        raise ValueError("\n".join(database_errors))
    if not isinstance(approval, dict) or set(approval) != {
        "schema_version", "project_id", "operations"
    }:
        raise ValueError("Schvalovací JSON musí obsahovat schema_version, project_id a operations.")
    if approval["schema_version"] != OUTBOX_APPROVAL_SCHEMA_VERSION:
        raise ValueError("Nepodporovaná verze schvalovacího JSON.")
    project_id = sqlite_store.validate_id(approval["project_id"], "project_id")
    operations = approval["operations"]
    if not isinstance(operations, list) or not operations:
        raise ValueError("Schvalovací JSON musí obsahovat neprázdný seznam operations.")
    allowed = {
        "branch_key", "idempotency_key", "operation_type", "aggregate_type",
        "aggregate_id", "claim_ids", "payload",
    }
    prepared = []
    seen = set()
    with sqlite_store.GenealogyStore(database, migrate=False, read_only=dry_run) as store:
        if store.connection.execute(
            "SELECT 1 FROM projects WHERE id = ?", (project_id,)
        ).fetchone() is None:
            raise ValueError("Projekt pro outbox neexistuje.")
        for index, operation in enumerate(operations):
            if not isinstance(operation, dict) or set(operation) != allowed:
                raise ValueError(f"operations[{index}] má neplatná pole.")
            for field in (
                "branch_key", "idempotency_key", "operation_type",
                "aggregate_type", "aggregate_id",
            ):
                if not isinstance(operation[field], str) or not operation[field].strip():
                    raise ValueError(f"operations[{index}].{field} nesmí být prázdné.")
            if operation["idempotency_key"] in seen:
                raise ValueError("Schvalovací JSON obsahuje duplicitní idempotency_key.")
            seen.add(operation["idempotency_key"])
            if not isinstance(operation["payload"], dict):
                raise ValueError(f"operations[{index}].payload musí být objekt.")
            if not isinstance(operation["claim_ids"], list) or not operation["claim_ids"]:
                raise ValueError(f"operations[{index}].claim_ids musí být neprázdný seznam.")
            branch = store.connection.execute(
                "SELECT id FROM import_branches WHERE project_id = ? AND branch_key = ?",
                (project_id, operation["branch_key"]),
            ).fetchone()
            if branch is None:
                raise ValueError(f"Neznámá importní větev {operation['branch_key']!r}.")
            for claim_id in operation["claim_ids"]:
                _eligible_claim(store.connection, project_id, branch["id"], claim_id)
            prepared.append((operation, branch["id"]))

        if dry_run:
            return {
                "dry_run": True, "approved": 0, "eligible": len(prepared),
                "network_writes": False, "sent": 0,
            }

        created = 0
        unchanged = 0
        with sqlite_store.transaction(store.connection):
            for operation, branch_id in prepared:
                outbox_payload = {
                    "operation_payload": operation["payload"],
                    "approval_evidence": {
                        "branch_key": operation["branch_key"],
                        "claim_source_identifiers": operation["claim_ids"],
                    },
                }
                existing = store.connection.execute(
                    "SELECT * FROM sync_outbox WHERE project_id = ? AND idempotency_key = ?",
                    (project_id, operation["idempotency_key"]),
                ).fetchone()
                payload_json = sqlite_store.canonical_json(outbox_payload)
                if existing is not None:
                    same = (
                        existing["branch_id"] == branch_id
                        and existing["operation_type"] == operation["operation_type"]
                        and existing["aggregate_type"] == operation["aggregate_type"]
                        and existing["aggregate_id"] == operation["aggregate_id"]
                        and existing["payload_json"] == payload_json
                        and existing["approved_by"] == approved_by
                    )
                    if not same:
                        raise ValueError("Idempotency klíč outboxu už označuje jinou operaci.")
                    unchanged += 1
                    continue
                store.enqueue_outbox(
                    _stable_id("outbox", project_id, operation["idempotency_key"]),
                    project_id, operation["idempotency_key"], operation["operation_type"],
                    operation["aggregate_type"], operation["aggregate_id"],
                    outbox_payload, approved_by=approved_by,
                    approved_at=sqlite_store.now(), branch_id=branch_id,
                )
                created += 1
    return {
        "dry_run": False, "approved": created, "unchanged": unchanged,
        "eligible": len(prepared), "network_writes": False, "sent": 0,
    }
