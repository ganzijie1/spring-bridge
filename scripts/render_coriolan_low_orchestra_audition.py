from __future__ import annotations

import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import librosa
import mido
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt


ROOT = Path(__file__).resolve().parents[1]
MIDI = ROOT / ".tools" / "coriolan" / "midi" / "coriolan.mid"
SSO = ROOT / ".tools" / "sso" / "repo" / "Sonatina Symphonic Orchestra" / "Samples"
OUTPUT = ROOT / "output" / "music" / "auditions" / "map-war-continuous-pressure-38s.wav"

SR = 44_100
SOURCE_START = 22.4
EXCERPT_DURATION = 38.0
SOURCE_END = SOURCE_START + EXCERPT_DURATION
TAIL = 2.0
TEMPO = 400_000  # 150 BPM, as encoded by the Mutopia MIDI control track.

NOTE_NAMES = {
    28: "e1",
    33: "a1",
    34: "a#1",
    36: "c2",
    37: "c#2",
    39: "d#2",
    40: "e2",
    42: "f#2",
    43: "g2",
    45: "a2",
    46: "a#2",
    48: "c3",
    49: "c#3",
    51: "d#3",
    52: "e3",
    54: "f#3",
    55: "g3",
    57: "a3",
    58: "a#3",
    60: "c4",
    61: "c#4",
    63: "d#4",
    64: "e4",
    66: "f#4",
    67: "g4",
    69: "a4",
    70: "a#4",
    72: "c5",
    73: "c#5",
    75: "d#5",
    76: "e5",
}

STRING_DIRS = {"basses": "Basses", "celli": "Celli", "violas": "Violas"}
ENSEMBLE_DIRS = {"horns": "Horns", "trombones": "Trombones"}
PAN = {
    "basses": 0.16,
    "celli": 0.28,
    "violas": -0.22,
    "horns": -0.34,
    "trombones": 0.34,
}


def nearest_root(note: int, candidates: tuple[int, ...]) -> int:
    return min(candidates, key=lambda root: abs(root - note))


def find_string_sample(instrument: str, articulation: str, note: int, rr: int) -> tuple[Path, int]:
    directory = SSO / STRING_DIRS[instrument]
    available: list[tuple[int, Path]] = []
    for root, name in NOTE_NAMES.items():
        suffix = f"rr{rr}-{name}" if articulation == "stc" else name
        stem = f"{instrument}-{articulation}-{suffix}"
        for extension in (".wav", ".flac"):
            candidate = directory / f"{stem}{extension}"
            if candidate.exists():
                available.append((root, candidate))
    if available:
        root, path = min(available, key=lambda item: abs(item[0] - note))
        return path, root
    raise FileNotFoundError(f"No {instrument} {articulation} sample near MIDI {note}")


def find_ensemble_sample(instrument: str, articulation: str, note: int, rr: int) -> tuple[Path, int]:
    directory = SSO / ENSEMBLE_DIRS[instrument]
    available: list[tuple[int, Path]] = []
    for root, name in NOTE_NAMES.items():
        if articulation == "stc":
            stem = f"{instrument}-stc-rr{rr}-{name}"
        elif instrument == "horns":
            stem = f"horns-sus-ff-{name}-PB-loop"
        else:
            stem = f"trombones-sus-{name}"
        for extension in (".wav", ".flac"):
            candidate = directory / f"{stem}{extension}"
            if candidate.exists():
                available.append((root, candidate))
    if available:
        root, path = min(available, key=lambda item: abs(item[0] - note))
        return path, root
    raise FileNotFoundError(f"No {instrument} {articulation} sample near MIDI {note}")


@lru_cache(maxsize=256)
def read_audio(path_string: str) -> np.ndarray:
    audio, sample_rate = sf.read(path_string, dtype="float32", always_2d=True)
    if sample_rate != SR:
        audio = np.stack(
            [librosa.resample(audio[:, channel], orig_sr=sample_rate, target_sr=SR) for channel in range(audio.shape[1])],
            axis=1,
        )
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    return audio


