from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from analyze_music_affect import analyze_segment


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "output" / "music" / "context-candidate-ranking.json"
WINDOWS = {
    "opening": (0.0, 10.0),
    "pressure_1": (10.0, 20.0),
    "photo": (21.5, 25.5),
    "pressure_2": (27.0, 40.0),
    "crisis": (43.0, 54.0),
    "ending": (54.0, 60.0),
}


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def triangular(value: float, center: float, half_width: float) -> float:
    return clamp(1.0 - abs(value - center) / half_width)


def silences(path: Path) -> list[dict]:
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
        "-af", "silencedetect=noise=-45dB:d=0.5", "-f", "null", "-",
    ], check=True, capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", result.stderr)]
    ends = [
        (float(end), float(length))
        for end, length in re.findall(
            r"silence_end: ([0-9.]+) \| silence_duration: ([0-9.]+)",
            result.stderr,
        )
    ]
    return [
        {
            "start": starts[index] if index < len(starts) else None,
            "end": end,
            "duration": length,
        }
        for index, (end, length) in enumerate(ends)
    ]


def score(path: Path) -> dict:
    samples, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    waveform = samples.T
    duration = waveform.shape[-1] / sample_rate
    metrics = {
        name: analyze_segment(waveform, sample_rate, start, end)
        for name, (start, end) in WINDOWS.items()
    }

    opening = metrics["opening"]
    pressure_1 = metrics["pressure_1"]
    photo = metrics["photo"]
    pressure_2 = metrics["pressure_2"]
    crisis = metrics["crisis"]
    ending = metrics["ending"]

    adjacent_rms = (pressure_1["rms_dbfs"] + pressure_2["rms_dbfs"]) / 2.0
    photo_drop_db = adjacent_rms - photo["rms_dbfs"]
    adjacent_transients = max(
        0.01,
        (pressure_1["transient_density_per_second"] + pressure_2["transient_density_per_second"]) / 2.0,
    )
    photo_transient_ratio = photo["transient_density_per_second"] / adjacent_transients

    reference_rms = max(pressure_1["rms_dbfs"], pressure_2["rms_dbfs"])
    crisis_energy_margin_db = crisis["rms_dbfs"] - reference_rms
    reference_flux = max(pressure_1["spectral_flux"], pressure_2["spectral_flux"], 1e-6)
    reference_transients = max(
        pressure_1["transient_density_per_second"],
        pressure_2["transient_density_per_second"],
        0.01,
    )
    reference_centroid = max(
        pressure_1["spectral_centroid_hz"], pressure_2["spectral_centroid_hz"], 1.0
    )
    crisis_flux_ratio = crisis["spectral_flux"] / reference_flux
    crisis_transient_ratio = crisis["transient_density_per_second"] / reference_transients
    crisis_centroid_ratio = crisis["spectral_centroid_hz"] / reference_centroid

    components = {
        "opening_presence": clamp((opening["rms_dbfs"] + 34.0) / 10.0),
        "opening_low_frequency_weight": triangular(
            opening["low_band_ratio_below_250hz"], center=0.58, half_width=0.35
        ),
        "photo_energy_thinning": triangular(photo_drop_db, center=4.0, half_width=5.0),
        "photo_percussion_thinning": clamp((1.25 - photo_transient_ratio) / 0.85),
        "crisis_energy_growth": clamp((crisis_energy_margin_db + 1.0) / 6.0),
        "crisis_flux_growth": clamp((crisis_flux_ratio - 0.70) / 0.80),
        "crisis_transient_growth": clamp((crisis_transient_ratio - 0.60) / 0.90),
        "crisis_spectral_growth": clamp((crisis_centroid_ratio - 0.70) / 0.80),
        "ending_pressure": triangular(ending["rms_dbfs"], center=-23.0, half_width=13.0),
    }
    silence_ranges = silences(path)
    components["continuity"] = clamp(
        1.0 - sum(item["duration"] for item in silence_ranges) / 3.0
    )

    crisis_structure = (
        components["crisis_energy_growth"]
        + components["crisis_flux_growth"]
        + components["crisis_transient_growth"]
        + components["crisis_spectral_growth"]
    ) / 4.0
    technical_score = 100.0 * (
        0.14 * components["opening_presence"]
        + 0.08 * components["opening_low_frequency_weight"]
        + 0.10 * components["photo_energy_thinning"]
        + 0.08 * components["photo_percussion_thinning"]
        + 0.35 * crisis_structure
        + 0.15 * components["ending_pressure"]
        + 0.10 * components["continuity"]
    )
    hard_checks = {
        "duration_is_60s": abs(duration - 60.0) <= 0.08,
        "opening_not_empty": opening["rms_dbfs"] >= -31.0,
        "photo_is_thinner": photo_drop_db >= 1.5,
        "crisis_is_louder_than_prior_pressure": crisis_energy_margin_db >= 0.5,
        "crisis_has_non_loudness_development": max(
            crisis_flux_ratio, crisis_transient_ratio, crisis_centroid_ratio
        ) >= 1.05,
        "ending_not_abandoned": ending["rms_dbfs"] >= -34.0,
        "no_long_silence": not silence_ranges,
    }
    return {
        "file": str(path),
        "duration_seconds": round(duration, 6),
        "status": "PASS" if all(hard_checks.values()) else "REVIEW",
        "technical_score_0_100": round(technical_score, 2),
        "hard_checks": hard_checks,
        "components_0_1": {key: round(value, 4) for key, value in components.items()},
        "diagnostics": {
            "photo_drop_db": round(photo_drop_db, 3),
            "photo_transient_ratio": round(photo_transient_ratio, 3),
            "crisis_energy_margin_db": round(crisis_energy_margin_db, 3),
            "crisis_flux_ratio": round(crisis_flux_ratio, 3),
            "crisis_transient_ratio": round(crisis_transient_ratio, 3),
            "crisis_centroid_ratio": round(crisis_centroid_ratio, 3),
        },
        "segments": metrics,
        "silences_over_0_5s": silence_ranges,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank video-context music candidates")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    results = [score(path.resolve()) for path in args.files]
    results.sort(key=lambda item: item["technical_score_0_100"], reverse=True)
    report = {
        "status": "PASS",
        "method": {
            "scope": "Acoustic pre-screen for the documented 60-second context curve",
            "warning": "This score cannot determine solemnity, triumph, historical fit, or absence of voice-like timbre.",
        },
        "ranking": [item["file"] for item in results],
        "candidates": results,
        "manual_blind_review": [
            "Danger is present from the first second",
            "Solemn and threatening rather than merely sad or ambient",
            "Photo passage is severe but still unsafe",
            "Late crisis develops harmonically and rhythmically, not only in loudness",
            "Ending remains unresolved and non-triumphant",
            "No vocals, choir, speech, or speech-like texture",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
