"""Private image import and IIIF assembly; authorized live transport in mza_live."""
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from io import BytesIO
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import parse_qs, unquote, urlsplit
import warnings

import research


MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_DIMENSION = 30_000
MAX_REQUESTS = 2048
MAX_TRANSFER_BYTES = 128 * 1024 * 1024
METHODS = ("browser_download", "archival_copy", "iiif_assembled", "screenshot", "manual_import")
FORMATS = {"JPEG": ".jpg", "PNG": ".png", "TIFF": ".tif", "JPEG2000": ".jp2"}
BLOCK_REASON = (
    "Automatické stahování MZA není povoleno bez soukromé evidence souhlasu pro IIIF. "
    "Použij uložení v archivním prohlížeči nebo oficiální kopii od archivu a archive mza import."
)


def archive_url(value):
    if not isinstance(value, str) or len(value) > 2048 or re.search(r"[\s\\\x00-\x1f]", value):
        raise ValueError("Neplatná URL MZA.")
    parts = urlsplit(value)
    if (parts.scheme != "https" or parts.netloc != "www.mza.cz" or parts.fragment
            or not re.fullmatch(r"/actapublica/matrika/detail/[1-9][0-9]*/?", parts.path)):
        raise ValueError("Očekáván HTTPS detail jedné matriky na www.mza.cz.")
    query = parse_qs(parts.query, keep_blank_values=True, max_num_fields=10)
    if set(query) - {"image"} or (query and (
        len(query["image"]) != 1 or ".." in query["image"][0]
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,255}", query["image"][0])
    )):
        raise ValueError("URL musí označovat jednu obrazovou přílohu bez dalších parametrů.")
    return value


def dimensions(width, height):
    if (type(width) is not int or type(height) is not int or min(width, height) < 1
            or max(width, height) > MAX_DIMENSION or width * height > MAX_PIXELS):
        raise ValueError("Neplatné nebo nadměrné rozměry obrazu.")
    return width, height


def image_info(path):
    from PIL import Image

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                width, height = dimensions(*image.size)
                fmt = image.format
                if fmt not in FORMATS or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Podporován je jeden snímek JPEG, PNG, TIFF nebo JP2.")
                image.verify()
            with Image.open(path) as image:
                image.load()
    except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Poškozený nebo nadměrný obrazový soubor.") from exc
    return {"format": fmt, "width": width, "height": height}


def publish_new(staged, target):
    """Publish a complete file atomically, with no replacement even in a race."""
    os.link(staged, target)


