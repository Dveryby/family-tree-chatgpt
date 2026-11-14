"""Headed, manually confirmed MZA session. Credentials never leave the browser."""
import asyncio
import base64
import concurrent.futures
from html import escape
import ipaddress
import math
import time
from urllib.parse import parse_qs, urlsplit
import uuid

import mza
import mza_live
import research


FETCH_IMAGE = r"""async ({url, limit, timeout}) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout * 1000);
    let received = 0;
    try {
        const response = await fetch(url, {
            credentials: 'include', redirect: 'error', cache: 'no-store',
            signal: controller.signal
        });
        const headers = {};
        for (const name of ['content-type', 'content-length', 'retry-after', 'date']) {
            const value = response.headers.get(name);
            if (value !== null) headers[name] = value;
        }
        const length = headers['content-length'];
        if (length !== undefined && (!/^\d+$/.test(length) || Number(length) > limit)) {
            controller.abort();
            return {error: 'size_limit', received};
        }
        const reader = response.body.getReader();
        const chunks = [];
        while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            received += value.byteLength;
            if (received > limit) {
                controller.abort();
                return {error: 'size_limit', received};
            }
            chunks.push(value);
        }
        // Chrome decodes compressed HTTP bodies; Content-Length can describe
        // the compressed bytes. A truncated stream rejects reader.read().
        const data = new Uint8Array(received);
        let offset = 0;
        for (const chunk of chunks) { data.set(chunk, offset); offset += chunk.length; }
        let binary = '';
        for (let i = 0; i < data.length; i += 16384) {
            binary += String.fromCharCode(...data.subarray(i, i + 16384));
        }
        return {status: response.status, headers, body: btoa(binary), received};
    } catch (error) {
        return {error: error.name === 'AbortError' ? 'timeout' : 'browser_network', received};
    } finally { clearTimeout(timer); }
}"""


def selected_page(actual, expected):
    try:
        mza.archive_url(actual)
        a, b = urlsplit(actual), urlsplit(expected)
        return a.path.rstrip('/') == b.path.rstrip('/') and parse_qs(a.query) == parse_qs(b.query)
    except ValueError:
        return False


def resolver_rules():
    rules = []
    for host in mza_live.HOSTS:
        addresses = mza_live.public_addresses(host)
        address = next((ip for ip in addresses if ipaddress.ip_address(ip).version == 4), addresses[0])
        if ipaddress.ip_address(address).version == 6:
            address = f"[{address}]"
        rules.append(f"MAP {host} {address}")
    return "--host-resolver-rules=" + ",".join(rules)


class BrowserPolicy:
    """Manual native page flow, followed by one controlled fetch at a time."""

    def __init__(self, url, permission_check=None):
        self.url = url
        self.permission_check = permission_check
        self.phase = "manual"
        self.fatal = None
        self.page = None
        self.expected_url = None
        self.consumed = False
        self.request_count = 0

    def allow(self, request):
        if self.fatal:
            return False
        parts = urlsplit(request.url)
        if parts.scheme != "https" or parts.netloc not in mza_live.HOSTS:
            return False
        if self.permission_check is not None:
            try:
                self.permission_check()
            except (ValueError, OSError):
                self.fatal = "Evidence souhlasu se změnila nebo není platná; operace byla zastavena."
                return False
        if request.redirected_from is not None:
            self.fatal = "Prohlížeč obdržel přesměrování; operace byla zastavena."
            return False
        if self.request_count >= mza.MAX_REQUESTS:
            self.fatal = "Prohlížeč překročil počet požadavků."
            return False
        if self.phase == "manual":
            # Only the user opens the selected document. Native archive scripts
            # may perform their own verification in that same visible page.
            allowed = parts.netloc == "www.mza.cz" and (
                (request.method == "GET" and selected_page(request.url, self.url))
                or (request.method == "GET" and parts.path.startswith("/actapublica/assets/")
                    and request.resource_type in ("script", "stylesheet", "font", "image"))
                or (request.method == "GET" and parts.path == "/actapublica/altcha/challenge" and not parts.query)
                or (request.method == "POST" and parts.path == "/actapublica/altcha/verify" and not parts.query)
            )
        else:
            allowed = (request.method == "GET" and request.url == self.expected_url
                       and request.resource_type in ("fetch", "xhr") and not self.consumed
                       and request.frame == self.page.main_frame)
            if allowed:
                mza_live.live_url(request.url)
                self.consumed = True
        if allowed:
            self.request_count += 1
        return allowed

    async def route(self, route):
        if self.allow(route.request):
            await route.continue_()
        else:
            await route.abort()

    def response(self, response):
        if response.status in (401, 403, 429) or 300 <= response.status < 400:
            self.fatal = f"HTTP {response.status} v prohlížeči; další požadavky byly zastaveny."


