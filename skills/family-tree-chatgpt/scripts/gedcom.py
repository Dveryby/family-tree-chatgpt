#!/usr/bin/env python3
"""Import GEDCOM claims into a private JSON file and create an evidence plan."""
import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


SCHEMA_VERSION = 1
MAX_INPUT_BYTES = 50 * 1024 * 1024
MAX_LINES = 1_000_000
MAX_ANCESTOR_GENERATIONS = 20
MAX_ANCESTOR_POSITIONS = 100_000
LINE_RE = re.compile(
    r"^(?P<level>[0-9]+)\s+(?:(?P<xref>@[^@\s]+@)\s+)?"
    r"(?P<tag>[A-Za-z0-9_]+)(?:\s(?P<value>.*))?$"
)
INDIVIDUAL_EVENTS = {
    "BIRT", "CHR", "BAPM", "DEAT", "BURI", "CREM", "ADOP", "MARR",
    "DIV", "EMIG", "IMMI", "NATU", "CENS", "RESI", "OCCU", "EDUC",
    "RELI", "EVEN", "FACT",
}
FAMILY_EVENTS = {"ANUL", "DIV", "DIVF", "ENGA", "MARB", "MARC", "MARL", "MARR", "MARS", "EVEN"}


class Node:
    def __init__(self, level, tag, value="", xref=None, line=0):
        self.level = level
        self.tag = tag
        self.value = value
        self.xref = xref
        self.line = line
        self.children = []


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def in_git_tree(path):
    path = Path(path).resolve()
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


def input_file(path):
    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise ValueError("GEDCOM vstup musí být běžný soubor, nikoli symlink.")
    path = candidate.resolve()
    if not path.is_file():
        raise ValueError("GEDCOM vstup musí být běžný soubor, nikoli symlink.")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("GEDCOM soubor překračuje limit 50 MiB.")
    return path


def output_file(path):
    candidate = Path(path).expanduser()
    if candidate.exists() or candidate.is_symlink():
        raise FileExistsError(f"Výstup už existuje: {candidate}")
    path = candidate.resolve()
    if not path.parent.is_dir():
        raise ValueError("Nadřazený adresář výstupu neexistuje.")
    if in_git_tree(path):
        raise ValueError("Importovaný rodokmen ulož mimo git repozitář.")
    return path


def decode_gedcom(raw):
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16"), "UNICODE"
    try:
        return raw.decode("utf-8-sig"), "UTF-8"
    except UnicodeDecodeError as exc:
        raise ValueError(
            "Soubor není platný UTF-8 ani Unicode s BOM. ANSEL zatím není podporován; "
            "exportuj GEDCOM znovu jako UTF-8."
        ) from exc


def parse_lines(text):
    roots = []
    stack = []
    warnings = []
    previous_level = None
    count = 0
    for number, raw_line in enumerate(text.splitlines(), 1):
        if not raw_line.strip():
            warnings.append(f"Řádek {number}: prázdný řádek byl přeskočen.")
            continue
        count += 1
        if count > MAX_LINES:
            raise ValueError("GEDCOM obsahuje příliš mnoho řádků.")
        match = LINE_RE.fullmatch(raw_line)
        if not match:
            raise ValueError(f"Řádek {number}: neplatná syntaxe GEDCOM.")
        level = int(match.group("level"))
        if level > 99:
            raise ValueError(f"Řádek {number}: nepodporovaná hloubka {level}.")
        if previous_level is None and level != 0:
            raise ValueError("První datový řádek GEDCOM musí mít úroveň 0.")
        if previous_level is not None and level > previous_level + 1:
            raise ValueError(f"Řádek {number}: úroveň přeskočila z {previous_level} na {level}.")
        if level > len(stack):
            raise ValueError(f"Řádek {number}: chybí nadřazený řádek úrovně {level - 1}.")
        node = Node(
            level=level,
            tag=match.group("tag").upper(),
            value=match.group("value") or "",
            xref=match.group("xref"),
            line=number,
        )
        if level == 0:
            roots.append(node)
        else:
            stack[level - 1].children.append(node)
        stack = stack[:level]
        stack.append(node)
        previous_level = level
    if not roots:
        raise ValueError("GEDCOM neobsahuje žádné záznamy.")
    return roots, warnings


def children(node, tag):
    if node is None:
        return []
    return [child for child in node.children if child.tag == tag]


def first(node, tag):
    found = children(node, tag)
    return found[0] if found else None