def validate_acquisition(value, source, root, verify_hashes=False):
    """Optional record extension; older records remain valid without it."""
    try:
        if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            raise ValueError("Nepodporovaná metadata získání snímku.")
        archive_url(value.get("url"))
        if (value["url"] != source.get("url") or value.get("archive") != source.get("archive")
                or value["archive"] != "Moravský zemský archiv v Brně"):
            raise ValueError("Původ snímku nesouhlasí s pramenem.")
        if value.get("reference") != source.get("reference"):
            raise ValueError("Identifikace matriky nesouhlasí s pramenem.")
        if value.get("method") not in METHODS or value.get("digital_copy") not in ("original", "derived", "unknown"):
            raise ValueError("Neplatný způsob získání nebo původ digitální kopie.")
        if value["digital_copy"] == "original" and value["method"] != "archival_copy":
            raise ValueError("Originální digitální kopie vyžaduje doloženou archivní kopii.")
        if value["method"] in ("browser_download", "screenshot", "iiif_assembled") and value["digital_copy"] != "derived":
            raise ValueError("Screenshot a IIIF sestava jsou odvozené soubory.")
        if not isinstance(value.get("provenance_note"), str) or (
            value["digital_copy"] == "original" and not value["provenance_note"].strip()
        ):
            raise ValueError("Původ originální digitální kopie musí mít zdůvodnění.")
        number = value.get("image_number")
        if number is not None and (type(number) is not int or number < 1):
            raise ValueError("Neplatné číslo snímku.")
        for field in ("acquired_at", "imported_at"):
            stamp = datetime.fromisoformat(value[field])
            if stamp.tzinfo is None:
                raise ValueError("Čas získání musí obsahovat časové pásmo.")
        if value.get("format") not in FORMATS:
            raise ValueError("Neplatný formát snímku.")
        dimensions(value.get("width"), value.get("height"))
        if type(value.get("size_bytes")) is not int or not 0 < value["size_bytes"] <= MAX_FILE_BYTES:
            raise ValueError("Neplatná velikost snímku.")
        if (not isinstance(value.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"])
                or value["sha256"] != source.get("file_sha256")):
            raise ValueError("SHA-256 metadat nesouhlasí s pramenem.")
        expected_file = "sources/mza-" + value["sha256"] + FORMATS[value["format"]]
        if source.get("file") != expected_file or (root / expected_file).is_symlink():
            raise ValueError("Neplatná cesta importovaného snímku.")
        if verify_hashes and research.asset(root, source["file"]).stat().st_size != value["size_bytes"]:
            raise ValueError("Velikost souboru nesouhlasí s metadaty.")
        if "permission" in value or "iiif" in value:
            permission, iiif = value["permission"], value["iiif"]
            if (not isinstance(permission, dict) or not isinstance(iiif, dict)
                    or value["method"] != "iiif_assembled" or permission.get("basis") != "user_attestation"
                    or permission.get("scope") != "single_image"):
                raise ValueError("Neplatná evidence oprávnění živého IIIF.")
            for field in ("statement", "evidence_reference"):
                if not isinstance(permission.get(field), str) or not permission[field].strip():
                    raise ValueError("Chybí podklad souhlasu pro IIIF.")
            if (not isinstance(permission.get("sha256"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", permission["sha256"])
                    or datetime.fromisoformat(permission["recorded_at"]).tzinfo is None):
                raise ValueError("Neplatný otisk nebo čas evidence souhlasu.")
            import mza_live

            mza_live.live_url(iiif["info_url"])
            if (not iiif["info_url"].endswith("/info.json")
                    or type(iiif.get("version")) is not int or iiif["version"] not in (2, 3)
                    or type(iiif.get("request_count")) is not int or not 3 <= iiif["request_count"] <= MAX_REQUESTS
                    or type(iiif.get("image_requests")) is not int or not 1 <= iiif["image_requests"] <= iiif["request_count"] - 2
                    or type(iiif.get("live_access_verified")) is not bool):
                raise ValueError("Neplatná metadata živého IIIF přístupu.")
    except (ValueError, TypeError, KeyError) as exc:
        return [f"source.acquisition: {exc}"]
    return []


def import_image(root, path, url, *, method="manual_import", reference="", image_number=None,
                 digital_copy="unknown", provenance_note="", acquired_at=None,
                 expected_revision=None, acquisition_extra=None):
    root = research.private_workspace(root)
    archive_url(url)
    original = Path(path).expanduser()
    if original.is_symlink() or not original.is_file() or research.in_git_tree(original.resolve()):
        raise ValueError("Importuj běžný soukromý soubor mimo git repozitář, nikoli symlink.")
    if method in ("browser_download", "screenshot", "iiif_assembled"):
        if digital_copy == "original":
            raise ValueError("Odvozený soubor nelze označit jako originální digitální kopii.")
        digital_copy = "derived"
    if not isinstance(reference, str) or not isinstance(provenance_note, str):
        raise ValueError("Identifikace a poznámka původu musí být text.")
    sources = root / "sources"
    if sources.is_symlink() or not sources.is_dir():
        raise ValueError("sources musí být běžná složka uvnitř projektu.")
    with research.locked(root):
        state = research.read_state(root)
        if expected_revision is not None and state["revision"] != expected_revision:
            raise ValueError("Stav se mezitím změnil; znovu načti resume.")
        errors = research.check_state(state, root)
        if errors:
            raise ValueError("\n".join(errors))
        fd, name = tempfile.mkstemp(prefix=".mza-import-", dir=sources)
        staged = Path(name)
        published = None
        try:
            with os.fdopen(fd, "wb") as output, original.open("rb") as input_file:
                size = 0
                while chunk := input_file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise ValueError("Snímek překračuje limit 64 MiB.")
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            info = image_info(staged)
            digest = research.sha256(staged)
            key = "mza_" + hashlib.sha256((url + "\0" + digest).encode()).hexdigest()
            target = sources / ("mza-" + digest + FORMATS[info["format"]])
            stamp = research.now()
            metadata = {
                "schema_version": 1, "url": url, "archive": "Moravský zemský archiv v Brně",
                "reference": reference, "image_number": image_number,
                "acquired_at": acquired_at or stamp, "imported_at": stamp,
                "method": method, "digital_copy": digital_copy, "provenance_note": provenance_note,
                **info, "size_bytes": size, "sha256": digest,
            }
            if acquisition_extra is not None:
                if not isinstance(acquisition_extra, dict) or set(acquisition_extra) - {"permission", "iiif"}:
                    raise ValueError("Nepovolená dodatečná metadata získání snímku.")
                metadata.update(deepcopy(acquisition_extra))
            record = {
                "id": key, "source": {
                    "archive": metadata["archive"], "reference": reference,
                    "page": f"snímek {image_number}" if image_number is not None else "",
                    "url": url, "accessed_on": metadata["acquired_at"][:10],
                    "file": target.relative_to(root).as_posix(), "crop": "",
                    "file_sha256": digest, "acquisition": metadata,
                },
                "reading_status": "unread", "visual_review": False,
                "transcription": "", "translation": "", "interpretation": "", "uncertainties": [],
                "identity": {"status": "unresolved", "rationale": "", "evidence": []},
            }
            errors = validate_acquisition(metadata, record["source"], root)
            if errors:
                raise ValueError("\n".join(errors))
            if key in state["records"]:
                old = state["records"][key]["source"].get("acquisition")
                if not isinstance(old, dict):
                    raise ValueError("ID importu již používá jiný záznam; nic nebylo přepsáno.")
                fields = ("method", "reference", "image_number", "digital_copy", "provenance_note")
                if any(metadata[field] != old[field] for field in fields) or (
                    acquired_at is not None and acquired_at != old["acquired_at"]
                ):
                    raise ValueError("Snímek už existuje s jinými metadaty; zkontroluj record put.")
                return {"imported": False, "duplicate": True, "record_id": key,
                        "revision": state["revision"], "file": record["source"]["file"], "acquisition": old}
            if target.exists() or target.is_symlink():
                if target.is_symlink() or not target.is_file() or research.sha256(target) != digest:
                    raise FileExistsError("Cílový soubor existuje s jiným obsahem; nic nebylo přepsáno.")
            else:
                publish_new(staged, target)
                published = target
            new = deepcopy(state)
            new["records"][key] = record
            new["revision"] += 1
            new["events"].append({"result": "mza_image_imported", "record_id": key,
                                  "at": stamp, "revision": new["revision"]})
            new["next_step"] = "Vizuálně ověřit importovaný snímek a doplnit citaci před čtením zápisu."
            errors = research.check_state(new, root)
            if errors:
                raise ValueError("\n".join(errors))
            research.backup_and_write(root, state, new)
            published = None
            return {"imported": True, "duplicate": False, "record_id": key,
                    "revision": new["revision"], "file": record["source"]["file"], "acquisition": metadata}
        finally:
            staged.unlink(missing_ok=True)
            if published is not None:
                published.unlink()


def inspect(url, root=None, path=None, *, permission_file=None):
    archive_url(url)
    result = {"url": url, "network_accessed": False, "download_allowed": False,
              "reason": BLOCK_REASON, "matches": []}
    import mza_live

    try:
        permission = mza_live.load_permission(permission_file)
    except (ValueError, OSError):
        pass
    else:
        result.update(download_allowed=True, permission_basis=permission["basis"],
                      reason="Živý režim je dostupný na základě uživatelského potvrzení souhlasu; přístup k serveru zatím neověřen.")
    digest = None
    if path is not None:
        path = Path(path).expanduser()
        if path.is_symlink() or not path.is_file() or research.in_git_tree(path.resolve()):
            raise ValueError("Kontrolovaný snímek musí být běžný soukromý soubor mimo Git.")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Snímek překračuje limit 64 MiB.")
        digest = research.sha256(path)
        result["local_file"] = {**image_info(path), "sha256": digest, "size_bytes": path.stat().st_size}
    if root is not None:
        root = research.private_workspace(root)
        state = research.read_state(root)
        errors = research.check_state(state, root)
        if errors:
            raise ValueError("\n".join(errors))
        for key, record in state["records"].items():
            source = record["source"]
            if source.get("url") == url or (digest and source.get("file_sha256") == digest):
                details = image_info(research.asset(root, source["file"])) if source.get("file") else {}
                acquisition = source.get("acquisition")
                if acquisition and any(details.get(field) != acquisition[field] for field in ("format", "width", "height")):
                    raise ValueError("Obrazová metadata nesouhlasí s uloženým souborem.")
                result["matches"].append({"record_id": key, "file": source.get("file"),
                                          "acquisition": source.get("acquisition"), **details})
    return result


def download(url, root=None, **options):
    if root is None:
        raise ValueError(BLOCK_REASON + " Vyžadován je také --workspace.")
    import mza_live

    return mza_live.download(root, url, **options)


def test_service_url(url):
    """Only a reserved test host; neither archive endpoints nor real HTTP exist here."""
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc != "iiif.example.invalid" or parts.query
            or parts.fragment or re.search(r"[\s\\\x00-\x1f]", url)
            or any(p in (".", "..") for p in unquote(parts.path).split("/"))):
        raise ValueError("Offline IIIF adaptér přijímá pouze HTTPS iiif.example.invalid bez přesměrování.")
    return url


def parse_info(info, validator=test_service_url):
    if not isinstance(info, dict):
        raise ValueError("IIIF info.json musí být objekt.")
    context = info.get("@context", [])
    context = [context] if isinstance(context, str) else context
    if not isinstance(context, list):
        raise ValueError("Neplatný IIIF kontext.")
    version = next((v for v in (2, 3) if any(
        c in (f"http://iiif.io/api/image/{v}/context.json", f"https://iiif.io/api/image/{v}/context.json")
        for c in context
    )), None)
    if version is None or info.get("protocol") != "http://iiif.io/api/image":
        raise ValueError("Podporována jsou metadata IIIF Image API 2 nebo 3.")
    if version == 3 and info.get("type") != "ImageService3":
        raise ValueError("Chybí typ ImageService3.")
    base = info.get("@id" if version == 2 else "id")
    if not isinstance(base, str):
        raise ValueError("Chybí identifikátor obrazové služby.")
    validator(base)
    width, height = dimensions(info.get("width"), info.get("height"))
    profiles = info.get("profile")
    profiles = profiles if isinstance(profiles, list) else [profiles]
    profile_pattern = (rf"https?://iiif.io/api/image/{version}/level[012]\.json"
                       if version == 2 else r"level[012]")
    if not profiles or not isinstance(profiles[0], str) or not re.fullmatch(profile_pattern, profiles[0]):
        raise ValueError("Chybí podporovaný profil IIIF.")
    limits = dict(info)
    for profile in profiles[1:]:
        if not isinstance(profile, dict):
            raise ValueError("Neplatný profil IIIF.")
        limits.update(profile)
    for field in ("maxWidth", "maxHeight", "maxArea"):
        if field in limits and (type(limits[field]) is not int or limits[field] < 1):
            raise ValueError("Neplatný limit IIIF.")
    if "maxHeight" in limits and "maxWidth" not in limits:
        raise ValueError("maxHeight vyžaduje maxWidth.")
    if "maxWidth" in limits:
        limits.setdefault("maxHeight", limits["maxWidth"])
    sizes = info.get("sizes", [])
    if not isinstance(sizes, list) or len(sizes) > MAX_REQUESTS:
        raise ValueError("Neplatné podporované velikosti IIIF.")
    listed_sizes = []
    for size in sizes:
        if not isinstance(size, dict):
            raise ValueError("Neplatná podporovaná velikost IIIF.")
        listed_sizes.append(dimensions(size.get("width"), size.get("height")))
    tiles = info.get("tiles", [])
    if not isinstance(tiles, list):
        raise ValueError("Neplatný seznam dlaždic IIIF.")
    full_tiles = []
    for tile in tiles:
        if not isinstance(tile, dict):
            raise ValueError("Neplatná dlaždice IIIF.")
        tw, th = dimensions(tile.get("width"), tile.get("height", tile.get("width")))
        scales = tile.get("scaleFactors")
        if not isinstance(scales, list) or not scales or any(type(s) is not int or s < 1 for s in scales):
            raise ValueError("Neplatné měřítko dlaždic IIIF.")
        if 1 in scales:
            full_tiles.append((tw, th))
    fits = lambda w, h: (w <= limits.get("maxWidth", w) and h <= limits.get("maxHeight", h)
                         and w * h <= limits.get("maxArea", w * h))
    full_supported = not ("level0" in profiles[0] and listed_sizes and (width, height) not in listed_sizes)
    if fits(width, height) and full_supported:
        requests = [("full", "full" if version == 2 else "max", (0, 0, width, height))]
    else:
        candidates = [(tw, th) for tw, th in full_tiles if fits(min(tw, width), min(th, height))]
        if not candidates:
            raise ValueError("Služba nedokládá podporu získání celého plného rozlišení.")
        tw, th = min(candidates, key=lambda t: ((width + t[0] - 1) // t[0]) * ((height + t[1] - 1) // t[1]))
        if ((width + tw - 1) // tw) * ((height + th - 1) // th) >= MAX_REQUESTS:
            raise ValueError("Příliš mnoho dlaždic.")
        requests = []
        for y in range(0, height, th):
            for x in range(0, width, tw):
                w, h = min(tw, width - x), min(th, height - y)
                requests.append((f"{x},{y},{w},{h}", f"{w}," if version == 2 else f"{w},{h}", (x, y, w, h)))
    return {"base": base.rstrip("/"), "version": version, "width": width, "height": height,
            "requests": requests}


class ProtectionPage(HTMLParser):
    """Recognize HTML challenge controls, not words in JS, links or prose."""

    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    IGNORED_TAGS = {"script", "style", "template", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.signals = set()

    def handle_starttag(self, tag, attrs):
        attrs = {key: value or "" for key, value in attrs}
        hidden = (bool(self.stack and self.stack[-1][1]) or tag in self.IGNORED_TAGS
                  or "hidden" in attrs or "inert" in attrs or attrs.get("aria-hidden", "").lower() == "true"
                  or bool(re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", attrs.get("style", ""), re.I)))
        if not hidden:
            classes = set(attrs.get("class", "").lower().split())
            if tag == "altcha-widget":
                self.signals.add("altcha_widget")
            for name in ("g-recaptcha", "h-captcha", "cf-turnstile"):
                if name in classes and attrs.get("data-sitekey"):
                    self.signals.add(name)
            if tag == "form" and attrs.get("id", "").lower() in {
                "challenge-form", "captcha-form", "altcha-form", "hcaptcha-form", "cf-chl-form"
            }:
                self.signals.add("challenge_form")
        if tag not in self.VOID_TAGS:
            if len(self.stack) >= 512:
                raise ValueError("HTML překračuje limit vnoření; další požadavky nebyly provedeny.")
            self.stack.append((tag, hidden))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


def response_diagnosis(status, headers, body, allow_html=False):
    prefix = body[:2048].lstrip().lower()
    is_html = ("text/html" in headers.get("content-type", "").lower()
               or prefix.startswith((b"<!doctype html", b"<html", b"<head", b"<body", b"<form", b"<altcha-widget")))
    if status in (401, 403, 429) or 300 <= status < 400:
        return {"classification": "redirect" if 300 <= status < 400 else f"http_{status}",
                "signals": [], "is_html": is_html}
    signals = []
    if is_html or allow_html:
        parser = ProtectionPage()
        parser.feed(body[:2 * 1024 * 1024].decode("utf-8", errors="replace"))
        parser.close()
        signals = sorted(parser.signals)
    if signals:
        classification = "active_challenge"
    elif status == 200 and is_html and not allow_html:
        classification = "unexpected_html"
    elif status != 200:
        classification = "http_error"
    else:
        classification = "ok"
    return {"classification": classification, "signals": signals, "is_html": is_html}


class IIIFSession:
    """Bounded sequential IIIF session; redirects and challenges always stop it."""

    def __init__(self, transport, *, sleep=time.sleep, validator=test_service_url, interval=2, observer=None):
        self.transport, self.sleep = transport, sleep
        self.validator, self.interval = validator, interval
        self.observer = observer
        self.stopped = False
        self.count = self.transferred = 0

    def get(self, url, limit, *, allow_html=False):
        self.validator(url)
        if self.stopped:
            raise ValueError("IIIF relace byla zastavena; další požadavky jsou zakázány.")
        for attempt in range(2):
            if self.count >= MAX_REQUESTS:
                self.stopped = True
                raise ValueError("Překročen limit počtu požadavků.")
            if self.count:
                self.sleep(self.interval)
            self.count += 1
            try:
                status, headers, body = self.transport(url, timeout=15, max_bytes=limit)
            except TimeoutError:
                if attempt == 0:
                    continue
                self.stopped = True
                raise ValueError("IIIF timeout; operace ukončena.")
            headers = {k.lower(): v for k, v in headers.items()}
            self.transferred += len(body)
            if len(body) > limit or self.transferred > MAX_TRANSFER_BYTES:
                self.stopped = True
                raise ValueError("Překročen limit přenosu.")
            try:
                diagnosis = response_diagnosis(status, headers, body, allow_html)
            except ValueError:
                self.stopped = True
                if self.observer is not None:
                    self.observer(url, status, headers, body, {
                        "classification": "html_parse_error", "signals": [], "is_html": True,
                    })
                raise
            if self.observer is not None:
                self.observer(url, status, headers, body, diagnosis)
            classification = diagnosis["classification"]
            if classification in ("http_401", "http_403", "http_429", "redirect", "active_challenge", "unexpected_html"):
                self.stopped = True
                detail = ", ".join(diagnosis["signals"])
                raise ValueError(f"HTTP {status}: {classification}" + (f" ({detail})" if detail else "") + "; zastaveno.")
            if status in (500, 502, 503, 504) and attempt == 0:
                retry = headers.get("retry-after", "2")
                try:
                    delay = max(0, int(retry))
                except ValueError:
                    try:
                        delay = max(0, (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds())
                    except (ValueError, TypeError, OverflowError):
                        self.stopped = True
                        raise ValueError("Neplatný Retry-After; zastaveno.")
                if delay > 60:
                    self.stopped = True
                    raise ValueError("Retry-After vyžaduje pozdější ruční opakování.")
                self.sleep(delay)
                continue
            if status != 200:
                self.stopped = True
                raise ValueError(f"HTTP {status}: neúspěšný IIIF požadavek.")
            return body

    def acquire(self, info_url, output):
        from PIL import Image

        output = Path(output).expanduser()
        if output.suffix.lower() != ".png" or output.exists() or output.is_symlink():
            raise ValueError("Výstup musí být nový soubor PNG.")
        if research.in_git_tree(output.resolve()):
            raise ValueError("Výstup ulož mimo git repozitář.")
        if not isinstance(info_url, str) or not info_url.endswith("/info.json"):
            raise ValueError("Očekáván info.json jednoho testovacího obrazu.")
        try:
            info = parse_info(json.loads(self.get(info_url, 1024 * 1024)), self.validator)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Neplatný IIIF JSON.") from exc
        if info["base"] + "/info.json" != info_url:
            raise ValueError("Identifikátor služby nesouhlasí s info.json.")
        with Image.new("RGB", (info["width"], info["height"])) as canvas:
            for region, size, (x, y, w, h) in info["requests"]:
                payload = self.get(f"{info['base']}/{region}/{size}/0/default.jpg", MAX_FILE_BYTES)
                details = image_info(BytesIO(payload))
                if (details["width"], details["height"], details["format"]) != (w, h, "JPEG"):
                    raise ValueError("Dlaždice má nesprávný formát nebo rozměry; nic nebylo uloženo.")
                with Image.open(BytesIO(payload)) as tile:
                    canvas.paste(tile.convert("RGB"), (x, y))
            fd, name = tempfile.mkstemp(prefix=".iiif-", dir=output.parent)
            staged = Path(name)
            try:
                with os.fdopen(fd, "wb") as stream:
                    canvas.save(stream, format="PNG")
                    stream.flush()
                    os.fsync(stream.fileno())
                details = image_info(staged)
                if staged.stat().st_size > MAX_FILE_BYTES:
                    raise ValueError("Výstup překračuje limit velikosti.")
                publish_new(staged, output)
            finally:
                staged.unlink(missing_ok=True)
        return {**details, "method": "iiif_assembled", "digital_copy": "derived",
                "sha256": research.sha256(output), "size_bytes": output.stat().st_size,
                "image_requests": len(info["requests"]), "iiif_version": info["version"],
                "live_mza_verified": False}


class OfflineIIIF(IIIFSession):
    """Mock-only compatibility adapter restricted to the reserved .invalid host."""

    def __init__(self, transport, *, sleep=time.sleep):
        super().__init__(transport, sleep=sleep)
