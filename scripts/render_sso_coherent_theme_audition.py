from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

import render_sso_confrontation_audition as sso


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "music" / "auditions" / "sso-coherent-confrontation-theme-30s.wav"
SR = sso.SR
DURATION = 30.0
BAR = 3.75  # 64 BPM, 4/4


def sustain(
    mix: np.ndarray,
    start: float,
    instrument: str,
    note: int,
    duration: float,
    gain: float,
    position: float,
) -> None:
    audio = sso.pitched_note(instrument, "sus", note, duration)
    sso.place(mix, audio, start, gain, position)


def chord(
    mix: np.ndarray,
    start: float,
    duration: float,
    notes: tuple[int, int, int, int],
    gain: float,
) -> None:
    instruments = ("basses", "celli", "celli", "violas")
    positions = (-0.38, -0.16, 0.16, 0.40)
    balances = (1.0, 0.82, 0.68, 0.52)
    for instrument, position, balance, note in zip(instruments, positions, balances, notes):
        sustain(mix, start, instrument, note, duration, gain * balance, position)


def melody(
    mix: np.ndarray,
    events: tuple[tuple[float, int, float, float], ...],
    instrument: str,
    position: float,
) -> None:
    for start, note, duration, gain in events:
        # Slight overlaps bind the notes into phrases instead of isolated attacks.
        sustain(mix, start, instrument, note, duration + 0.10, gain, position)


def main() -> None:
    mix = np.zeros((round(DURATION * SR), 2), dtype=np.float32)

    # Eight-bar harmonic argument with parsimonious voice leading. The low D/A
    # anchors public confrontation while the inner voices supply unresolved motion.
    harmony = (
        (0 * BAR, (38, 45, 50, 63), 0.22),  # Dm(add b9)
        (1 * BAR, (38, 45, 53, 62), 0.23),  # Dm/A, inner voice descends
        (2 * BAR, (38, 46, 51, 62), 0.24),  # E-flat over D
        (3 * BAR, (43, 50, 55, 58), 0.25),  # G minor
        (4 * BAR, (38, 45, 50, 63), 0.26),  # thematic return
        (5 * BAR, (39, 46, 53, 62), 0.27),  # E-flat / B-flat pressure
        (6 * BAR, (45, 52, 58, 62), 0.29),  # A sus(b9), no dominant triumph
        (7 * BAR, (38, 45, 51, 62), 0.31),  # unresolved D/E-flat field
    )
    for start, notes, gain in harmony:
        chord(mix, start, BAR + 0.16, notes, gain)

    # One recognizable two-bar idea, followed by development and an augmented
    # return. Rhythms vary within a shared meter rather than abandoning meter.
    cello_theme = (
        (0.42, 50, 1.58, 0.34),
        (2.17, 51, 0.72, 0.35),
        (3.02, 57, 0.66, 0.36),
        (3.84, 55, 2.16, 0.37),
        (6.18, 53, 1.12, 0.36),
        # Development: same interval tensions, compressed and displaced.
        (7.66, 50, 0.96, 0.38),
        (8.78, 53, 0.81, 0.39),
        (9.74, 51, 1.36, 0.40),
        (11.39, 46, 1.82, 0.41),
        (13.42, 45, 0.64, 0.42),
        (14.22, 50, 0.73, 0.43),
        # Augmented return: the opening is recognizable but breathes differently.
        (15.18, 50, 2.32, 0.44),
        (17.67, 51, 1.08, 0.45),
        (18.94, 57, 0.92, 0.46),
        (20.02, 55, 1.56, 0.47),
        # Final continuation refuses the expected cadence.
        (21.82, 53, 0.82, 0.48),
        (22.79, 51, 1.27, 0.49),
        (24.25, 50, 0.69, 0.50),
        (25.08, 46, 1.42, 0.51),
        (26.72, 51, 2.98, 0.48),
    )
    melody(mix, cello_theme, "celli", 0.02)

    # A sparse counterline enters only after the theme is established and moves
    # mainly by step, keeping the ensemble coherent rather than conversational.
    viola_counterline = (
        (4.62, 62, 2.12, 0.20),
        (7.92, 63, 1.46, 0.21),
        (9.58, 62, 1.72, 0.22),
        (12.04, 58, 2.34, 0.23),
        (16.02, 62, 1.68, 0.24),
        (17.94, 63, 1.14, 0.25),
        (19.30, 62, 2.05, 0.26),
        (22.14, 58, 1.48, 0.27),
        (24.08, 62, 1.92, 0.28),
        (26.38, 63, 3.32, 0.29),
    )
    melody(mix, viola_counterline, "violas", 0.38)

    # Structural accents only. Their irregular spacing follows phrase endings,
    # while the stable bar structure supplies continuity underneath.
    for filename, start, gain in (
        ("timpani-p-rh-d#1.wav", 7.42, 0.18),
        ("timpani-roll-crsc-a1.wav", 13.74, 0.18),
        ("timpani-p-lh-d#1.wav", 15.02, 0.22),
        ("timpani-roll-crsc-d#1.wav", 24.92, 0.21),
        ("timpani-f-rh-a1.wav", 27.84, 0.30),
    ):
        sso.add_percussion(mix, filename, start, gain)

    dry = mix.copy()
    for delay, gain, swap in ((0.054, 0.12, True), (0.101, 0.075, False), (0.163, 0.04, True)):
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