def text(node):
    if node is None:
        return ""
    value = node.value
    for child in node.children:
        if child.tag == "CONC":
            value += text(child)
        elif child.tag == "CONT":
            value += "\n" + text(child)
    return value


def pointer(value):
    return value if re.fullmatch(r"@[^@\s]+@", value or "") else ""


def serialize_node(node):
    result = {"tag": node.tag, "value": text(node), "line": node.line}
    if node.xref:
        result["xref"] = node.xref
    nested = [serialize_node(child) for child in node.children if child.tag not in ("CONT", "CONC")]
    if nested:
        result["children"] = nested
    return result


def notes(node):
    return [text(item) for item in children(node, "NOTE") if text(item)]


def citations(node):
    result = []
    for item in children(node, "SOUR"):
        source_id = pointer(item.value)
        citation = {
            "source_id": source_id,
            "description": "" if source_id else text(item),
            "page": text(first(item, "PAGE")),
            "text": "",
            "quality": text(first(item, "QUAY")),
        }
        data = first(item, "DATA")
        if data:
            citation["text"] = "\n".join(text(value) for value in children(data, "TEXT") if text(value))
        result.append(citation)
    return result


def event(node):
    known = {"TYPE", "DATE", "PLAC", "ADDR", "AGE", "CAUS", "SOUR", "NOTE", "OBJE"}
    return {
        "tag": node.tag,
        "type": text(first(node, "TYPE")),
        "value": node.value,
        "date": text(first(node, "DATE")),
        "place": text(first(node, "PLAC")),
        "address": text(first(node, "ADDR")),
        "age": text(first(node, "AGE")),
        "cause": text(first(node, "CAUS")),
        "sources": citations(node),
        "notes": notes(node),
        "extensions": [serialize_node(child) for child in node.children if child.tag not in known],
        "evidence_status": "unverified",
    }


def personal_name(node):
    raw = text(node)
    match = re.fullmatch(r"(.*?)\s*/(.*?)/(.*)", raw)
    derived_given = match.group(1).strip() if match else raw.strip()
    derived_surname = match.group(2).strip() if match else ""
    derived_suffix = match.group(3).strip() if match else ""
    return {
        "raw": raw,
        "type": text(first(node, "TYPE")),
        "prefix": text(first(node, "NPFX")),
        "given": text(first(node, "GIVN")) or derived_given,
        "surname_prefix": text(first(node, "SPFX")),
        "surname": text(first(node, "SURN")) or derived_surname,
        "suffix": text(first(node, "NSFX")) or derived_suffix,
        "nickname": text(first(node, "NICK")),
    }


def individual(node):
    known = INDIVIDUAL_EVENTS | {"NAME", "SEX", "FAMC", "FAMS", "SOUR", "NOTE", "OBJE", "CHAN", "REFN", "RIN", "RFN", "AFN", "RESN", "ALIA", "ASSO", "ANCI", "DESI", "SUBM"}
    return {
        "id": node.xref,
        "names": [personal_name(item) for item in children(node, "NAME")],
        "sex": text(first(node, "SEX")),
        "family_child": [item.value for item in children(node, "FAMC")],
        "family_spouse": [item.value for item in children(node, "FAMS")],
        "events": [event(item) for item in node.children if item.tag in INDIVIDUAL_EVENTS],
        "sources": citations(node),
        "notes": notes(node),
        "extensions": [serialize_node(child) for child in node.children if child.tag not in known],
        "evidence_status": "unverified",
    }


def family(node):
    known = FAMILY_EVENTS | {"HUSB", "WIFE", "CHIL", "SOUR", "NOTE", "OBJE", "CHAN", "REFN", "RIN", "RESN", "SUBM"}
    return {
        "id": node.xref,
        "husband": text(first(node, "HUSB")),
        "wife": text(first(node, "WIFE")),
        "children": [item.value for item in children(node, "CHIL")],
        "events": [event(item) for item in node.children if item.tag in FAMILY_EVENTS],
        "sources": citations(node),
        "notes": notes(node),
        "extensions": [serialize_node(child) for child in node.children if child.tag not in known],
        "evidence_status": "unverified",
    }


def source_record(node):
    repository = first(node, "REPO")
    return {
        "id": node.xref,
        "title": text(first(node, "TITL")),
        "author": text(first(node, "AUTH")),
        "publication": text(first(node, "PUBL")),
        "abbreviation": text(first(node, "ABBR")),
        "repository_id": pointer(repository.value) if repository else "",
        "repository_text": "" if repository is None or pointer(repository.value) else text(repository),
        "notes": notes(node),
        "evidence_status": "unverified",
    }


