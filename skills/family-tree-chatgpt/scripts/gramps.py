#!/usr/bin/env python3
"""Conservative Gramps Web API adapter for the evidence model."""
from datetime import date, datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


PLAN_SCHEMA_VERSION = 1
TASK_PLAN_SCHEMA_VERSION = 1
SUPPORTED_API_MAJOR = 3
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_OBJECTS = 5_000
MAX_TASKS = 500
MAX_TASK_TITLE_LENGTH = 500
MAX_TASK_DESCRIPTION_LENGTH = 50_000
TASK_PRIORITIES = {"high": "1", "medium": "5", "low": "9"}
TASK_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
ENDPOINTS = {
    "Repository": "repositories",
    "Source": "sources",
    "Citation": "citations",
    "Note": "notes",
    "Event": "events",
    "Person": "people",
    "Family": "families",
}
CLASS_ORDER = {name: index for index, name in enumerate(ENDPOINTS)}
GRAMPS_ID_PREFIX = {
    "Repository": "R",
    "Source": "S",
    "Citation": "C",
    "Note": "N",
    "Event": "E",
    "Person": "I",
    "Family": "F",
}
DATE_EVENTS = {
    "birth.date": "Birth",
    "baptism.date": "Baptism",
    "death.date": "Death",
    "burial.date": "Burial",
}
SEX_VALUES = {
    "f": 0,
    "female": 0,
    "žena": 0,
    "m": 1,
    "male": 1,
    "muž": 1,
    "u": 2,
    "unknown": 2,
    "neznámé": 2,
}


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_handle(object_class, local_key):
    value = f"family-tree-chatgpt:v1\0{object_class}\0{local_key}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:32]


def stable_gramps_id(object_class, local_key):
    short = hashlib.sha256(local_key.encode("utf-8")).hexdigest()[:12].upper()
    return f"FT{GRAMPS_ID_PREFIX[object_class]}-{short}"


def marker(local_key):
    return {
        "type": "FamilyTreeChatGPT ID",
        "value": local_key,
        "private": True,
    }


def normalize_url(value, allow_http=False):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Gramps Web URL nesmí být prázdné.")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise ValueError("Gramps Web URL musí být úplná HTTP(S) adresa.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Gramps Web URL nesmí obsahovat přihlašovací údaje, dotaz ani fragment.")
    if parsed.scheme != "https" and not allow_http:
        raise ValueError("Nešifrované HTTP je zakázané; pro izolovaný test použij --allow-http.")
    path = parsed.path.rstrip("/")
    if not path.endswith("/api"):
        path += "/api"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ApiError(ValueError):
    def __init__(self, status, detail=""):
        suffix = f": {detail[:500]}" if detail else ""
        super().__init__(f"Gramps Web API vrátilo HTTP {status}{suffix}")
        self.status = status


class Client:
    def __init__(self, base_url, token=None, timeout=20, allow_http=False):
        self.base_url = normalize_url(base_url, allow_http=allow_http)
        if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 120:
            raise ValueError("Síťový timeout musí být v rozsahu 0–120 sekund.")
        self.timeout = timeout
        self.token = token
        self.opener = build_opener(_NoRedirect())

    def request(
        self,
        method,
        path,
        payload=None,
        expected=(200,),
        authenticated=True,
        trailing_slash=True,
    ):
        body = None if payload is None else canonical(payload)
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if authenticated:
            if not self.token:
                raise ValueError("Chybí přístupový token Gramps Web.")
            headers["Authorization"] = f"Bearer {self.token}"
        endpoint = path.strip("/")
        route, separator, query = endpoint.partition("?")
        suffix = "/" if trailing_slash else ""
        url = f"{self.base_url}/{route}{suffix}"
        if separator:
            url += f"?{query}"
        request = Request(
            url, data=body, headers=headers, method=method
        )
        try:
            response = self.opener.open(request, timeout=self.timeout)
            status = response.status
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raw = exc.read(16_385)
            detail = ""
            try:
                decoded = json.loads(raw.decode("utf-8"))
                if isinstance(decoded, dict):
                    detail = str(decoded.get("message") or decoded.get("error") or "")
            except (UnicodeError, json.JSONDecodeError):
                pass
            raise ApiError(exc.code, detail) from None
        except URLError as exc:
            raise ValueError(f"Gramps Web API není dostupné: {exc.reason}") from None
        if status not in expected:
            raise ValueError(f"Gramps Web API vrátilo neočekávané HTTP {status}.")
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("Odpověď Gramps Web API překročila bezpečnostní limit.")
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Gramps Web API vrátilo neplatný JSON.") from exc

    def login(self, username, password):
        if not username or not password:
            raise ValueError("Pro přihlášení je nutné uživatelské jméno a heslo.")
        result = self.request(
            "POST", "token", {"username": username, "password": password}, authenticated=False
        )
        token = result.get("access_token") if isinstance(result, dict) else None
        if not isinstance(token, str) or not token:
            raise ValueError("Přihlášení nevrátilo přístupový token.")
        self.token = token

    def metadata(self):
        result = self.request("GET", "metadata")
        if not isinstance(result, dict):
            raise ValueError("Metadata Gramps Web mají neplatný formát.")
        return result

    def get_optional(self, object_class, handle):
        endpoint = ENDPOINTS[object_class]
        try:
            result = self.request(
                "GET", f"{endpoint}/{handle}", trailing_slash=False
            )
        except ApiError as exc:
            if exc.status == 404:
                return None
            raise
        if not isinstance(result, dict):
            raise ValueError(f"Gramps Web vrátilo neplatný objekt {object_class}.")
        return result

    def create_objects(self, payloads):
        if payloads:
            self.request("POST", "objects", payloads, expected=(201,))

    def list_tags(self):
        result = self.request("GET", "tags?pagesize=500")
        if not isinstance(result, list) or not all(isinstance(tag, dict) for tag in result):
            raise ValueError("Gramps Web vrátilo neplatný seznam tagů.")
        return result

    def create_tag(self, handle, name):
        if not isinstance(handle, str) or not handle or not isinstance(name, str) or not name:
            raise ValueError("Nový Gramps tag musí mít handle a název.")
        result = self.request(
            "POST", "tags", {"handle": handle, "name": name}, expected=(201,)
        )
        return result


