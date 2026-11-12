"""Offline image-review tests use generated images only."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

from PIL import Image


REPO = Path(__file__).resolve().parents[1]
SKILL = Path(os.environ.get("FAMILY_TREE_SKILL", REPO / "skills/family-tree-chatgpt"))


def load():
    spec = importlib.util.spec_from_file_location("image_review", SKILL / "scripts" / "image_review.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


image_review = load()


class ImageReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.png"
        image = Image.new("RGB", (100, 80))
        image.putdata([(x, y, (x + y) % 256) for y in range(80) for x in range(100)])
        image.save(self.source)

    def test_split_has_overlap_preserves_source_and_strips_metadata(self):
        original = self.source.read_bytes()
        first, second = self.root / "first.png", self.root / "second.png"
        result = image_review.split_review(
            self.source,
            (first, second),
            box=(0.1, 0.25, 0.9, 0.75),
            direction="left-right",
            overlap=0.1,
        )
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(result["outputs"][0]["pixels"], [10, 20, 54, 60])
        self.assertEqual(result["outputs"][1]["pixels"], [46, 20, 90, 60])
        self.assertEqual(stat.S_IMODE(first.stat().st_mode), 0o600)
        with Image.open(first) as image:
            self.assertEqual(image.size, (44, 40))
            self.assertFalse(image.getexif())

    def test_mark_draws_boxes_without_changing_source(self):
        original = self.source.read_bytes()
        output = self.root / "marked.png"
        result = image_review.marked_preview(self.source, output, [(0.1, 0.1, 0.9, 0.9)])
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(result["pixels"], [[10, 8, 90, 72]])
        with Image.open(output) as image:
            self.assertEqual(image.getpixel((10, 8)), (215, 48, 42))

    def test_sheet_uses_only_local_files_and_labels_order(self):
        second = self.root / "scan-20.png"
        Image.new("RGB", (80, 100), "white").save(second)
        output = self.root / "sheet.png"
        result = image_review.contact_sheet(
            [self.source, second], output, box=(0, 0, 1, 0.2), columns=2, width=400
        )
        self.assertEqual([Path(item["path"]).name for item in result["sources"]], ["source.png", "scan-20.png"])
        self.assertEqual(result["columns"], 2)
        self.assertTrue(output.is_file())
        self.assertLessEqual(result["output_size"][0], 400)

    def test_rejects_overwrite_symlink_bad_box_and_git_output(self):
        output = self.root / "marked.png"
        image_review.marked_preview(self.source, output, [(0, 0, 1, 1)])
        with self.assertRaises(FileExistsError):
            image_review.marked_preview(self.source, output, [(0, 0, 1, 1)])
        with self.assertRaises(ValueError):
            image_review.split_review(self.source, (self.root / "a.png", self.root / "b.png"), (0, 0, 2, 1))

        external = self.root / "external.png"
        Image.new("RGB", (2, 2)).save(external)
        linked = self.root / "linked.png"
        linked.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "symlink"):
            image_review.marked_preview(linked, self.root / "linked-output.png", [(0, 0, 1, 1)])

        repository = self.root / "code"
        subprocess.run(["git", "init", str(repository)], check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, "mimo git"):
            image_review.marked_preview(self.source, repository / "private.png", [(0, 0, 1, 1)])

    def test_cli_returns_json_and_contrast_derivative(self):
        first, second = self.root / "first.png", self.root / "second.png"
        run = subprocess.run(
            [
                sys.executable,
                str(SKILL / "scripts/image_review.py"),
                "split",
                str(self.source),
                str(first),
                str(second),
                "--contrast",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(run.stdout)
        self.assertTrue(result["contrast_applied"])
        self.assertEqual(len(result["outputs"]), 2)


if __name__ == "__main__":
    unittest.main()
