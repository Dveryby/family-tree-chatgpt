"""Opt-in, single-image MZA transport. No cookies, authentication or challenges."""
from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
from html import unescape
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import socket
import ssl
import tempfile
import time
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit

import mza
import research


DEFAULT_PERMISSION_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "family-tree-chatgpt/mza-permission.json"
HOSTS = ("www.mza.cz", "iipserver.mza.cz")
LOCK_KEY = hashlib.sha256(str(Path.home().resolve()).encode()).hexdigest()[:16]
LOCK_FILE = Path(tempfile.gettempdir()) / f"family-tree-mza-{LOCK_KEY}.lock"


@contextmanager
def acquisition_lock():
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("Jiné získávání MZA běží nebo zanechalo zámek; ověř proces před odstraněním zámku.") from exc
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        LOCK_FILE.unlink()


def load_permission(path=None):
    path = Path(path) if path is not None else DEFAULT_PERMISSION_FILE
    if path.is_symlink() or not path.is_file() or research.in_git_tree(path.resolve()):
        raise ValueError(mza.BLOCK_REASON)
    if path.stat().st_size > 65536 or path.stat().st_mode & 0o077:
        raise ValueError("Soukromá evidence souhlasu musí mít nejvýše 64 KiB a práva 0600.")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
        if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            raise ValueError("Neplatná verze evidence souhlasu.")
        if (value.get("archive") != "mza" or value.get("basis") != "user_attestation"
                or value.get("scope") != "single_image"):
            raise ValueError("Souhlas musí výslovně zahrnovat jednotlivý snímek MZA přes IIIF.")
        for field in ("statement", "evidence_reference"):
            if not isinstance(value.get(field), str) or not value[field].strip():
                raise ValueError("Chybí potvrzení souhlasu nebo jeho dohledatelný podklad.")
        if datetime.fromisoformat(value["recorded_at"]).tzinfo is None:
            raise ValueError("Čas potvrzení musí obsahovat časové pásmo.")
        if value.get("expires_at"):
            expiry = datetime.fromisoformat(value["expires_at"])
            if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
                raise ValueError("Souhlas již vypršel nebo má neplatnou dobu platnosti.")
        interval = value.get("min_interval_seconds", 2)
        if type(interval) not in (int, float) or not math.isfinite(interval) or not 2 <= interval <= 60:
            raise ValueError("Odstup požadavků musí být 2–60 sekund.")
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Neplatný soukromý záznam souhlasu.") from exc
    return {**value, "sha256": hashlib.sha256(raw).hexdigest(), "min_interval_seconds": interval}


def live_url(url):
    if not isinstance(url, str) or len(url) > 4096 or re.search(r"[\s\\\x00-\x1f]", url):
        raise ValueError("Neplatná síťová URL MZA.")
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc not in HOSTS or parts.fragment:
        raise ValueError("Povoleny jsou pouze HTTPS domény www.mza.cz a iipserver.mza.cz bez přístupových údajů.")
    if parts.netloc == "www.mza.cz" and parts.path.startswith("/actapublica/matrika/detail/"):
        return mza.archive_url(url)
    if not re.fullmatch(r"/iipsrv/+iipsrv\.fcgi", parts.path):
        raise ValueError("Nepovolená cesta obrazové služby MZA.")
    query = parse_qs(parts.query, strict_parsing=True, max_num_fields=1)
    if set(query) != {"IIIF"} or len(query["IIIF"]) != 1:
        raise ValueError("Očekáván jediný obrazový požadavek IIIF.")
    resource = query["IIIF"][0]
    if not re.fullmatch(
        r"/srv/[A-Za-z0-9/_-]+\.jp2(?:/info\.json|/(?:full|[0-9]+,[0-9]+,[0-9]+,[0-9]+)/(?:full|max|[0-9]+,[0-9]*)/0/default\.jpg)?",
        resource,
    ):
        raise ValueError("Nepovolený identifikátor nebo operace obrazové služby.")
    return url