def header(roots, decoded_as):
    heads = [node for node in roots if node.tag == "HEAD"]
    trailers = [node for node in roots if node.tag == "TRLR"]
    if len(heads) != 1 or len(trailers) != 1:
        raise ValueError("GEDCOM musí obsahovat právě jeden HEAD a jeden TRLR záznam.")
    if roots[0].tag != "HEAD" or roots[-1].tag != "TRLR":
        raise ValueError("HEAD musí být první a TRLR poslední záznam GEDCOMu.")
    head = heads[0]
    gedc = first(head, "GEDC")
    source = first(head, "SOUR")
    declared = text(first(head, "CHAR")).upper()
    if declared and declared not in ("UTF-8", "UTF8", "ASCII", "UNICODE"):
        raise ValueError(
            f"Deklarované kódování {declared} není podporováno; exportuj GEDCOM jako UTF-8."
        )
    return {
        "gedcom_version": text(first(gedc, "VERS")),
        "form": text(first(gedc, "FORM")),
        "declared_character_set": declared,
        "decoded_as": decoded_as,
        "source_system": text(source),
        "source_version": text(first(source, "VERS")),
    }


def valid_citation(citation, source_ids):
    if citation["source_id"]:
        return citation["source_id"] in source_ids
    return bool(citation["description"].strip())


def label(person):
    if person["names"]:
        return person["names"][0]["raw"] or person["id"]
    return person["id"]


def evidence_plan(persons, families, source_ids):
    plan = []
    for person in persons:
        start_events = [item for item in person["events"] if item["tag"] in ("BIRT", "CHR", "BAPM")]
        if not start_events:
            plan.append({
                "subject_type": "person",
                "subject_id": person["id"],
                "subject_label": label(person),
                "event": "BIRT_OR_CHR",
                "issue": "missing_event",
                "priority": "high",
                "suggested_action": "Dohledat narození nebo křest a zapsat přesnou archivní citaci.",
            })
        for item in person["events"]:
            if not any(valid_citation(citation, source_ids) for citation in item["sources"]):
                plan.append({
                    "subject_type": "person",
                    "subject_id": person["id"],
                    "subject_label": label(person),
                    "event": item["tag"],
                    "issue": "missing_source",
                    "priority": "high" if item["tag"] in ("BIRT", "CHR", "BAPM", "DEAT", "MARR") else "normal",
                    "suggested_action": "Ověřit tvrzení v původním prameni a doplnit přesnou citaci.",
                })
    for item in families:
        for family_event in item["events"]:
            if not any(valid_citation(citation, source_ids) for citation in family_event["sources"]):
                plan.append({
                    "subject_type": "family",
                    "subject_id": item["id"],
                    "subject_label": item["id"],
                    "event": family_event["tag"],
                    "issue": "missing_source",
                    "priority": "high" if family_event["tag"] == "MARR" else "normal",
                    "suggested_action": "Ověřit rodinnou událost v původním prameni a doplnit přesnou citaci.",
                })
    return plan


def event_year(value):
    years = [int(item) for item in re.findall(r"(?<!\d)(\d{3,4})(?!\d)", value or "")]
    return max(years) if years else -1


def research_anchor(person, families_by_id):
    """Choose a late-life claim with a place as a starting point, never as proof."""
    candidates = list(person["events"])
    for family_id in person["family_spouse"]:
        family_item = families_by_id.get(family_id)
        if family_item:
            candidates.extend(family_item["events"])
    for tag in ("DEAT", "BURI", "MARR", "BIRT", "CHR", "BAPM"):
        matching = [item for item in candidates if item["tag"] == tag and item["place"].strip()]
        if matching:
            selected = max(matching, key=lambda item: event_year(item["date"]))
            return {
                "event": selected["tag"],
                "date_claim": selected["date"],
                "place_claim": selected["place"],
                "evidence_status": "unverified",
                "suggested_action": (
                    "Začít ověřením tohoto pozdního známého údaje v původním prameni; "
                    "teprve potom postupovat ke starší generaci."
                ),
            }
    return {
        "event": "UNKNOWN",
        "date_claim": "",
        "place_claim": "",
        "evidence_status": "unverified",
        "suggested_action": "Nejprve zjistit konkrétní událost a místo z doložitelného pramene.",
    }


