from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

import render_sso_confrontation_audition as sso


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "music" / "counterfactual-last-stand-48.wav"
SR = sso.SR
DURATION = 48.0
BRASS_ROOTS = {
    40: "e2", 43: "g2", 46: "a#2", 49: "c#3",
    52: "e3", 55: "g3", 58: "a#3", 61: "c#4",
    64: "e4", 67: "g4", 70: "a#4",
}


def brass_note(section: str, note: int, duration: float, dynamic: str = "mp") -> np.ndarray:
    root = min(BRASS_ROOTS, key=lambda candidate: abs(candidate - note))
    label = BRASS_ROOTS[root]
    if section == "horns":
        filename = f"horns-sus-{dynamic}-{label}-PB-loop.wav"
        directory = "Horns"
    else:
        filename = f"trombones-sus-{label}.wav"
        directory = "Trombones"
    audio = sso.read_audio(sso.SSO / directory / filename)
    semitones = note - root
    if semitones:
        audio = np.stack(
            [librosa.effects.pitch_shift(audio[:, channel], sr=SR, n_steps=semitones) for channel in range(2)],
            axis=1,
        )
    return sso.fit_duration(audio, duration, release=min(0.55, duration * 0.3))


def add_brass(mix: np.ndarray, section: str, note: int, start: float, duration: float, gain: float, pan: float) -> None:
    sso.place(mix, brass_note(section, note, duration), start, gain, pan)


def add_string_phrase(
    mix: np.ndarray,
    start: float,
    notes: tuple[int, ...],
    durations: tuple[float, ...],
    gain: float,
    register: str,
) -> None:
    cursor = start
    for index, (note, duration) in enumerate(zip(notes, durations)):
        sso.add_marcato(mix, cursor, register, note, duration, gain * (1.0 - index * 0.035), -0.16, index % 2 + 1)
        cursor += duration


def gain_curve(mix: np.ndarray, points: tuple[tuple[float, float], ...]) -> None:
    positions = np.array([round(time * SR) for time, _ in points], dtype=np.int64)
    gains = np.array([gain for _, gain in points], dtype=np.float32)
    mix *= np.interp(np.arange(len(mix)), positions, gains).astype(np.float32)[:, None]


def main() -> None:
    mix = np.zeros((round(DURATION * SR), 2), dtype=np.float32)

    # The pressure inherited from the campaign cue changes harmony and density
    # every field; it is continuous, but never a copied loop.
    fields = (
        (0.0, 8.2, ((38, 0.22), (45, 0.13), (51, 0.09))),
        (7.4, 8.3, ((39, 0.24), (45, 0.15), (50, 0.10))),
        (15.0, 8.6, ((38, 0.26), (44, 0.16), (53, 0.11))),
        (22.9, 8.0, ((39, 0.28), (45, 0.18), (50, 0.12))),
        (30.2, 8.7, ((38, 0.31), (44, 0.20), (51, 0.14))),
        (38.1, 9.9, ((38, 0.25), (39, 0.20), (45, 0.13))),
    )
    for field_index, (start, duration, notes) in enumerate(fields):
        for note_index, (note, gain) in enumerate(notes):
            instrument = "basses" if note < 43 else "celli"
            sso.add_tremolo(mix, start, instrument, note, duration, gain, -0.30 + note_index * 0.28 + field_index * 0.01)

    # D-Eb-A-F appears in different durations and directions. The last phrase
    # reaches upward once, then falls back without a cadence.
    add_string_phrase(mix, 3.2, (50, 51, 45, 53), (1.15, 1.05, 1.55, 2.00), 0.42, "celli")
    add_string_phrase(mix, 10.2, (45, 50, 53, 51), (1.35, 1.20, 1.70, 2.15), 0.46, "celli")
    add_string_phrase(mix, 18.1, (51, 53, 50, 45), (1.65, 1.45, 2.05, 2.55), 0.50, "celli")
    add_string_phrase(mix, 27.0, (50, 53, 57, 55, 51), (1.25, 1.30, 1.55, 1.60, 2.40), 0.55, "violas")
    add_string_phrase(mix, 36.0, (57, 55, 53, 51, 50), (1.25, 1.25, 1.45, 1.55, 3.20), 0.58, "violas")

    # Broad brass answers make the resistance public and collective, not furtive.
    for note, start, duration, gain, pan in (
        (50, 7.4, 3.7, 0.15, 0.22),
        (45, 14.2, 4.1, 0.17, 0.28),
        (51, 22.1, 4.6, 0.19, 0.24),
        (53, 30.4, 5.0, 0.22, 0.20),
        (50, 38.5, 6.2, 0.20, 0.18),
    ):
        add_brass(mix, "horns", note, start, duration, gain, pan)
    add_brass(mix, "trombones", 38, 32.0, 4.4, 0.12, -0.10)
    add_brass(mix, "trombones", 39, 39.0, 6.0, 0.10, -0.08)

    # Unequal punctuation prevents a parade rhythm and keeps the last stand moving.
    for filename, start, gain in (
        ("timpani-p-rh-d#1.wav", 0.35, 0.20),
        ("timpani-p-lh-a1.wav", 6.9, 0.22),
        ("timpani-p-rh-d#1.wav", 13.8, 0.23),
        ("timpani-f-lh-a1.wav", 21.7, 0.25),
        ("timpani-roll-crsc-d#1.wav", 29.9, 0.20),
        ("timpani-f-rh-d#1.wav", 35.8, 0.28),
        ("timpani-roll-crsc-a1.wav", 39.8, 0.18),
    ):
        sso.add_percussion(mix, filename, start, gain)

    dry = mix.copy()
    for delay, gain, swap in ((0.061, 0.13, True), (0.107, 0.085, False), (0.173, 0.045, True)):
        offset = round(delay * SR)
        source = dry[:, ::-1] if swap else dry
        mix[offset:] += source[:-offset] * gain

    gain_curve(mix, (
        (0.0, 0.72), (8.0, 0.82), (18.0, 0.90), (28.0, 0.98),
        (36.0, 1.07), (40.5, 1.12), (43.0, 0.92), (48.0, 0.50),
    ))
    highpass = butter(3, 31.0, btype="highpass", fs=SR, output="sos")
    lowpass = butter(3, 16_500.0, btype="lowpass", fs=SR, output="sos")
    mix = np.stack([sosfilt(lowpass, sosfilt(highpass, mix[:, channel])) for channel in range(2)], axis=1).astype(np.float32)
    peak = float(np.max(np.abs(mix)))
    if peak:
        mix *= (10 ** (-1.8 / 20.0)) / peak

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sf.write(OUTPUT, mix, SR, subtype="PCM_24")
    print(OUTPUT)


if __name__ == "__main__":
    main()