def public_addresses(host):
    addresses = []
    for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        address = entry[4][0]
        ip = ipaddress.ip_address(address)
        if not ip.is_global or getattr(ip, "ipv4_mapped", None) is not None:
            raise ValueError("DNS MZA ukazuje na neveřejnou nebo mapovanou IP adresu; přístup zastaven.")
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise ValueError("DNS MZA nevrátilo veřejnou IP adresu.")
    return addresses


class HTTPSTransport:
    """Verify TLS for the hostname while connecting to the checked DNS address.

    No proxies, automatic redirects, cookie jars or alternate endpoints. The
    response is bounded before allocation, including chunked HTTP responses.
    """

    def __init__(self, *, capture_error_body=False):
        self.transferred = 0
        self.capture_error_body = capture_error_body

    def __call__(self, url, *, timeout, max_bytes):
        live_url(url)
        parts = urlsplit(url)
        address = public_addresses(parts.hostname)[0]
        context = ssl.create_default_context()
        connection = http.client.HTTPSConnection(parts.hostname, 443, timeout=timeout, context=context)
        # HTTPSConnection.connect still uses the original host for SNI and
        # certificate verification; only its TCP destination is pinned.
        connection._create_connection = lambda endpoint, seconds, source_address=None: socket.create_connection(
            (address, 443), seconds, source_address=source_address
        )
        deadline = time.monotonic() + timeout
        try:
            path = urlunsplit(("", "", parts.path, parts.query, ""))
            connection.request("GET", path, headers={
                "User-Agent": "family-tree-chatgpt/0.6.0 (single-image research)",
                "Accept-Encoding": "identity", "Connection": "close",
            })
            active_socket = connection.sock
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            active_socket.settimeout(remaining)
            response = connection.getresponse()
            headers = {key.lower(): value for key, value in response.getheaders()}
            if (response.status in (401, 403, 429) or 300 <= response.status < 400) and not self.capture_error_body:
                return response.status, headers, b""
            length = headers.get("content-length")
            if length is not None and (not length.isdigit() or int(length) > min(max_bytes, mza.MAX_TRANSFER_BYTES - self.transferred)):
                raise ValueError("Odpověď MZA překračuje povolenou velikost.")
            if headers.get("content-encoding", "identity").lower() != "identity":
                raise ValueError("Komprimovaný HTTP přenos není podporován.")
            chunks, size = [], 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                if active_socket.fileno() != -1:
                    active_socket.settimeout(remaining)
                chunk = response.read(min(65536, max_bytes + 1 - size, mza.MAX_TRANSFER_BYTES + 1 - self.transferred))
                if not chunk:
                    break
                size += len(chunk)
                self.transferred += len(chunk)
                if size > max_bytes or self.transferred > mza.MAX_TRANSFER_BYTES:
                    raise ValueError("Odpověď MZA překračuje povolenou velikost.")
                chunks.append(chunk)
            if length is not None and size != int(length):
                raise ValueError("Neúplná odpověď MZA.")
            return response.status, headers, b"".join(chunks)
        except TimeoutError:
            raise
        except ssl.SSLError as exc:
            raise ValueError("TLS ověření MZA selhalo; certifikáty se nesmí obcházet.") from exc
        except (http.client.HTTPException, OSError) as exc:
            raise ValueError("Spojení s MZA selhalo; operace byla ukončena.") from exc
        finally:
            connection.close()


