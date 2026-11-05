from __future__ import annotations

import math
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]
SSO = ROOT / ".tools" / "sso" / "repo" / "Sonatina Symphonic Orchestra" / "Samples"
OUTPUT = ROOT / "output" / "music" / "auditions" / "sso-resistance-strings-15s.wav"
SR = 44100
DURATION = 15.0


NOTE_NAMES = {
    36: "c2", 39: "d#2", 42: "f#2", 45: "a2",
    48: "c3", 51: "d#3", 54: "f#3", 57: "a3",
    60: "c4", 63: "d#4", 66: "f#4", 69: "a4",
}


def nearest_root(note: int, roots: tuple[int, ...]) -> int:
    return min(roots, key=lambda root: abs(root - note))


def find_sample(instrument: str, articulation: str, note: int, rr: int) -> tuple[Path, int]:
    roots = tuple(NOTE_NAMES)
    root = nearest_root(note, roots)
    stem = f"{instrument}-{articulation}-rr{rr}-{NOTE_NAMES[root]}"
    directory = SSO / {"basses": "Basses", "celli": "Celli", "violas": "Violas"}[instrument]
    for extension in (".wav", ".flac"):
        path = directory / f"{stem}{extension}"
        if path.exists():
            return path, root
    raise FileNotFoundError(f"Missing SSO sample: {directory / stem}")


def load_note(instrument: str, articulation: str, note: int, rr: int, duration: float) -> np.ndarray:
    path, root = find_sample(instrument, articulation, note, rr)
    audio, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    if sample_rate != SR:
        audio = np.stack([librosa.resample(audio[:, channel], orig_sr=sample_rate, target_sr=SR) for channel in range(audio.shape[1])], axis=1)
    steps = note - root
    if steps:
        audio = np.stack([librosa.effects.pitch_shift(audio[:, channel], sr=SR, n_steps=steps) for channel in range(audio.shape[1])], axis=1)
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    target = max(1, round(duration * SR))
    audio = audio[:target]
    if len(audio) < target:
        audio = np.pad(audio, ((0, target - len(audio)), (0, 0)))
    attack = min(round(0.008 * SR), len(audio))
    release = min(round(0.08 * SR), len(audio))
    if attack:
        audio[:attack] *= np.linspace(0, 1, attack, dtype=np.float32)[:, None]
    if release:
        audio[-release:] *= np.linspace(1, 0, release, dtype=np.float32)[:, None]
    return audio


def pan(audio: np.ndarray, position: float) -> np.ndarray:
    angle = (position + 1.0) * math.pi / 4.0
    mono = audio.mean(axis=1)
    return np.stack((mono * math.cos(angle), mono * math.sin(angle)), axis=1)


def add_note(mix: np.ndarray, start: float, instrument: str, articulation: str, note: int, rr: int, duration: float, gain: float, position: float) -> None:
    audio = pan(load_note(instrument, articulation, note, rr, duration), position) * gain
    offset = round(start * SR)
    end = min(len(mix), offset + len(audio))
    if end > offset:
        mix[offset:end] += audio[: end - offset]


def main() -> None:
    mix = np.zeros((round(DURATION * SR), 2), dtype=np.float32)
    pulse_times = (0.00, 0.66, 1.38, 2.46, 3.12, 4.35, 5.02, 6.18, 7.26, 8.02, 9.31, 10.04, 11.42, 12.17, 13.36, 14.08)
    pulse_notes = (38, 45, 38, 39, 45, 38, 45, 39)
    for index, start in enumerate(pulse_times):
        add_note(mix, start, "basses", "piz", pulse_notes[index % len(pulse_notes)], index % 2 + 1, 0.72, 0.66, -0.35)

    phrases = (2.8, 5.55, 8.55, 11.35)
    for phrase_index, start in enumerate(phrases):
        for note_index, (offset, note) in enumerate(((0.0, 50), (0.72, 53), (1.43, 56))):
            add_note(mix, start + offset, "celli", "stc", note, (phrase_index + note_index) % 2 + 1, 0.58, 0.58 + phrase_index * 0.025, 0.18)

    counter = ((5.0, 63), (5.82, 62), (6.98, 58), (7.72, 57), (9.72, 63), (10.48, 62), (12.68, 58), (13.54, 57))
    for index, (start, note) in enumerate(counter):
        add_note(mix, start, "violas", "stc", note, index % 2 + 1, 0.52, 0.43, 0.48)

    # Unequal, dry ensemble challenges replace the old low-brass stabs.
    for challenge_index, start in enumerate((8.78, 11.86, 14.22)):
        for note_index, note in enumerate((50, 51, 56)):
            add_note(mix, start + note_index * 0.018, "celli", "stc", note, (challenge_index + note_index) % 2 + 1, 0.42, 0.45, 0.05)

    # A short room tail made from decorrelated taps, not a long funeral-style reverb.
    dry = mix.copy()
    for delay, gain, swap in ((0.043, 0.18, False), (0.071, 0.11, True), (0.109, 0.07, False)):
        offset = round(delay * SR)
        source = dry[:, ::-1] if swap else dry
        mix[offset:] += source[:-offset] * gain
    peak = float(np.max(np.abs(mix)))
    if peak > 0:
        mix *= (10 ** (-1.0 / 20.0)) / peak
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sf.write(OUTPUT, mix, SR, subtype="PCM_24")
    print(OUTPUT)


if __name__ == "__main__":
    main()
