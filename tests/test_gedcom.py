"""GEDCOM import tests use synthetic family data only."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILL = Path(os.environ.get("FAMILY_TREE_SKILL", REPO / "skills/family-tree-chatgpt"))


def load():
    spec = importlib.util.spec_from_file_location("gedcom", SKILL / "scripts/gedcom.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gedcom = load()


SYNTHETIC_GEDCOM = """0 HEAD
1 SOUR SyntheticSuite
2 VERS 1.0
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Test /Person/
2 GIVN Test
2 SURN Person
1 SEX M
1 BIRT
2 DATE 1 JAN 1900
2 PLAC Testov
2 SOUR @S1@
3 PAGE Synthetic page 1
1 DEAT
2 DATE AFT 1970
1 FAMS @F1@
1 NOTE Synthetic first
2 CONT second
2 CONC  part
1 _PRIVATE_EXTENSION kept
0 @I2@ INDI
1 NAME Example /Person/
1 SEX F
1 FAMS @F1@
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 MARR
2 DATE 1 JAN 1920
0 @S1@ SOUR
1 TITL Synthetic register
1 AUTH Synthetic author
0 TRLR
"""

SYNTHETIC_ANCESTORS = """0 HEAD
1 SOUR SyntheticAncestors
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Root /Example/
1 FAMC @F1@
0 @I2@ INDI
1 NAME Father /Example/
1 DEAT
2 DATE 4 MAY 1980
2 PLAC Testov
1 FAMC @F2@
1 FAMS @F1@
0 @I3@ INDI
1 NAME Mother /Example/
1 BIRT
2 DATE 1905
2 PLAC Ukázkov
1 FAMS @F1@
0 @I4@ INDI
1 NAME Grandfather /Example/
1 FAMS @F2@
0 @F1@ FAM
1 HUSB @I2@
1 WIFE @I3@
1 CHIL @I1@
0 @F2@ FAM
1 HUSB @I4@
1 CHIL @I2@
0 TRLR
"""


class GedcomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "synthetic.ged"
        self.source.write_text(SYNTHETIC_GEDCOM, encoding="utf-8")

    def test_import_preserves_claims_and_creates_evidence_plan(self):
        result = gedcom.build_import(self.source)
        self.assertEqual(result["source"]["gedcom_version"], "5.5.1")
        self.assertEqual(result["source"]["declared_character_set"], "UTF-8")
        self.assertEqual(result["data_status"], "unverified_claims")
        self.assertEqual(len(result["persons"]), 2)
        self.assertEqual(len(result["families"]), 1)
        self.assertEqual(len(result["sources"]), 1)

        first = result["persons"][0]
        self.assertEqual(first["names"][0]["given"], "Test")
        self.assertEqual(first["names"][0]["surname"], "Person")
        self.assertEqual(first["notes"], ["Synthetic first\nsecond part"])
        self.assertEqual(first["extensions"][0]["tag"], "_PRIVATE_EXTENSION")
        self.assertEqual(first["events"][0]["sources"][0]["source_id"], "@S1@")
        self.assertEqual(first["evidence_status"], "unverified")

        issues = {(item["subject_id"], item["event"], item["issue"]) for item in result["research_plan"]}
        self.assertNotIn(("@I1@", "BIRT", "missing_source"), issues)
        self.assertIn(("@I1@", "DEAT", "missing_source"), issues)
        self.assertIn(("@I2@", "BIRT_OR_CHR", "missing_event"), issues)
        self.assertIn(("@F1@", "MARR", "missing_source"), issues)

    def test_cli_writes_private_non_overwriting_output(self):
        output = self.root / "import.json"
        command = [sys.executable, str(SKILL / "scripts/gedcom.py"), str(self.source), str(output)]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        summary = json.loads(completed.stdout)
        self.assertTrue(summary["imported"])
        self.assertEqual(summary["persons"], 2)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["schema_version"], 1)

        repeated = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(repeated.returncode, 0)
        self.assertIn("existuje", repeated.stderr)

    def test_ancestor_queue_keeps_relationships_unverified(self):
        source = self.root / "ancestors.ged"
        source.write_text(SYNTHETIC_ANCESTORS, encoding="utf-8")
        imported = gedcom.build_import(source)
        plan = gedcom.ancestor_research(imported, "@I1@", max_generations=4)
        by_number = {item["ahnentafel"]: item for item in plan["positions"]}
        self.assertEqual(set(by_number), {1, 2, 3, 4})
        self.assertEqual(by_number[2]["person_id"], "@I2@")
        self.assertEqual(by_number[3]["person_id"], "@I3@")
        self.assertEqual(by_number[4]["person_id"], "@I4@")
        self.assertEqual(by_number[2]["research_anchor"]["event"], "DEAT")
        self.assertEqual(by_number[2]["research_anchor"]["place_claim"], "Testov")
        self.assertEqual(by_number[2]["relationship_status"], "unverified_claim")
        self.assertEqual(plan["data_status"], "unverified_claims")

    def test_ancestor_queue_stops_on_ambiguous_parent_family_and_cycle(self):
        source = self.root / "ancestors.ged"
        source.write_text(SYNTHETIC_ANCESTORS, encoding="utf-8")
        imported = gedcom.build_import(source)
        imported["persons"][0]["family_child"].append("@F2@")
        ambiguous = gedcom.ancestor_research(imported, "@I1@")
        self.assertEqual(len(ambiguous["positions"]), 1)
        self.assertTrue(any("více FAMC" in item for item in ambiguous["warnings"]))

        imported = gedcom.build_import(source)
        imported["persons"][3]["family_child"] = ["@F1@"]
        imported["families"][0]["children"].append("@I4@")
        cycle = gedcom.ancestor_research(imported, "@I1@")
        self.assertTrue(any("cyklus" in item for item in cycle["warnings"]))

        imported = gedcom.build_import(source)
        imported["families"][0]["children"] = []
        one_sided = gedcom.ancestor_research(imported, "@I1@")
        self.assertEqual(len(one_sided["positions"]), 1)
        self.assertTrue(any("CHIL" in item for item in one_sided["warnings"]))

    def test_cli_can_add_private_ancestor_queue(self):
        source = self.root / "ancestors.ged"
        source.write_text(SYNTHETIC_ANCESTORS, encoding="utf-8")
        output = self.root / "ancestors.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(SKILL / "scripts/gedcom.py"),
                str(source),
                str(output),
                "--root",
                "@I1@",
                "--max-generations",
                "4",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["ancestor_positions"], 4)
        self.assertIn("ancestor_research", json.loads(output.read_text(encoding="utf-8")))

    def test_ancestor_queue_has_expansion_limit(self):
        source = self.root / "ancestors.ged"
        source.write_text(SYNTHETIC_ANCESTORS, encoding="utf-8")
        imported = gedcom.build_import(source)
        original = gedcom.MAX_ANCESTOR_POSITIONS
        try:
            gedcom.MAX_ANCESTOR_POSITIONS = 3
            with self.assertRaisesRegex(ValueError, "překročila"):
                gedcom.ancestor_research(imported, "@I1@", max_generations=4)
        finally:
            gedcom.MAX_ANCESTOR_POSITIONS = original

    def test_invalid_structure_duplicate_ids_and_charset_are_rejected(self):
        cases = {
            "jump": "0 HEAD\n2 SOUR Bad\n0 TRLR\n",
            "duplicate": "0 HEAD\n1 GEDC\n2 VERS 5.5.1\n1 CHAR UTF-8\n0 @I1@ INDI\n0 @I1@ INDI\n0 TRLR\n",
            "ansel": "0 HEAD\n1 GEDC\n2 VERS 5.5.1\n1 CHAR ANSEL\n0 TRLR\n",
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                path = self.root / f"{name}.ged"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    gedcom.build_import(path)

    def test_dangling_references_are_warnings_not_facts(self):
        source = self.root / "dangling.ged"
        source.write_text(
            "0 HEAD\n1 SOUR SyntheticSuite\n1 GEDC\n2 VERS 7.0\n1 CHAR UTF-8\n"
            "0 @I1@ INDI\n1 NAME Synthetic /Person/\n1 BIRT\n2 SOUR @S404@\n1 FAMS @F404@\n0 TRLR\n",
            encoding="utf-8",
        )
        result = gedcom.build_import(source)
        self.assertTrue(any("@F404@" in item for item in result["warnings"]))
        self.assertTrue(any("@S404@" in item for item in result["warnings"]))
        self.assertIn(
            ("@I1@", "BIRT", "missing_source"),
            {(item["subject_id"], item["event"], item["issue"]) for item in result["research_plan"]},
        )

    def test_output_inside_git_repository_is_rejected(self):
        repository = self.root / "code"
        subprocess.run(["git", "init", str(repository)], check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, "mimo git"):
            gedcom.atomic_output(repository / "private.json", gedcom.build_import(self.source))

    def test_symlink_input_and_output_are_rejected(self):
        linked_input = self.root / "linked.ged"
        linked_input.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "symlink"):
            gedcom.build_import(linked_input)

        target = self.root / "target.json"
        linked_output = self.root / "linked.json"
        linked_output.symlink_to(target)
        with self.assertRaisesRegex(FileExistsError, "existuje"):
            gedcom.atomic_output(linked_output, gedcom.build_import(self.source))


if __name__ == "__main__":
    unittest.main()
