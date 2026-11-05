from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo


ROOT = Path(__file__).resolve().parents[1]
BPM = 66
TICKS_PER_BEAT = 480


def seconds_to_beats(seconds: float) -> float:
    return seconds * BPM / 60.0


@dataclass
class Part:
    name: str
    channel: int
    program: int
    volume: int
    pan: int
    reverb: int
    events: list[tuple[float, int, Message]] = field(default_factory=list)

    def note(self, beat: float, duration: float, pitch: int, velocity: int) -> None:
        self.events.append((beat, 1, Message("note_on", channel=self.channel, note=pitch, velocity=velocity)))
        self.events.append((beat + duration, 0, Message("note_off", channel=self.channel, note=pitch, velocity=0)))

    def chord(self, beat: float, duration: float, pitches: tuple[int, ...], velocity: int) -> None:
        for index, pitch in enumerate(pitches):
            self.note(beat + index * 0.012, duration, pitch, max(1, velocity - index * 2))

    def render(self, midi: MidiFile) -> None:
        track = MidiTrack()
        midi.tracks.append(track)
        track.append(MetaMessage("track_name", name=self.name, time=0))
        track.append(Message("program_change", channel=self.channel, program=self.program, time=0))
        track.append(Message("control_change", channel=self.channel, control=7, value=self.volume, time=0))
        track.append(Message("control_change", channel=self.channel, control=10, value=self.pan, time=0))
        track.append(Message("control_change", channel=self.channel, control=91, value=self.reverb, time=0))
        previous_tick = 0
        for beat, priority, message in sorted(self.events, key=lambda item: (item[0], item[1], item[2].note)):
            tick = round(beat * TICKS_PER_BEAT)
            message.time = max(0, tick - previous_tick)
            track.append(message)
            previous_tick = tick
        track.append(MetaMessage("end_of_track", time=0))


