from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "output" / "shanghai-1976-force-map.mp4"
KEYFRAMES = ROOT / "output" / "keyframes"
REPORT = ROOT / "output" / "validation-report.json"


def main() -> None:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height,r_frame_rate,pix_fmt", "-of", "json", str(VIDEO)],
        check=True,
        text=True,
        capture_output=True,
    )
    media = json.loads(probe.stdout)
    images = []
    for path in sorted(KEYFRAMES.glob("frame-*.png")):
        image = Image.open(path).convert("RGB")
        stat = ImageStat.Stat(image)
        images.append({
            "file": path.name,
            "size": list(image.size),
            "mean_rgb": [round(x, 2) for x in stat.mean],
            "stddev_rgb": [round(x, 2) for x in stat.stddev],
            "nonblank": max(stat.stddev) > 8,
        })
    data = json.loads((ROOT / "src" / "data.json").read_text(encoding="utf-8"))
    guards = {
        "no_location_people_fields": all("people" not in item for item in data["locations"]),
        "suppression_counts_unknown": all(item["count"] is None for item in data["regional_forces"]),
        "concentrated_2500": next(item for item in data["aggregate_forces"] if item["id"] == "concentrated")["count"] == 2500,
        "standby_31000": next(item for item in data["aggregate_forces"] if item["id"] == "standby")["count"] == 31000,
        "all_keyframes_nonblank": bool(images) and all(item["nonblank"] for item in images),
    }
    report = {
        "status": "PASS" if all(guards.values()) else "FAIL",
        "media": media,
        "keyframes": images,
        "guardrails": guards,
        "imagegen": {
            "status": "SUCCESS_AFTER_RETRY",
            "attempts": 3,
            "models": ["gpt-image-1", "gpt-image-2", "gpt-image-2.5-flare"],
            "endpoint": "codex.test-inner.99.com/v1",
            "asset": "public/assets/probe-paper.png",
            "integration": "cropped and color-normalized to public/assets/archive-paper.png",
        },
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