def discover_service(html, detail_url):
    """Use only a complete published source for the exact selected JP2.

    IIPImage's documented IIIF selector replaces Deepzoom on the same endpoint
    and exact resource. No directory or filename is guessed or substituted.
    """
    selected = parse_qs(urlsplit(detail_url).query).get("image", [])
    if len(selected) != 1:
        raise ValueError("Stažení vyžaduje URL jednoho snímku s parametrem image.")
    text = unescape(html).replace("\\/", "/").replace("\\u0026", "&")
    found = set()
    for candidate in re.findall(r'https://[^\s\x00-\x1f"\'<>]+', text):
        parts = urlsplit(candidate)
        try:
            query = parse_qs(parts.query, strict_parsing=True, max_num_fields=1)
        except ValueError:
            continue
        if len(query) != 1:
            continue
        protocol = next(iter(query))
        if protocol not in ("IIIF", "Deepzoom") or len(query[protocol]) != 1:
            continue
        resource = query[protocol][0].removesuffix("/info.json").removesuffix(".dzi")
        if resource.rsplit("/", 1)[-1] != selected[0]:
            continue
        base = urlunsplit((parts.scheme, parts.netloc, parts.path, "IIIF=" + quote(resource, safe="/,-_."), ""))
        live_url(base)
        found.add(base)
    if len(found) != 1:
        raise ValueError("Stránka nedokládá jediný úplný obrazový zdroj vybraného snímku; adresu neodhaduji.")
    return found.pop()