def authenticate(client, username=None, password_env="GRAMPS_WEB_PASSWORD", token_env="GRAMPS_WEB_TOKEN"):
    token = os.environ.get(token_env, "") if token_env else ""
    if token:
        client.token = token
        return "token"
    if not username:
        raise ValueError(f"Nastav {token_env} nebo zadej --username.")
    password = os.environ.get(password_env, "") if password_env else ""
    if not password:
        if not os.isatty(0):
            raise ValueError(f"Heslo chybí; nastav ho do proměnné {password_env}.")
        password = getpass.getpass("Gramps Web heslo: ")
    client.login(username, password)
    return "password"


def api_version(metadata):
    value = metadata.get("gramps_webapi", {}).get("version", "")
    if not isinstance(value, str):
        return ""
    return value


def compatible(metadata):
    match = re.match(r"(\d+)", api_version(metadata))
    return bool(match and int(match.group(1)) == SUPPORTED_API_MAJOR)


def probe(client):
    metadata = client.metadata()
    database = metadata.get("database", {})
    gramps = metadata.get("gramps", {})
    server = metadata.get("server", {})
    return {
        "connected": True,
        "base_url": client.base_url,
        "compatible": compatible(metadata),
        "supported_api_major": SUPPORTED_API_MAJOR,
        "api_version": api_version(metadata),
        "gramps_version": gramps.get("version", ""),
        "database": {
            "id": database.get("id", ""),
            "name": database.get("name", ""),
            "schema": database.get("schema", ""),
        },
        "object_counts": metadata.get("object_counts", {}),
        "server": {
            "multi_tree": bool(server.get("multi_tree", False)),
            "task_queue": bool(server.get("task_queue", False)),
        },
    }


def _todo_tags(tags):
    return [tag for tag in tags if tag.get("name") == "ToDo"]


def tasks_probe(client):
    result = probe(client)
    tags = client.list_tags()
    matches = _todo_tags(tags)
    if len(matches) == 0:
        state = "missing"
    elif len(matches) == 1 and isinstance(matches[0].get("handle"), str):
        state = "ready"
    else:
        state = "ambiguous"
    result["tasks"] = {
        "supported": result["compatible"],
        "todo_tag": {
            "status": state,
            "count": len(matches),
            "handles": sorted(
                tag["handle"] for tag in matches if isinstance(tag.get("handle"), str)
            ),
        },
        "plan_ready": result["compatible"] and state != "ambiguous",
    }
    return result


def validate_task_input(value):
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("Vstup úkolů musí být objekt se schema_version 1.")
    if set(value) != {"schema_version", "tasks"} or not isinstance(value["tasks"], list):
        raise ValueError("Vstup úkolů smí obsahovat pouze schema_version a seznam tasks.")
    if not value["tasks"]:
        raise ValueError("Vstup úkolů nesmí být prázdný.")
    if len(value["tasks"]) > MAX_TASKS:
        raise ValueError(f"Jeden plán smí obsahovat nejvýše {MAX_TASKS} úkolů.")
    normalized = []
    identifiers = set()
    allowed = {"id", "title", "description", "priority"}
    for index, task in enumerate(value["tasks"], start=1):
        if not isinstance(task, dict) or not set(task).issubset(allowed):
            raise ValueError(f"Úkol {index} obsahuje neznámé pole nebo není objekt.")
        identifier = task.get("id")
        title = task.get("title")
        description = task.get("description", "")
        priority = task.get("priority", "medium")
        if not isinstance(identifier, str) or not TASK_ID_PATTERN.fullmatch(identifier):
            raise ValueError(
                f"Úkol {index} musí mít stabilní id dlouhé 1–128 znaků bez mezer."
            )
        if identifier in identifiers:
            raise ValueError(f"Duplicitní ID úkolu: {identifier}")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Úkol {identifier} musí mít neprázdný titul.")
        title = title.strip()
        if len(title) > MAX_TASK_TITLE_LENGTH:
            raise ValueError(f"Titul úkolu {identifier} je příliš dlouhý.")
        if not isinstance(description, str):
            raise ValueError(f"Popis úkolu {identifier} musí být text.")
        description = description.strip()
        if len(description) > MAX_TASK_DESCRIPTION_LENGTH:
            raise ValueError(f"Popis úkolu {identifier} je příliš dlouhý.")
        if priority not in TASK_PRIORITIES:
            raise ValueError(
                f"Priorita úkolu {identifier} musí být high, medium nebo low."
            )
        identifiers.add(identifier)
        normalized.append(
            {
                "id": identifier,
                "title": title,
                "description": description,
                "priority": priority,
            }
        )
    return {"schema_version": 1, "tasks": normalized}


