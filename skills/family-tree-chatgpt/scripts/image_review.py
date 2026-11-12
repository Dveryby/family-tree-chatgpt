#!/usr/bin/env python3
"""Create private review derivatives from local scans; never reads archive networks.

The split, marked-preview, and local contact-sheet workflows adapt ideas from
Jindřich Šaršon's rodokmen-skill tools/overit.py, tools/ramecek.py, and the
local-file mode of tools/mapa_knihy.py (MIT), revision 0fb0c037. See
../LICENSE and references/upstream.md.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageOps


MAX_SHEET_IMAGES = 60
DEFAULT_REVIEW_WIDTH = 1900
DEFAULT_SHEET_WIDTH = 1200


def in_git_tree(path):
    path = Path(path).resolve()
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


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_file(path):
    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise ValueError(f"Vstupní obrázek nesmí být symlink: {candidate}")
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ValueError(f"Vstupní obrázek neexistuje: {candidate}")
    return resolved


def output_file(path):
    candidate = Path(path).expanduser()
    if candidate.exists() or candidate.is_symlink():
        raise FileExistsError(f"Výstup už existuje: {candidate}")
    resolved = candidate.resolve()
    if in_git_tree(resolved):
        raise ValueError("Kontrolní obrázky ulož mimo git repozitář.")
    resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    return resolved


def normalized_box(value):
    box = tuple(value)
    if len(box) != 4 or not all(isinstance(item, (int, float)) and math.isfinite(item) for item in box):
        raise ValueError("Oblast musí mít čtyři konečné souřadnice.")
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("Oblast musí být ve zlomcích 0–1 a splňovat x0 < x1, y0 < y1.")
    return box


def parse_box(value):
    try:
        return normalized_box(tuple(float(item) for item in value.split(",")))
    except ValueError as exc:
        if str(exc).startswith("Oblast"):
            raise
        raise ValueError("Oblast zadej jako x0,y0,x1,y1 v rozsahu 0–1.") from exc


def pixels(box, size):
    x0, y0, x1, y1 = normalized_box(box)
    width, height = size
    result = (
        round(x0 * width),
        round(y0 * height),
        round(x1 * width),
        round(y1 * height),
    )
    if result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError("Oblast je menší než jeden pixel.")
    return result


def clean_rgb(image):
    converted = image.convert("RGB")
    clean = Image.new("RGB", converted.size)
    clean.paste(converted)
    return clean


def fit_width(image, width):
    if type(width) is not int or width < 1:
        raise ValueError("Cílová šířka musí být kladné celé číslo.")
    if image.width <= width:
        return clean_rgb(image)
    height = max(1, round(image.height * width / image.width))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def publish_png(path, image):
    path = output_file(path)
    temporary = None
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        clean_rgb(image).save(temporary, format="PNG")
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Výstup už existuje: {path}")
        os.link(temporary, path)
        path.chmod(0o600)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return path


def open_oriented(path):
    path = source_file(path)
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        image.load()
        return path, clean_rgb(image)


def split_boxes(box, direction, overlap):
    x0, y0, x1, y1 = normalized_box(box)
    if not isinstance(overlap, (int, float)) or not math.isfinite(overlap) or not 0 <= overlap < 1:
        raise ValueError("Překryv musí být číslo od 0 včetně do 1 bez 1.")
    if direction == "left-right":
        middle = (x0 + x1) / 2
        extra = (x1 - x0) * overlap / 2
        return ((x0, y0, min(x1, middle + extra), y1),
                (max(x0, middle - extra), y0, x1, y1))
    if direction == "top-bottom":
        middle = (y0 + y1) / 2
        extra = (y1 - y0) * overlap / 2
        return ((x0, y0, x1, min(y1, middle + extra)),
                (x0, max(y0, middle - extra), x1, y1))
    raise ValueError("Směr musí být left-right nebo top-bottom.")


def split_review(source, outputs, box=(0, 0, 1, 1), direction="left-right", overlap=0.04,
                 contrast=False, width=DEFAULT_REVIEW_WIDTH):
    if len(outputs) != 2 or Path(outputs[0]).resolve() == Path(outputs[1]).resolve():
        raise ValueError("Pro rozdělení zadej dva různé výstupy.")
    for output in outputs:
        output_file(output)
    source, image = open_oriented(source)
    parts = []
    metadata = []
    for part_box in split_boxes(box, direction, overlap):
        part_pixels = pixels(part_box, image.size)
        part = image.crop(part_pixels)
        if contrast:
            part = ImageOps.autocontrast(ImageOps.grayscale(part), cutoff=(2, 35)).convert("RGB")
        part = fit_width(part, width)
        parts.append(part)
        metadata.append({"box": list(part_box), "pixels": list(part_pixels), "size": list(part.size)})
    written = [publish_png(path, part) for path, part in zip(outputs, parts)]
    return {
        "operation": "split",
        "source_sha256": sha256(source),
        "source_size": list(image.size),
        "direction": direction,
        "overlap": overlap,
        "contrast_applied": bool(contrast),
        "outputs": [
            {**item, "path": str(path), "sha256": sha256(path)}
            for item, path in zip(metadata, written)
        ],
    }


def marked_preview(source, output, boxes):
    if not boxes:
        raise ValueError("Zadej alespoň jeden rámeček.")
    output_file(output)
    source, image = open_oriented(source)
    converted = [pixels(box, image.size) for box in boxes]
    preview = clean_rgb(image)
    draw = ImageDraw.Draw(preview)
    stroke = max(3, image.width // 400)
    for rectangle in converted:
        draw.rectangle(rectangle, outline="#d7302a", width=stroke)
    output = publish_png(output, preview)
    return {
        "operation": "mark",
        "source_sha256": sha256(source),
        "source_size": list(image.size),
        "boxes": [list(normalized_box(box)) for box in boxes],
        "pixels": [list(rectangle) for rectangle in converted],
        "output": str(output),
        "output_sha256": sha256(output),
    }


def label_image(image, label):
    banner_height = 34
    canvas = Image.new("RGB", (image.width, image.height + banner_height), "white")
    canvas.paste(image, (0, banner_height))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 9), label, fill="#a00000", font=ImageFont.load_default())
    return canvas


def contact_sheet(sources, output, box=(0, 0, 1, 0.15), columns=1, width=DEFAULT_SHEET_WIDTH):
    if not sources:
        raise ValueError("Pro přehled zadej alespoň jeden obrázek.")
    if len(sources) > MAX_SHEET_IMAGES:
        raise ValueError(f"Přehled může obsahovat nejvýše {MAX_SHEET_IMAGES} obrázků.")
    if type(columns) is not int or columns < 1 or columns > len(sources):
        raise ValueError("Počet sloupců musí být kladný a nejvýše počet obrázků.")
    output_file(output)
    items = []
    source_metadata = []
    for number, source in enumerate(sources, 1):
        path, image = open_oriented(source)
        area = pixels(box, image.size)
        crop = image.crop(area)
        cell_width = max(1, width // columns)
        crop = fit_width(crop, cell_width)
        label = f"{number}: {path.name}"
        items.append(label_image(crop, label))
        source_metadata.append({
            "path": str(path),
            "sha256": sha256(path),
            "source_size": list(image.size),
            "pixels": list(area),
        })
    rows = math.ceil(len(items) / columns)
    cell_width = max(item.width for item in items)
    cell_height = max(item.height for item in items)
    sheet = Image.new("RGB", (cell_width * columns, cell_height * rows), "white")
    for index, item in enumerate(items):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        sheet.paste(item, (x, y))
    output = publish_png(output, sheet)
    return {
        "operation": "sheet",
        "box": list(normalized_box(box)),
        "columns": columns,
        "sources": source_metadata,
        "output": str(output),
        "output_size": list(sheet.size),
        "output_sha256": sha256(output),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    split = commands.add_parser("split", help="rozdělit čtenou oblast na dvě překrývající se části")
    split.add_argument("source", type=Path)
    split.add_argument("output_first", type=Path)
    split.add_argument("output_second", type=Path)
    split.add_argument("--box", default="0,0,1,1", help="x0,y0,x1,y1 v rozsahu 0–1")
    split.add_argument("--direction", choices=("left-right", "top-bottom"), default="left-right")
    split.add_argument("--overlap", type=float, default=0.04)
    split.add_argument("--contrast", action="store_true", help="vytvořit kontrastní černobílou pracovní kopii")
    split.add_argument("--width", type=int, default=DEFAULT_REVIEW_WIDTH)

    mark = commands.add_parser("mark", help="vyznačit kontrolované oblasti červenými rámečky")
    mark.add_argument("source", type=Path)
    mark.add_argument("output", type=Path)
    mark.add_argument("--box", action="append", required=True, help="lze opakovat; x0,y0,x1,y1")

    sheet = commands.add_parser("sheet", help="složit místní obrázky do přehledu bez síťového stahování")
    sheet.add_argument("output", type=Path)
    sheet.add_argument("sources", nargs="+", type=Path)
    sheet.add_argument("--box", default="0,0,1,0.15", help="oblast každého snímku")
    sheet.add_argument("--columns", type=int, default=1)
    sheet.add_argument("--width", type=int, default=DEFAULT_SHEET_WIDTH)

    args = parser.parse_args(argv)
    try:
        if args.command == "split":
            result = split_review(
                args.source,
                (args.output_first, args.output_second),
                parse_box(args.box),
                args.direction,
                args.overlap,
                args.contrast,
                args.width,
            )
        elif args.command == "mark":
            result = marked_preview(args.source, args.output, [parse_box(value) for value in args.box])
        else:
            result = contact_sheet(
                args.sources,
                args.output,
                parse_box(args.box),
                args.columns,
                args.width,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