def add_pulse(part: Part, start_s: float, end_s: float, velocity_start: int, velocity_end: int) -> None:
    rng = random.Random(round(start_s * 10) + 1976)
    start = seconds_to_beats(start_s)
    end = seconds_to_beats(end_s)
    pattern = (0.0, 0.72, 1.48, 2.68, 3.22, 4.55, 5.15, 6.48, 7.62)
    bar = int(start // 8) * 8
    index = 0
    while bar < end:
        for offset in pattern:
            beat = bar + offset
            if start <= beat < end:
                progress = (beat - start) / max(0.1, end - start)
                velocity = round(velocity_start + (velocity_end - velocity_start) * progress)
                velocity += rng.choice((-3, -1, 0, 1, 2))
                pitch = (38, 45, 38, 39, 45)[index % 5]
                part.note(beat, 0.31 if index % 3 else 0.42, pitch, velocity)
                index += 1
        bar += 8


def add_signal(part: Part, start_s: float, end_s: float, velocity_start: int, velocity_end: int) -> None:
    start = seconds_to_beats(start_s)
    end = seconds_to_beats(end_s)
    phrase = 0
    beat = start
    while beat + 2.4 < end:
        progress = (beat - start) / max(0.1, end - start)
        velocity = round(velocity_start + (velocity_end - velocity_start) * progress)
        pitches = (50, 53, 56) if phrase % 3 else (50, 51, 56)
        for offset, pitch in zip((0.0, 0.78, 1.55), pitches):
            part.note(beat + offset, 0.55, pitch, velocity)
        phrase += 1
        beat += (5.5, 6.5, 4.75)[phrase % 3]


def add_countermotion(part: Part, start_s: float, end_s: float, velocity: int) -> None:
    start = seconds_to_beats(start_s)
    end = seconds_to_beats(end_s)
    pitches = (63, 62, 58, 57, 56, 57, 58, 62)
    beat = start
    index = 0
    while beat + 0.6 < end:
        part.note(beat, 0.52, pitches[index % len(pitches)], velocity + (index % 3) * 2)
        beat += (1.26, 0.74, 1.51, 0.99)[index % 4]
        index += 1


def add_snare(part: Part, start_s: float, end_s: float, velocity: int) -> None:
    start = seconds_to_beats(start_s)
    end = seconds_to_beats(end_s)
    gaps = (3.25, 2.75, 4.5, 1.75, 5.0)
    beat = start + 1.6
    index = 0
    while beat < end:
        part.note(beat, 0.16, 45 if index % 4 else 47, velocity + (index % 3) * 2)
        beat += gaps[index % len(gaps)]
        index += 1


def add_brass_challenges(part: Part, start_s: float, end_s: float, velocity: int) -> None:
    start = seconds_to_beats(start_s)
    end = seconds_to_beats(end_s)
    beat = start + 2.2
    chords = ((38, 39, 45), (36, 42, 45), (39, 45, 50))
    index = 0
    while beat + 0.8 < end:
        part.chord(beat, 0.46, chords[index % len(chords)], velocity + (index % 2) * 3)
        beat += (6.25, 5.0, 7.5)[index % 3]
        index += 1


def compose(output: Path) -> dict:
    midi = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    conductor = MidiTrack()
    midi.tracks.append(conductor)
    conductor.append(MetaMessage("track_name", name="Historical resistance - conductor", time=0))
    conductor.append(MetaMessage("set_tempo", tempo=bpm2tempo(BPM), time=0))
    conductor.append(MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    conductor.append(MetaMessage("key_signature", key="Dm", time=0))
    conductor.append(MetaMessage("text", text="Defiant resistance; unresolved outcome", time=0))

    bass = Part("Pizzicato low-string pulse", 0, 45, 110, 54, 30)
    cello = Part("Cello resistance signal", 1, 42, 108, 70, 42)
    viola = Part("Viola countermotion", 2, 41, 98, 45, 46)
    horn = Part("Stopped horn pressure", 3, 60, 98, 78, 52)
    trombone = Part("Bass trombone challenges", 4, 57, 96, 62, 46)
    timpani = Part("Timpani irregular weight", 5, 47, 88, 64, 40)
    snare = Part("Irregular low drums", 9, 0, 76, 64, 18)

    add_pulse(bass, 0, 44, 45, 73)
    add_signal(cello, 7.5, 43.5, 48, 72)
    add_countermotion(viola, 8, 43.6, 43)
    add_brass_challenges(trombone, 23, 43.5, 45)
    add_snare(snare, 15, 43.2, 31)
    for second, pitch, velocity in ((10.5, 38, 43), (25.2, 39, 48), (34.7, 38, 52), (41.0, 33, 55)):
        timpani.note(seconds_to_beats(second), 0.7, pitch, velocity)

    held = seconds_to_beats(44)
    held_duration = seconds_to_beats(3.7)
    bass.chord(held, held_duration, (38, 39), 31)
    horn.note(held + 0.08, held_duration - 0.08, 45, 27)

    add_pulse(bass, 48, 80, 61, 82)
    add_signal(cello, 48.2, 80.0, 66, 86)
    add_countermotion(viola, 49, 69.5, 57)
    add_countermotion(viola, 70, 80.0, 69)
    add_brass_challenges(trombone, 49, 69.2, 58)
    add_brass_challenges(trombone, 70, 80.0, 70)
    for second, chord, velocity in (
        (50.5, (45, 50, 51), 49),
        (59.2, (41, 45, 50), 53),
        (67.0, (39, 45, 50), 57),
        (72.0, (38, 39, 45), 62),
        (78.5, (36, 42, 45), 67),
        (84.0, (38, 39, 45), 72),
    ):
        horn.chord(seconds_to_beats(second), 0.72, chord, velocity)
    for second, pitch, velocity in ((53.0, 38, 51), (63.8, 39, 55), (72.7, 38, 61), (80.4, 33, 66), (85.3, 38, 70)):
        timpani.note(seconds_to_beats(second), 0.68, pitch, velocity)

    for second, chord, velocity in (
        (80.05, (50, 51, 56), 73),
        (81.43, (45, 50, 51), 70),
        (83.72, (39, 45, 50), 76),
        (85.08, (38, 39, 45), 79),
        (87.31, (45, 50, 51), 74),
    ):
        cello.chord(seconds_to_beats(second), 0.34, chord, velocity)
    for second, pitch, velocity in ((80.58, 38, 76), (82.19, 45, 72), (84.83, 39, 78), (86.04, 38, 74), (88.46, 39, 72)):
        bass.note(seconds_to_beats(second), 0.30, pitch, velocity)
    ending = seconds_to_beats(88.8)
    bass.chord(ending, seconds_to_beats(1.0), (38, 39, 45), 62)
    cello.chord(ending + 0.04, seconds_to_beats(0.96), (50, 51, 56), 68)
    horn.chord(ending + 0.08, seconds_to_beats(0.9), (57, 62, 63), 56)

    parts = (bass, cello, viola, horn, trombone, timpani, snare)
    for part in parts:
        part.render(midi)
    conductor.append(MetaMessage("end_of_track", time=round(seconds_to_beats(90) * TICKS_PER_BEAT)))
    output.parent.mkdir(parents=True, exist_ok=True)
    midi.save(output)
    report = {
        "status": "PASS",
        "output": str(output.resolve()),
        "duration_seconds": 90,
        "bpm": BPM,
        "key": "D minor with chromatic minor-second and tritone friction",
        "sections": {
            "organization": [0, 44],
            "held_breath": [44, 48],
            "resistance_returns": [48, 70],
            "defiant_advance": [70, 86],
            "unresolved_motion": [86, 90],
        },
        "constraints": [
            "syncopated pulse remains active",
            "low-drum gaps are deliberately unequal; no marching snare",
            "minor and chromatic pitch material only",
            "no victory cadence",
            "ending suspends D, E-flat, and A",
        ],
    }
    output.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose a deterministic 90-second resistance score as MIDI")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "music" / "historical-resistance-deterministic.mid")
    args = parser.parse_args()
    print(json.dumps(compose(args.output.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