class BrowserTransport:
    """Synchronous IIIF bridge to fetch in the *original* verified page."""

    def __init__(self, page, context, policy, loop, confirmation, *, live_access_verifiable=False):
        self.page, self.context, self.policy, self.loop = page, context, policy, loop
        self.verified_browser_session = confirmation
        self.live_access_verifiable = live_access_verifiable
        self.transferred = 0

    def check_session(self):
        if (self.page.is_closed() or self.page.context != self.context
                or not selected_page(self.page.url, self.policy.url)):
            raise ValueError("Ověřená karta byla zavřena, změnila snímek nebo relaci; operace byla zastavena.")

    def __call__(self, url, *, timeout, max_bytes):
        future = asyncio.run_coroutine_threadsafe(self.fetch(url, timeout, max_bytes), self.loop)
        try:
            return future.result(timeout=timeout + 5)
        except concurrent.futures.TimeoutError as exc:
            if future.done():
                return future.result()
            future.cancel()
            raise ValueError("Prohlížeč neodpověděl; relaci je nutné zkontrolovat ručně.") from exc

    async def fetch(self, url, timeout, max_bytes):
        mza_live.live_url(url)
        self.check_session()
        if self.policy.fatal:
            raise ValueError(self.policy.fatal)
        limit = min(max_bytes, mza.MAX_TRANSFER_BYTES - self.transferred)
        if limit < 1:
            raise ValueError("Prohlížeč překročil přenosový limit.")
        self.policy.expected_url, self.policy.consumed = url, False
        try:
            result = await self.page.evaluate(FETCH_IMAGE, {"url": url, "limit": limit, "timeout": timeout})
        except Exception as exc:
            raise ValueError("Přístup v ověřené kartě selhal; jiný síťový klient nebyl použit.") from exc
        finally:
            self.policy.expected_url = None
        self.check_session()
        if not isinstance(result, dict):
            raise ValueError("Neplatná odpověď prohlížeče.")
        received = result.get("received")
        if type(received) is not int or received < 0:
            raise ValueError("Neplatná odpověď prohlížeče.")
        self.transferred += received
        if received > limit or self.transferred > mza.MAX_TRANSFER_BYTES:
            raise ValueError("Prohlížeč překročil přenosový limit.")
        if result.get("error") == "timeout":
            raise TimeoutError()
        if result.get("error"):
            raise ValueError("Prohlížeč odmítl obrazový požadavek (síť, CORS, přesměrování nebo velikost); bez dalšího klienta.")
        encoded = result.get("body")
        if not isinstance(encoded, str) or len(encoded) > ((received + 2) // 3) * 4:
            raise ValueError("Neplatná velikost obrazových dat prohlížeče.")
        try:
            body = base64.b64decode(encoded, validate=True)
        except (ValueError, KeyError) as exc:
            raise ValueError("Neplatná obrazová data prohlížeče.") from exc
        if len(body) != received:
            raise ValueError("Neúplná odpověď prohlížeče.")
        if type(result.get("status")) is not int or not 100 <= result["status"] <= 599 or not isinstance(result.get("headers"), dict):
            raise ValueError("Neplatný HTTP výsledek prohlížeče.")
        return result["status"], result["headers"], body


def control_html(url):
    return """<!doctype html><html lang="cs"><meta charset="utf-8"><title>Jeden snímek MZA</title>
    <body style="max-width:44em;margin:3em auto;font:18px sans-serif;line-height:1.6">
    <h1>Jeden snímek MZA</h1><ol>
    <li><a href=""" + '"' + escape(url, quote=True) + '"' + """ target="_blank" rel="noopener">Otevřít vybraný snímek v archivu</a>.</li>
    <li>V otevřené kartě dokončete ověření archivu. Pak se vraťte sem.</li>
    <li><button id="continue">Ověření je hotové — stáhnout jeden snímek</button></li></ol>
    <button id="cancel">Zrušit</button><p id="status" role="status">Čekám na vaše ověření.</p>
    <script>for (const action of ['continue', 'cancel']) {
        document.getElementById(action).addEventListener('click', event => {
            if (event.isTrusted) window.confirmMzaManual(action);
        });
    }</script></body></html>"""


async def confirmed_page(context, control, policy, manual_timeout):
    event = asyncio.Event()
    action = None
    async def confirm(source, value):
        nonlocal action
        if source["page"] == control and control.url == "about:blank" and value in ("continue", "cancel"):
            action = value
            event.set()
    await control.expose_binding("confirmMzaManual", confirm)
    control.on("close", lambda: event.set())
    context.on("close", lambda: event.set())
    await control.set_content(control_html(policy.url))
    deadline = time.monotonic() + manual_timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Čas pro ruční ověření vypršel; nic nebylo automaticky ověřeno.")
        try:
            await asyncio.wait_for(event.wait(), remaining)
        except asyncio.TimeoutError as exc:
            raise ValueError("Čas pro ruční ověření vypršel; nic nebylo automaticky ověřeno.") from exc
        event.clear()
        if action != "continue" or control.is_closed():
            raise ValueError("Ruční ověření bylo zrušeno.")
        if policy.fatal:
            raise ValueError(policy.fatal)
        pages = [page for page in context.pages if page != control and not page.is_closed()
                 and selected_page(page.url, policy.url)]
        if len(pages) != 1:
            await control.locator("#status").evaluate("el => el.textContent = 'Otevřete právě jednu kartu s vybraným snímkem.'")
            continue
        page = pages[0]
        diagnosis = mza.response_diagnosis(200, {"content-type": "text/html"}, (await page.content()).encode(), True)
        if diagnosis["classification"] != "ok":
            await control.locator("#status").evaluate("el => el.textContent = 'Ověření archivu ještě není dokončené. Dokončete je v kartě archivu a potvrďte znovu.'")
            continue
        policy.page, policy.phase = page, "download"
        return page, {"schema_version": 1, "session_id": uuid.uuid4().hex,
                      "manual_confirmed_at": research.now(), "same_browser_context": True,
                      "cookies_exported": False, "transport": "browser_fetch",
                      "manual_request_count": policy.request_count}


def download(root, url, *, permission_file=None, diagnostics_dir=None, reference="", image_number=None,
             expected_revision=None, manual_timeout=600, browser_channel="chrome"):
    if type(manual_timeout) not in (int, float) or not math.isfinite(manual_timeout) or not 5 <= manual_timeout <= 1800:
        raise ValueError("Čas pro ruční ověření musí být 5–1800 sekund.")
    if browser_channel not in ("chrome", "chromium"):
        raise ValueError("Podporován je Chrome nebo Chromium.")
    permission = mza_live.load_permission(permission_file)
    def permission_check():
        if mza_live.load_permission(permission_file)["sha256"] != permission["sha256"]:
            raise ValueError("Evidence souhlasu se změnila.")
    root = research.private_workspace(root)
    mza.archive_url(url)
    if "image" not in parse_qs(urlsplit(url).query):
        raise ValueError("Vyber jeden konkrétní snímek s parametrem image.")
    state = research.read_state(root)
    errors = research.check_state(state, root)
    if errors:
        raise ValueError("\n".join(errors))
    if expected_revision is not None and expected_revision != state["revision"]:
        raise ValueError("Stav se mezitím změnil; znovu načti resume.")
    if image_number is not None and (type(image_number) is not int or image_number < 1):
        raise ValueError("Číslo snímku musí být kladné celé číslo.")
    existing = [key for key, record in state["records"].items()
                if record["source"].get("url") == url and record["source"].get("acquisition")]
    if existing:
        return {"downloaded": False, "already_stored": True, "network_accessed": False,
                "record_ids": existing, "inspection": mza.inspect(url, root, permission_file=permission_file)}
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise ValueError("Browserový režim vyžaduje volitelné requirements-browser.txt a místní Chrome/Chromium.") from exc
    diagnostics = None
    with mza_live.acquisition_lock():
        try:
            diagnostics = mza_live.ResponseDiagnostics(diagnostics_dir) if diagnostics_dir is not None else None
            async def run():
                async with async_playwright() as driver:
                    browser = await driver.chromium.launch(
                        channel="chrome" if browser_channel == "chrome" else None,
                        headless=False, chromium_sandbox=True,
                        args=[resolver_rules(), "--no-proxy-server"],
                    )
                    try:
                        context = await browser.new_context(ignore_https_errors=False, service_workers="block", accept_downloads=False)
                        policy = BrowserPolicy(url, permission_check)
                        await context.route("**/*", policy.route)
                        await context.route_web_socket("**/*", lambda socket: socket.close())
                        context.on("response", policy.response)
                        control = await context.new_page()
                        page, confirmation = await confirmed_page(context, control, policy, manual_timeout)
                        client = BrowserTransport(page, context, policy, asyncio.get_running_loop(), confirmation,
                                                  live_access_verifiable=True)
                        return await asyncio.to_thread(
                            mza_live._download, root, url, permission_file=permission_file, reference=reference,
                            image_number=image_number, expected_revision=expected_revision,
                            transport=client, observer=diagnostics,
                        )
                    finally:
                        await browser.close()
            result = asyncio.run(run())
            if diagnostics is not None:
                diagnostics.finish()
                result["diagnostics_dir"] = str(diagnostics.root)
            return result
        except Exception as exc:
            if diagnostics is not None:
                diagnostics.finish(error=type(exc).__name__)
                detail = str(exc) if isinstance(exc, (ValueError, OSError)) else type(exc).__name__
                raise ValueError(f"{detail} Diagnostika: {diagnostics.root}") from exc
            if isinstance(exc, (ValueError, OSError)):
                raise
            raise ValueError("Browserový režim skončil bez přepnutí na jiný klient; ověř místní prohlížeč a relaci.") from exc
