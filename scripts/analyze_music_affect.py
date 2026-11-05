from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import stft


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIO = ROOT / "output" / "music" / "shanghai-1976-score-master.wav"
DEFAULT_REPORT = ROOT / "output" / "music" / "music-affect-acoustic-report.json"
SEGMENTS = [
    ("opening", 0.0, 10.0),
    ("pressure_1", 10.0, 20.0),
    ("photo", 20.0, 27.0),
    ("pressure_2", 27.0, 40.0),
    ("climax", 40.0, 52.0),
    ("aftermath", 52.0, 60.0),
]


def db(value: float) -> float:
    scalar = float(value)
    return 20.0 * math.log10(max(scalar, 1e-12))


def analyze_segment(waveform: np.ndarray, sample_rate: int, start: float, end: float) -> dict:
    begin = round(start * sample_rate)
    finish = min(round(end * sample_rate), waveform.shape[-1])
    stereo = waveform[:, begin:finish]
    mono = stereo.mean(axis=0)
    frequencies, _, complex_spectrum = stft(
        mono,
        fs=sample_rate,
        window="hann",
        nperseg=2048,
        noverlap=1536,
        nfft=2048,
        boundary=None,
        padded=False,
    )
    spectrum = np.abs(complex_spectrum)
    power = np.square(spectrum)
    mean_power = power.mean(axis=1)
    total_power = max(float(mean_power.sum()), 1e-12)
    centroid = float((frequencies * mean_power).sum() / total_power)
    low_ratio = float(mean_power[frequencies < 250].sum() / total_power)
    high_ratio = float(mean_power[frequencies >= 4000].sum() / total_power)
    flatness = float(np.exp(np.log(np.maximum(mean_power, 1e-12)).mean()) / max(float(mean_power.mean()), 1e-12))

    normalized = spectrum / np.maximum(spectrum.sum(axis=0, keepdims=True), 1e-12)
    flux_curve = np.sqrt(np.square(np.maximum(normalized[:, 1:] - normalized[:, :-1], 0.0)).sum(axis=0))
    flux = flux_curve.mean()
    threshold = np.median(flux_curve) + flux_curve.std()
    if flux_curve.size >= 3:
        peaks = int(np.count_nonzero(
            (flux_curve[1:-1] > flux_curve[:-2])
            & (flux_curve[1:-1] >= flux_curve[2:])
            & (flux_curve[1:-1] > threshold)
        ))
    else:
        peaks = 0

    frame_count = max(1, (mono.size - 2048) // 512 + 1)
    framed = np.lib.stride_tricks.sliding_window_view(mono, 2048)[::512][:frame_count]
    frame_rms_db = 20.0 * np.log10(np.maximum(np.sqrt(np.square(framed).mean(axis=1)), 1e-12))
    rms = float(np.sqrt(np.square(mono).mean()))
    peak = float(np.abs(mono).max())
    mid = stereo.mean(axis=0)
    side = (stereo[0] - stereo[-1]) * 0.5 if stereo.shape[0] > 1 else np.zeros_like(mid)
    stereo_width = float(np.sqrt(np.square(side).mean()) / max(float(np.sqrt(np.square(mid).mean())), 1e-12))

    return {
        "start_seconds": start,
        "end_seconds": end,
        "rms_dbfs": round(db(rms), 3),
        "peak_dbfs": round(db(peak), 3),
        "crest_db": round(db(peak / max(rms, 1e-12)), 3),
        "frame_rms_std_db": round(float(frame_rms_db.std()), 3),
        "spectral_centroid_hz": round(centroid, 1),
        "low_band_ratio_below_250hz": round(low_ratio, 4),
        "high_band_ratio_above_4khz": round(high_ratio, 4),
        "spectral_flatness": round(flatness, 6),
        "spectral_flux": round(float(flux), 6),
        "transient_density_per_second": round(peaks / max(end - start, 1e-6), 3),
        "stereo_width_side_to_mid": round(stereo_width, 4),
    }


def zscores(values: list[float]) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    std = float(array.std())
    if std < 1e-12:
        return [0.0] * len(values)
    return [float(value) for value in ((array - array.mean()) / std)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure relative musical activity and spectral development")
    parser.add_argument("audio", nargs="?", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    audio = args.audio.resolve()
    samples, sample_rate = sf.read(audio, dtype="float32", always_2d=True)
    waveform = samples.T
    results = []
    for name, start, end in SEGMENTS:
        metrics = analyze_segment(waveform, sample_rate, start, end)
        metrics["name"] = name
        results.append(metrics)

    energy_z = zscores([item["rms_dbfs"] for item in results])
    centroid_z = zscores([item["spectral_centroid_hz"] for item in results])
    transient_z = zscores([item["transient_density_per_second"] for item in results])
    flux_z = zscores([item["spectral_flux"] for item in results])
    for index, item in enumerate(results):
        relative_arousal = 0.45 * energy_z[index] + 0.20 * centroid_z[index] + 0.25 * transient_z[index] + 0.10 * flux_z[index]
        item["relative_arousal_proxy_0_100"] = round(100.0 / (1.0 + math.exp(-relative_arousal)), 1)

    climax = next(item for item in results if item["name"] == "climax")
    non_climax = [item for item in results if item["name"] != "climax"]
    report = {
        "status": "PASS",
        "audio": str(audio),
        "sample_rate": sample_rate,
        "channels": int(waveform.shape[0]),
        "duration_seconds": round(waveform.shape[-1] / sample_rate, 6),
        "method": {
            "scope": "Acoustic activity and relative arousal proxy; not a semantic emotion classifier",
            "features": ["RMS", "spectral centroid", "spectral flux", "transient density", "band energy", "stereo width"],
        },
        "segments": results,
        "diagnostics": {
            "energy_range_db": round(max(item["rms_dbfs"] for item in results) - min(item["rms_dbfs"] for item in results), 3),
            "centroid_range_hz": round(max(item["spectral_centroid_hz"] for item in results) - min(item["spectral_centroid_hz"] for item in results), 1),
            "climax_arousal_proxy": climax["relative_arousal_proxy_0_100"],
            "non_climax_arousal_proxy_mean": round(sum(item["relative_arousal_proxy_0_100"] for item in non_climax) / len(non_climax), 1),
            "climax_transient_density": climax["transient_density_per_second"],
            "non_climax_transient_density_mean": round(sum(item["transient_density_per_second"] for item in non_climax) / len(non_climax), 3),
        },
        "limitations": [
            "Loudness automation can raise the arousal proxy without adding harmonic or orchestral development.",
            "Sadness, tragedy, resolve, and historical meaning require a trained semantic model and human listening.",
            "This report cannot by itself prove the absence of voice-like timbres.",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
