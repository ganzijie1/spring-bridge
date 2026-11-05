from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

import render_sso_confrontation_audition as sso


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "music" / "shanghai-1976-imminent-confrontation-90.wav"
SR = sso.SR
DURATION = 90.0


def add_field(
    mix: np.ndarray,
    start: float,
    duration: float,
    notes: tuple[tuple[int, float], ...],
    pan_bias: float = 0.0,
) -> None:
    for index, (note, gain) in enumerate(notes):
        instrument = "basses" if note < 43 else "celli"
        position = -0.34 + index * 0.30 + pan_bias
        sso.add_tremolo(mix, start, instrument, note, duration, gain, position)


def add_declaration(
    mix: np.ndarray,
    start: float,
    duration: float,
    notes: tuple[int, int, int],
    gain: float,
    variation: int,
) -> None:
    for index, note in enumerate(notes):
        instrument = "celli" if note < 48 else "violas"
        position = (-0.40, 0.0, 0.40)[index]
        sso.add_marcato(mix, start, instrument, note, duration, gain, position, variation % 2 + 1)


def apply_gain_curve(mix: np.ndarray, points: tuple[tuple[float, float], ...]) -> None:
    sample_points = np.array([round(time * SR) for time, _ in points], dtype=np.int64)
    gains = np.array([gain for _, gain in points], dtype=np.float32)
    envelope = np.interp(np.arange(len(mix)), sample_points, gains).astype(np.float32)
    mix *= envelope[:, None]


def main() -> None:
    mix = np.zeros((round(DURATION * SR), 2), dtype=np.float32)

    # Every field changes its internal interval. The overlap keeps pressure continuous
    # without copying the accepted 18-second audition as a loop.
    fields = (
        (0.0, 8.0, ((38, 0.24), (45, 0.16), (51, 0.08)), -0.03),
        (7.3, 7.5, ((38, 0.28), (44, 0.18), (50, 0.10)), 0.00),
        (14.0, 7.5, ((39, 0.30), (45, 0.20), (50, 0.12)), 0.03),
        (20.8, 7.2, ((38, 0.32), (44, 0.22), (51, 0.13)), -0.02),
        (27.2, 7.4, ((39, 0.35), (45, 0.24), (50, 0.15)), 0.02),
        (33.8, 6.8, ((38, 0.38), (44, 0.26), (51, 0.17)), -0.01),
        (39.8, 4.2, ((39, 0.41), (45, 0.28), (50, 0.19)), 0.03),
        (48.0, 7.5, ((38, 0.33), (45, 0.22), (51, 0.13)), -0.03),
        (54.8, 7.2, ((39, 0.36), (45, 0.24), (50, 0.15)), 0.00),
        (61.2, 7.4, ((38, 0.39), (44, 0.27), (51, 0.17)), 0.03),
        (67.8, 7.5, ((39, 0.43), (45, 0.30), (50, 0.19)), -0.02),
        (74.5, 7.2, ((38, 0.46), (44, 0.32), (51, 0.21)), 0.02),
        (80.9, 6.2, ((39, 0.49), (45, 0.34), (50, 0.23)), 0.00),
        (86.2, 3.8, ((38, 0.37), (44, 0.26), (51, 0.18)), -0.01),
    )
    for start, duration, notes, pan_bias in fields:
        add_field(mix, start, duration, notes, pan_bias)

    declarations = (
        (1.10, 2.50, (38, 45, 51), 0.38),
        (5.05, 2.20, (38, 44, 50), 0.41),
        (8.85, 2.45, (39, 45, 50), 0.44),
        (12.55, 2.20, (38, 44, 51), 0.46),
        (16.10, 2.55, (39, 45, 50), 0.48),
        (19.75, 2.25, (38, 44, 51), 0.50),
        (23.15, 2.50, (39, 45, 50), 0.52),
        (26.75, 2.30, (38, 44, 51), 0.54),
        (30.10, 2.45, (39, 45, 50), 0.56),
        (33.35, 2.15, (38, 44, 51), 0.58),
        (36.40, 2.40, (39, 45, 50), 0.60),
        (39.35, 2.10, (38, 44, 51), 0.62),
        (42.05, 1.75, (39, 45, 50), 0.64),
        (48.10, 2.70, (38, 45, 51), 0.46),
        (52.00, 2.45, (39, 45, 50), 0.50),
        (55.65, 2.60, (38, 44, 51), 0.53),
        (59.20, 2.30, (39, 45, 50), 0.56),
        (62.55, 2.55, (38, 44, 51), 0.59),
        (65.75, 2.25, (39, 45, 50), 0.62),
        (68.75, 2.55, (38, 44, 51), 0.65),
        (71.65, 2.20, (39, 45, 50), 0.68),
        (74.45, 2.45, (38, 44, 51), 0.71),
        (77.15, 2.15, (39, 45, 50), 0.73),
        (79.70, 2.35, (38, 44, 51), 0.75),
        (82.10, 2.10, (39, 45, 50), 0.77),
        (84.35, 2.30, (38, 44, 51), 0.79),
        (87.00, 2.85, (39, 45, 50), 0.59),
    )
    for index, (start, duration, notes, gain) in enumerate(declarations):
        add_declaration(mix, start, duration, notes, gain, index)

    percussion = (
        ("timpani-p-rh-d#1.wav", 7.65, 0.25),
        ("timpani-p-lh-a1.wav", 14.35, 0.27),
        ("timpani-p-rh-d#1.wav", 21.60, 0.29),
        ("timpani-p-lh-a1.wav", 28.50, 0.30),
        ("timpani-p-rh-d#1.wav", 35.75, 0.32),
        ("timpani-roll-crsc-d#1.wav", 40.45, 0.24),
        ("timpani-f-lh-a1.wav", 42.65, 0.34),
        ("timpani-p-rh-d#1.wav", 48.05, 0.28),
        ("timpani-p-lh-a1.wav", 56.70, 0.30),
        ("timpani-p-rh-d#1.wav", 63.45, 0.32),
        ("timpani-f-lh-a1.wav", 70.45, 0.35),
        ("timpani-roll-crsc-d#1.wav", 75.75, 0.28),
        ("timpani-f-rh-d#1.wav", 79.80, 0.38),
        ("timpani-roll-crsc-a1.wav", 82.15, 0.30),
        ("timpani-f-lh-a1.wav", 85.15, 0.42),
    )
    for filename, start, gain in percussion:
        sso.add_percussion(mix, filename, start, gain)

    dry = mix.copy()
    for delay, gain, swap in ((0.052, 0.15, True), (0.093, 0.10, False), (0.151, 0.055, True)):
        offset = round(delay * SR)
        source = dry[:, ::-1] if swap else dry
        mix[offset:] += source[:-offset] * gain

    # The photograph passage is a held breath, not a dramatic impact or full stop.
    apply_gain_curve(mix, (
        (0.0, 0.82), (8.0, 0.90), (26.0, 0.98), (41.8, 1.00),
        (44.0, 0.055), (47.6, 0.045), (48.0, 0.78),
        (62.0, 0.92), (70.0, 1.00), (84.8, 1.08), (86.0, 0.88), (90.0, 0.62),
    ))

    highpass = butter(3, 34.0, btype="highpass", fs=SR, output="sos")
    mix = np.stack([sosfilt(highpass, mix[:, channel]) for channel in range(2)], axis=1).astype(np.float32)
    peak = float(np.max(np.abs(mix)))
    if peak:
        mix *= (10 ** (-1.5 / 20.0)) / peak

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sf.write(OUTPUT, mix, SR, subtype="PCM_24")
    print(OUTPUT)


if __name__ == "__main__":
    main()
