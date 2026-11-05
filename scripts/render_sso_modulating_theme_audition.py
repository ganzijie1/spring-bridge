from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

import render_sso_confrontation_audition as sso


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "music" / "auditions" / "sso-modulating-confrontation-theme-36s.wav"
SR = sso.SR
DURATION = 36.0
BAR = 3.0  # 80 BPM, 4/4


def sustain(
    mix: np.ndarray,
    start: float,
    instrument: str,
    note: int,
    duration: float,
    gain: float,
    position: float,
) -> None:
    sso.place(mix, sso.pitched_note(instrument, "sus", note, duration), start, gain, position)


def add_harmony(
    mix: np.ndarray,
    start: float,
    notes: tuple[int, int, int, int],
    gain: float,
) -> None:
    for instrument, position, balance, note in zip(
        ("basses", "celli", "celli", "violas"),
        (-0.39, -0.15, 0.15, 0.40),
        (1.0, 0.82, 0.68, 0.51),
        notes,
    ):
        sustain(mix, start, instrument, note, BAR + 0.15, gain * balance, position)


def add_phrase(
    mix: np.ndarray,
    events: tuple[tuple[float, int, float, float], ...],
    instrument: str = "celli",
    position: float = 0.04,
) -> None:
    for start, note, duration, gain in events:
        sustain(mix, start, instrument, note, duration + 0.10, gain, position)


def main() -> None:
    mix = np.zeros((round(DURATION * SR), 2), dtype=np.float32)

    # A circle-of-fourths tonal journey supplies large-scale direction. Alternate
    # bars add a semitone neighbour above each tonic to preserve the crisis colour.
    harmonies = (
        ((38, 45, 50, 53), 0.205),  # D minor
        ((38, 46, 51, 55), 0.215),  # E-flat over D pivot
        ((43, 50, 55, 58), 0.225),  # G minor
        ((43, 51, 56, 60), 0.235),  # A-flat over G pivot
        ((36, 43, 48, 51), 0.245),  # C minor
        ((36, 44, 49, 53), 0.255),  # D-flat over C pivot
        ((41, 48, 53, 56), 0.265),  # F minor
        ((41, 49, 54, 58), 0.275),  # G-flat over F pivot
        ((34, 41, 46, 49), 0.285),  # B-flat minor
        ((34, 42, 47, 51), 0.295),  # C-flat over B-flat pivot
        ((33, 40, 46, 50), 0.305),  # A sus(b9)
        ((38, 45, 51, 57), 0.315),  # unresolved D/E-flat return
    )
    for bar_index, (notes, gain) in enumerate(harmonies):
        add_harmony(mix, bar_index * BAR, notes, gain)

    # The same interval identity migrates through six tonal centres. Each phrase
    # has a different rhythmic form, so recognition comes from contour, not looping.
    phrases = (
        # D: original statement.
        (
            (0.36, 50, 1.24, 0.32), (1.74, 51, 0.53, 0.33),
            (2.42, 57, 0.48, 0.34), (3.09, 55, 1.39, 0.35),
            (4.66, 53, 0.97, 0.34),
        ),
        # G: compressed head and broadened answer.
        (
            (6.19, 55, 0.76, 0.36), (7.08, 56, 0.44, 0.37),
            (7.66, 62, 0.71, 0.38), (8.55, 60, 1.71, 0.39),
            (10.49, 58, 1.05, 0.38),
        ),
        # C: displaced entry with a held centre.
        (
            (12.42, 48, 1.06, 0.40), (13.64, 49, 0.68, 0.41),
            (14.48, 55, 1.31, 0.42), (15.98, 53, 0.82, 0.43),
            (17.04, 51, 1.43, 0.42),
        ),
        # F: augmented, heavier version.
        (
            (18.18, 53, 1.53, 0.44), (19.89, 54, 0.79, 0.45),
            (20.85, 60, 0.62, 0.46), (21.66, 58, 1.16, 0.47),
            (23.06, 56, 1.49, 0.46),
        ),
        # B-flat: fragmented under pressure.
        (
            (24.27, 58, 0.69, 0.48), (25.14, 59, 0.42, 0.49),
            (25.73, 65, 0.91, 0.50), (26.89, 63, 0.57, 0.51),
            (27.62, 61, 1.78, 0.50),
        ),
        # A function and D return: the contour is cut short and left unresolved.
        (
            (30.16, 57, 0.88, 0.52), (31.22, 58, 0.51, 0.53),
            (31.91, 64, 0.73, 0.54), (32.83, 62, 0.61, 0.55),
            (33.61, 50, 0.94, 0.54), (34.73, 51, 1.17, 0.52),
        ),
    )
    for phrase in phrases:
        add_phrase(mix, phrase)

    # Long upper tones reveal each modulation while avoiding a second busy melody.
    counterline = (
        (4.05, 62, 1.67, 0.18),
        (9.46, 63, 2.03, 0.20),
        (15.31, 60, 1.49, 0.22),
        (21.38, 61, 1.82, 0.24),
        (27.16, 66, 2.21, 0.26),
        (32.47, 63, 3.18, 0.28),
    )
    add_phrase(mix, counterline, instrument="violas", position=0.39)

    # Only three irreversible structural markers; percussion never carries the beat.
    for filename, start, gain in (
        ("timpani-roll-crsc-d#1.wav", 10.92, 0.17),
        ("timpani-p-rh-a1.wav", 23.72, 0.21),
        ("timpani-roll-crsc-a1.wav", 31.44, 0.22),
        ("timpani-f-lh-d#1.wav", 33.42, 0.29),
    ):
        sso.add_percussion(mix, filename, start, gain)

    dry = mix.copy()
    for delay, gain, swap in ((0.056, 0.115, True), (0.104, 0.07, False), (0.168, 0.038, True)):
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
