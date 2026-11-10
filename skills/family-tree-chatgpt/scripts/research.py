#!/usr/bin/env python3
"""Offline evidence notebook. One atomic JSON state; no archive or cloud access."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


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


def read_state(root):
    state = json.loads((root / "research.json").read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise ValueError("Nepodporovaný formát badatelského stavu.")
    if type(state.get("revision")) is not int or state["revision"] < 0:
        raise ValueError("Neplatná revize stavu.")
    if not isinstance(state.get("records"), dict) or not isinstance(state.get("events"), list) or not isinstance(state.get("next_step"), str):
        raise ValueError("Poškozená struktura stavu.")
    return state


def check_state(state, root):
    errors = []
    for key, record in state["records"].items():
        errors.extend(f"{key}: {e}" for e in validate_record(record, root, verify_hashes=True))
        if not isinstance(record, dict) or key != record.get("id"):
            errors.append(f"{key}: klíč se neshoduje s id zápisu.")
    return errors


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
        atomic_json(root / "research.json", {"schema_version": 1, "revision": 0, "records": {}, "events": [], "next_step": "Vybrat první zápis a doložit jeho pramen."})


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
        backup = root / "history" / f"revision-{state['revision']:06d}.json"
        # Exclusive backup creation: never silently replace a previous snapshot.
        if backup.exists():
            if json.loads(backup.read_text(encoding="utf-8")) != state:
                raise ValueError("Záloha revize už existuje s jiným obsahem.")
        else:
            with backup.open("x", encoding="utf-8") as stream:
                json.dump(state, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
        atomic_json(root / "research.json", new)
        return new


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "resume", "check"):
        commands.add_parser(name)
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
        else:
            print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