def build_task_objects(task_input, todo_handle):
    task_input = validate_task_input(task_input)
    if not isinstance(todo_handle, str) or not todo_handle:
        raise ValueError("Pro Gramps úkoly chybí handle tagu ToDo.")
    objects = []
    for task in task_input["tasks"]:
        local_key = f"task:{task['id']}"
        source_handle = stable_handle("Source", local_key)
        note_handle = stable_handle("Note", f"{local_key}:description")
        note_list = [note_handle] if task["description"] else []
        source = {
            "_class": "Source",
            "handle": source_handle,
            "gramps_id": stable_gramps_id("Source", local_key),
            "private": True,
            "title": task["title"],
            "author": "",
            "abbrev": "Research task",
            "pubinfo": "",
            "attribute_list": [
                marker(local_key),
                {"_class": "SrcAttribute", "type": "Status", "value": "Open"},
                {
                    "_class": "SrcAttribute",
                    "type": "Priority",
                    "value": TASK_PRIORITIES[task["priority"]],
                },
            ],
            "reporef_list": [],
            "media_list": [],
            "note_list": note_list,
            "tag_list": [todo_handle],
        }
        objects.append(
            {
                "object_class": "Source",
                "endpoint": ENDPOINTS["Source"],
                "local_key": local_key,
                "task_id": task["id"],
                "payload": source,
            }
        )
        if task["description"]:
            note = {
                "_class": "Note",
                "handle": note_handle,
                "gramps_id": stable_gramps_id("Note", f"{local_key}:description"),
                "private": True,
                "type": "To Do",
                "text": {
                    "_class": "StyledText",
                    "string": task["description"],
                    "tags": [],
                },
                "tag_list": [todo_handle],
            }
            objects.append(
                {
                    "object_class": "Note",
                    "endpoint": ENDPOINTS["Note"],
                    "local_key": f"{local_key}:description",
                    "task_id": task["id"],
                    "payload": note,
                }
            )
    return {
        "task_input": task_input,
        "objects": sorted(
            objects,
            key=lambda item: (CLASS_ORDER[item["object_class"]], item["local_key"]),
        ),
    }


def _eligible_claims(state):
    excluded = {}
    conflicts_by_claim = {}
    for conflict in state["conflicts"].values():
        for claim_id in conflict["claim_ids"]:
            conflicts_by_claim.setdefault(claim_id, []).append(conflict)
    eligible = {}
    for claim_id, claim in state["claims"].items():
        if claim["status"] != "supported":
            excluded[claim_id] = f"status_{claim['status']}"
            continue
        reason = None
        for conflict in conflicts_by_claim.get(claim_id, []):
            if conflict["status"] == "open":
                reason = f"open_conflict:{conflict['id']}"
                break
            preferred = conflict["resolution"]["preferred_claim_ids"]
            if claim_id not in preferred:
                reason = f"not_preferred:{conflict['id']}"
                break
        if reason:
            excluded[claim_id] = reason
        else:
            eligible[claim_id] = claim
    return eligible, excluded


def _claim_note(claim_id, claim):
    lines = [
        "FamilyTreeChatGPT supported claim",
        f"ID: {claim_id}",
        f"Predicate: {claim['predicate']}",
        f"Value: {json.dumps(claim['value'], ensure_ascii=False, sort_keys=True)}",
        f"Rationale: {claim['rationale']}",
    ]
    if claim["notes"]:
        lines.append(f"Notes: {claim['notes']}")
    for index, citation in enumerate(claim["citations"], start=1):
        lines.append(
            f"Citation {index}: source={citation['source_id']}; locator={citation['locator']}"
        )
        if citation["quotation"]:
            lines.append(f"Quotation {index}: {citation['quotation']}")
        if citation["note"]:
            lines.append(f"Citation note {index}: {citation['note']}")
    return "\n".join(lines)


