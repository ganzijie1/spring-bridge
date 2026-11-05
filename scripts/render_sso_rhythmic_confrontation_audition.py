from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

import render_sso_confrontation_audition as sso


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "music" / "auditions" / "sso-rhythmic-confrontation-26s.wav"
SR = sso.SR
DURATION = 26.0


def tremolo_chord(
    mix: np.ndarray,
    start: float,
    duration: float,
    notes: tuple[int, ...],
    gain: float,
) -> None:
    for index, note in enumerate(notes):
        instrument = "basses" if note < 43 else "celli"
        sso.add_tremolo(mix, start, instrument, note, duration, gain * (1.0 - index * 0.17), -0.34 + index * 0.31)


def string_strike(
    mix: np.ndarray,
    start: float,
    duration: float,
    notes: tuple[int, ...],
    gain: float,
    variation: int,
) -> None:
    pans = (-0.42, -0.08, 0.34)
    for index, note in enumerate(notes):
        instrument = "celli" if note < 48 else "violas"
        sso.add_marcato(mix, start, instrument, note, duration, gain, pans[index], variation % 2 + 1)


def main() -> None:
    mix = np.zeros((round(DURATION * SR), 2), dtype=np.float32)

    # Sustained pressure changes harmony under the rhythm instead of acting as a loop.
    tremolo_chord(mix, 0.0, 6.3, (38, 45, 51), 0.31)
    tremolo_chord(mix, 5.8, 6.8, (39, 45, 50), 0.35)
    tremolo_chord(mix, 12.0, 5.2, (38, 44, 51), 0.39)
    tremolo_chord(mix, 17.0, 3.4, (39, 45, 50), 0.25)
    tremolo_chord(mix, 19.8, 6.2, (38, 44, 51), 0.45)

    # Phase A: broad deployment, deliberately spacious but not periodic.
    phase_a = (
        (0.35, 1.25, (38, 45, 51), 0.46),
        (2.05, 0.90, (38, 44, 50), 0.48),
        (3.22, 1.45, (39, 45, 50), 0.50),
        (5.12, 1.75, (38, 44, 51), 0.53),
    )

    # Phase B: a 3+3+2 accent field. These are broad ensemble strokes, not furtive taps.
    phase_b = (
        (7.18, 0.95, (39, 45, 50), 0.54),
        (8.55, 0.88, (38, 44, 51), 0.55),
        (9.92, 0.72, (39, 45, 50), 0.57),
        (10.84, 1.42, (38, 44, 51), 0.59),
    )

    # Phase C: intervals contract toward the confrontation, then stop on a held breath.
    phase_c = (
        (12.70, 1.05, (39, 45, 50), 0.60),
        (14.02, 0.82, (38, 44, 51), 0.62),
        (15.06, 0.68, (39, 45, 50), 0.64),
        (15.91, 1.18, (38, 44, 51), 0.67),
    )

    # Phase D: low and middle strings exchange unequal spans after the breath.
    phase_d = (
        (19.72, 1.30, (38, 45, 51), 0.59),
        (21.31, 0.70, (39, 45, 50), 0.62),
        (22.18, 1.12, (38, 44, 51), 0.65),
        (23.58, 0.78, (39, 45, 50), 0.68),
        (24.54, 1.42, (38, 44, 51), 0.72),
    )

    all_phases = phase_a + phase_b + phase_c + phase_d
    for index, (start, duration, notes, gain) in enumerate(all_phases):
        string_strike(mix, start, duration, notes, gain, index)

    # Timpani confirms structural boundaries only; it does not carry the beat.
    for filename, start, gain in (
        ("timpani-p-rh-d#1.wav", 5.05, 0.25),
        ("timpani-p-lh-a1.wav", 10.78, 0.27),
        ("timpani-roll-crsc-d#1.wav", 14.90, 0.25),
        ("timpani-f-rh-d#1.wav", 16.62, 0.34),
        ("timpani-p-lh-a1.wav", 19.65, 0.27),
        ("timpani-f-rh-d#1.wav", 24.48, 0.38),
    ):
        sso.add_percussion(mix, filename, start, gain)

    dry = mix.copy()
    for delay, gain, swap in ((0.050, 0.14, True), (0.091, 0.09, False), (0.147, 0.05, True)):
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
