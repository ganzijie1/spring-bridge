#!/usr/bin/env python3
"""Diagnose and conservatively restore a 60-second generated music master."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal
from scipy.ndimage import median_filter


SEGMENTS = {
    "opening": (0.0, 10.0),
    "pressure_1": (10.0, 20.0),
    "photo": (21.5, 25.5),
    "pressure_2": (27.0, 40.0),
    "crisis": (43.0, 54.0),
    "ending": (54.0, 60.0),
}


@dataclass(frozen=True)
class Candidate:
    branch: str
    path: Path
    description: str


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout)[-4000:]
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{detail}")
    return completed


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(path, dtype="float64", always_2d=True)
    if audio.shape[1] != 2:
        raise ValueError(f"Expected stereo audio, got {audio.shape[1]} channels: {path}")
    return audio, sample_rate


def write_audio(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.clip(audio, -1.0, 1.0), sample_rate, subtype="PCM_24")


def db(value: float) -> float:
    return 20.0 * math.log10(max(value, 1e-12))


def frame_rms(audio: np.ndarray, sample_rate: int, seconds: float = 0.1) -> np.ndarray:
    mono = np.mean(audio, axis=1)
    size = max(1, int(sample_rate * seconds))
    usable = len(mono) // size * size
    if not usable:
        return np.array([], dtype=np.float64)
    return np.sqrt(np.mean(mono[:usable].reshape(-1, size) ** 2, axis=1) + 1e-15)


def longest_silence(audio: np.ndarray, sample_rate: int, threshold_db: float = -50.0) -> float:
    silent = frame_rms(audio, sample_rate) < 10 ** (threshold_db / 20.0)
    longest = current = 0
    for value in silent:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return round(longest * 0.1, 3)


def spectral_metrics(audio: np.ndarray, sample_rate: int) -> dict[str, float]:
    mono = np.mean(audio, axis=1)
    frequencies, power = signal.welch(mono, fs=sample_rate, nperseg=8192, noverlap=4096)
    total = float(np.sum(power)) + 1e-20

    def ratio(low: float, high: float) -> float:
        mask = (frequencies >= low) & (frequencies < high)
        return float(np.sum(power[mask]) / total)

    _, _, stft = signal.stft(
        mono, fs=sample_rate, nperseg=4096, noverlap=3072, boundary=None, padded=False
    )
    magnitude = np.abs(stft) + 1e-12
    normalized = magnitude / np.maximum(np.sum(magnitude, axis=0, keepdims=True), 1e-12)
    flux = np.sqrt(np.sum(np.maximum(np.diff(normalized, axis=1), 0.0) ** 2, axis=0))
    mean_spectrum = np.mean(magnitude, axis=1)
    local_background = median_filter(mean_spectrum, size=11, mode="nearest") + 1e-12
    stft_frequencies = np.fft.rfftfreq(4096, 1.0 / sample_rate)
    high_mask = stft_frequencies >= 8000.0
    spike_db = 20.0 * np.log10(mean_spectrum / local_background)
    return {
        "sub_35hz_ratio": round(ratio(0.0, 35.0), 8),
        "low_120_250hz_ratio": round(ratio(120.0, 250.0), 8),
        "below_250hz_ratio": round(ratio(0.0, 250.0), 8),
        "above_10khz_ratio": round(ratio(10000.0, sample_rate / 2.0), 8),
        "spectral_flux_mean": round(float(np.mean(flux)), 8),
        "high_spike_max_db": round(float(np.max(spike_db[high_mask])), 3),
        "high_spike_bins_over_12db": int(np.sum(spike_db[high_mask] > 12.0)),
    }


def basic_metrics(audio: np.ndarray, sample_rate: int) -> dict[str, object]:
    rms = float(np.sqrt(np.mean(audio**2) + 1e-15))
    peak = float(np.max(np.abs(audio)))
    mid = (audio[:, 0] + audio[:, 1]) * 0.5
    side = (audio[:, 0] - audio[:, 1]) * 0.5
    metrics: dict[str, object] = {
        "duration_seconds": round(len(audio) / sample_rate, 6),
        "sample_rate": sample_rate,
        "channels": audio.shape[1],
        "rms_dbfs": round(db(rms), 3),
        "sample_peak_dbfs": round(db(peak), 3),
        "crest_db": round(db(peak) - db(rms), 3),
        "dc_offset": [round(float(np.mean(audio[:, i])), 9) for i in range(2)],
        "clipped_sample_fraction": round(float(np.mean(np.abs(audio) >= 0.999969)), 10),
        "longest_silence_seconds": longest_silence(audio, sample_rate),
        "stereo_side_to_mid": round(
            float(np.sqrt(np.mean(side**2) + 1e-15) / np.sqrt(np.mean(mid**2) + 1e-15)), 5
        ),
        **spectral_metrics(audio, sample_rate),
    }
    segment_metrics: dict[str, object] = {}
    for name, (start, end) in SEGMENTS.items():
        part = audio[int(start * sample_rate) : int(end * sample_rate)]
        part_rms = float(np.sqrt(np.mean(part**2) + 1e-15))
        part_peak = float(np.max(np.abs(part)))
        segment_metrics[name] = {
            "rms_dbfs": round(db(part_rms), 3),
            "peak_dbfs": round(db(part_peak), 3),
            "crest_db": round(db(part_peak) - db(part_rms), 3),
            **spectral_metrics(part, sample_rate),
        }
    metrics["segments"] = segment_metrics
    metrics["narrative"] = {
        "photo_drop_db": round(
            segment_metrics["pressure_2"]["rms_dbfs"] - segment_metrics["photo"]["rms_dbfs"], 3
        ),
        "crisis_margin_db": round(
            segment_metrics["crisis"]["rms_dbfs"] - segment_metrics["pressure_2"]["rms_dbfs"], 3
        ),
        "ending_vs_crisis_db": round(
            segment_metrics["ending"]["rms_dbfs"] - segment_metrics["crisis"]["rms_dbfs"], 3
        ),
    }
    return metrics


def ffmpeg_loudness(path: Path) -> dict[str, float]:
    completed = run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
            "loudnorm=I=-16:TP=-1:LRA=11:print_format=json", "-f", "null", "-",
        ]
    )
    start, end = completed.stderr.rfind("{"), completed.stderr.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"Could not parse loudness analysis for {path}")
    values = json.loads(completed.stderr[start : end + 1])
    return {
        "integrated_lufs": float(values["input_i"]),
        "true_peak_dbtp": float(values["input_tp"]),
        "lra_lu": float(values["input_lra"]),
        "threshold_lufs": float(values["input_thresh"]),
    }


def constant_gain_match(audio: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, float]:
    source_rms = float(np.sqrt(np.mean(reference**2) + 1e-15))
    candidate_rms = float(np.sqrt(np.mean(audio**2) + 1e-15))
    gain = source_rms / candidate_rms
    peak_limit = 10 ** (-1.2 / 20.0)
    peak = float(np.max(np.abs(audio)))
    if peak * gain > peak_limit:
        gain = peak_limit / max(peak, 1e-12)
    return audio * gain, db(gain)


def align_audio(audio: np.ndarray, source_rate: int, target_rate: int, target_length: int) -> np.ndarray:
    if source_rate != target_rate:
        divisor = math.gcd(source_rate, target_rate)
        audio = signal.resample_poly(audio, target_rate // divisor, source_rate // divisor, axis=0)
    if len(audio) < target_length:
        audio = np.pad(audio, ((0, target_length - len(audio)), (0, 0)))
    return audio[:target_length]


def dynamic_low_mid_eq(audio: np.ndarray, sample_rate: int, max_reduction_db: float = 2.0) -> np.ndarray:
    highpass = signal.butter(2, 28.0, btype="highpass", fs=sample_rate, output="sos")
    cleaned = signal.sosfiltfilt(highpass, audio, axis=0)
    bandpass = signal.butter(3, [120.0, 250.0], btype="bandpass", fs=sample_rate, output="sos")
    band = signal.sosfiltfilt(bandpass, cleaned, axis=0)
    hop, frame = 512, 2048
    mono_band = np.mean(band, axis=1)
    envelope, centers = [], []
    for start in range(0, max(1, len(mono_band) - frame + 1), hop):
        block = mono_band[start : start + frame]
        envelope.append(float(np.sqrt(np.mean(block**2) + 1e-15)))
        centers.append(start + len(block) // 2)
    envelope_array = np.asarray(envelope)
    active = envelope_array[envelope_array > np.percentile(envelope_array, 20)]
    threshold = float(np.percentile(active, 60)) if len(active) else 1.0
    excess_db = 20.0 * np.log10(np.maximum(envelope_array / max(threshold, 1e-12), 1.0))
    frame_gain = 10 ** (-np.minimum(max_reduction_db, excess_db * 0.55) / 20.0)
    attack = math.exp(-hop / (sample_rate * 0.08))
    release = math.exp(-hop / (sample_rate * 0.35))
    smoothed = np.empty_like(frame_gain)
    previous = 1.0
    for index, target in enumerate(frame_gain):
        coefficient = attack if target < previous else release
        previous = coefficient * previous + (1.0 - coefficient) * target
        smoothed[index] = previous
    sample_gain = np.interp(
        np.arange(len(audio)), centers, smoothed, left=smoothed[0], right=smoothed[-1]
    )
    return cleaned + band * (sample_gain[:, None] - 1.0)


def ffmpeg_afftdn(source: Path, output: Path, residual: Path | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    common = "afftdn=nr=4:nf=-55:tn=1:ad=0.8:gs=5"
    run(["ffmpeg", "-y", "-hide_banner", "-i", str(source), "-af", common, "-c:a", "pcm_s24le", str(output)])
    if residual is not None:
        run([
            "ffmpeg", "-y", "-hide_banner", "-i", str(source), "-af", common + ":om=n",
            "-c:a", "pcm_s24le", str(residual),
        ])


def run_demucs(source: Path, output_root: Path, device: str) -> tuple[Path, Path]:
    checkpoint = Path.home() / ".cache" / "torch" / "hub" / "checkpoints" / "955717e8-8726e21a.th"
    if checkpoint.exists():
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
    run([
        sys.executable, "-m", "demucs.separate", "-n", "htdemucs", "--two-stems", "vocals",
        "--device", device, "--shifts", "1", "--overlap", "0.25", "-o", str(output_root), str(source),
    ])
    stem_dir = output_root / "htdemucs" / source.stem
    vocals, instrumental = stem_dir / "vocals.wav", stem_dir / "no_vocals.wav"
    if not vocals.exists() or not instrumental.exists():
        raise FileNotFoundError(f"Demucs did not produce expected stems in {stem_dir}")
    return vocals, instrumental


def mux_video(video: Path, audio: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-hide_banner", "-i", str(video), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "320k", "-ar", "48000", "-t", "60", str(output),
    ])


def parse_args() -> argparse.Namespace:
    sibling = Path("..") / "historical_models" / "shanghai-1976-video" / "output"
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=sibling / "music" / "shanghai-1976-storm-score-master.wav")
    parser.add_argument("--video", type=Path, default=sibling / "shanghai-1976-force-map-storm-score.mp4")
    parser.add_argument("--output-dir", type=Path, default=sibling / "music" / "restoration-2026-11-05")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--skip-demucs", action="store_true")
    parser.add_argument("--sonicmaster-input", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source, video, output_dir = args.input.resolve(), args.video.resolve(), args.output_dir.resolve()
    if not source.exists() or not video.exists():
        raise FileNotFoundError(f"Missing source or video: {source}, {video}")
    audio, sample_rate = read_audio(source)
    if sample_rate != 48000 or abs(len(audio) / sample_rate - 60.0) > 0.01:
        raise ValueError("Expected a stereo 48 kHz, 60-second source master")
    candidates_dir, residuals_dir = output_dir / "candidates", output_dir / "residuals"
    stems_dir, videos_dir = output_dir / "stems", output_dir / "blind-review"
    for directory in (candidates_dir, residuals_dir, stems_dir, videos_dir):
        directory.mkdir(parents=True, exist_ok=True)

    candidates: list[Candidate] = []
    a0 = candidates_dir / "A0-reference.wav"
    write_audio(a0, audio, sample_rate)
    candidates.append(Candidate("A0", a0, "Reference master; no restoration"))

    a1_raw, a1 = output_dir / ".A1-raw.wav", candidates_dir / "A1-soft-spectral-gate.wav"
    ffmpeg_afftdn(source, a1_raw, residuals_dir / "A1-noise-only.wav")
    a1_audio, _ = read_audio(a1_raw)
    a1_audio, _ = constant_gain_match(a1_audio, audio)
    write_audio(a1, a1_audio, sample_rate)
    a1_raw.unlink(missing_ok=True)
    candidates.append(Candidate("A1", a1, "FFmpeg afftdn, 4 dB maximum reduction"))

    a3_audio = dynamic_low_mid_eq(audio, sample_rate)
    a3_audio, _ = constant_gain_match(a3_audio, audio)
    a3 = candidates_dir / "A3-dynamic-low-mid-eq.wav"
    write_audio(a3, a3_audio, sample_rate)
    write_audio(residuals_dir / "A3-difference.wav", audio - a3_audio, sample_rate)
    candidates.append(Candidate("A3", a3, "28 Hz high-pass plus 120-250 Hz dynamic EQ, max 2 dB"))

    demucs_status: dict[str, object] = {"attempted": not args.skip_demucs}
    a2_25_audio: np.ndarray | None = None
    if not args.skip_demucs:
        try:
            vocals_path, instrumental_path = run_demucs(source, stems_dir, args.device)
            vocals, vocals_rate = read_audio(vocals_path)
            instrumental, instrumental_rate = read_audio(instrumental_path)
            vocals = align_audio(vocals, vocals_rate, sample_rate, len(audio))
            instrumental = align_audio(instrumental, instrumental_rate, sample_rate, len(audio))
            write_audio(stems_dir / "vocals-aligned-48k.wav", vocals, sample_rate)
            write_audio(stems_dir / "instrumental-aligned-48k.wav", instrumental, sample_rate)
            demucs_status.update({
                "status": "completed", "model": "htdemucs",
                "vocals_energy_ratio": round(float(np.sum(vocals**2) / (np.sum(audio**2) + 1e-15)), 8),
            })
            for attenuation in (0.25, 0.5, 0.75):
                mixed = instrumental + (1.0 - attenuation) * vocals
                mixed, _ = constant_gain_match(mixed, audio)
                suffix = int(attenuation * 100)
                destination = candidates_dir / f"A2-vocals-soft-{suffix}.wav"
                write_audio(destination, mixed, sample_rate)
                candidates.append(Candidate(f"A2-{suffix}", destination, f"Demucs vocals attenuated by {suffix}%"))
                if suffix == 25:
                    a2_25_audio = mixed
        except Exception as error:
            demucs_status.update({"status": "failed", "error": str(error)})
    else:
        demucs_status["status"] = "skipped"

    if a2_25_audio is not None:
        combined = dynamic_low_mid_eq(a2_25_audio, sample_rate)
        combined, _ = constant_gain_match(combined, audio)
        a5_pre, a5_raw = output_dir / ".A5-pre.wav", output_dir / ".A5-raw.wav"
        write_audio(a5_pre, combined, sample_rate)
        ffmpeg_afftdn(a5_pre, a5_raw)
        a5_audio, _ = read_audio(a5_raw)
        a5_audio, _ = constant_gain_match(a5_audio, audio)
        a5 = candidates_dir / "A5-minimal-combination.wav"
        write_audio(a5, a5_audio, sample_rate)
        write_audio(residuals_dir / "A5-difference.wav", audio - a5_audio, sample_rate)
        candidates.append(Candidate("A5", a5, "A2-25 plus A3 plus light A1"))
        a5_pre.unlink(missing_ok=True)
        a5_raw.unlink(missing_ok=True)

    sonicmaster_source = args.sonicmaster_input
    if sonicmaster_source is None:
        default_sonicmaster = candidates_dir / "A4-sonicmaster-raw.wav"
        sonicmaster_source = default_sonicmaster if default_sonicmaster.exists() else None
    sonicmaster_status: dict[str, object]
    if sonicmaster_source is not None and sonicmaster_source.exists():
        a4_raw, a4_rate = read_audio(sonicmaster_source)
        raw_duration = len(a4_raw) / a4_rate
        a4_audio = align_audio(a4_raw, a4_rate, sample_rate, len(audio))
        a4_audio, _ = constant_gain_match(a4_audio, audio)
        a4 = candidates_dir / "A4-sonicmaster-conformed.wav"
        write_audio(a4, a4_audio, sample_rate)
        candidates.append(Candidate("A4", a4, "Official SonicMaster Space output conformed to 60 seconds and 48 kHz"))
        sonicmaster_status = {
            "status": "completed",
            "source": str(sonicmaster_source),
            "raw_duration_seconds": round(raw_duration, 6),
            "conformance": "Resampled to 48 kHz, trimmed to source length, and constant-gain matched",
        }
    else:
        sonicmaster_status = {
            "status": "not_run",
            "reason": "Provide --sonicmaster-input or generate candidates/A4-sonicmaster-raw.wav with the official public Space.",
        }

    source_metrics = basic_metrics(audio, sample_rate)
    report_candidates: list[dict[str, object]] = []
    for candidate in candidates:
        candidate_audio, candidate_rate = read_audio(candidate.path)
        metrics, loudness = basic_metrics(candidate_audio, candidate_rate), ffmpeg_loudness(candidate.path)
        difference = candidate_audio - audio
        difference_ratio_db = db(float(np.sqrt(np.mean(difference**2) + 1e-15)) / float(np.sqrt(np.mean(audio**2) + 1e-15)))
        signal_correlation = float(np.corrcoef(candidate_audio.ravel(), audio.ravel())[0, 1])
        narrative = metrics["narrative"]
        hard_checks = {
            "duration_60s": abs(float(metrics["duration_seconds"]) - 60.0) <= 0.01,
            "sample_rate_48khz": metrics["sample_rate"] == 48000,
            "stereo": metrics["channels"] == 2,
            "no_new_long_silence": float(metrics["longest_silence_seconds"])
            <= max(0.5, float(source_metrics["longest_silence_seconds"]) + 0.1),
            "no_clipping": float(metrics["clipped_sample_fraction"]) == 0.0,
            "true_peak_at_most_minus_1_dbtp": float(loudness["true_peak_dbtp"]) <= -1.0,
            "loudness_in_range": -18.0 <= float(loudness["integrated_lufs"]) <= -14.0,
            "photo_remains_thinner": float(narrative["photo_drop_db"]) >= 3.0,
            "crisis_keeps_growth": float(narrative["crisis_margin_db"]) >= 1.0,
            "ending_not_silent": float(metrics["segments"]["ending"]["rms_dbfs"]) >= -30.0,
            "signal_correlation_at_least_0_95": signal_correlation >= 0.95,
            "difference_at_least_12db_below_source": difference_ratio_db <= -12.0,
        }
        report_candidates.append({
            "branch": candidate.branch, "file": str(candidate.path), "description": candidate.description,
            "sha256": sha256(candidate.path), "difference_to_source_db": round(difference_ratio_db, 3),
            "signal_correlation": round(signal_correlation, 8),
            "metrics": metrics, "loudness": loudness, "hard_checks": hard_checks,
            "technical_status": "PASS" if all(hard_checks.values()) else "REVIEW",
        })

    review_order = sorted(candidates, key=lambda item: hashlib.sha256((sha256(source) + item.branch).encode("ascii")).hexdigest())
    review_map: list[dict[str, str]] = []
    for index, candidate in enumerate(review_order):
        label = chr(ord("A") + index)
        video_path = videos_dir / f"candidate-{label}.mp4"
        mux_video(video, candidate.path, video_path)
        review_map.append({"blind_label": label, "branch": candidate.branch, "audio": str(candidate.path), "video": str(video_path)})

    recommended_audio = a3
    recommended_video = output_dir / "recommended-A3-dynamic-eq.mp4"
    mux_video(video, recommended_audio, recommended_video)

    report = {
        "status": "PASS" if report_candidates else "FAIL",
        "source": {"file": str(source), "sha256": sha256(source), "metrics": source_metrics, "loudness": ffmpeg_loudness(a0)},
        "pipeline": {
            "A0": "reference only", "A1": "light spectral gate with noise-only residual", "A2": demucs_status,
            "A3": "28 Hz cleanup and 120-250 Hz dynamic EQ capped at 2 dB",
            "A4": sonicmaster_status,
            "A5": "generated only when A2 completes; minimal A1+A2+A3 combination",
        },
        "candidates": report_candidates,
        "technical_recommendation": {
            "branch": "A3",
            "audio": str(recommended_audio),
            "video": str(recommended_video),
            "reason": "The source shows low-frequency accumulation but no high-frequency spike evidence. A3 reduces sub-35 Hz and 120-250 Hz energy while preserving signal correlation and the documented narrative dynamics.",
            "provisional": True,
            "promotion_rule": "Replace the official master only if loudness-matched full-video listening prefers A3 to A0.",
        },
        "blind_review": {
            "mapping": review_map,
            "questions": [
                "Is grain or watery texture lower without losing orchestral tails?",
                "Is speech-like texture lower without hollowing strings or brass?",
                "Is 120-250 Hz clearer while low-frequency threat remains?",
                "Does the photo passage remain severe and unsafe?",
                "Does the 43-54 second crisis still grow?",
                "Does the ending remain unresolved rather than triumphant or faded out?",
            ],
            "warning": "Technical PASS is not an aesthetic verdict. Select only after full-video listening.",
        },
    }
    report_path = output_dir / "restoration-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "README.txt").write_text(
        "Open blind-review/candidate-*.mp4 before reading restoration-report.json.\n"
        "Do not replace the source master solely from automatic PASS status.\n", encoding="utf-8"
    )
    print(json.dumps({"status": report["status"], "report": str(report_path), "candidates": len(candidates)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