def ancestor_research(data, root_id, max_generations=12):
    """Build an Ahnentafel queue from imported claims without asserting relationships."""
    if type(max_generations) is not int or not 1 <= max_generations <= MAX_ANCESTOR_GENERATIONS:
        raise ValueError(f"Počet generací musí být 1–{MAX_ANCESTOR_GENERATIONS}.")
    persons_by_id = {item["id"]: item for item in data["persons"]}
    families_by_id = {item["id"]: item for item in data["families"]}
    if root_id not in persons_by_id:
        raise ValueError(f"Výchozí osoba {root_id} v GEDCOMu není.")
    queue = deque([(1, root_id, (root_id,))])
    positions = []
    warnings = []
    by_person = {}
    while queue:
        if len(positions) >= MAX_ANCESTOR_POSITIONS:
            raise ValueError(
                f"Fronta předků překročila {MAX_ANCESTOR_POSITIONS} pozic; sniž --max-generations."
            )
        number, person_id, path = queue.popleft()
        person = persons_by_id[person_id]
        generation = number.bit_length()
        positions.append({
            "ahnentafel": number,
            "generation": generation,
            "person_id": person_id,
            "person_label": label(person),
            "relationship_status": "unverified_claim",
            "research_anchor": research_anchor(person, families_by_id),
        })
        by_person.setdefault(person_id, []).append(number)
        if generation >= max_generations:
            continue
        parent_families = person["family_child"]
        if len(parent_families) > 1:
            warnings.append(
                f"{person_id}: více FAMC rodin ({', '.join(parent_families)}); "
                "bez informace o typu rodičovství nelze automaticky vybrat jednu."
            )
            continue
        if not parent_families:
            continue
        family_id = parent_families[0]
        family_item = families_by_id.get(family_id)
        if not family_item:
            warnings.append(f"{person_id}: rodičovská rodina {family_id} chybí; větev nebyla rozvinuta.")
            continue
        if person_id not in family_item["children"]:
            warnings.append(
                f"{person_id}: uvádí FAMC {family_id}, ale rodina osobu neuvádí jako CHIL; "
                "větev nebyla rozvinuta."
            )
            continue
        for parent_number, role in ((number * 2, "husband"), (number * 2 + 1, "wife")):
            parent_id = family_item[role]
            if not parent_id:
                continue
            if parent_id not in persons_by_id:
                warnings.append(f"{family_id}: odkaz na chybějící osobu {parent_id}; větev nebyla rozvinuta.")
                continue
            if parent_id in path:
                warnings.append(
                    f"{family_id}: cyklus {person_id} → {parent_id}; větev byla zastavena."
                )
                continue
            queue.append((parent_number, parent_id, (*path, parent_id)))
    repeated = [
        {"person_id": person_id, "ahnentafel_positions": numbers}
        for person_id, numbers in sorted(by_person.items()) if len(numbers) > 1
    ]
    return {
        "root_id": root_id,
        "max_generations": max_generations,
        "data_status": "unverified_claims",
        "positions": positions,
        "pedigree_collapse": repeated,
        "warnings": warnings,
    }


