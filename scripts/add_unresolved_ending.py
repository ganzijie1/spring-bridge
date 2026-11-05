from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a quiet unresolved low cluster to an abandoned ending")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=float, default=86.0)
    args = parser.parse_args()

    audio, sample_rate = sf.read(args.source, dtype="float32", always_2d=True)
    if sample_rate != 48000:
        raise SystemExit(f"Expected 48 kHz input, received {sample_rate}")
    start = round(args.start * sample_rate)
    if start >= len(audio):
        raise SystemExit("Ending start falls beyond the source")

    length = len(audio) - start
    t = np.arange(length, dtype=np.float64) / sample_rate
    attack = np.minimum(t / 0.8, 1.0)
    release = np.minimum((length / sample_rate - t) / 0.035, 1.0)
    envelope = np.clip(attack * release, 0.0, 1.0)
    slow_breath = 0.82 + 0.18 * np.sin(2.0 * math.pi * 0.17 * t + 0.6)

    frequencies = [36.708, 38.891, 51.913]
    phases = [0.0, 1.7, 3.1]
    cluster = sum(
        np.sin(2.0 * math.pi * frequency * t + phase)
        for frequency, phase in zip(frequencies, phases)
    ) / len(frequencies)
    cluster *= 0.065 * envelope * slow_breath

    left = cluster + 0.012 * np.sin(2.0 * math.pi * 73.416 * t + 0.2) * envelope
    right = cluster + 0.012 * np.sin(2.0 * math.pi * 77.782 * t + 1.1) * envelope
    overlay = np.column_stack([left, right]).astype(np.float32)
    if audio.shape[1] == 1:
        overlay = overlay.mean(axis=1, keepdims=True)
    audio[start:] = np.clip(audio[start:] + overlay[:, : audio.shape[1]], -0.98, 0.98)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.output, audio, sample_rate, subtype="PCM_24")
    report = {
        "source": str(args.source.resolve()),
        "output": str(args.output.resolve()),
        "start_seconds": args.start,
        "frequencies_hz": frequencies,
        "purpose": "quiet unresolved ending presence; no melody or rhythmic event added",
    }
    args.output.with_suffix(".ending.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