def loop_and_shape(audio: np.ndarray, duration: float, articulation: str) -> np.ndarray:
    target = max(1, round(duration * SR))
    if len(audio) < target:
        body_start = min(round(0.55 * SR), max(0, len(audio) // 4))
        body_end = max(body_start + 1, len(audio) - round(0.35 * SR))
        body = audio[body_start:body_end]
        pieces = [audio[:body_start]]
        while sum(len(piece) for piece in pieces) < target:
            pieces.append(body)
        audio = np.concatenate(pieces, axis=0)
    audio = audio[:target].copy()
    attack_seconds = 0.018 if articulation == "stc" else 0.075
    release_seconds = min(0.18 if articulation == "stc" else 0.30, duration * 0.35)
    attack = min(round(attack_seconds * SR), len(audio))
    release = min(round(release_seconds * SR), len(audio))
    if attack:
        audio[:attack] *= np.linspace(0.0, 1.0, attack, dtype=np.float32)[:, None]
    if release:
        audio[-release:] *= np.linspace(1.0, 0.0, release, dtype=np.float32)[:, None]
    return audio


@lru_cache(maxsize=512)
def pitched_source(instrument: str, articulation: str, note: int, rr: int) -> np.ndarray:
    if instrument in STRING_DIRS:
        path, root = find_string_sample(instrument, articulation, note, rr)
    else:
        path, root = find_ensemble_sample(instrument, articulation, note, rr)
    audio = read_audio(str(path)).copy()
    if note != root:
        audio = np.stack(
            [librosa.effects.pitch_shift(audio[:, channel], sr=SR, n_steps=note - root) for channel in range(2)],
            axis=1,
        )
    return audio


def pan_audio(audio: np.ndarray, position: float) -> np.ndarray:
    mono = audio.mean(axis=1)
    angle = (max(-1.0, min(1.0, position)) + 1.0) * math.pi / 4.0
    return np.stack((mono * math.cos(angle), mono * math.sin(angle)), axis=1)


def place(mix: np.ndarray, audio: np.ndarray, start: float, gain: float, position: float) -> None:
    offset = round(start * SR)
    if offset >= len(mix):
        return
    shaped = pan_audio(audio, position) * gain
    end = min(len(mix), offset + len(shaped))
    mix[offset:end] += shaped[: end - offset]


def midi_notes(track: mido.MidiTrack) -> list[tuple[float, float, int, int]]:
    elapsed = 0.0
    active: dict[tuple[int, int], list[tuple[float, int]]] = defaultdict(list)
    notes: list[tuple[float, float, int, int]] = []
    for message in track:
        elapsed += mido.tick2second(message.time, 384, TEMPO)
        key = (getattr(message, "channel", 0), getattr(message, "note", -1))
        if message.type == "note_on" and message.velocity > 0:
            active[key].append((elapsed, message.velocity))
        elif message.type in {"note_off", "note_on"} and active[key]:
            start, velocity = active[key].pop(0)
            notes.append((start, max(0.06, elapsed - start), message.note, velocity))
    return notes


def fold_note(note: int, low: int, high: int) -> int:
    while note > high:
        note -= 12
    while note < low:
        note += 12
    return note


def add_track(
    mix: np.ndarray,
    midi: mido.MidiFile,
    track_index: int,
    instrument: str,
    low: int,
    high: int,
    gain: float,
    start_at: float = 0.0,
) -> None:
    for event_index, (start, duration, note, velocity) in enumerate(midi_notes(midi.tracks[track_index])):
        if start < max(start_at, SOURCE_START) or start >= SOURCE_END:
            continue
        folded = fold_note(note, low, high)
        articulation = "stc" if duration <= 0.72 else "sus"
        rr = event_index % 2 + 1
        source = pitched_source(instrument, articulation, folded, rr)
        note_duration = min(duration + (0.035 if articulation == "stc" else 0.0), SOURCE_END - start + 0.5)
        audio = loop_and_shape(source, note_duration, articulation)
        velocity_gain = 0.48 + 0.52 * (velocity / 127.0)
        place(mix, audio, start - SOURCE_START, gain * velocity_gain, PAN[instrument])


def add_timpani(mix: np.ndarray, midi: mido.MidiFile) -> None:
    roots = {36: "c1", 45: "a1", 48: "c2", 51: "d#1", 54: "f#1"}
    for event_index, (start, _duration, note, velocity) in enumerate(midi_notes(midi.tracks[7])):
        if start < SOURCE_START or start >= SOURCE_END:
            continue
        target = nearest_root(note - 12, tuple(roots))
        hand = "rh" if event_index % 2 == 0 else "lh"
        dynamic = "f" if velocity >= 82 else "p"
        path = SSO / "Percussion" / f"timpani-{dynamic}-{hand}-{roots[target]}.wav"
        place(mix, read_audio(str(path)), start - SOURCE_START, 0.33 + velocity / 440.0, 0.0)


def add_bass_drum(mix: np.ndarray) -> None:
    for start, gain in ((9.20, 0.24), (19.60, 0.27), (30.40, 0.29), (36.00, 0.32)):
        place(mix, read_audio(str(SSO / "Percussion" / "bass_drum-f.wav")), start, gain, 0.0)


def main() -> None:
    midi = mido.MidiFile(MIDI)
    mix = np.zeros((round((EXCERPT_DURATION + TAIL) * SR), 2), dtype=np.float32)

    # Original string ranks, kept low and weighty.
    add_track(mix, midi, 12, "basses", 28, 48, 0.48)
    add_track(mix, midi, 11, "celli", 36, 60, 0.43)
    add_track(mix, midi, 10, "violas", 43, 67, 0.36)

    # The upper-string counterlines are moved down into cello/viola register.
    # Their written rhythms remain intact, but no bright violin timbre survives.
    add_track(mix, midi, 8, "celli", 43, 62, 0.22)
    add_track(mix, midi, 9, "violas", 48, 65, 0.20)

    # Coriolan's horn and trumpet declarations become low horns and trombones.
    add_track(mix, midi, 5, "horns", 40, 57, 0.30)
    add_track(mix, midi, 6, "trombones", 40, 58, 0.31)
    add_timpani(mix, midi)
    add_bass_drum(mix)

    # A restrained scoring-stage reflection glues the ranks without a glossy tail.
    dry = mix.copy()
    for delay, gain, reverse in ((0.061, 0.11, True), (0.109, 0.07, False), (0.181, 0.035, True)):
        offset = round(delay * SR)
        source = dry[:, ::-1] if reverse else dry
        mix[offset:] += source[:-offset] * gain

    highpass = butter(3, 31.0, btype="highpass", fs=SR, output="sos")
    lowpass = butter(2, 9_200.0, btype="lowpass", fs=SR, output="sos")
    mix = np.stack(
        [sosfilt(lowpass, sosfilt(highpass, mix[:, channel])) for channel in range(2)],
        axis=1,
    ).astype(np.float32)

    fade = round(1.5 * SR)
    mix[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)[:, None]
    peak = float(np.max(np.abs(mix)))
    if peak:
        mix *= (10 ** (-1.2 / 20.0)) / peak

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sf.write(OUTPUT, mix, SR, subtype="PCM_24")
    print(OUTPUT)


if __name__ == "__main__":
    main()
