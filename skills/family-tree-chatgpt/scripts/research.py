#!/usr/bin/env python3
"""Offline evidence notebook. One atomic JSON state; no archive or cloud access."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import zipfile


BUNDLE_SCHEMA_VERSION = 1
CURRENT_RESEARCH_SCHEMA_VERSION = 2
SUPPORTED_RESEARCH_SCHEMA_VERSIONS = (1, 2)
BUNDLE_MANIFEST = "manifest.json"
BUNDLE_DIRECTORIES = ("sources", "crops", "history")
MODEL_COLLECTIONS = ("persons", "relationships", "claims", "sources", "conflicts")
MODEL_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,95}")
PREDICATE_RE = re.compile(r"[a-z][a-z0-9_.-]{0,95}")
MAX_BUNDLE_FILES = 10_000
MAX_BUNDLE_BYTES = 10 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def private_workspace(path):
    root = Path(path).expanduser().resolve()
    if in_git_tree(root):
        raise ValueError("Badatelskou složku vytvoř mimo git repozitář.")
    return root


def in_git_tree(path):
    for parent in (path, *path.parents):
        marker = parent / ".git"
        if marker.is_dir() and (marker / "HEAD").is_file():
            return True
        if marker.is_file():
            try:
                if marker.read_text(encoding="utf-8").startswith("gitdir:"):
                    return True
            except (OSError, UnicodeError):
                return True
    return False


def asset(root, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("Cesta ke snímku musí být relativní vůči badatelské složce.")
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Soubor chybí nebo leží mimo badatelskou složku: {name}")
    return path


def validate_record(record, root, verify_hashes=False):
    errors = []
    if not isinstance(record, dict):
        return ["Zápis musí být JSON objekt."]
    key = record.get("id", "")
    if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,95}", key):
        errors.append("id: použij 1–96 malých ASCII písmen, číslic, pomlček či podtržítek.")
    status = record.get("reading_status")
    if status not in ("unread", "draft", "reviewed"):
        errors.append("reading_status: očekáváno unread, draft nebo reviewed.")
    for field in ("transcription", "translation", "interpretation"):
        if not isinstance(record.get(field), str):
            errors.append(f"{field}: očekáván text.")
    if not isinstance(record.get("uncertainties"), list) or not all(
        isinstance(x, str) for x in record.get("uncertainties", [])
    ):
        errors.append("uncertainties: očekáván seznam textů.")
    source = record.get("source")
    if not isinstance(source, dict):
        errors.append("source: očekáván objekt.")
        source = {}
    for field in ("archive", "reference", "page", "url", "accessed_on", "file", "crop"):
        if not isinstance(source.get(field), str):
            errors.append(f"source.{field}: očekáván text.")
    if source.get("url") and (not isinstance(source["url"], str) or not source["url"].startswith(("https://", "http://"))):
        errors.append("source.url: očekáván úplný HTTP(S) odkaz.")
    if source.get("accessed_on"):
        try:
            date.fromisoformat(source["accessed_on"])
        except (TypeError, ValueError):
            errors.append("source.accessed_on: očekáváno ISO datum YYYY-MM-DD.")
    if not isinstance(record.get("visual_review"), bool):
        errors.append("visual_review: očekávána boolean hodnota.")
    if status == "reviewed":
        for field in ("archive", "reference", "page", "url", "accessed_on", "file", "crop"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                errors.append(f"Pro reviewed chybí source.{field}.")
        if record.get("visual_review") is not True or not str(record.get("transcription", "")).strip():
            errors.append("Pro reviewed je nutný přepis a výslovná vizuální kontrola.")
    identity = record.get("identity")
    if not isinstance(identity, dict):
        errors.append("identity: očekáván objekt.")
        identity = {}
    if identity.get("status") not in ("unresolved", "supported", "rejected"):
        errors.append("identity.status: očekáváno unresolved, supported nebo rejected.")
    if not isinstance(identity.get("rationale"), str):
        errors.append("identity.rationale: očekáván text.")
    evidence = identity.get("evidence")
    if not isinstance(evidence, list) or not all(isinstance(x, str) and x.strip() for x in evidence or []):
        errors.append("identity.evidence: očekáván seznam neprázdných citací.")
    if identity.get("status") in ("supported", "rejected"):
        if not isinstance(identity.get("rationale"), str) or not identity["rationale"].strip() or not evidence:
            errors.append("Závěr o totožnosti vyžaduje zdůvodnění a citace.")
    for field in ("file", "crop"):
        if source.get(field):
            try:
                path = asset(root, source[field])
                if verify_hashes and source.get(field + "_sha256") != sha256(path):
                    errors.append(f"Změněný soubor nebo chybějící SHA-256: source.{field}.")
            except ValueError as exc:
                errors.append(str(exc))
    return errors


def validate_model_id(value, path, errors):
    if not isinstance(value, str) or not MODEL_ID_RE.fullmatch(value):
        errors.append(f"{path}: použij 1–96 malých ASCII písmen, číslic, pomlček či podtržítek.")


def validate_keys(value, allowed, path, errors):
    if not isinstance(value, dict):
        errors.append(f"{path}: očekáván objekt.")
        return False
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        errors.append(f"{path}: neznámá pole: {', '.join(unknown)}.")
    return True


def validate_text(value, path, errors, required=False):
    if not isinstance(value, str):
        errors.append(f"{path}: očekáván text.")
    elif required and not value.strip():
        errors.append(f"{path}: text nesmí být prázdný.")


def validate_extensions(value, path, errors):
    if not isinstance(value, dict):
        errors.append(f"{path}: očekáván objekt pro rozšíření.")


def validate_model(state, root, verify_hashes=False):
    """Validate the schema-2 evidence graph without judging genealogy."""
    errors = []
    persons = state.get("persons", {})
    relationships = state.get("relationships", {})
    claims = state.get("claims", {})
    sources = state.get("sources", {})
    conflicts = state.get("conflicts", {})
    collections = {
        "persons": persons,
        "relationships": relationships,
        "claims": claims,
        "sources": sources,
        "conflicts": conflicts,
    }
    for name, collection in collections.items():
        if not isinstance(collection, dict):
            errors.append(f"{name}: očekávána mapa objektů podle ID.")
    if errors:
        return errors

    person_fields = ("id", "label", "notes", "extensions")
    for key, person in persons.items():
        path = f"persons.{key}"
        if not validate_keys(person, person_fields, path, errors):
            continue
        validate_model_id(key, path, errors)
        if key != person.get("id"):
            errors.append(f"{path}: klíč se neshoduje s id osoby.")
        validate_text(person.get("label"), f"{path}.label", errors, required=True)
        validate_text(person.get("notes"), f"{path}.notes", errors)
        validate_extensions(person.get("extensions"), f"{path}.extensions", errors)

    relationship_fields = ("id", "type", "participants", "notes", "extensions")
    for key, relationship in relationships.items():
        path = f"relationships.{key}"
        if not validate_keys(relationship, relationship_fields, path, errors):
            continue
        validate_model_id(key, path, errors)
        if key != relationship.get("id"):
            errors.append(f"{path}: klíč se neshoduje s id vztahu.")
        validate_text(relationship.get("type"), f"{path}.type", errors, required=True)
        validate_text(relationship.get("notes"), f"{path}.notes", errors)
        validate_extensions(relationship.get("extensions"), f"{path}.extensions", errors)
        participants = relationship.get("participants")
        if not isinstance(participants, list) or len(participants) < 2:
            errors.append(f"{path}.participants: očekáváni alespoň dva účastníci.")
            continue
        seen = set()
        for index, participant in enumerate(participants):
            item_path = f"{path}.participants[{index}]"
            if not validate_keys(participant, ("person_id", "role"), item_path, errors):
                continue
            person_id = participant.get("person_id")
            role = participant.get("role")
            validate_text(person_id, f"{item_path}.person_id", errors, required=True)
            validate_text(role, f"{item_path}.role", errors, required=True)
            if isinstance(person_id, str) and person_id not in persons:
                errors.append(f"{item_path}.person_id: neznámá osoba {person_id!r}.")
            if isinstance(person_id, str) and isinstance(role, str):
                marker = (person_id, role)
                if marker in seen:
                    errors.append(f"{item_path}: duplicitní účastník a role.")
                seen.add(marker)

    source_fields = (
        "id", "kind", "title", "citation", "repository", "url", "accessed_on",
        "files", "record_ids", "notes", "extensions",
    )
    for key, source in sources.items():
        path = f"sources.{key}"
        if not validate_keys(source, source_fields, path, errors):
            continue
        validate_model_id(key, path, errors)
        if key != source.get("id"):
            errors.append(f"{path}: klíč se neshoduje s id pramene.")
        validate_text(source.get("kind"), f"{path}.kind", errors, required=True)
        validate_text(source.get("title"), f"{path}.title", errors, required=True)
        for field in ("citation", "repository", "url", "accessed_on", "notes"):
            validate_text(source.get(field), f"{path}.{field}", errors)
        validate_extensions(source.get("extensions"), f"{path}.extensions", errors)
        url = source.get("url")
        if isinstance(url, str) and url and not url.startswith(("https://", "http://")):
            errors.append(f"{path}.url: očekáván úplný HTTP(S) odkaz.")
        accessed_on = source.get("accessed_on")
        if isinstance(accessed_on, str) and accessed_on:
            try:
                date.fromisoformat(accessed_on)
            except ValueError:
                errors.append(f"{path}.accessed_on: očekáváno ISO datum YYYY-MM-DD.")
        record_ids = source.get("record_ids")
        if not isinstance(record_ids, list) or not all(isinstance(item, str) for item in record_ids):
            errors.append(f"{path}.record_ids: očekáván seznam ID zápisů.")
        else:
            if len(record_ids) != len(set(record_ids)):
                errors.append(f"{path}.record_ids: ID zápisů se nesmí opakovat.")
            for record_id in record_ids:
                if record_id not in state.get("records", {}):
                    errors.append(f"{path}.record_ids: neznámý zápis {record_id!r}.")
        files = source.get("files")
        if not isinstance(files, list):
            errors.append(f"{path}.files: očekáván seznam souborů.")
        else:
            seen_files = set()
            for index, item in enumerate(files):
                item_path = f"{path}.files[{index}]"
                if not validate_keys(item, ("path", "sha256"), item_path, errors):
                    continue
                relative = item.get("path")
                digest = item.get("sha256")
                validate_text(relative, f"{item_path}.path", errors, required=True)
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    errors.append(f"{item_path}.sha256: očekáván SHA-256 malými hex znaky.")
                if isinstance(relative, str) and relative:
                    if relative in seen_files:
                        errors.append(f"{item_path}.path: soubor je uveden vícekrát.")
                    seen_files.add(relative)
                    try:
                        file_path = asset(root, relative)
                        if verify_hashes and isinstance(digest, str) and digest != sha256(file_path):
                            errors.append(f"{item_path}: změněný soubor nebo chybný SHA-256.")
                    except ValueError as exc:
                        errors.append(str(exc))

    claim_fields = (
        "id", "subject", "predicate", "value", "status", "citations",
        "rationale", "notes", "extensions",
    )
    for key, claim in claims.items():
        path = f"claims.{key}"
        if not validate_keys(claim, claim_fields, path, errors):
            continue
        validate_model_id(key, path, errors)
        if key != claim.get("id"):
            errors.append(f"{path}: klíč se neshoduje s id tvrzení.")
        subject = claim.get("subject")
        if validate_keys(subject, ("type", "id"), f"{path}.subject", errors):
            subject_type = subject.get("type")
            subject_id = subject.get("id")
            if subject_type not in ("person", "relationship"):
                errors.append(f"{path}.subject.type: očekáváno person nebo relationship.")
            validate_text(subject_id, f"{path}.subject.id", errors, required=True)
            target = persons if subject_type == "person" else relationships
            if isinstance(subject_id, str) and subject_type in ("person", "relationship") and subject_id not in target:
                errors.append(f"{path}.subject.id: neznámý subjekt {subject_id!r}.")
        predicate = claim.get("predicate")
        if not isinstance(predicate, str) or not PREDICATE_RE.fullmatch(predicate):
            errors.append(f"{path}.predicate: použij malé ASCII jméno, případně tečky, pomlčky či podtržítka.")
        try:
            json.dumps(claim.get("value"), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            errors.append(f"{path}.value: hodnota musí být platná JSON hodnota bez NaN či nekonečna.")
        status = claim.get("status")
        if status not in ("unverified", "supported", "rejected"):
            errors.append(f"{path}.status: očekáváno unverified, supported nebo rejected.")
        validate_text(claim.get("rationale"), f"{path}.rationale", errors)
        validate_text(claim.get("notes"), f"{path}.notes", errors)
        validate_extensions(claim.get("extensions"), f"{path}.extensions", errors)
        citations = claim.get("citations")
        if not isinstance(citations, list):
            errors.append(f"{path}.citations: očekáván seznam citací.")
            citations = []
        for index, citation in enumerate(citations):
            item_path = f"{path}.citations[{index}]"
            if not validate_keys(citation, ("source_id", "locator", "quotation", "note"), item_path, errors):
                continue
            source_id = citation.get("source_id")
            validate_text(source_id, f"{item_path}.source_id", errors, required=True)
            for field in ("locator", "quotation", "note"):
                validate_text(citation.get(field), f"{item_path}.{field}", errors)
            if isinstance(source_id, str) and source_id not in sources:
                errors.append(f"{item_path}.source_id: neznámý pramen {source_id!r}.")
        if status in ("supported", "rejected"):
            if not isinstance(claim.get("rationale"), str) or not claim["rationale"].strip() or not citations:
                errors.append(f"{path}: závěr supported/rejected vyžaduje zdůvodnění a citaci.")

    conflict_fields = ("id", "claim_ids", "status", "resolution", "notes", "extensions")
    for key, conflict in conflicts.items():
        path = f"conflicts.{key}"
        if not validate_keys(conflict, conflict_fields, path, errors):
            continue
        validate_model_id(key, path, errors)
        if key != conflict.get("id"):
            errors.append(f"{path}: klíč se neshoduje s id konfliktu.")
        claim_ids = conflict.get("claim_ids")
        if not isinstance(claim_ids, list) or len(claim_ids) < 2 or not all(isinstance(item, str) for item in claim_ids):
            errors.append(f"{path}.claim_ids: očekávána alespoň dvě ID tvrzení.")
            claim_ids = []
        elif len(claim_ids) != len(set(claim_ids)):
            errors.append(f"{path}.claim_ids: tvrzení se nesmí opakovat.")
        for claim_id in claim_ids:
            if claim_id not in claims:
                errors.append(f"{path}.claim_ids: neznámé tvrzení {claim_id!r}.")
        status = conflict.get("status")
        if status not in ("open", "resolved"):
            errors.append(f"{path}.status: očekáváno open nebo resolved.")
        resolution = conflict.get("resolution")
        if validate_keys(resolution, ("preferred_claim_ids", "rationale"), f"{path}.resolution", errors):
            preferred = resolution.get("preferred_claim_ids")
            if not isinstance(preferred, list) or not all(isinstance(item, str) for item in preferred):
                errors.append(f"{path}.resolution.preferred_claim_ids: očekáván seznam ID tvrzení.")
                preferred = []
            elif len(preferred) != len(set(preferred)):
                errors.append(f"{path}.resolution.preferred_claim_ids: tvrzení se nesmí opakovat.")
            for claim_id in preferred:
                if claim_id not in claim_ids:
                    errors.append(f"{path}.resolution.preferred_claim_ids: {claim_id!r} není v konfliktu.")
            validate_text(resolution.get("rationale"), f"{path}.resolution.rationale", errors)
            if status == "resolved" and (
                not isinstance(resolution.get("rationale"), str) or not resolution["rationale"].strip()
            ):
                errors.append(f"{path}: vyřešený konflikt vyžaduje zdůvodnění.")
        validate_text(conflict.get("notes"), f"{path}.notes", errors)
        validate_extensions(conflict.get("extensions"), f"{path}.extensions", errors)
    return errors


def read_state(root):
    state = json.loads((root / "research.json").read_text(encoding="utf-8"))
    if (
        not isinstance(state, dict)
        or type(state.get("schema_version")) is not int
        or state["schema_version"] not in SUPPORTED_RESEARCH_SCHEMA_VERSIONS
    ):
        raise ValueError("Nepodporovaný formát badatelského stavu.")
    if type(state.get("revision")) is not int or state["revision"] < 0:
        raise ValueError("Neplatná revize stavu.")
    if not isinstance(state.get("records"), dict) or not isinstance(state.get("events"), list) or not isinstance(state.get("next_step"), str):
        raise ValueError("Poškozená struktura stavu.")
    if state["schema_version"] == 2 and any(not isinstance(state.get(name), dict) for name in MODEL_COLLECTIONS):
        raise ValueError("Poškozená struktura obecného genealogického modelu.")
    return state


def check_state(state, root):
    errors = []
    for key, record in state["records"].items():
        errors.extend(f"{key}: {e}" for e in validate_record(record, root, verify_hashes=True))
        if not isinstance(record, dict) or key != record.get("id"):
            errors.append(f"{key}: klíč se neshoduje s id zápisu.")
    if state["schema_version"] == 2:
        errors.extend(validate_model(state, root, verify_hashes=True))
    return errors


def audit_state(state):
    """Return non-blocking quality warnings for a structurally valid state.

    The separation of hard errors from research warnings adapts the approach in
    rodokmen-skill tools/kontrola.py (MIT), revision 0fb0c037. The checks are
    rewritten for this project's evidence-record schema.
    """
    warnings = []
    reading_status = {name: 0 for name in ("unread", "draft", "reviewed")}
    identity_status = {name: 0 for name in ("unresolved", "supported", "rejected")}
    event_results = {}
    locations = {}
    for key, record in state["records"].items():
        status = record["reading_status"]
        reading_status[status] += 1
        identity = record["identity"]
        identity_status[identity["status"]] += 1
        source = record["source"]
        locator = tuple(source[field].strip() for field in ("archive", "reference", "page", "url"))
        if all(locator):
            locations.setdefault(locator, []).append(key)
        complete_review = (
            record["visual_review"] is True
            and record["transcription"].strip()
            and all(source[field].strip() for field in (
                "archive", "reference", "page", "url", "accessed_on", "file", "crop"
            ))
        )
        if status == "draft" and complete_review:
            warnings.append({
                "code": "draft_ready_for_review",
                "record_id": key,
                "message": "Draft má citaci, přepis, snímky a vizuální kontrolu; rozhodni, zda může být reviewed.",
            })
        if status == "reviewed" and not record["translation"].strip():
            warnings.append({
                "code": "reviewed_without_translation",
                "record_id": key,
                "message": "Vizuálně zkontrolovaný zápis nemá samostatný překlad.",
            })
        if status == "reviewed" and not record["interpretation"].strip():
            warnings.append({
                "code": "reviewed_without_interpretation",
                "record_id": key,
                "message": "Vizuálně zkontrolovaný zápis nemá samostatnou interpretaci.",
            })
        if status == "reviewed" and record["uncertainties"]:
            warnings.append({
                "code": "open_reading_uncertainties",
                "record_id": key,
                "message": f"Zápis má {len(record['uncertainties'])} výslovně otevřených nejistot; ponech je viditelné.",
            })
        if identity["status"] in ("supported", "rejected") and status != "reviewed":
            warnings.append({
                "code": "identity_before_review",
                "record_id": key,
                "message": "Závěr o totožnosti existuje dříve než vizuálně zkontrolované čtení zápisu.",
            })
    for locator, record_ids in locations.items():
        if len(record_ids) > 1:
            warnings.append({
                "code": "duplicate_source_locator",
                "record_ids": record_ids,
                "message": (
                    "Více záznamů používá stejný archiv, signaturu, stranu/snímek a URL; "
                    "ověř, zda jde úmyslně o více položek na jednom snímku."
                ),
            })
    for event in state["events"]:
        result = event.get("result", "unknown")
        event_results[result] = event_results.get(result, 0) + 1
    if not state["records"]:
        warnings.append({
            "code": "no_records",
            "message": "Badatelský stav zatím neobsahuje žádný archivní zápis.",
        })
    model_counts = {name: len(state.get(name, {})) for name in MODEL_COLLECTIONS}
    claim_status = {name: 0 for name in ("unverified", "supported", "rejected")}
    if state["schema_version"] == 2:
        claims_by_subject = {}
        for claim_id, claim in state["claims"].items():
            claim_status[claim["status"]] += 1
            subject = (claim["subject"]["type"], claim["subject"]["id"])
            claims_by_subject.setdefault(subject, []).append(claim_id)
            if not claim["citations"]:
                warnings.append({
                    "code": "claim_without_citation",
                    "claim_id": claim_id,
                    "message": "Tvrzení nemá žádnou citaci pramene; ponech je jako neověřené.",
                })
        for person_id in state["persons"]:
            if ("person", person_id) not in claims_by_subject:
                warnings.append({
                    "code": "person_without_claims",
                    "person_id": person_id,
                    "message": "Pracovní osoba nemá žádné samostatně evidované tvrzení.",
                })
        for relationship_id in state["relationships"]:
            if ("relationship", relationship_id) not in claims_by_subject:
                warnings.append({
                    "code": "relationship_without_claims",
                    "relationship_id": relationship_id,
                    "message": "Vztah nemá žádné tvrzení, které by šlo doložit nebo odmítnout.",
                })
        for source_id, source in state["sources"].items():
            if not source["citation"].strip():
                warnings.append({
                    "code": "source_without_citation",
                    "source_id": source_id,
                    "message": "Pramen nemá úplnou textovou citaci.",
                })
        for conflict_id, conflict in state["conflicts"].items():
            if conflict["status"] == "open":
                warnings.append({
                    "code": "open_conflict",
                    "conflict_id": conflict_id,
                    "claim_ids": conflict["claim_ids"],
                    "message": "Rozporná tvrzení zůstávají otevřená; nevybírej vítěze bez zdůvodnění.",
                })
    return {
        "schema_version": state["schema_version"],
        "revision": state["revision"],
        "records": len(state["records"]),
        "reading_status": reading_status,
        "identity_status": identity_status,
        "event_results": event_results,
        "model_counts": model_counts,
        "claim_status": claim_status,
        "warnings": warnings,
    }


def atomic_json(path, state):
    fd, name = tempfile.mkstemp(prefix=".research-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def workspace_files(root):
    files = []
    state = root / "research.json"
    if state.is_symlink() or not state.is_file():
        raise ValueError("Chybí běžný soubor research.json.")
    files.append(("research.json", state))
    for name in BUNDLE_DIRECTORIES:
        directory = root / name
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"Chybí běžný adresář {name}/.")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Balíček nesmí obsahovat symlink: {path.relative_to(root)}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(f"Balíček podporuje pouze běžné soubory: {path.relative_to(root)}")
            files.append((path.relative_to(root).as_posix(), path))
    if len(files) > MAX_BUNDLE_FILES:
        raise ValueError("Badatelská složka obsahuje příliš mnoho souborů pro jeden balíček.")
    return files


def bundle_output(path, root):
    output = Path(path).expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Výstupní balíček už existuje: {output}")
    if not output.parent.is_dir():
        raise ValueError("Nadřazený adresář výstupního balíčku neexistuje.")
    if output.is_relative_to(root):
        raise ValueError("Výstupní balíček musí ležet mimo badatelskou složku.")
    if in_git_tree(output):
        raise ValueError("Soukromý badatelský balíček vytvoř mimo git repozitář.")
    return output


def zip_file_info(name):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    return info


def export_bundle(root, output_path):
    root = private_workspace(root)
    output = bundle_output(output_path, root)
    temporary = None
    with locked(root):
        state = read_state(root)
        errors = check_state(state, root)
        if errors:
            raise ValueError("\n".join(errors))
        files = workspace_files(root)
        fd, temporary = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
        try:
            entries = []
            with os.fdopen(fd, "w+b") as stream:
                with zipfile.ZipFile(stream, "w", allowZip64=True) as archive:
                    for relative, path in files:
                        digest = hashlib.sha256()
                        size = 0
                        with path.open("rb") as source, archive.open(zip_file_info(relative), "w") as target:
                            while chunk := source.read(1024 * 1024):
                                digest.update(chunk)
                                size += len(chunk)
                                if size > MAX_BUNDLE_BYTES:
                                    raise ValueError(f"Soubor je pro balíček příliš velký: {relative}")
                                target.write(chunk)
                        entries.append({"path": relative, "size": size, "sha256": digest.hexdigest()})
                    if sum(entry["size"] for entry in entries) > MAX_BUNDLE_BYTES:
                        raise ValueError("Badatelský balíček překračuje povolenou velikost.")
                    manifest = {
                        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
                        "research_schema_version": state["schema_version"],
                        "revision": state["revision"],
                        "created_at": now(),
                        "files": entries,
                    }
                    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
                    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
                        raise ValueError("Manifest balíčku je příliš velký.")
                    archive.writestr(zip_file_info(BUNDLE_MANIFEST), manifest_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            if output.exists() or output.is_symlink():
                raise FileExistsError(f"Výstupní balíček už existuje: {output}")
            # The temporary file lives in the same directory. A hard link publishes
            # the fully flushed inode atomically and, unlike replace(), never
            # overwrites a destination created by a concurrent process.
            os.link(temporary, output)
            os.unlink(temporary)
            temporary = None
            output.chmod(0o600)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
    return {
        "exported": True,
        "bundle": str(output),
        "bundle_sha256": sha256(output),
        "revision": state["revision"],
        "files": len(files),
    }


def safe_bundle_path(name):
    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name:
        raise ValueError("Balíček obsahuje neplatnou cestu.")
    parts = name.split("/")
    if name.startswith("/") or any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"Balíček obsahuje nebezpečnou cestu: {name}")
    if re.fullmatch(r"[A-Za-z]:", parts[0]):
        raise ValueError(f"Balíček obsahuje nebezpečnou cestu: {name}")
    path = PurePosixPath(name)
    if path.is_absolute():
        raise ValueError(f"Balíček obsahuje nebezpečnou cestu: {name}")
    return path


def validate_manifest(manifest):
    if (
        not isinstance(manifest, dict)
        or type(manifest.get("bundle_schema_version")) is not int
        or manifest["bundle_schema_version"] != BUNDLE_SCHEMA_VERSION
    ):
        raise ValueError("Nepodporovaný formát přenosového balíčku.")
    research_schema_version = manifest.get("research_schema_version")
    if type(research_schema_version) is not int or research_schema_version not in SUPPORTED_RESEARCH_SCHEMA_VERSIONS:
        raise ValueError("Balíček obsahuje nepodporovaný formát badatelského stavu.")
    revision = manifest.get("revision")
    if type(revision) is not int or revision < 0 or not isinstance(manifest.get("created_at"), str):
        raise ValueError("Manifest balíčku má neplatná metadata.")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries or len(entries) > MAX_BUNDLE_FILES:
        raise ValueError("Manifest balíčku má neplatný seznam souborů.")
    validated = {}
    total = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Manifest balíčku obsahuje neplatnou položku.")
        name = entry.get("path")
        path = safe_bundle_path(name)
        allowed = name == "research.json" or any(name.startswith(directory + "/") for directory in BUNDLE_DIRECTORIES)
        if not allowed or name == BUNDLE_MANIFEST or name in validated:
            raise ValueError(f"Manifest obsahuje nepovolenou nebo duplicitní cestu: {name}")
        size = entry.get("size")
        digest = entry.get("sha256")
        if type(size) is not int or size < 0 or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Manifest obsahuje neplatné údaje souboru: {name}")
        total += size
        if total > MAX_BUNDLE_BYTES:
            raise ValueError("Badatelský balíček překračuje povolenou velikost.")
        validated[name] = {"path": path, "size": size, "sha256": digest}
    if "research.json" not in validated:
        raise ValueError("Manifest neobsahuje research.json.")
    return validated


def read_bundle_manifest(archive):
    infos = archive.infolist()
    if len(infos) > MAX_BUNDLE_FILES + 1:
        raise ValueError("Balíček obsahuje příliš mnoho položek.")
    by_name = {}
    for info in infos:
        safe_bundle_path(info.filename)
        if info.filename in by_name:
            raise ValueError(f"Balíček obsahuje duplicitní cestu: {info.filename}")
        mode = (info.external_attr >> 16) & 0o177777
        if info.is_dir() or stat.S_ISLNK(mode) or (mode and not stat.S_ISREG(mode)):
            raise ValueError(f"Balíček obsahuje nepodporovanou položku: {info.filename}")
        by_name[info.filename] = info
    info = by_name.get(BUNDLE_MANIFEST)
    if info is None or info.file_size > MAX_MANIFEST_BYTES:
        raise ValueError("Balíček neobsahuje platný manifest.")
    try:
        manifest = json.loads(archive.read(info).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Manifest balíčku není platný JSON v UTF-8.") from exc
    entries = validate_manifest(manifest)
    if set(by_name) != set(entries) | {BUNDLE_MANIFEST}:
        raise ValueError("Obsah balíčku neodpovídá manifestu.")
    for name, entry in entries.items():
        if by_name[name].file_size != entry["size"]:
            raise ValueError(f"Velikost souboru neodpovídá manifestu: {name}")
    return manifest, entries, by_name


def restore_bundle(root, bundle_path):
    root = private_workspace(root)
    bundle = Path(bundle_path).expanduser().resolve()
    if not bundle.is_file():
        raise ValueError("Přenosový balíček neexistuje nebo není běžný soubor.")
    if root.exists() or root.is_symlink():
        raise FileExistsError("Cílová badatelská složka už existuje; obnova ji nepřepíše.")
    if not root.parent.is_dir():
        raise ValueError("Nadřazený adresář cílové badatelské složky neexistuje.")
    staging = None
    try:
        with zipfile.ZipFile(bundle, "r") as archive:
            manifest, entries, infos = read_bundle_manifest(archive)
            staging = Path(tempfile.mkdtemp(prefix=".research-restore-", dir=root.parent))
            staging.chmod(0o700)
            for directory in BUNDLE_DIRECTORIES:
                (staging / directory).mkdir(mode=0o700)
            for name, entry in entries.items():
                target = staging.joinpath(*entry["path"].parts)
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                digest = hashlib.sha256()
                size = 0
                with archive.open(infos[name], "r") as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        size += len(chunk)
                        if size > entry["size"] or size > MAX_BUNDLE_BYTES:
                            raise ValueError(f"Rozbalený soubor překračuje očekávanou velikost: {name}")
                        digest.update(chunk)
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                target.chmod(0o600)
                if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
                    raise ValueError(f"Kontrolní součet souboru neodpovídá manifestu: {name}")
        state = read_state(staging)
        if state["revision"] != manifest["revision"]:
            raise ValueError("Revize research.json neodpovídá manifestu.")
        if state["schema_version"] != manifest["research_schema_version"]:
            raise ValueError("Verze research.json neodpovídá manifestu.")
        errors = check_state(state, staging)
        if errors:
            raise ValueError("\n".join(errors))
        if root.exists() or root.is_symlink():
            raise FileExistsError("Cílová badatelská složka mezitím vznikla; obnova ji nepřepíše.")
        os.rename(staging, root)
        staging = None
        return {
            "restored": True,
            "workspace": str(root),
            "bundle_sha256": sha256(bundle),
            "revision": state["revision"],
            "records": len(state["records"]),
        }
    except zipfile.BadZipFile as exc:
        raise ValueError("Přenosový balíček není platný ZIP archiv.") from exc
    finally:
        if staging and staging.exists():
            shutil.rmtree(staging)


@contextmanager
def locked(root):
    path = root / ".research.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("Badatelská složka je zamčená. Ověř, zda neběží jiný zápis.") from exc
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def initialize(root):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with locked(root):
        if (root / "research.json").exists():
            raise ValueError("Badatelský stav už existuje; použij resume.")
        for name in ("sources", "crops", "history"):
            (root / name).mkdir(exist_ok=True, mode=0o700)
        state = {
            "schema_version": CURRENT_RESEARCH_SCHEMA_VERSION,
            "revision": 0,
            "records": {},
            "persons": {},
            "relationships": {},
            "claims": {},
            "sources": {},
            "conflicts": {},
            "events": [],
            "next_step": "Vybrat první výzkumnou otázku a doložit výchozí tvrzení.",
        }
        atomic_json(root / "research.json", state)


def backup_and_write(root, previous, new):
    backup = root / "history" / f"revision-{previous['revision']:06d}.json"
    if backup.exists():
        if json.loads(backup.read_text(encoding="utf-8")) != previous:
            raise ValueError("Záloha revize už existuje s jiným obsahem.")
    else:
        with backup.open("x", encoding="utf-8") as stream:
            json.dump(previous, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        backup.chmod(0o600)
    atomic_json(root / "research.json", new)


def migrate(root, expected_revision, next_step):
    if not next_step.strip():
        raise ValueError("Další krok nesmí být prázdný.")
    with locked(root):
        state = read_state(root)
        if state["revision"] != expected_revision:
            raise ValueError("Stav se mezitím změnil; znovu načti resume a spoj změny.")
        if state["schema_version"] == CURRENT_RESEARCH_SCHEMA_VERSION:
            raise ValueError("Badatelský stav už používá aktuální formát 2.")
        errors = check_state(state, root)
        if errors:
            raise ValueError("\n".join(errors))
        new = deepcopy(state)
        new["schema_version"] = CURRENT_RESEARCH_SCHEMA_VERSION
        for name in MODEL_COLLECTIONS:
            new[name] = {}
        new["revision"] += 1
        new["events"].append({
            "result": "schema_migrated",
            "from_schema_version": state["schema_version"],
            "to_schema_version": CURRENT_RESEARCH_SCHEMA_VERSION,
            "at": now(),
            "revision": new["revision"],
        })
        new["next_step"] = next_step
        errors = check_state(new, root)
        if errors:
            raise ValueError("\n".join(errors))
        backup_and_write(root, state, new)
        return new


def normalize_model_patch(patch):
    if not isinstance(patch, dict) or not patch:
        raise ValueError("Modelová změna musí být neprázdný JSON objekt.")
    unknown = sorted(set(patch) - set(MODEL_COLLECTIONS))
    if unknown:
        raise ValueError(f"Modelová změna obsahuje neznámé kolekce: {', '.join(unknown)}.")
    normalized = {}
    for name, items in patch.items():
        if not isinstance(items, list):
            raise ValueError(f"{name}: očekáván seznam objektů k vložení nebo nahrazení.")
        by_id = {}
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"{name}[{index}]: očekáván objekt.")
            item_id = item.get("id")
            if not isinstance(item_id, str) or not MODEL_ID_RE.fullmatch(item_id):
                raise ValueError(f"{name}[{index}].id: neplatné stabilní ID.")
            if item_id in by_id:
                raise ValueError(f"{name}: duplicitní ID {item_id!r} v jedné změně.")
            by_id[item_id] = item
        normalized[name] = by_id
    if not any(normalized.values()):
        raise ValueError("Modelová změna neobsahuje žádný objekt.")
    return normalized


def apply_model(root, expected_revision, patch, next_step):
    if not next_step.strip():
        raise ValueError("Další krok nesmí být prázdný.")
    changes = normalize_model_patch(patch)
    with locked(root):
        state = read_state(root)
        if state["schema_version"] != CURRENT_RESEARCH_SCHEMA_VERSION:
            raise ValueError("Obecný model vyžaduje formát 2; nejprve spusť výslovnou migraci.")
        if state["revision"] != expected_revision:
            raise ValueError("Stav se mezitím změnil; znovu načti resume a spoj změny.")
        errors = check_state(state, root)
        if errors:
            raise ValueError("\n".join(errors))
        new = deepcopy(state)
        counts = {}
        for name, items in changes.items():
            new[name].update(deepcopy(items))
            counts[name] = len(items)
        errors = check_state(new, root)
        if errors:
            raise ValueError("\n".join(errors))
        new["revision"] += 1
        new["events"].append({
            "result": "model_applied",
            "counts": counts,
            "at": now(),
            "revision": new["revision"],
        })
        new["next_step"] = next_step
        backup_and_write(root, state, new)
        return new


def model_view(state, collection=None, item_id=None):
    if state["schema_version"] != CURRENT_RESEARCH_SCHEMA_VERSION:
        raise ValueError("Obecný model není ve formátu 1 dostupný; nejprve spusť migraci.")
    if collection is None:
        return {name: state[name] for name in MODEL_COLLECTIONS}
    if collection not in MODEL_COLLECTIONS:
        raise ValueError("Neznámá kolekce obecného modelu.")
    if item_id is None:
        return state[collection]
    if item_id not in state[collection]:
        raise ValueError(f"V kolekci {collection} není ID {item_id!r}.")
    return state[collection][item_id]


def update(root, expected_revision, *, record=None, result=None, scope=None, next_step):
    if not next_step.strip():
        raise ValueError("Další krok nesmí být prázdný.")
    with locked(root):
        state = read_state(root)
        if state["revision"] != expected_revision:
            raise ValueError("Stav se mezitím změnil; znovu načti resume a spoj změny.")
        errors = check_state(state, root)
        if record is not None:
            errors.extend(validate_record(record, root))
        elif result not in ("not_found", "blocked", "note") or not scope or not scope.strip():
            errors.append("Událost vyžaduje platný výsledek a neprázdný rozsah hledání.")
        if errors:
            raise ValueError("\n".join(errors))
        new = deepcopy(state)
        if record is not None:
            record = deepcopy(record)
            for field in ("file", "crop"):
                if record["source"][field]:
                    record["source"][field + "_sha256"] = sha256(asset(root, record["source"][field]))
            new["records"][record["id"]] = record
            event = {"result": "record_saved", "record_id": record["id"]}
        else:
            event = {"result": result, "scope": scope}
        new["revision"] += 1
        event.update({"at": now(), "revision": new["revision"]})
        new["events"].append(event)
        new["next_step"] = next_step
        backup_and_write(root, state, new)
        return new


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "resume", "check", "audit"):
        commands.add_parser(name)
    export = commands.add_parser("export")
    export.add_argument("bundle", type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("bundle", type=Path)
    put = commands.add_parser("put")
    put.add_argument("record_json", type=Path)
    log = commands.add_parser("log")
    log.add_argument("--result", required=True, choices=("not_found", "blocked", "note"))
    log.add_argument("--scope", required=True)
    for command in (put, log):
        command.add_argument("--expected-revision", required=True, type=int)
        command.add_argument("--next-step", required=True)
    args = parser.parse_args(argv)
    try:
        root = private_workspace(args.workspace)
        if args.command == "init":
            initialize(root)
        elif args.command == "export":
            print(json.dumps(export_bundle(root, args.bundle), ensure_ascii=False, indent=2))
            return 0
        elif args.command == "restore":
            print(json.dumps(restore_bundle(root, args.bundle), ensure_ascii=False, indent=2))
            return 0
        elif args.command == "put":
            record = json.loads(args.record_json.read_text(encoding="utf-8"))
            update(root, args.expected_revision, record=record, next_step=args.next_step)
        elif args.command == "log":
            update(root, args.expected_revision, result=args.result, scope=args.scope, next_step=args.next_step)
        state = read_state(root)
        errors = check_state(state, root)
        if errors:
            raise ValueError("\n".join(errors))
        if args.command == "check":
            print(json.dumps({"valid": True, "revision": state["revision"], "records": len(state["records"])}))
        elif args.command == "audit":
            print(json.dumps(audit_state(state), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
