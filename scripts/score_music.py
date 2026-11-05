from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MUSIC_DIR = ROOT / "output" / "music"
CANDIDATES_DIR = MUSIC_DIR / "candidates"
REPORT_PATH = MUSIC_DIR / "candidate-scores.json"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def duration(path: Path) -> float:
    result = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    return float(result.stdout.strip())


def volume(path: Path, start: float, length: float) -> tuple[float, float]:
    result = run([
        "ffmpeg", "-hide_banner", "-nostats", "-ss", str(start), "-t", str(length),
        "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-",
    ])
    mean_match = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", result.stderr)
    max_match = re.search(r"max_volume:\s*(-?[0-9.]+) dB", result.stderr)
    if not mean_match or not max_match:
        raise RuntimeError(f"Could not measure volume for {path}")
    return float(mean_match.group(1)), float(max_match.group(1))


def loudnorm(path: Path) -> dict:
    result = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
        "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json", "-f", "null", "-",
    ])
    matches = re.findall(r"\{\s*\"input_i\".*?\}", result.stderr, flags=re.DOTALL)
    if not matches:
        raise RuntimeError(f"Could not parse loudness data for {path}")
    return json.loads(matches[-1])


def silences(path: Path) -> list[dict]:
    result = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
        "-af", "silencedetect=noise=-45dB:d=0.5", "-f", "null", "-",
    ])
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", result.stderr)]
    ends = [(float(a), float(b)) for a, b in re.findall(r"silence_end: ([0-9.]+) \| silence_duration: ([0-9.]+)", result.stderr)]
    return [
        {"start": starts[i] if i < len(starts) else None, "end": end, "duration": length}
        for i, (end, length) in enumerate(ends)
    ]


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def score(path: Path) -> dict:
    length = duration(path)
    segments = {
        "cold_open": volume(path, 0, 6),
        "build": volume(path, 6, 12),
        "pre_photo": volume(path, 18, 3.5),
        "photo": volume(path, 21.5, 4),
        "post_photo": volume(path, 25.5, 14.5),
        "climax": volume(path, 40, 12),
        "aftermath": volume(path, 52, 6),
        "last_two": volume(path, 58, 2),
    }
    silence_ranges = silences(path)
    measured = loudnorm(path)

    duration_score = clamp(1.0 - abs(length - 60.0) / 0.5)
    photo_reference = (segments["pre_photo"][0] + segments["post_photo"][0]) / 2
    photo_drop_db = photo_reference - segments["photo"][0]
    photo_score = clamp((photo_drop_db + 1.0) / 5.0)
    non_peak_means = [segments[name][0] for name in ("cold_open", "build", "photo", "post_photo", "aftermath")]
    peak_margin_db = segments["climax"][0] - max(non_peak_means)
    peak_score = clamp((peak_margin_db + 1.0) / 5.0)
    ending_mean = segments["last_two"][0]
    ending_score = clamp((ending_mean + 50.0) / 25.0)
    continuity_score = 1.0 if not silence_ranges else clamp(1.0 - sum(x["duration"] for x in silence_ranges) / 3.0)
    technical_score = (
        0.20 * duration_score
        + 0.30 * photo_score
        + 0.30 * peak_score
        + 0.10 * ending_score
        + 0.10 * continuity_score
    )
    if not math.isfinite(technical_score):
        technical_score = 0.0
    return {
        "file": str(path.relative_to(ROOT)),
        "duration_seconds": round(length, 6),
        "loudness": measured,
        "segments_mean_and_max_db": {name: {"mean": values[0], "max": values[1]} for name, values in segments.items()},
        "silences_over_0_5s": silence_ranges,
        "diagnostics": {
            "photo_drop_db": round(photo_drop_db, 3),
            "climax_margin_db": round(peak_margin_db, 3),
        },
        "component_scores": {
            "duration": round(duration_score, 4),
            "photo": round(photo_score, 4),
            "climax": round(peak_score, 4),
            "ending": round(ending_score, 4),
            "continuity": round(continuity_score, 4),
        },
        "technical_score": round(technical_score, 4),
        "manual_review_required": [
            "No vocals, choir, or speech-like texture",
            "Supports map readability",
            "Tragic pressure rather than triumph",
            "Unresolved ending without an abrupt cutoff"
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score generated music candidates against the video timeline")
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()
    files = args.files or sorted(CANDIDATES_DIR.glob("*.mp3"))
    if not files:
        raise SystemExit(f"No candidates found in {CANDIDATES_DIR}")
    results = [score(path.resolve()) for path in files]
    results.sort(key=lambda item: item["technical_score"], reverse=True)
    report = {"status": "PASS", "selected_technical_candidate": results[0]["file"], "candidates": results}
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
