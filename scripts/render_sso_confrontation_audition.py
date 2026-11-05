from __future__ import annotations

import math
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt


ROOT = Path(__file__).resolve().parents[1]
SSO = ROOT / ".tools" / "sso" / "repo" / "Sonatina Symphonic Orchestra" / "Samples"
OUTPUT = ROOT / "output" / "music" / "auditions" / "sso-imminent-confrontation-18s.wav"
SR = 44100
DURATION = 18.0

NOTE_NAMES = {
    33: "a1", 36: "c2", 39: "d#2", 42: "f#2", 45: "a2",
    48: "c3", 51: "d#3", 54: "f#3", 57: "a3",
    60: "c4", 63: "d#4", 66: "f#4", 69: "a4",
}
INSTRUMENT_DIR = {"basses": "Basses", "celli": "Celli", "violas": "Violas"}


def nearest_root(note: int, allowed: tuple[int, ...]) -> int:
    return min(allowed, key=lambda root: abs(root - note))


def sample_path(instrument: str, articulation: str, note: int, rr: int = 1) -> tuple[Path, int]:
    if articulation in {"sus", "trm"}:
        allowed = tuple(NOTE_NAMES)
        stem_for = lambda root: f"{instrument}-{articulation}-{NOTE_NAMES[root]}"
    else:
        allowed = tuple(NOTE_NAMES)
        stem_for = lambda root: f"{instrument}-{articulation}-rr{rr}-{NOTE_NAMES[root]}"
    root = nearest_root(note, allowed)
    directory = SSO / INSTRUMENT_DIR[instrument]
    for extension in (".wav", ".flac"):
        candidate = directory / f"{stem_for(root)}{extension}"
        if candidate.exists():
            return candidate, root
    raise FileNotFoundError(f"No SSO sample for {instrument} {articulation} {note}")


def read_audio(path: Path) -> np.ndarray:
    audio, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    if sample_rate != SR:
        audio = np.stack(
            [librosa.resample(audio[:, channel], orig_sr=sample_rate, target_sr=SR) for channel in range(audio.shape[1])],
            axis=1,
        )
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    return audio


