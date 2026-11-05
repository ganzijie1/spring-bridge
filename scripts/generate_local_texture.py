from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "assets" / "archive-paper.png"
IMAGEGEN_SOURCE = ROOT / "public" / "assets" / "probe-paper.png"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if IMAGEGEN_SOURCE.exists():
        source = Image.open(IMAGEGEN_SOURCE).convert("RGB")
        texture = ImageOps.fit(source, (1920, 1080), method=Image.Resampling.LANCZOS)
        texture = ImageEnhance.Color(texture).enhance(0.78)
        texture.save(OUT, optimize=True)
        print(f"Promoted ImageGen texture {IMAGEGEN_SOURCE} -> {OUT} ({OUT.stat().st_size} bytes)")
        return
    noise = Image.effect_noise((1920, 1080), 24).convert("L")
    noise = ImageEnhance.Contrast(noise).enhance(0.35).filter(ImageFilter.GaussianBlur(0.7))
    warm = Image.new("RGB", noise.size, (222, 214, 197))
    fiber = Image.merge("RGB", (noise, noise, noise))
    texture = Image.blend(warm, fiber, 0.12)
    vignette = Image.new("L", noise.size, 255)
    px = vignette.load()
    cx, cy = noise.size[0] / 2, noise.size[1] / 2
    for y in range(noise.size[1]):
        dy = abs(y - cy) / cy
        for x in range(noise.size[0]):
            dx = abs(x - cx) / cx
            px[x, y] = max(218, int(255 - 22 * (dx * dx + dy * dy)))
    texture = Image.composite(texture, Image.new("RGB", noise.size, (204, 196, 180)), vignette)
    texture.save(OUT, optimize=True)
    print(f"Wrote deterministic fallback {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
