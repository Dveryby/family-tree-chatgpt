#!/usr/bin/env python3
"""Crop an existing scan without changing its original; needs Pillow.

Adapted from the normalized-coordinate workflow in Jindřich Šaršon's
rodokmen-skill tools/vyrez.py (MIT). See ../LICENSE and references/upstream.md.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from PIL import Image, ImageOps


def in_git_tree(path):
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


def crop_scan(source, output, box):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output:
        raise ValueError("Originál a výřez musí být různé soubory.")
    if in_git_tree(output.parent):
        raise ValueError("Výřez ulož mimo git repozitář.")
    if len(box) != 4 or not all(math.isfinite(v) for v in box):
        raise ValueError("Oblast musí mít čtyři konečné souřadnice.")
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("Oblast musí být ve zlomcích 0–1, nikoli v pixelech.")
    with source.open("rb") as stream:
        original_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    with Image.open(source) as image:
        oriented = ImageOps.exif_transpose(image)
        w, h = oriented.size
        pixels = (round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h))
        if pixels[2] <= pixels[0] or pixels[3] <= pixels[1]:
            raise ValueError("Oblast je menší než jeden pixel.")
        selected = oriented.crop(pixels).convert("RGB")
        # New image strips EXIF/GPS and comments from the derivative.
        clean = Image.new("RGB", selected.size)
        clean.paste(selected)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            clean.save(stream, format="PNG")
    with output.open("rb") as stream:
        output_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"source_sha256": original_hash, "crop_sha256": output_hash,
            "box": list(box), "pixels": list(pixels), "source_size": [w, h],
            "crop_size": list(clean.size), "orientation": "EXIF applied", "format": "PNG"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--box", required=True, help="x0,y0,x1,y1 v rozsahu 0–1")
    args = parser.parse_args(argv)
    try:
        box = tuple(float(v) for v in args.box.split(","))
        print(json.dumps(crop_scan(args.source, args.output, box)))
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
