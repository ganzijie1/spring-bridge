from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

import render_sso_confrontation_audition as sso


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "music" / "auditions" / "sso-through-composed-confrontation-38s.wav"
SR = sso.SR
DURATION = 38.0


def add_bed(
    mix: np.ndarray,
    start: float,
    duration: float,
    notes: tuple[int, int, int],
    gain: float,
) -> None:
    for index, note in enumerate(notes):
        instrument = "basses" if note < 43 else "celli"
        sso.add_tremolo(
            mix,
            start,
            instrument,
            note,
            duration,
            gain * (1.0 - 0.18 * index),
            (-0.38, -0.02, 0.34)[index],
        )


def add_voice(
    mix: np.ndarray,
    instrument: str,
    events: tuple[tuple[float, int, float, float], ...],
    position: float,
    variation_offset: int,
) -> None:
    for index, (start, note, duration, gain) in enumerate(events):
        sso.add_marcato(
            mix,
            start,
            instrument,
            note,
            duration,
            gain,
            position,
            (index + variation_offset) % 2 + 1,
        )


def main() -> None:
    mix = np.zeros((round(DURATION * SR), 2), dtype=np.float32)

    # Harmonic pressure is continuous, but every field changes duration and voicing.
    for field in (
        (0.0, 8.2, (38, 45, 51), 0.24),
        (7.7, 7.9, (39, 45, 50), 0.27),
        (15.1, 8.7, (38, 44, 51), 0.30),
        (23.2, 7.8, (39, 45, 50), 0.33),
        (30.4, 7.6, (38, 44, 51), 0.37),
    ):
        add_bed(mix, *field)

    # No onset-interval series is repeated. The lower line alternately advances,
    # waits, interrupts, and broadens instead of carrying an ostinato.
    lower = (
        (0.42, 38, 1.55, 0.39),
        (2.63, 45, 0.82, 0.41),
        (4.08, 39, 2.18, 0.43),
        (7.12, 44, 1.06, 0.45),
        (8.67, 38, 1.72, 0.46),
        (11.31, 45, 0.68, 0.47),
        (13.17, 39, 2.42, 0.49),
        (16.61, 44, 0.91, 0.50),
        (18.02, 38, 1.34, 0.52),
        (20.58, 45, 2.31, 0.54),
        (24.21, 39, 0.73, 0.55),
        (25.27, 44, 1.46, 0.57),
        (27.18, 38, 0.86, 0.59),
        (29.92, 45, 1.92, 0.60),
        (31.18, 39, 0.77, 0.62),
        (33.52, 44, 1.63, 0.64),
        (35.23, 38, 0.96, 0.66),
        (37.02, 45, 0.98, 0.57),
    )

    # The middle voice carries a contour rather than a repeated beat. Its later
    # forms are shortened, displaced, and occasionally overlap the lower line.
    middle = (
        (1.18, 50, 1.86, 0.35),
        (3.46, 51, 0.74, 0.36),
        (5.83, 57, 2.06, 0.38),
        (8.03, 53, 1.11, 0.40),
        (9.94, 50, 2.27, 0.41),
        (12.49, 56, 0.69, 0.43),
        (15.14, 51, 1.58, 0.45),
        (17.36, 57, 0.83, 0.46),
        (19.39, 53, 2.14, 0.48),
        (22.24, 50, 0.71, 0.50),
        (23.47, 56, 1.37, 0.51),
        (26.03, 51, 0.92, 0.53),
        (28.53, 57, 1.76, 0.55),
        (30.57, 53, 0.66, 0.56),
        (32.43, 50, 1.24, 0.58),
        (34.84, 56, 0.79, 0.60),
        (36.46, 51, 1.54, 0.55),
    )

    # The upper line appears only at turns. It never doubles either lower rhythm.
    upper = (
        (6.34, 62, 2.41, 0.28),
        (10.76, 63, 1.19, 0.30),
        (14.43, 68, 2.63, 0.32),
        (18.73, 65, 1.07, 0.34),
        (21.46, 62, 2.21, 0.36),
        (25.04, 68, 0.88, 0.38),
        (28.82, 63, 1.69, 0.40),
        (32.13, 65, 1.13, 0.42),
        (35.74, 62, 2.18, 0.44),
    )

    add_voice(mix, "celli", lower, -0.34, 0)
    add_voice(mix, "celli", middle, 0.08, 1)
    add_voice(mix, "violas", upper, 0.43, 0)

    # Each percussion event has a distinct role and spacing; none carries a meter.
    for filename, start, gain in (
        ("timpani-p-rh-d#1.wav", 5.47, 0.22),
        ("timpani-roll-crsc-a1.wav", 13.62, 0.21),
        ("timpani-f-lh-d#1.wav", 16.83, 0.31),
        ("timpani-p-rh-a1.wav", 24.92, 0.25),
        ("timpani-roll-crsc-d#1.wav", 31.66, 0.25),
        ("timpani-f-rh-a1.wav", 36.71, 0.37),
    ):
        sso.add_percussion(mix, filename, start, gain)

    dry = mix.copy()
    for delay, gain, swap in ((0.051, 0.14, True), (0.096, 0.085, False), (0.153, 0.045, True)):
        offset = round(delay * SR)
        source = dry[:, ::-1] if swap else dry
        mix[offset:] += source[:-offset] * gain

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