class ResponseDiagnostics:
    """Explicit private response capture, excluding credential headers and fields."""

    def __init__(self, directory):
        candidate = Path(directory).expanduser()
        if candidate.is_symlink() or research.in_git_tree(candidate.resolve()):
            raise ValueError("Diagnostiku ulož do nové soukromé složky mimo Git, nikoli symlinku.")
        self.root = candidate.resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.count = 0

    def write(self, name, data):
        fd = os.open(self.root / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)

    @staticmethod
    def redact(body):
        names = rb"(?:_token|token|csrf(?:[_-]?token)?|authenticity_token|(?:access|refresh|auth)[_-]?token|password|authorization)"
        def credential_tag(match):
            tag = match.group(0)
            if re.search(rb"\bname\s*=\s*[\"']?" + names + rb"(?:[\"'\s>])", tag, re.I):
                tag = re.sub(rb"\b(value|content)\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
                             lambda value: value[1] + b'="[REDACTED]"', tag, flags=re.I)
            return tag
        value = re.sub(rb"<(?:input|meta)\b[^>]*>", credential_tag, body, flags=re.I)
        return re.sub(rb"([\"']?" + names + rb"[\"']?\s*[:=]\s*)([\"'])(.*?)\2",
                      lambda match: match[1] + match[2] + b"[REDACTED]" + match[2], value, flags=re.I | re.S)

    def __call__(self, url, status, headers, body, diagnosis):
        self.count += 1
        prefix = f"response-{self.count:04d}"
        textual = diagnosis["is_html"] or "json" in headers.get("content-type", "").lower()
        saved = self.redact(body) if textual else body
        suffix = ".html" if diagnosis["is_html"] else ".json" if textual else ".bin"
        self.write(prefix + suffix, saved)
        metadata = {
            "at": research.now(), "url": url, "status": status,
            "headers": {key: value for key, value in headers.items() if key in (
                "content-type", "content-length", "retry-after", "date"
            )},
            "diagnosis": diagnosis, "body_file": prefix + suffix,
            "received_size_bytes": len(body), "received_sha256": hashlib.sha256(body).hexdigest(),
            "saved_size_bytes": len(saved), "saved_sha256": hashlib.sha256(saved).hexdigest(),
            "redacted": saved != body,
        }
        self.write(prefix + ".metadata.json", (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode())

    def finish(self, *, error=None):
        self.write("attempt.json", (json.dumps({
            "at": research.now(), "responses": self.count, "error": error,
        }, ensure_ascii=False, indent=2) + "\n").encode())


def download(root, url, *, diagnostics_dir=None, **options):
    with acquisition_lock():
        diagnostics = ResponseDiagnostics(diagnostics_dir) if diagnostics_dir is not None else None
        try:
            result = _download(root, url, observer=diagnostics, **options)
        except (ValueError, OSError) as exc:
            if diagnostics is not None:
                diagnostics.finish(error=str(exc))
                raise ValueError(f"{exc} Diagnostika: {diagnostics.root}") from exc
            raise
        if diagnostics is not None:
            diagnostics.finish()
            result["diagnostics_dir"] = str(diagnostics.root)
        return result


def _download(root, url, *, permission_file=None, reference="", image_number=None,
             expected_revision=None, transport=None, sleep=time.sleep, observer=None):
    permission = load_permission(permission_file)
    root = research.private_workspace(root)
    mza.archive_url(url)
    if image_number is not None and (type(image_number) is not int or image_number < 1):
        raise ValueError("Číslo snímku musí být kladné celé číslo.")
    if "image" not in parse_qs(urlsplit(url).query):
        raise ValueError("Stažení vyžaduje URL jednoho snímku s parametrem image.")
    state = research.read_state(root)
    errors = research.check_state(state, root)
    if errors:
        raise ValueError("\n".join(errors))
    if expected_revision is not None and state["revision"] != expected_revision:
        raise ValueError("Stav se mezitím změnil; znovu načti resume.")
    # A URL already imported can be inspected without contacting the archive.
    existing = [key for key, record in state["records"].items()
                if record["source"].get("url") == url and record["source"].get("acquisition")]
    if existing:
        return {"downloaded": False, "already_stored": True, "record_ids": existing,
                "network_accessed": False, "inspection": mza.inspect(url, root, permission_file=permission_file)}
    def authorized_url(candidate):
        current = load_permission(permission_file)
        if current["sha256"] != permission["sha256"]:
            raise ValueError("Evidence souhlasu se mezitím změnila; operace byla zastavena.")
        return live_url(candidate)

    session = mza.IIIFSession(transport or HTTPSTransport(capture_error_body=observer is not None), validator=authorized_url,
                              interval=permission["min_interval_seconds"], sleep=sleep, observer=observer)
    html = session.get(url, 2 * 1024 * 1024, allow_html=True)
    try:
        base = discover_service(html.decode("utf-8"), url)
    except UnicodeError as exc:
        raise ValueError("Stránka MZA není platné UTF-8.") from exc
    # Root-level staging is excluded from project bundles. On a failed import,
    # keep the complete copy so it can be imported without another HTTP request.
    directory = Path(tempfile.mkdtemp(prefix=".mza-acquisition-", dir=root))
    output = directory / "scan.png"
    try:
        image = session.acquire(base + "/info.json", output)
        live_verified = transport is None or getattr(transport, "live_access_verifiable", False) is True
        image["live_mza_verified"] = live_verified
        evidence = {key: permission[key] for key in (
            "basis", "statement", "recorded_at", "evidence_reference", "scope", "sha256", "min_interval_seconds"
        )}
        extra = {"permission": evidence, "iiif": {
            "info_url": base + "/info.json", "version": image["iiif_version"],
            "request_count": session.count, "image_requests": image["image_requests"],
            "live_access_verified": live_verified,
        }}
        browser_session = getattr(transport, "verified_browser_session", None)
        if browser_session is not None:
            extra["browser_session"] = browser_session
        result = mza.import_image(
            root, output, url, method="iiif_assembled", reference=reference,
            image_number=image_number, expected_revision=expected_revision,
            provenance_note="IIIF; souhlas potvrzen uživatelem: " + permission["evidence_reference"],
            acquisition_extra=extra,
        )
        return {**result, "downloaded": True, "network_accessed": True,
                "iiif": image, "request_count": session.count,
                "permission": evidence}
    except (ValueError, OSError) as exc:
        if output.exists():
            raise ValueError(f"Získaná úplná kopie zůstává pro ruční import v {output}: {exc}") from exc
        raise
    finally:
        # Remove staging only after a successful import or before any file exists.
        if not output.exists():
            directory.rmdir()
        elif "result" in locals():
            output.unlink()
            directory.rmdir()
