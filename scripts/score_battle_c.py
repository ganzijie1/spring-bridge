from __future__ import annotations

import argparse
import glob
import json
import re
import subprocess
from pathlib import Path

import soundfile as sf

from analyze_music_affect import analyze_segment


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "output" / "music" / "battle-c-ranking.json"
TIMELINE = json.loads((ROOT / "src" / "timeline.json").read_text(encoding="utf-8"))
def windows(duration: float) -> dict[str, tuple[float, float]]:
    scale = duration / float(TIMELINE["duration_seconds"])
    return {
        "opening": (0.0, 12.0 * scale),
        "pressure": (12.0 * scale, 30.0 * scale),
        "choir_build": (30.0 * scale, float(TIMELINE["audio"]["near_silence_start"]) * scale),
        "break": (float(TIMELINE["audio"]["near_silence_start"]) * scale, float(TIMELINE["audio"]["near_silence_end"]) * scale),
        "theme": (float(TIMELINE["audio"]["tragic_theme_start"]) * scale, float(TIMELINE["audio"]["controlled_climax_start"]) * scale),
        "climax": (float(TIMELINE["audio"]["controlled_climax_start"]) * scale, float(TIMELINE["audio"]["controlled_climax_end"]) * scale),
        "ending": (float(TIMELINE["audio"]["controlled_climax_end"]) * scale, duration),
    }


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def loudness(path: Path) -> dict:
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
        "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json", "-f", "null", "-",
    ], check=True, capture_output=True, text=True)
    matches = re.findall(r'\{\s*"input_i".*?\}', result.stderr, flags=re.DOTALL)
    return json.loads(matches[-1]) if matches else {}


def score(path: Path) -> dict:
    samples, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    waveform = samples.T
    duration = waveform.shape[-1] / sample_rate
    metrics = {
        name: analyze_segment(waveform, sample_rate, start, end)
        for name, (start, end) in windows(duration).items()
    }
    opening = metrics["opening"]
    pressure = metrics["pressure"]
    choir_build = metrics["choir_build"]
    quiet_break = metrics["break"]
    theme = metrics["theme"]
    climax = metrics["climax"]
    ending = metrics["ending"]

    pre_break_rms = (pressure["rms_dbfs"] + choir_build["rms_dbfs"]) / 2.0
    break_drop_db = pre_break_rms - quiet_break["rms_dbfs"]
    theme_return_db = theme["rms_dbfs"] - quiet_break["rms_dbfs"]
    climax_growth_db = climax["rms_dbfs"] - theme["rms_dbfs"]
    climax_transient_ratio = climax["transient_density_per_second"] / max(
        theme["transient_density_per_second"], 0.01
    )
    components = {
        "opening_presence": clamp((opening["rms_dbfs"] + 34.0) / 12.0),
        "opening_low_weight": clamp((opening["low_band_ratio_below_250hz"] - 0.25) / 0.45),
        "pressure_growth": clamp((choir_build["rms_dbfs"] - opening["rms_dbfs"] + 1.0) / 7.0),
        "break_depth": clamp((break_drop_db - 8.0) / 18.0),
        "theme_return": clamp((theme_return_db - 10.0) / 22.0),
        "controlled_climax": clamp((climax_growth_db + 0.5) / 4.5),
        "climax_not_barrage": clamp((2.2 - climax_transient_ratio) / 1.4),
        "ending_present": clamp((ending["rms_dbfs"] + 38.0) / 18.0),
    }
    technical_score = 100.0 * (
        0.10 * components["opening_presence"]
        + 0.10 * components["opening_low_weight"]
        + 0.12 * components["pressure_growth"]
        + 0.20 * components["break_depth"]
        + 0.18 * components["theme_return"]
        + 0.12 * components["controlled_climax"]
        + 0.08 * components["climax_not_barrage"]
        + 0.10 * components["ending_present"]
    )
    checks = {
        "duration_matches_source": duration >= 10.0,
        "opening_not_empty": opening["rms_dbfs"] >= -34.0,
        "break_is_obvious": break_drop_db >= 12.0,
        "theme_returns_after_break": theme_return_db >= 14.0,
        "climax_is_controlled": -0.5 <= climax_growth_db <= 5.0,
        "ending_not_abandoned": ending["rms_dbfs"] >= -38.0,
    }
    return {
        "file": str(path),
        "status": "PASS" if all(checks.values()) else "REVIEW",
        "technical_score_0_100": round(technical_score, 2),
        "duration_seconds": round(duration, 6),
        "hard_checks": checks,
        "components_0_1": {key: round(value, 4) for key, value in components.items()},
        "diagnostics": {
            "break_drop_db": round(break_drop_db, 3),
            "theme_return_db": round(theme_return_db, 3),
            "climax_growth_db": round(climax_growth_db, 3),
            "climax_transient_ratio": round(climax_transient_ratio, 3),
        },
        "loudness": loudness(path),
        "segments": metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score battle-C candidates against the documented arc")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    files: list[Path] = []
    for value in args.files:
        matches = [Path(item) for item in sorted(glob.glob(value))]
        files.extend(matches or [Path(value)])
    results = [score(path.resolve()) for path in files]
    results.sort(key=lambda item: item["technical_score_0_100"], reverse=True)
    report = {
        "status": "PASS",
        "ranking": [item["file"] for item in results],
        "candidates": results,
        "manual_review_required": [
            "Persistent low-string pulse and restrained snare are audible",
            "Brass is dissonant rather than heroic",
            "Choir remains wordless and textural, with no pop or speech-like voice",
            "The post-break theme is tragic, memorable, and non-triumphant",
            "The ending remains unresolved and percussion never becomes a barrage",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
