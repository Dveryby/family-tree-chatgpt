"""Validate the skills-only ChatGPT/Codex plugin package."""
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]


def load_json(relative):
    return json.loads((REPO / relative).read_text(encoding="utf-8"))


class PluginPackageTests(unittest.TestCase):
    def setUp(self):
        self.version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
        self.portable = load_json("plugin.json")
        self.compatible = load_json(".codex-plugin/plugin.json")
        self.marketplace = load_json(".agents/plugins/marketplace.json")

    def test_portable_manifest_matches_release_and_layout(self):
        self.assertEqual(
            self.portable["$schema"],
            "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        )
        self.assertEqual(self.portable["name"], "family-tree-chatgpt")
        self.assertEqual(self.portable["version"], self.version)
        self.assertTrue(REPO.joinpath("skills/family-tree-chatgpt/SKILL.md").is_file())
        self.assertNotIn("skills", self.portable)

    def test_compatibility_manifest_stays_in_sync(self):
        interface = self.portable["extensions"]["com.openai"]["interface"]
        for field in ("name", "version", "description", "author", "repository", "license"):
            self.assertEqual(self.compatible[field], self.portable[field])
        self.assertEqual(self.compatible["interface"], interface)
        self.assertEqual(self.compatible["skills"], "./skills/")

    def test_listing_metadata_meets_local_package_limits(self):
        interface = self.portable["extensions"]["com.openai"]["interface"]
        self.assertLessEqual(len(interface["shortDescription"]), 30)
        self.assertEqual(interface["category"], "Education & Research")
        self.assertLessEqual(len(interface["defaultPrompt"]), 3)
        self.assertTrue(all(len(item) <= 128 for item in interface["defaultPrompt"]))

    def test_marketplace_points_to_repository_plugin_root(self):
        self.assertEqual(self.marketplace["name"], "family-tree-chatgpt")
        self.assertEqual(len(self.marketplace["plugins"]), 1)
        entry = self.marketplace["plugins"][0]
        self.assertEqual(entry["name"], self.portable["name"])
        self.assertEqual(entry["source"], {"source": "local", "path": "./"})
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(entry["category"], "Education & Research")


if __name__ == "__main__":
    unittest.main()
