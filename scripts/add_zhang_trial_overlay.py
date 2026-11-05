from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE_VIDEO = ROOT / "output" / "shanghai-1976-force-map.mp4"
SOURCE_PHOTO = ROOT / "public" / "assets" / "zhang-chunqiao-trial-1980-byte.jpg"
OVERLAY = ROOT / "public" / "assets" / "zhang-chunqiao-trial-overlay.png"
OUTPUT_VIDEO = ROOT / "output" / "shanghai-1976-force-map-with-zhang.mp4"
REPORT = ROOT / "output" / "zhang-trial-overlay-validation.json"
KEYFRAMES = ROOT / "output" / "zhang-trial-keyframes"

START = 21.5
FADE_IN_END = 22.0
FADE_OUT_START = 25.0
END = 25.5
X, Y = 82, 205
CARD_W, CARD_H = 548, 410


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def make_overlay() -> None:
    source = Image.open(SOURCE_PHOTO).convert("RGB")
    source = ImageEnhance.Contrast(source).enhance(1.08)
    source = ImageEnhance.Color(source).enhance(0.72)

    photo_box = (18, 18, CARD_W - 18, 324)
    target_w = photo_box[2] - photo_box[0]
    target_h = photo_box[3] - photo_box[1]
    scale = max(target_w / source.width, target_h / source.height)
    resized = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    cropped = resized.crop((left, top, left + target_w, top + target_h))

    card = Image.new("RGBA", (CARD_W, CARD_H), (239, 233, 219, 246))
    draw = ImageDraw.Draw(card, "RGBA")
    draw.rectangle((0, 0, CARD_W - 1, CARD_H - 1), outline=(23, 27, 29, 235), width=3)
    draw.rectangle((0, 0, 9, CARD_H), fill=(182, 52, 46, 255))
    card.paste(cropped, (photo_box[0], photo_box[1]))
    draw.rectangle(photo_box, outline=(23, 27, 29, 215), width=2)

    title_font = font("C:/Windows/Fonts/msyhbd.ttc", 25)
    detail_font = font("C:/Windows/Fonts/msyh.ttc", 17)
    draw.text((22, 338), "张春桥｜特别法庭审判", font=title_font, fill=(23, 27, 29, 255))
    draw.text((22, 373), "1980—1981 · 历史照片", font=detail_font, fill=(93, 98, 94, 255))
    card.save(OVERLAY, optimize=True)


def render_video() -> None:
    filter_graph = (
        f"[1:v]format=rgba,fade=t=in:st={START}:d={FADE_IN_END - START}:alpha=1,"
        f"fade=t=out:st={FADE_OUT_START}:d={END - FADE_OUT_START}:alpha=1[photo];"
        f"[0:v][photo]overlay={X}:{Y}:enable='between(t,{START},{END})':eof_action=pass,format=yuv420p[v]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(SOURCE_VIDEO), "-loop", "1", "-framerate", "30", "-i", str(OVERLAY),
            "-filter_complex", filter_graph, "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "medium",
            "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", "60", str(OUTPUT_VIDEO),
        ],
        check=True,
    )


def probe() -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate,pix_fmt,duration",
            "-show_entries", "format=duration,size", "-of", "json", str(OUTPUT_VIDEO),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def write_keyframes() -> None:
    KEYFRAMES.mkdir(parents=True, exist_ok=True)
    for second, label in ((21.4, "before"), (22.2, "visible"), (24.2, "hold"), (25.4, "fade-out")):
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-ss", str(second), "-i", str(OUTPUT_VIDEO),
                "-frames:v", "1", "-update", "1", str(KEYFRAMES / f"{label}-{second:.1f}s.png"),
            ],
            check=True,
        )


def main() -> None:
    if not SOURCE_VIDEO.exists():
        raise SystemExit(f"Missing source video: {SOURCE_VIDEO}")
    if not SOURCE_PHOTO.exists():
        raise SystemExit(f"Missing source photo: {SOURCE_PHOTO}")
    make_overlay()
    render_video()
    write_keyframes()
    report = {
        "status": "PASS",
        "sourceVideo": str(SOURCE_VIDEO.relative_to(ROOT)).replace("\\", "/"),
        "sourcePhoto": str(SOURCE_PHOTO.relative_to(ROOT)).replace("\\", "/"),
        "sourcePhotoSha256": sha256(SOURCE_PHOTO),
        "overlay": str(OVERLAY.relative_to(ROOT)).replace("\\", "/"),
        "output": str(OUTPUT_VIDEO.relative_to(ROOT)).replace("\\", "/"),
        "outputSha256": sha256(OUTPUT_VIDEO),
        "placement": {"x": X, "y": Y, "width": CARD_W, "height": CARD_H},
        "timing": {"start": START, "fullyVisible": FADE_IN_END, "fadeOut": FADE_OUT_START, "end": END},
        "probe": probe(),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