def fit_duration(audio: np.ndarray, duration: float, release: float = 0.22) -> np.ndarray:
    target = max(1, round(duration * SR))
    if len(audio) < target:
        # SSO sustained samples are long enough here; this is only a guarded loop fallback.
        body_start = min(round(0.8 * SR), len(audio) // 3)
        body_end = max(body_start + 1, len(audio) - round(0.5 * SR))
        body = audio[body_start:body_end]
        pieces = [audio[:body_start]]
        while sum(len(piece) for piece in pieces) < target:
            pieces.append(body)
        audio = np.concatenate(pieces, axis=0)
    audio = audio[:target].copy()
    attack = min(round(0.035 * SR), len(audio))
    tail = min(round(release * SR), len(audio))
    if attack:
        audio[:attack] *= np.linspace(0.0, 1.0, attack, dtype=np.float32)[:, None]
    if tail:
        audio[-tail:] *= np.linspace(1.0, 0.0, tail, dtype=np.float32)[:, None]
    return audio


def pitched_note(instrument: str, articulation: str, note: int, duration: float, rr: int = 1) -> np.ndarray:
    path, root = sample_path(instrument, articulation, note, rr)
    audio = read_audio(path)
    semitones = note - root
    if semitones:
        audio = np.stack(
            [librosa.effects.pitch_shift(audio[:, channel], sr=SR, n_steps=semitones) for channel in range(2)],
            axis=1,
        )
    return fit_duration(audio, duration)


def panned(audio: np.ndarray, position: float) -> np.ndarray:
    position = max(-1.0, min(1.0, position))
    angle = (position + 1.0) * math.pi / 4.0
    mono = audio.mean(axis=1)
    return np.stack((mono * math.cos(angle), mono * math.sin(angle)), axis=1)


def place(mix: np.ndarray, audio: np.ndarray, start: float, gain: float, position: float = 0.0) -> None:
    audio = panned(audio, position) * gain
    offset = round(start * SR)
    end = min(len(mix), offset + len(audio))
    if end > offset:
        mix[offset:end] += audio[: end - offset]


def add_tremolo(mix: np.ndarray, start: float, instrument: str, note: int, duration: float, gain: float, position: float) -> None:
    place(mix, pitched_note(instrument, "trm", note, duration), start, gain, position)


def add_marcato(mix: np.ndarray, start: float, instrument: str, note: int, duration: float, gain: float, position: float, rr: int) -> None:
    sustain = pitched_note(instrument, "sus", note, duration)
    attack = pitched_note(instrument, "stc", note, min(0.75, duration), rr)
    place(mix, sustain, start, gain * 0.78, position)
    place(mix, attack, start, gain * 0.48, position)


def add_percussion(mix: np.ndarray, filename: str, start: float, gain: float) -> None:
    audio = read_audio(SSO / "Percussion" / filename)
    # Preserve the natural decay instead of cutting it into a trailer-style impact.
    place(mix, audio, start, gain, 0.0)


def main() -> None:
    mix = np.zeros((round(DURATION * SR), 2), dtype=np.float32)

    # Unbroken tremolo fields: massed forces and unresolved pressure, not a tune.
    fields = (
        (0.0, 6.2, ((38, 0.34), (45, 0.24), (51, 0.13))),
        (5.7, 6.0, ((38, 0.39), (44, 0.27), (50, 0.17))),
        (11.2, 6.8, ((39, 0.44), (45, 0.30), (50, 0.20))),
    )
    for field_index, (start, duration, notes) in enumerate(fields):
        for note_index, (note, gain) in enumerate(notes):
            instrument = "basses" if note < 43 else "celli"
            pan = -0.32 + 0.28 * note_index + 0.05 * field_index
            add_tremolo(mix, start, instrument, note, duration, gain, pan)

    # Broad synchronized declarations. Long values and dense intervals make the
    # ensemble sound publicly arrayed, never furtive or conversational.
    declarations = (
        (0.45, 2.35, (38, 45, 51), 0.45),
        (3.55, 2.15, (38, 44, 50), 0.49),
        (6.55, 2.55, (39, 45, 50), 0.53),
        (9.65, 2.15, (38, 44, 51), 0.57),
        (12.45, 2.55, (39, 45, 50), 0.62),
        (15.35, 2.50, (38, 44, 51), 0.69),
    )
    for declaration_index, (start, duration, notes, gain) in enumerate(declarations):
        for note_index, note in enumerate(notes):
            instrument = "celli" if note < 48 else "violas"
            pan = (-0.38, 0.02, 0.42)[note_index]
            add_marcato(mix, start, instrument, note, duration, gain, pan, declaration_index % 2 + 1)

    # Restrained battlefield punctuation: four structural blows and one rising roll.
    add_percussion(mix, "timpani-p-rh-d#1.wav", 0.18, 0.31)
    add_percussion(mix, "timpani-p-lh-a1.wav", 6.30, 0.34)
    add_percussion(mix, "timpani-f-rh-d#1.wav", 11.95, 0.37)
    add_percussion(mix, "timpani-roll-crsc-d#1.wav", 14.25, 0.31)
    add_percussion(mix, "timpani-f-lh-a1.wav", 16.95, 0.43)

    # A compact scoring-stage tail glues the ranks together without turning solemn.
    dry = mix.copy()
    for delay, gain, swap in ((0.052, 0.15, True), (0.093, 0.10, False), (0.151, 0.055, True)):
        offset = round(delay * SR)
        source = dry[:, ::-1] if swap else dry
        mix[offset:] += source[:-offset] * gain

    # Remove subsonic rumble that previously read as a comic low-frequency burst.
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