def cross_reference_warnings(persons, families, sources):
    warnings = []
    persons_by_id = {item["id"]: item for item in persons}
    families_by_id = {item["id"]: item for item in families}
    person_ids = set(persons_by_id)
    family_ids = set(families_by_id)
    source_ids = {item["id"] for item in sources}
    for person in persons:
        if not person["names"]:
            warnings.append(f"{person['id']}: osoba nemá NAME.")
        if person["sex"] and person["sex"] not in ("M", "F", "U", "X"):
            warnings.append(f"{person['id']}: neznámá hodnota SEX {person['sex']!r}.")
        for family_id in person["family_child"]:
            if family_id not in family_ids:
                warnings.append(f"{person['id']}: odkaz na chybějící rodinu {family_id}.")
            elif person["id"] not in families_by_id[family_id]["children"]:
                warnings.append(f"{person['id']}: FAMC {family_id} nemá zpětný odkaz CHIL.")
        for family_id in person["family_spouse"]:
            if family_id not in family_ids:
                warnings.append(f"{person['id']}: odkaz na chybějící rodinu {family_id}.")
            elif person["id"] not in (families_by_id[family_id]["husband"], families_by_id[family_id]["wife"]):
                warnings.append(f"{person['id']}: FAMS {family_id} nemá zpětný odkaz HUSB/WIFE.")
    for item in families:
        for role in ("husband", "wife"):
            if item[role] and item[role] not in person_ids:
                warnings.append(f"{item['id']}: odkaz na chybějící osobu {item[role]}.")
            elif item[role] and item["id"] not in persons_by_id[item[role]]["family_spouse"]:
                warnings.append(f"{item['id']}: {role} {item[role]} nemá zpětný odkaz FAMS.")
        for child_id in item["children"]:
            if child_id not in person_ids:
                warnings.append(f"{item['id']}: odkaz na chybějící dítě {child_id}.")
            elif item["id"] not in persons_by_id[child_id]["family_child"]:
                warnings.append(f"{item['id']}: dítě {child_id} nemá zpětný odkaz FAMC.")
    for owner in [*persons, *families]:
        for citation in owner["sources"]:
            if citation["source_id"] and citation["source_id"] not in source_ids:
                warnings.append(f"{owner['id']}: odkaz na chybějící pramen {citation['source_id']}.")
        for item in owner["events"]:
            for citation in item["sources"]:
                if citation["source_id"] and citation["source_id"] not in source_ids:
                    warnings.append(f"{owner['id']} {item['tag']}: odkaz na chybějící pramen {citation['source_id']}.")
    return warnings


def build_import(path):
    path = input_file(path)
    raw = path.read_bytes()
    decoded, decoded_as = decode_gedcom(raw)
    roots, warnings = parse_lines(decoded)
    metadata = header(roots, decoded_as)
    version = metadata["gedcom_version"]
    if not version:
        warnings.append("HEAD neobsahuje deklarovanou verzi GEDCOMu.")
    elif version not in ("5.5", "5.5.1") and not version.startswith("7."):
        warnings.append(f"Verze GEDCOM {version} nebyla cíleně otestována.")
    indexed = {}
    for node in roots:
        if node.xref:
            if node.xref in indexed:
                raise ValueError(f"Duplicitní cross-reference {node.xref} na řádku {node.line}.")
            indexed[node.xref] = node
    persons = []
    families = []
    sources = []
    other_records = []
    for node in roots:
        if node.tag in ("INDI", "FAM", "SOUR") and not node.xref:
            raise ValueError(f"Řádek {node.line}: záznam {node.tag} nemá cross-reference identifikátor.")
        if node.tag == "INDI":
            persons.append(individual(node))
        elif node.tag == "FAM":
            families.append(family(node))
        elif node.tag == "SOUR":
            sources.append(source_record(node))
        elif node.tag not in ("HEAD", "TRLR"):
            other_records.append(serialize_node(node))
    warnings.extend(cross_reference_warnings(persons, families, sources))
    source_ids = {item["id"] for item in sources}
    return {
        "schema_version": SCHEMA_VERSION,
        "imported_at": utc_now(),
        "source": {
            "file_name": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            **metadata,
        },
        "data_status": "unverified_claims",
        "persons": persons,
        "families": families,
        "sources": sources,
        "other_records": other_records,
        "warnings": warnings,
        "research_plan": evidence_plan(persons, families, source_ids),
    }


def atomic_output(path, data):
    path = output_file(path)
    temporary = None
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Výstup už existuje: {path}")
        os.link(temporary, path)
        path.chmod(0o600)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gedcom", type=Path, help="soukromý vstupní soubor .ged")
    parser.add_argument("output", type=Path, help="nový soukromý JSON výstup mimo Git")
    parser.add_argument("--root", help="GEDCOM ID výchozí osoby, např. @I1@; přidá frontu předků")
    parser.add_argument("--max-generations", type=int, default=12, help="hloubka fronty předků, výchozí 12")
    args = parser.parse_args(argv)
    try:
        result = build_import(args.gedcom)
        if args.root:
            result["ancestor_research"] = ancestor_research(result, args.root, args.max_generations)
        output = atomic_output(args.output, result)
        summary = {
            "imported": True,
            "output": str(output),
            "source_sha256": result["source"]["sha256"],
            "persons": len(result["persons"]),
            "families": len(result["families"]),
            "sources": len(result["sources"]),
            "warnings": len(result["warnings"]),
            "plan_items": len(result["research_plan"]),
        }
        if "ancestor_research" in result:
            summary["ancestor_positions"] = len(result["ancestor_research"]["positions"])
            summary["ancestor_warnings"] = len(result["ancestor_research"]["warnings"])
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
