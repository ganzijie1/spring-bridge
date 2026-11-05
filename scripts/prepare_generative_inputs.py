from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1280, 720
PAPER = "#e8e0cf"
INK = "#171b1d"
RIVER = "#819da2"
MILITIA = "#b6342e"
SUPPRESSION = "#31566a"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def create_clean_plate() -> Path:
    texture_path = ROOT / "public" / "assets" / "archive-paper.png"
    texture = Image.open(texture_path).convert("RGB").resize((WIDTH, HEIGHT))
    image = Image.blend(Image.new("RGB", (WIDTH, HEIGHT), PAPER), texture, 0.30)
    draw = ImageDraw.Draw(image, "RGBA")

    map_box = (36, 70, 1244, 686)
    draw.rectangle(map_box, fill=(217, 208, 189, 215), outline=INK, width=2)

    roads = [
        [(52, 540), (255, 450), (450, 420), (670, 438), (960, 520), (1225, 455)],
        [(48, 390), (310, 378), (510, 305), (715, 330), (1000, 390), (1230, 310)],
        [(120, 150), (340, 215), (545, 185), (760, 205), (1010, 150), (1220, 205)],
        [(225, 75), (275, 255), (320, 470), (300, 680)],
        [(480, 72), (520, 270), (495, 490), (550, 684)],
        [(760, 72), (720, 300), (775, 520), (750, 686)],
        [(1010, 72), (960, 275), (1040, 490), (1080, 686)],
    ]
    for road in roads:
        draw.line(road, fill=(90, 87, 78, 66), width=2, joint="curve")

    river = [
        (875, 68), (840, 145), (855, 225), (915, 300), (960, 375),
        (915, 450), (940, 530), (1030, 600), (1238, 660),
    ]
    draw.line(river, fill=(129, 157, 162, 150), width=56, joint="curve")
    draw.line(river, fill=(220, 230, 228, 190), width=2, joint="curve")

    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow, "RGBA")
    for x, y, radius, color in [
        (515, 380, 105, MILITIA),
        (690, 305, 72, MILITIA),
        (350, 440, 82, MILITIA),
        (1040, 245, 105, SUPPRESSION),
        (1045, 520, 125, SUPPRESSION),
    ]:
        rgb = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
        glow_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=rgb + (72,))
    glow = glow.filter(ImageFilter.GaussianBlur(42))
    image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")

    vignette = Image.new("L", (WIDTH, HEIGHT), 0)
    vignette_draw = ImageDraw.Draw(vignette)
    vignette_draw.ellipse((-180, -160, WIDTH + 180, HEIGHT + 160), fill=210)
    vignette = vignette.filter(ImageFilter.GaussianBlur(90))
    shade = Image.new("RGB", (WIDTH, HEIGHT), (45, 43, 38))
    image = Image.composite(image, shade, vignette)

    out_dir = ROOT / "output" / "generative" / "inputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "shanghai-clean-plate-1280x720.png"
    image.save(path, optimize=True)

    metadata = {
        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "width": WIDTH,
        "height": HEIGHT,
        "sha256": sha256(path),
        "policy": "No text, labels, numbers, unit markers, arrows, or factual overlays.",
    }
    (out_dir / "input-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return path


if __name__ == "__main__":
    create_clean_plate()
