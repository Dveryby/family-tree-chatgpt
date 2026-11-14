"""Synthetic HTML distinguishes challenge controls from ordinary references."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/family-tree-chatgpt/scripts"))
import mza

URL = "https://iiif.example.invalid/synthetic"


class ProtectionDetectionTests(unittest.TestCase):
    def diagnosis(self, html, *, allow_html=True):
        return mza.response_diagnosis(200, {"content-type": "text/html"}, html.encode(), allow_html)

    def test_scripts_styles_comments_links_and_prose_do_not_block(self):
        pages = [
            '<html><script src="/js/altcha.min.js"></script><main>Matrika</main></html>',
            '<html><script src="https://www.google.com/recaptcha/api.js"></script></html>',
            '<html><script>const captcha = "altcha"; const sample = "<altcha-widget>";</script></html>',
            '<html><link rel="preload" href="/captcha.js"><style>.g-recaptcha {color: red}</style></html>',
            '<html><!-- <altcha-widget challengeurl="/challenge"> --><a href="/captcha">Nápověda CAPTCHA</a></html>',
            '<html><p>Altcha a CAPTCHA jsou popsány v nápovědě.</p></html>',
            '<html><div class><script src="/altcha.js"></script></div></html>',
        ]
        for page in pages:
            with self.subTest(page=page):
                result = self.diagnosis(page)
                self.assertEqual(result["classification"], "ok")
                self.assertEqual(result["signals"], [])

    def test_templates_and_explicitly_hidden_controls_do_not_block(self):
        for page in (
            '<template><altcha-widget challengeurl="/challenge"></altcha-widget></template>',
            '<div hidden><altcha-widget></altcha-widget></div>',
            '<div aria-hidden="true"><div class="g-recaptcha" data-sitekey="public"></div></div>',
            '<altcha-widget style="display: none"></altcha-widget>',
            '<div inert><form id="challenge-form"></form></div>',
        ):
            with self.subTest(page=page):
                self.assertEqual(self.diagnosis(page)["classification"], "ok")

    def test_visible_challenge_controls_stop(self):
        for page, signal in (
            ('<html><altcha-widget challengeurl="/challenge"></altcha-widget></html>', "altcha_widget"),
            ('<div class="g-recaptcha" data-sitekey="public"></div>', "g-recaptcha"),
            ('<div class="h-captcha" data-sitekey="public"></div>', "h-captcha"),
            ('<div class="cf-turnstile" data-sitekey="public"></div>', "cf-turnstile"),
            ('<html><form id="challenge-form" action="/verify"></form></html>', "challenge_form"),
        ):
            with self.subTest(page=page):
                result = self.diagnosis(page)
                self.assertEqual(result["classification"], "active_challenge")
                self.assertIn(signal, result["signals"])

    def test_plain_json_and_binary_words_are_not_challenges(self):
        for body, content_type in ((b'{"label":"captcha altcha"}', "application/json"),
                                   (b'\xff\xd8 captcha altcha \xff\xd9', "image/jpeg")):
            result = mza.response_diagnosis(200, {"content-type": content_type}, body)
            self.assertEqual(result["classification"], "ok")
            self.assertFalse(result["is_html"])

    def test_automatic_gate_widget_still_blocks_when_only_one_pixel_wide(self):
        page = ('<html><div id="altcha-gate"><p>SYNTHETIC verification</p>'
                '<altcha-widget id="altcha-gate-widget" auto challenge="SYNTHETIC" '
                'style="position:absolute; width:1px; height:1px; overflow:hidden;"></altcha-widget>'
                '</div></html>')
        self.assertEqual(self.diagnosis(page)["classification"], "active_challenge")

    def test_html_instead_of_iiif_has_separate_protocol_error(self):
        result = self.diagnosis('<html><script src="/altcha.js"></script></html>', allow_html=False)
        self.assertEqual(result["classification"], "unexpected_html")
        self.assertEqual(result["signals"], [])

    def test_http_statuses_take_precedence_and_do_not_need_keywords(self):
        for status, expected in ((401, "http_401"), (403, "http_403"), (429, "http_429"),
                                 (302, "redirect"), (404, "http_error")):
            self.assertEqual(mza.response_diagnosis(status, {}, b"")["classification"], expected)
        self.assertEqual(mza.response_diagnosis(403, {"content-type": "text/html"}, b"<div>" * 513)["classification"], "http_403")

    def test_only_real_challenge_stops_session_after_successful_page(self):
        transport = Mock(side_effect=[
            (200, {"Content-Type": "text/html"}, b'<html><script src="/altcha.js"></script></html>'),
            (200, {"Content-Type": "text/html"}, b'<html><altcha-widget></altcha-widget></html>'),
        ])
        client = mza.IIIFSession(transport, sleep=Mock())
        client.get(URL, 4096, allow_html=True)
        with self.assertRaisesRegex(ValueError, "active_challenge.*altcha_widget"):
            client.get(URL, 4096, allow_html=True)
        with self.assertRaises(ValueError):
            client.get(URL, 4096, allow_html=True)
        self.assertEqual(transport.call_count, 2)


if __name__ == "__main__":
    unittest.main()
