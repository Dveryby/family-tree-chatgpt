"""Manual-session policy and synthetic browser tests; no requests reach MZA."""
import asyncio
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

import test_mza_live
from test_mza_live import LiveMock, LIVE_BASE
from test_mza import URL
import mza
import mza_browser
import mza_live
import research


def confirmation():
    return {"schema_version": 1, "session_id": "a" * 32,
            "manual_confirmed_at": research.now(), "same_browser_context": True,
            "cookies_exported": False, "transport": "browser_fetch", "manual_request_count": 4}


def request(url=URL, method="GET", resource_type="document", **options):
    return SimpleNamespace(url=url, method=method, resource_type=resource_type,
                           redirected_from=options.get("redirected_from"), frame=options.get("frame"))


class BrowserPolicyTests(unittest.TestCase):
    def test_manual_native_verification_allowed_but_viewer_and_other_origins_blocked(self):
        policy = mza_browser.BrowserPolicy(URL)
        for item in (request(), request("https://www.mza.cz/actapublica/assets/altcha/altcha.min.js", resource_type="script"),
                     request("https://www.mza.cz/actapublica/altcha/challenge", resource_type="fetch"),
                     request("https://www.mza.cz/actapublica/altcha/verify", "POST", "fetch")):
            self.assertTrue(policy.allow(item))
        for item in (request(LIVE_BASE + "/info.json", resource_type="fetch"),
                     request(URL.replace("001", "002")), request(URL.replace("https:", "http:")),
                     request("https://example.invalid/"), request("https://www.mza.cz:444/actapublica/assets/x", resource_type="script"),
                     request("https://www.mza.cz/actapublica/altcha/verify", "GET", "fetch")):
            self.assertFalse(policy.allow(item))
        self.assertEqual(policy.request_count, 4)

    def test_download_permits_exact_single_fetch_in_original_frame_and_no_verification(self):
        policy = mza_browser.BrowserPolicy(URL)
        frame = object()
        policy.phase, policy.page = "download", SimpleNamespace(main_frame=frame)
        policy.expected_url = LIVE_BASE + "/info.json"
        self.assertFalse(policy.allow(request(policy.expected_url, resource_type="fetch", frame=object())))
        self.assertFalse(policy.allow(request(policy.expected_url + "x", resource_type="fetch", frame=frame)))
        self.assertFalse(policy.allow(request("https://www.mza.cz/actapublica/altcha/verify", "POST", "fetch", frame=frame)))
        self.assertTrue(policy.allow(request(policy.expected_url, resource_type="fetch", frame=frame)))
        self.assertFalse(policy.allow(request(policy.expected_url, resource_type="fetch", frame=frame)))

    def test_status_redirect_and_budget_stop_future_requests(self):
        for status in (301, 302, 401, 403, 429):
            policy = mza_browser.BrowserPolicy(URL)
            policy.response(SimpleNamespace(status=status))
            self.assertFalse(policy.allow(request()))
        policy = mza_browser.BrowserPolicy(URL)
        self.assertFalse(policy.allow(request(redirected_from=object())))
        self.assertIsNotNone(policy.fatal)
        policy = mza_browser.BrowserPolicy(URL)
        policy.request_count = mza.MAX_REQUESTS
        self.assertFalse(policy.allow(request()))

    def test_permission_revocation_stops_even_native_verification(self):
        guard = Mock(side_effect=[None, ValueError("synthetic revocation")])
        policy = mza_browser.BrowserPolicy(URL, guard)
        self.assertTrue(policy.allow(request()))
        self.assertFalse(policy.allow(request("https://www.mza.cz/actapublica/altcha/verify", "POST", "fetch")))
        self.assertFalse(policy.allow(request()))
        self.assertEqual(guard.call_count, 2)
        self.assertIsNotNone(policy.fatal)

    def test_dns_is_pinned_and_private_ip_rejected_before_browser_launch(self):
        with patch.object(mza_live, "public_addresses", return_value=["2606:4700:4700::1111"]):
            rules = mza_browser.resolver_rules()
            self.assertIn("MAP www.mza.cz [2606:4700:4700::1111]", rules)
            self.assertIn("MAP iipserver.mza.cz [2606:4700:4700::1111]", rules)
        with patch.object(mza_live.socket, "getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                mza_browser.resolver_rules()


class BrowserTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.context = object()
        self.page = SimpleNamespace(context=self.context, url=URL, is_closed=Mock(return_value=False),
                                    evaluate=AsyncMock(), main_frame=object())
        self.policy = mza_browser.BrowserPolicy(URL)
        self.policy.phase, self.policy.page = "download", self.page
        self.client = mza_browser.BrowserTransport(self.page, self.context, self.policy,
                                                   asyncio.get_running_loop(), confirmation())

    async def test_worker_bridge_uses_original_page_and_counts_partial_timeout(self):
        self.page.evaluate.side_effect = [{"error": "timeout", "received": 3},
                                         {"status": 200, "headers": {}, "body": base64.b64encode(b"ok").decode(), "received": 2}]
        with self.assertRaises(TimeoutError):
            await asyncio.to_thread(self.client, URL, timeout=1, max_bytes=10)
        self.assertEqual(await asyncio.to_thread(self.client, URL, timeout=1, max_bytes=10), (200, {}, b"ok"))
        self.assertEqual(self.client.transferred, 5)
        self.assertIsNone(self.policy.expected_url)

    async def test_changed_or_closed_tab_and_context_rejected_before_fetch(self):
        for change in ({"url": URL.replace("001", "002")}, {"context": object()}, {"is_closed": Mock(return_value=True)}):
            old = {key: getattr(self.page, key) for key in change}
            for key, value in change.items():
                setattr(self.page, key, value)
            with self.assertRaises(ValueError):
                await self.client.fetch(URL, 1, 10)
            for key, value in old.items():
                setattr(self.page, key, value)
        self.page.evaluate.assert_not_called()

    async def test_network_cors_malformed_and_oversized_results_do_not_fall_back(self):
        for result in (None, {"received": -1}, {"received": True}, {"received": 11},
                       {"received": 1, "error": "browser_network"},
                       {"received": 1, "body": "!", "status": 200, "headers": {}},
                       {"received": 1, "body": "", "status": 200, "headers": {}},
                       {"received": 1, "body": "YQ==", "status": True, "headers": {}}):
            self.client.transferred = 0
            self.page.evaluate.return_value = result
            with self.subTest(result=result), patch.object(mza_live, "HTTPSTransport", side_effect=AssertionError("fallback")):
                with self.assertRaises(ValueError):
                    await self.client.fetch(URL, 1, 10)
        self.page.evaluate.side_effect = RuntimeError("synthetic browser closed")
        with self.assertRaisesRegex(ValueError, "jiný síťový klient nebyl použit"):
            await self.client.fetch(URL, 1, 10)


class BrowserMetadataTests(unittest.TestCase):
    def setUp(self):
        # Reuse the synthetic consent/workspace fixture without inheriting its tests.
        self.fixture = test_mza_live.LiveMZATests(methodName="test_duplicate_download_uses_local_copy_without_network")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_browser_provenance_validated_and_exported_without_changing_reading(self):
        server = LiveMock()
        server.verified_browser_session = confirmation()
        result = self.fixture.acquire(server)
        state = research.read_state(self.fixture.root)
        record = state["records"][result["record_id"]]
        acquisition = record["source"]["acquisition"]
        self.assertEqual(acquisition["browser_session"], confirmation() | {"manual_confirmed_at": acquisition["browser_session"]["manual_confirmed_at"]})
        self.assertFalse(acquisition["iiif"]["live_access_verified"])
        self.assertEqual(record["reading_status"], "unread")
        self.assertFalse(state["claims"])
        bundle = self.fixture.base / "browser.zip"
        research.export_bundle(self.fixture.root, bundle)
        restored = self.fixture.base / "restored-browser"
        research.restore_bundle(restored, bundle)
        self.assertEqual(research.read_state(restored), state)
        for change in ({"cookies_exported": True}, {"same_browser_context": False}, {"schema_version": True},
                       {"manual_confirmed_at": "2026-11-14"}, {"manual_request_count": 0}, {"session_id": "cookie-value"}):
            broken = deepcopy(state)
            broken["records"][result["record_id"]]["source"]["acquisition"]["browser_session"].update(change)
            with self.subTest(change=change):
                self.assertTrue(research.check_state(broken, self.fixture.root))

    def test_duplicate_and_invalid_input_do_not_open_browser(self):
        self.fixture.acquire()
        with patch.object(mza_browser, "resolver_rules", side_effect=AssertionError("browser")):
            result = mza_browser.download(self.fixture.root, URL, permission_file=self.fixture.permission)
        self.assertFalse(result["network_accessed"])
        for options in ({"manual_timeout": 0}, {"manual_timeout": float("nan")}, {"browser_channel": "remote"},
                        {"expected_revision": 123}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                mza_browser.download(self.fixture.root, URL, permission_file=self.fixture.permission, **options)


@unittest.skipUnless(os.environ.get("FAMILY_TREE_BROWSER_TEST") == "1", "optional real-browser fixture")
class NativeBrowserTests(unittest.IsolatedAsyncioTestCase):
    """Every HTTPS request is fulfilled/aborted locally, including native verification.

    Clicks below act ONLY on this synthetic fixture, never a real archive challenge.
    The fixture's HttpOnly cookie is verified server-side, not exported by the product.
    """

    async def asyncSetUp(self):
        from playwright.async_api import async_playwright
        self.driver = await async_playwright().start()
        self.addAsyncCleanup(self.driver.stop)
        self.browser = await self.driver.chromium.launch(channel="chrome", headless=False, chromium_sandbox=True)
        self.addAsyncCleanup(self.browser.close)
        self.fixture = test_mza_live.LiveMZATests(methodName="test_duplicate_download_uses_local_copy_without_network")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    async def session(self, *, tiled=False, version=3, cors=True, image_status=200):
        context = await self.browser.new_context(service_workers="block", accept_downloads=False)
        self.addAsyncCleanup(context.close)
        policy = mza_browser.BrowserPolicy(URL)
        server = LiveMock(tiled=tiled, version=version)
        accepted, blocked = [], []
        async def fixture_route(route):
            req = route.request
            if not policy.allow(req):
                blocked.append(req.url)
                await route.abort()
                return
            headers = await req.all_headers()
            has_session = "synthetic_verified=yes" in headers.get("cookie", "")
            accepted.append((req.url, req.method, has_session))
            if req.url.endswith("/altcha/challenge"):
                await route.fulfill(json={"synthetic": True})
            elif req.url.endswith("/altcha/verify"):
                await route.fulfill(body="ok", headers={"Set-Cookie": "synthetic_verified=yes; Domain=mza.cz; Path=/; Secure; HttpOnly; SameSite=None"})
            elif req.url == URL and policy.phase == "manual":
                if has_session:
                    body = server(URL, timeout=1, max_bytes=10000)[2].decode()
                else:
                    body = """<html><altcha-widget></altcha-widget><button id="native">Synthetic verification</button>
                    <script>document.getElementById('native').onclick = async () => {
                        await fetch('/actapublica/altcha/challenge');
                        await fetch('/actapublica/altcha/verify', {method:'POST', body:'synthetic'});
                        location.reload();
                    };</script></html>"""
                await route.fulfill(content_type="text/html", body=body)
            elif not has_session:
                await route.fulfill(status=403, body="synthetic session missing")
            else:
                status, outgoing, body = server(req.url, timeout=1, max_bytes=64 * 1024 * 1024)
                if req.url.startswith(LIVE_BASE):
                    if cors:
                        outgoing.update({"Access-Control-Allow-Origin": "https://www.mza.cz", "Access-Control-Allow-Credentials": "true"})
                    else:
                        outgoing["Access-Control-Allow-Origin"] = "https://different.example.invalid"
                    if not req.url.endswith("info.json"):
                        status = image_status
                await route.fulfill(status=status, headers=outgoing, body=body)
        # Strict intercept: even unrecognized or denied requests never reach the network.
        await context.route("**/*", fixture_route)
        context.on("response", policy.response)
        control = await context.new_page()
        pending = asyncio.create_task(mza_browser.confirmed_page(context, control, policy, 20))
        await control.locator("a").wait_for()
        async with context.expect_page() as popup:
            await control.locator("a").click()
        page = await popup.value
        await page.locator("#native").wait_for()
        # An early confirmation cannot proceed through the remaining gate.
        await control.locator("#continue").click()
        await control.locator("#status").filter(has_text="ještě není dokončené").wait_for()
        self.assertFalse(pending.done())
        await page.locator("#native").click()
        await page.wait_for_function("!document.querySelector('altcha-widget')")
        await control.locator("#continue").click()
        verified, evidence = await pending
        self.assertIs(verified, page)
        client = mza_browser.BrowserTransport(page, context, policy, asyncio.get_running_loop(), evidence)
        return context, page, policy, client, accepted, blocked

    async def test_cookie_bound_full_and_tiles_use_verified_context_then_preserve_state(self):
        for version, tiled in ((2, False), (3, True)):
            with self.subTest(version=version, tiled=tiled):
                context, page, policy, client, accepted, blocked = await self.session(version=version, tiled=tiled)
                root = self.fixture.base / f"native-{version}"
                research.initialize(root)
                result = await asyncio.to_thread(mza_live._download, root, URL,
                                                permission_file=self.fixture.permission, transport=client, sleep=Mock())
                self.assertTrue(result["downloaded"])
                controlled = accepted[client.verified_browser_session["manual_request_count"]:]
                self.assertEqual(len(controlled), 14 if tiled else 3)
                self.assertTrue(all(has_cookie for _, _, has_cookie in controlled))
                self.assertTrue(all(method == "GET" for _, method, _ in controlled))
                self.assertFalse(blocked)
                state = research.read_state(root)
                self.assertFalse(research.check_state(state, root))
                record = state["records"][result["record_id"]]
                self.assertEqual(record["reading_status"], "unread")
                self.assertFalse(record["source"]["acquisition"]["iiif"]["live_access_verified"])
                await context.close()

    async def test_cors_and_http_block_stop_without_changing_state_or_new_client(self):
        for options in ({"cors": False}, {"image_status": 403}):
            with self.subTest(options=options):
                context, _, _, client, accepted, _ = await self.session(**options)
                root = self.fixture.base / ("cors-denied" if "cors" in options else "http-denied")
                research.initialize(root)
                with patch.object(mza_live, "HTTPSTransport", side_effect=AssertionError("fallback")):
                    with self.assertRaises(ValueError):
                        await asyncio.to_thread(mza_live._download, root, URL,
                                                permission_file=self.fixture.permission, transport=client, sleep=Mock())
                self.assertEqual(research.read_state(root)["revision"], 0)
                self.assertFalse(list((root / "sources").iterdir()))
                count = len(accepted)
                await asyncio.sleep(0.05)
                self.assertEqual(len(accepted), count)
                await context.close()

    async def test_manual_cancel_timeout_and_control_page_close(self):
        for action in ("cancel", "close", "timeout"):
            with self.subTest(action=action):
                context = await self.browser.new_context(service_workers="block")
                await context.route("**/*", lambda route: route.abort())
                control = await context.new_page()
                pending = asyncio.create_task(mza_browser.confirmed_page(context, control, mza_browser.BrowserPolicy(URL), 0.15 if action == "timeout" else 5))
                await control.locator("#cancel").wait_for()
                if action == "cancel":
                    await control.locator("#cancel").click()
                elif action == "close":
                    await control.close()
                with self.assertRaises(ValueError):
                    await pending
                await context.close()

    async def test_public_browser_command_cancels_before_network_and_closes_context(self):
        captured = []
        original = mza_browser.confirmed_page
        async def local_cancel(context, control, policy, timeout):
            captured.append(control)
            task = asyncio.create_task(original(context, control, policy, timeout))
            await control.locator("#cancel").wait_for()
            await control.locator("#cancel").click()
            return await task
        diagnostics = self.fixture.base / "cancel-diagnostics"
        with patch.object(mza_browser, "confirmed_page", local_cancel), \
                patch.object(mza_browser, "resolver_rules", return_value="--host-resolver-rules=MAP * ~NOTFOUND"), \
                patch.object(mza_live, "_download", side_effect=AssertionError("no acquisition before confirmation")):
            with self.assertRaisesRegex(ValueError, "zrušeno.*Diagnostika"):
                await asyncio.to_thread(mza_browser.download, self.fixture.root, URL,
                                        permission_file=self.fixture.permission, diagnostics_dir=diagnostics)
        self.assertTrue(captured[0].is_closed())
        self.assertEqual(json.loads((diagnostics / "attempt.json").read_text())["responses"], 0)
        self.assertEqual(research.read_state(self.fixture.root)["revision"], 0)


if __name__ == "__main__":
    unittest.main()