def _date_value(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", value)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2) or 0)
    day = int(match.group(3) or 0)
    if not 1 <= year <= 9999 or not 0 <= month <= 12 or not 0 <= day <= 31:
        return None
    if day and not month:
        return None
    if month and day:
        try:
            date(year, month, day)
        except ValueError:
            return None
    return {
        "calendar": 0,
        "modifier": 0,
        "quality": 0,
        "dateval": [day, month, year, False],
        "text": "",
    }


def _unique_claim(claims, predicates, warnings, subject_id, label):
    selected = [item for item in claims if item[1]["predicate"] in predicates]
    values = {canonical(item[1]["value"]) for item in selected}
    if len(values) > 1:
        warnings.append({
            "code": "ambiguous_structured_value",
            "subject_id": subject_id,
            "field": label,
            "claim_ids": [item[0] for item in selected],
            "message": "Více podporovaných hodnot nemá vyřešený konflikt; do strukturovaného pole se nepřenese žádná.",
        })
        return None
    return selected[0] if selected else None


def build_objects(state):
    if state.get("schema_version") != 2:
        raise ValueError("Gramps export vyžaduje badatelský stav formátu 2.")
    eligible, excluded = _eligible_claims(state)
    warnings = []
    objects = {}

    def add(object_class, local_key, payload):
        handle = stable_handle(object_class, local_key)
        if handle in objects:
            raise ValueError("Interní kolize stabilních Gramps identifikátorů.")
        complete = {
            "_class": object_class,
            "handle": handle,
            "gramps_id": stable_gramps_id(object_class, local_key),
            "private": True,
            **payload,
        }
        objects[handle] = {
            "object_class": object_class,
            "endpoint": ENDPOINTS[object_class],
            "local_key": local_key,
            "payload": complete,
        }
        return handle

    claims_by_subject = {}
    for claim_id, claim in eligible.items():
        subject = (claim["subject"]["type"], claim["subject"]["id"])
        claims_by_subject.setdefault(subject, []).append((claim_id, claim))

    used_source_ids = {
        citation["source_id"]
        for claim in eligible.values()
        for citation in claim["citations"]
    }
    repository_handles = {}
    source_handles = {}
    for source_id in sorted(used_source_ids):
        source = state["sources"][source_id]
        repo_refs = []
        if source["repository"]:
            repo_key = source["repository"].strip()
            if repo_key not in repository_handles:
                repository_handles[repo_key] = add(
                    "Repository",
                    f"repository:{repo_key}",
                    {
                        "name": repo_key,
                        "type": "Archive",
                        "urls": [],
                        "note_list": [],
                        "tag_list": [],
                    },
                )
            repo_refs.append({
                "ref": repository_handles[repo_key],
                "call_number": source["citation"],
                "media_type": "Digital",
                "private": True,
                "note_list": [],
            })
        attributes = [marker(f"source:{source_id}")]
        if source["url"]:
            attributes.append({
                "type": "FamilyTreeChatGPT URL",
                "value": source["url"],
                "private": True,
            })
        if source["files"]:
            warnings.append({
                "code": "source_files_not_uploaded",
                "source_id": source_id,
                "message": "První verze adaptéru nepřenáší soubory; v Gramps zůstane pouze pramen a citace.",
            })
        source_handles[source_id] = add(
            "Source",
            f"source:{source_id}",
            {
                "title": source["title"],
                "abbrev": source["kind"],
                "author": "",
                "pubinfo": source["citation"],
                "attribute_list": attributes,
                "reporef_list": repo_refs,
                "media_list": [],
                "note_list": [],
                "tag_list": [],
            },
        )

    claim_citations = {}
    claim_notes = {}
    for claim_id in sorted(eligible):
        claim = eligible[claim_id]
        handles = []
        for index, citation in enumerate(claim["citations"]):
            local_key = f"citation:{claim_id}:{index}"
            handles.append(add(
                "Citation",
                local_key,
                {
                    "source_handle": source_handles[citation["source_id"]],
                    "page": citation["locator"],
                    "attribute_list": [marker(local_key)],
                    "media_list": [],
                    "note_list": [],
                    "tag_list": [],
                },
            ))
        claim_citations[claim_id] = handles
        note_key = f"claim:{claim_id}"
        claim_notes[claim_id] = add(
            "Note",
            note_key,
            {
                "format": 0,
                "type": "Research",
                "text": {"string": _claim_note(claim_id, claim), "tags": []},
                "tag_list": [],
            },
        )

    people_to_export = {
        subject_id
        for subject_type, subject_id in claims_by_subject
        if subject_type == "person"
    }
    for (subject_type, relationship_id), subject_claims in claims_by_subject.items():
        if subject_type != "relationship":
            continue
        for participant in state["relationships"][relationship_id]["participants"]:
            people_to_export.add(participant["person_id"])

    person_parts = {}
    person_handles = {}
    for person_id in sorted(people_to_export):
        subject_claims = claims_by_subject.get(("person", person_id), [])
        given = _unique_claim(subject_claims, {"name.given"}, warnings, person_id, "name.given")
        surname = _unique_claim(subject_claims, {"name.surname"}, warnings, person_id, "name.surname")
        sex = _unique_claim(subject_claims, {"sex", "person.sex"}, warnings, person_id, "sex")
        gender = None
        if sex:
            value = str(sex[1]["value"]).strip().casefold()
            gender = SEX_VALUES.get(value)
            if gender is None:
                warnings.append({
                    "code": "unsupported_sex_value",
                    "person_id": person_id,
                    "claim_id": sex[0],
                    "message": "Podporované tvrzení o pohlaví nemá hodnotu M/F/U ani rozpoznaný text; pole se nepřenese.",
                })
        primary_name = None
        name_claims = [item for item in (given, surname) if item]
        if name_claims:
            primary_name = {
                "first_name": str(given[1]["value"]) if given else "",
                "surname_list": ([{
                    "surname": str(surname[1]["value"]),
                    "prefix": "",
                    "connector": "",
                    "primary": True,
                }] if surname else []),
                "type": "Unknown",
                "citation_list": sorted({
                    handle for claim_id, _ in name_claims for handle in claim_citations[claim_id]
                }),
                "note_list": [claim_notes[claim_id] for claim_id, _ in name_claims],
                "private": True,
            }
        direct_note_handles = [claim_notes[claim_id] for claim_id, _ in subject_claims]
        direct_citations = sorted({
            handle for claim_id, _ in subject_claims for handle in claim_citations[claim_id]
        })
        event_refs = []
        birth_index = None
        death_index = None
        for claim_id, claim in subject_claims:
            event_type = DATE_EVENTS.get(claim["predicate"])
            if not event_type:
                continue
            date_value = _date_value(claim["value"])
            if not date_value:
                warnings.append({
                    "code": "unsupported_date_value",
                    "claim_id": claim_id,
                    "message": "Datum není přesné ISO YYYY, YYYY-MM nebo YYYY-MM-DD; zůstává pouze ve výzkumné poznámce.",
                })
                continue
            event_handle = add(
                "Event",
                f"event:{claim_id}",
                {
                    "type": event_type,
                    "date": date_value,
                    "description": "",
                    "citation_list": claim_citations[claim_id],
                    "note_list": [claim_notes[claim_id]],
                    "attribute_list": [marker(f"event:{claim_id}")],
                    "media_list": [],
                    "tag_list": [],
                },
            )
            event_refs.append({
                "ref": event_handle,
                "role": "Primary",
                "private": True,
                "attribute_list": [],
                "note_list": [],
            })
            if event_type == "Birth" and birth_index is None:
                birth_index = len(event_refs) - 1
            if event_type == "Death" and death_index is None:
                death_index = len(event_refs) - 1
        attributes = [marker(f"person:{person_id}")]
        label = state["persons"][person_id]["label"]
        if label:
            attributes.append({
                "type": "FamilyTreeChatGPT working label",
                "value": label,
                "private": True,
                "citation_list": [],
                "note_list": [],
            })
        payload = {
            "attribute_list": attributes,
            "alternate_names": [],
            "citation_list": direct_citations,
            "event_ref_list": event_refs,
            "family_list": [],
            "parent_family_list": [],
            "note_list": direct_note_handles,
            "media_list": [],
            "person_ref_list": [],
            "tag_list": [],
            "urls": [],
        }
        if primary_name:
            payload["primary_name"] = primary_name
        if gender is not None:
            payload["gender"] = gender
        if birth_index is not None:
            payload["birth_ref_index"] = birth_index
        if death_index is not None:
            payload["death_ref_index"] = death_index
        handle = add("Person", f"person:{person_id}", payload)
        person_handles[person_id] = handle
        person_parts[person_id] = {"payload": objects[handle]["payload"], "gender": gender}

    for (subject_type, relationship_id), subject_claims in sorted(claims_by_subject.items()):
        if subject_type != "relationship":
            continue
        relationship = state["relationships"][relationship_id]
        truth_claims = [
            item for item in subject_claims
            if item[1]["predicate"] == "relationship.parent_child" and item[1]["value"] is True
        ]
        parents = [item["person_id"] for item in relationship["participants"] if item["role"] == "parent"]
        children = [item["person_id"] for item in relationship["participants"] if item["role"] == "child"]
        if relationship["type"] != "parent_child" or len(truth_claims) != 1 or len(parents) != 1 or len(children) != 1:
            warnings.append({
                "code": "relationship_not_structured",
                "relationship_id": relationship_id,
                "message": "Vztah nelze bezeztrátově převést na jednu Gramps rodinu; zůstává v poznámkách účastníků.",
            })
            for participant in relationship["participants"]:
                payload = person_parts[participant["person_id"]]["payload"]
                payload["note_list"].extend(
                    claim_notes[claim_id] for claim_id, _ in subject_claims
                    if claim_notes[claim_id] not in payload["note_list"]
                )
            continue
        parent, child = parents[0], children[0]
        parent_gender = person_parts[parent]["gender"]
        if parent_gender not in (0, 1):
            warnings.append({
                "code": "parent_sex_required",
                "relationship_id": relationship_id,
                "message": "Gramps vyžaduje přiřazení rodiče jako otce nebo matky; bez podporovaného tvrzení o pohlaví se vztah nepřenese strukturovaně.",
            })
            for person_id in (parent, child):
                payload = person_parts[person_id]["payload"]
                payload["note_list"].extend(
                    claim_notes[claim_id] for claim_id, _ in subject_claims
                    if claim_notes[claim_id] not in payload["note_list"]
                )
            continue
        claim_id, _ = truth_claims[0]
        family_payload = {
            "type": "Unknown",
            "attribute_list": [marker(f"relationship:{relationship_id}")],
            "citation_list": claim_citations[claim_id],
            "note_list": [claim_notes[claim_id]],
            "child_ref_list": [{
                "ref": person_handles[child],
                "frel": "Birth" if parent_gender == 1 else "Unknown",
                "mrel": "Birth" if parent_gender == 0 else "Unknown",
                "private": True,
                "citation_list": claim_citations[claim_id],
                "note_list": [claim_notes[claim_id]],
            }],
            "event_ref_list": [],
            "media_list": [],
            "tag_list": [],
        }
        if parent_gender == 1:
            family_payload["father_handle"] = person_handles[parent]
        else:
            family_payload["mother_handle"] = person_handles[parent]
        family_handle = add("Family", f"relationship:{relationship_id}", family_payload)
        person_parts[parent]["payload"]["family_list"].append(family_handle)
        person_parts[child]["payload"]["parent_family_list"].append(family_handle)

    for claim_id, claim in eligible.items():
        if claim["predicate"] not in DATE_EVENTS and claim["predicate"] not in {
            "name.given", "name.surname", "sex", "person.sex", "relationship.parent_child"
        }:
            warnings.append({
                "code": "claim_note_only",
                "claim_id": claim_id,
                "predicate": claim["predicate"],
                "message": "Tvrzení nemá bezpečné strukturované mapování a je přeneseno pouze jako výzkumná poznámka.",
            })

    if len(objects) > MAX_OBJECTS:
        raise ValueError(f"Export by vytvořil více než {MAX_OBJECTS} objektů; rozděl výzkum na menší části.")
    ordered = sorted(
        objects.values(), key=lambda item: (CLASS_ORDER[item["object_class"]], item["local_key"])
    )
    return {
        "objects": ordered,
        "eligible_claim_ids": sorted(eligible),
        "excluded_claims": excluded,
        "warnings": warnings,
    }


def _matches(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key == "_class" or (key in actual and _matches(value, actual[key]))
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(
            _matches(left, right) for left, right in zip(expected, actual)
        )
    return expected == actual


def _task_object_matches(item, actual):
    if not isinstance(actual, dict):
        return False
    payload = item["payload"]
    if actual.get("private") is not True or actual.get("gramps_id") != payload["gramps_id"]:
        return False
    todo_handle = payload["tag_list"][0]
    if todo_handle not in actual.get("tag_list", []):
        return False
    if item["object_class"] == "Note":
        return actual.get("type") == "To Do"
    expected_marker = next(
        (
            attribute
            for attribute in payload["attribute_list"]
            if attribute.get("type") == "FamilyTreeChatGPT ID"
        ),
        None,
    )
    actual_markers = [
        attribute
        for attribute in actual.get("attribute_list", [])
        if attribute.get("type") == "FamilyTreeChatGPT ID"
    ]
    return any(_matches(expected_marker, marker_value) for marker_value in actual_markers) and set(
        payload["note_list"]
    ).issubset(actual.get("note_list", []))


def _planned_todo_tag(client):
    tags = client.list_tags()
    matches = _todo_tags(tags)
    if len(matches) > 1:
        raise ValueError("Gramps strom obsahuje více tagů ToDo; nejprve je ručně sjednoť.")
    if matches:
        handle = matches[0].get("handle")
        if not isinstance(handle, str) or not handle:
            raise ValueError("Existující tag ToDo nemá platný handle.")
        return {"name": "ToDo", "handle": handle, "action": "unchanged"}
    handle = stable_handle("Tag", "todo")
    collision = next((tag for tag in tags if tag.get("handle") == handle), None)
    if collision is not None:
        raise ValueError("Stabilní handle tagu ToDo koliduje s jiným tagem.")
    return {"name": "ToDo", "handle": handle, "action": "create"}


def make_task_plan(client, task_input):
    normalized = validate_task_input(task_input)
    metadata = client.metadata()
    if not compatible(metadata):
        raise ValueError(
            f"Podporováno je Gramps Web API {SUPPORTED_API_MAJOR}.x; server hlásí {api_version(metadata) or 'neznámou verzi'}."
        )
    todo_tag = _planned_todo_tag(client)
    built = build_task_objects(normalized, todo_tag["handle"])
    entries = []
    for item in built["objects"]:
        existing = client.get_optional(item["object_class"], item["payload"]["handle"])
        if existing is None:
            action = "create"
            remote_change = None
        elif _task_object_matches(item, existing):
            action = "unchanged"
            remote_change = existing.get("change")
        else:
            action = "conflict"
            remote_change = existing.get("change")
        entries.append({**item, "action": action, "remote_change": remote_change})
    database = metadata.get("database", {})
    plan = {
        "schema_version": TASK_PLAN_SCHEMA_VERSION,
        "kind": "tasks",
        "created_at": now(),
        "base_url": client.base_url,
        "api_version": api_version(metadata),
        "database": {"id": database.get("id", ""), "name": database.get("name", "")},
        "mode": "append_only",
        "task_input_sha256": digest(normalized),
        "task_ids": [task["id"] for task in normalized["tasks"]],
        "todo_tag": todo_tag,
        "objects": entries,
    }
    plan["plan_sha256"] = digest(plan)
    return plan


def validate_task_plan(plan):
    if (
        not isinstance(plan, dict)
        or plan.get("schema_version") != TASK_PLAN_SCHEMA_VERSION
        or plan.get("kind") != "tasks"
    ):
        raise ValueError("Nepodporovaný formát Gramps task plánu.")
    saved = plan.get("plan_sha256")
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    if not isinstance(saved, str) or saved != digest(unsigned):
        raise ValueError("Gramps task plán byl po vytvoření změněn nebo je poškozený.")
    todo_tag = plan.get("todo_tag")
    if (
        plan.get("mode") != "append_only"
        or not isinstance(plan.get("objects"), list)
        or not isinstance(plan.get("task_ids"), list)
        or not isinstance(todo_tag, dict)
        or todo_tag.get("name") != "ToDo"
        or not isinstance(todo_tag.get("handle"), str)
        or not todo_tag["handle"]
        or todo_tag.get("action") not in ("create", "unchanged")
    ):
        raise ValueError("Gramps task plán nemá bezpečný append-only formát.")
    task_ids = plan["task_ids"]
    if (
        not task_ids
        or len(set(task_ids)) != len(task_ids)
        or not all(isinstance(value, str) and TASK_ID_PATTERN.fullmatch(value) for value in task_ids)
        or not isinstance(plan.get("task_input_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", plan["task_input_sha256"])
    ):
        raise ValueError("Gramps task plán obsahuje neplatná ID nebo hash vstupu.")
    seen_handles = set()
    source_tasks = set()
    note_tasks = set()
    for item in plan["objects"]:
        if (
            not isinstance(item, dict)
            or item.get("object_class") not in ("Source", "Note")
            or item.get("action") not in ("create", "unchanged", "conflict")
            or not isinstance(item.get("task_id"), str)
            or item["task_id"] not in plan["task_ids"]
            or not isinstance(item.get("payload"), dict)
        ):
            raise ValueError("Gramps task plán obsahuje neplatnou operaci.")
        payload = item["payload"]
        local_key = f"task:{item['task_id']}"
        expected_local_key = (
            local_key if item["object_class"] == "Source" else f"{local_key}:description"
        )
        if (
            payload.get("_class") != item["object_class"]
            or payload.get("private") is not True
            or todo_tag["handle"] not in payload.get("tag_list", [])
            or item.get("local_key") != expected_local_key
            or payload.get("handle") != stable_handle(item["object_class"], expected_local_key)
            or payload.get("gramps_id")
            != stable_gramps_id(item["object_class"], expected_local_key)
            or payload["handle"] in seen_handles
        ):
            raise ValueError("Gramps task plán obsahuje neplatný nebo nestabilní objekt.")
        seen_handles.add(payload["handle"])
        if item["object_class"] == "Source":
            source_tasks.add(item["task_id"])
            expected_marker = marker(local_key)
            if not any(
                _matches(expected_marker, attribute)
                for attribute in payload.get("attribute_list", [])
            ):
                raise ValueError("Zdroj Gramps úkolu postrádá stabilní lokální ID.")
        else:
            note_tasks.add(item["task_id"])
            if payload.get("type") != "To Do":
                raise ValueError("Poznámka Gramps úkolu musí mít typ To Do.")
    if source_tasks != set(task_ids) or not note_tasks.issubset(source_tasks):
        raise ValueError("Gramps task plán nemá právě jeden zdroj pro každý úkol.")
    for item in plan["objects"]:
        if item["object_class"] != "Source":
            continue
        expected_notes = (
            [stable_handle("Note", f"task:{item['task_id']}:description")]
            if item["task_id"] in note_tasks
            else []
        )
        if item["payload"].get("note_list") != expected_notes:
            raise ValueError("Zdroj Gramps úkolu má neplatnou vazbu na poznámku.")
    return plan


def task_plan_summary(plan, output=None):
    validate_task_plan(plan)
    counts = {name: 0 for name in ("create", "unchanged", "conflict")}
    for item in plan["objects"]:
        counts[item["action"]] += 1
    result = {
        "planned": True,
        "kind": "tasks",
        "plan_sha256": plan["plan_sha256"],
        "base_url": plan["base_url"],
        "database": plan["database"],
        "mode": plan["mode"],
        "tasks": len(plan["task_ids"]),
        "todo_tag": plan["todo_tag"],
        "actions": counts,
    }
    if output is not None:
        result["output"] = str(output)
    return result


def _ensure_todo_tag(client, planned):
    tags = client.list_tags()
    matches = _todo_tags(tags)
    exact = next((tag for tag in tags if tag.get("handle") == planned["handle"]), None)
    if len(matches) > 1:
        raise ValueError("Gramps strom obsahuje více tagů ToDo; push je odmítnut.")
    if matches:
        if matches[0].get("handle") != planned["handle"]:
            raise ValueError("Tag ToDo se od vytvoření plánu změnil; vytvoř nový plán.")
        return False
    if exact is not None:
        raise ValueError("Handle plánovaného tagu ToDo koliduje s jiným tagem.")
    if planned["action"] != "create":
        raise ValueError("Tag ToDo od vytvoření plánu zmizel; vytvoř nový plán.")
    client.create_tag(planned["handle"], "ToDo")
    created = [
        tag
        for tag in client.list_tags()
        if tag.get("name") == "ToDo" and tag.get("handle") == planned["handle"]
    ]
    if len(created) != 1:
        raise ValueError("Vytvořený tag ToDo se nepodařilo zpětně ověřit.")
    return True


def push_task_plan(client, plan):
    validate_task_plan(plan)
    if plan["base_url"] != client.base_url:
        raise ValueError("URL serveru se neshoduje s uloženým Gramps task plánem.")
    metadata = client.metadata()
    database = metadata.get("database", {})
    if (
        database.get("id", "") != plan["database"].get("id", "")
        or database.get("name", "") != plan["database"].get("name", "")
    ):
        raise ValueError("Aktivní Gramps strom se neshoduje s task plánem.")
    conflicts = [item for item in plan["objects"] if item["action"] == "conflict"]
    if conflicts:
        raise ValueError("Gramps task plán obsahuje kolize; push je odmítnut.")
    tag_created = _ensure_todo_tag(client, plan["todo_tag"])
    creates = []
    already_present = 0
    for item in plan["objects"]:
        remote = client.get_optional(item["object_class"], item["payload"]["handle"])
        if item["action"] == "unchanged":
            if remote is None or not _task_object_matches(item, remote):
                raise ValueError("Gramps úkol se od vytvoření plánu změnil; vytvoř nový plán.")
            already_present += 1
        elif remote is None:
            creates.append(item)
        elif _task_object_matches(item, remote):
            already_present += 1
        else:
            raise ValueError("Stabilní handle Gramps úkolu koliduje s jiným objektem.")
    client.create_objects([item["payload"] for item in creates])
    missing = []
    for item in plan["objects"]:
        remote = client.get_optional(item["object_class"], item["payload"]["handle"])
        if remote is None or not _task_object_matches(item, remote):
            missing.append(item["local_key"])
    if missing:
        raise ValueError(
            "Zápis úkolů skončil bez úplného ověření objektů: " + ", ".join(missing[:10])
        )
    return {
        "pushed": True,
        "kind": "tasks",
        "mode": "append_only",
        "tag_created": tag_created,
        "created": len(creates),
        "already_present": already_present,
        "verified": len(plan["objects"]),
        "tasks": len(plan["task_ids"]),
        "plan_sha256": plan["plan_sha256"],
        "database": plan["database"],
    }


def make_plan(client, state, research_sha256):
    metadata = client.metadata()
    if not compatible(metadata):
        raise ValueError(
            f"Podporováno je Gramps Web API {SUPPORTED_API_MAJOR}.x; server hlásí {api_version(metadata) or 'neznámou verzi'}."
        )
    built = build_objects(state)
    entries = []
    for item in built["objects"]:
        existing = client.get_optional(item["object_class"], item["payload"]["handle"])
        if existing is None:
            action = "create"
            remote_change = None
        elif _matches(item["payload"], existing):
            action = "unchanged"
            remote_change = existing.get("change")
        else:
            action = "conflict"
            remote_change = existing.get("change")
        entries.append({**item, "action": action, "remote_change": remote_change})
    database = metadata.get("database", {})
    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "created_at": now(),
        "base_url": client.base_url,
        "api_version": api_version(metadata),
        "database": {"id": database.get("id", ""), "name": database.get("name", "")},
        "research_revision": state["revision"],
        "research_sha256": research_sha256,
        "mode": "append_only",
        "eligible_claim_ids": built["eligible_claim_ids"],
        "excluded_claims": built["excluded_claims"],
        "warnings": built["warnings"],
        "objects": entries,
    }
    plan["plan_sha256"] = digest(plan)
    return plan


def validate_plan(plan):
    if not isinstance(plan, dict) or plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise ValueError("Nepodporovaný formát Gramps plánu.")
    saved = plan.get("plan_sha256")
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    if not isinstance(saved, str) or saved != digest(unsigned):
        raise ValueError("Gramps plán byl po vytvoření změněn nebo je poškozený.")
    if plan.get("mode") != "append_only" or not isinstance(plan.get("objects"), list):
        raise ValueError("Gramps plán nemá bezpečný append-only režim.")
    for item in plan["objects"]:
        if (
            not isinstance(item, dict)
            or item.get("object_class") not in ENDPOINTS
            or item.get("action") not in ("create", "unchanged", "conflict")
            or not isinstance(item.get("payload"), dict)
        ):
            raise ValueError("Gramps plán obsahuje neplatnou operaci.")
        payload = item["payload"]
        if payload.get("_class") != item["object_class"] or payload.get("private") is not True:
            raise ValueError("Gramps plán obsahuje neplatný nebo nesoukromý objekt.")
    return plan


def plan_summary(plan, output=None):
    counts = {name: 0 for name in ("create", "unchanged", "conflict")}
    classes = {}
    for item in plan["objects"]:
        counts[item["action"]] += 1
        classes[item["object_class"]] = classes.get(item["object_class"], 0) + 1
    result = {
        "planned": True,
        "plan_sha256": plan["plan_sha256"],
        "base_url": plan["base_url"],
        "database": plan["database"],
        "research_revision": plan["research_revision"],
        "mode": plan["mode"],
        "actions": counts,
        "object_classes": classes,
        "eligible_claims": len(plan["eligible_claim_ids"]),
        "excluded_claims": len(plan["excluded_claims"]),
        "warnings": plan["warnings"],
    }
    if output is not None:
        result["output"] = str(output)
    return result


def write_plan(path, plan, in_git_tree):
    output = Path(path).expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Výstupní Gramps plán už existuje: {output}")
    if not output.parent.is_dir():
        raise ValueError("Nadřazený adresář Gramps plánu neexistuje.")
    if in_git_tree(output):
        raise ValueError("Gramps plán se soukromými daty ulož mimo git repozitář.")
    fd, temporary = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
        os.chmod(output, stat.S_IRUSR | stat.S_IWUSR)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return output


def push(client, plan, research_revision, research_sha256):
    validate_plan(plan)
    if plan["base_url"] != client.base_url:
        raise ValueError("URL serveru se neshoduje s uloženým Gramps plánem.")
    metadata = client.metadata()
    database = metadata.get("database", {})
    if (
        database.get("id", "") != plan["database"].get("id", "")
        or database.get("name", "") != plan["database"].get("name", "")
    ):
        raise ValueError("Aktivní Gramps strom se neshoduje s plánem.")
    if research_revision != plan["research_revision"] or research_sha256 != plan["research_sha256"]:
        raise ValueError("Badatelský stav se od vytvoření Gramps plánu změnil.")
    conflicts = [item for item in plan["objects"] if item["action"] == "conflict"]
    if conflicts:
        raise ValueError("Gramps plán obsahuje kolize existujících objektů; push je odmítnut.")
    creates = [item for item in plan["objects"] if item["action"] == "create"]
    for item in creates:
        if client.get_optional(item["object_class"], item["payload"]["handle"]) is not None:
            raise ValueError("Gramps strom se od vytvoření plánu změnil; vytvoř nový plán.")
    client.create_objects([item["payload"] for item in creates])
    missing = []
    for item in plan["objects"]:
        remote = client.get_optional(item["object_class"], item["payload"]["handle"])
        if remote is None or not _matches(item["payload"], remote):
            missing.append(item["local_key"])
    if missing:
        raise ValueError(
            "Zápis skončil bez úplného ověření objektů: " + ", ".join(missing[:10])
        )
    return {
        "pushed": True,
        "mode": "append_only",
        "created": len(creates),
        "unchanged": len(plan["objects"]) - len(creates),
        "verified": len(plan["objects"]),
        "plan_sha256": plan["plan_sha256"],
        "database": plan["database"],
    }


def status(plan):
    summary = plan_summary(plan)
    if summary["actions"]["conflict"]:
        state = "conflict"
    elif summary["actions"]["create"]:
        state = "pending"
    else:
        state = "synchronized"
    return {"status": state, **summary}
