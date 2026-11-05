from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACE_ROOT = ROOT.parent / "ai-tools" / "ACE-Step-1.5"
OUTPUT_ROOT = ROOT / "output" / "music"
TIMELINE = json.loads((ROOT / "src" / "timeline.json").read_text(encoding="utf-8"))
STORM_PROMPT = (
    "Instrumental siege score, ominous stillness before battle, storm over an encircled "
    "city, solemn and threatening from first second. Contrabass and low-cello tremolo, nervous "
    "muted strings, dark low-brass clusters, distant timpani heartbeat, minor seconds, tritones. Thin "
    "percussion at 21-26s but keep unsafe low drone; rebuild after 27s; strongest harmonic and rhythmic "
    "crisis at 40-53s. Unresolved low-cluster ending. No vocals, choir, speech, heroic fanfare, march, "
    "solo-cello elegy, ambient wash or braams."
)
BATTLE_C_PROMPT = (
    "Instrumental historical battle score, solemn, tense, tragic, and irreversible. 82 BPM in "
    "D minor. From the first second, persistent dry low-string spiccato pulse from "
    "contrabasses and cellos; restrained sparse military snare; dissonant low-brass breaths built "
    "from minor seconds and tritones. A dark wordless low choral texture grows very slowly without "
    "lyrics or a solo singer. Build pressure gradually, then create a genuine near-silence at the "
    "middle structural break. After the silence, cellos and horns introduce a clear, memorable, "
    "irreversible tragic main theme while the low-string pulse returns. Reach a controlled late climax, "
    "ending on unresolved D, A, and E-flat tension. Approaching battle, siege, final resistance. "
    "No bright major key, no triumphant or heroic cadence, no victory fanfare, no pop vocals, no "
    "lyrics, no narration, no guitar solo, no EDM, no trailer braams, no nonstop percussion barrage."
)
HISTORICAL_CRISIS_PROMPT = (
    "Instrumental score for a Chinese historical map documentary at the moment before an armed "
    "political confrontation, with the severe dramatic discipline of a Japanese historical war "
    "drama but no imitation of any existing soundtrack. The atmosphere must be tense, solemn, "
    "oppressive, rain-before-battle, tragic, and increasingly irreversible from the first second. "
    "A dry, persistent contrabass and low-cello ostinato is the structural spine. Add restrained "
    "military snare only in sparse phrases, dissonant bass trombone and horn clusters built from "
    "minor seconds and tritones, and a very slow-growing low mixed choir used only as nonverbal "
    "texture. Preserve negative space and a wide natural dynamic range. At the middle turn, collapse "
    "to near-silence without an impact hit. After the silence, introduce a clear descending tragic "
    "theme in cellos and low horns, with no cathartic release; let it become unavoidable rather than "
    "heroic. The late climax must feel like political pressure closing in, not combat victory. End "
    "on an unresolved low cluster with motion still continuing. No gunshots, explosions, battlefield "
    "sound effects, bright major harmony, victory cadence, heroic fanfare, patriotic march, pop vocal, "
    "lyrics, intelligible pseudo-language, solo singer, EDM, guitar solo, trailer braam, taiko barrage, "
    "or nonstop percussion. Do not sound celebratory, adventurous, glossy, or inspirational."
)
HISTORICAL_DREAD_PROMPT = (
    "Instrumental political-crisis requiem for a historical documentary, austere, oppressive, "
    "bereaved, and cold. This is the hours before an irreversible purge and armed confrontation, "
    "not a battle adventure. Extremely slow 52 BPM psychological dread. Begin with contrabass and "
    "low cello sul ponticello on a static D pedal, an irregular pulse with missing beats, long minor-"
    "second friction, tritones, and low cluster breathing. Use a muffled military snare only as rare "
    "half-time strokes, never as a march. Bass trombone and stopped horns enter as distant pressure, "
    "not fanfare. A low wordless choir is almost imperceptible, breath-like, nonreligious, and has no "
    "syllables. At 44 seconds everything collapses into four seconds of near-silence with only decaying "
    "room tone. After 48 seconds, introduce a slow descending lament of only three or four notes in "
    "cellos and bass clarinet; each phrase sinks and fails to resolve. From 70 to 86 seconds increase "
    "weight and harmonic compression, not speed, brightness, or rhythmic excitement. End suspended on "
    "D, E-flat, and A-flat with no tonic resolution. The emotional result must be grief, dread, moral "
    "injury, and an approaching historical catastrophe. No happiness, celebration, Lunar New Year "
    "feeling, festival, dance, bounce, jaunty rhythm, adventure, excitement, hope, uplift, inspiration, "
    "heroism, triumph, victory, anthem, fanfare, gallop, martial march, catchy ostinato, pentatonic tune, "
    "bright strings, cymbal crashes, taiko, snare roll, pop vocals, intelligible voice, lyrics, speech, "
    "gunshots, explosions, trailer braams, EDM, rock, or major cadence."
)
HISTORICAL_DREAD_ATONAL_PROMPT = (
    "Instrumental atonal orchestral pressure score for an archival documentary about an imminent "
    "political purge. No tune and no conventional chord progression. 46 BPM only as a hidden timing "
    "grid; the listener must not feel a beat or march. Contrabass and low cello sustain a nearly static "
    "D pedal while neighboring E-flat and A-flat tones enter as slow beating dissonance. Irregular "
    "col-legno knocks and one distant muffled bass-drum stroke appear with long unequal gaps. Violins "
    "remain absent. Bass clarinet multiphonics, low trombone air, bowed cymbal resonance, and granular "
    "wordless choral breath form a cold dark mass. Use silence, friction, decay, and narrowing register "
    "to create dread. At 44 seconds collapse into four seconds of near-silence. After 48 seconds return "
    "with a lower, denser version of the same unresolved sound mass; do not introduce a melody. From "
    "70 to 86 seconds increase acoustic weight very slowly without increasing tempo, rhythmic density, "
    "or brightness. End abruptly suspended in a semitone cluster, as if history continues outside the "
    "frame. The result must feel bereaved, claustrophobic, morally grave, and unavoidable. Absolutely "
    "no happiness, festivity, holiday feeling, Lunar New Year feeling, hope, inspiration, adventure, "
    "heroism, triumph, victory, emotional uplift, catharsis, catchy motif, hummable melody, pentatonic "
    "line, arpeggio, tonal cadence, major chord, rising theme, gallop, march, regular snare, taiko, cymbal "
    "crash, fanfare, trailer rhythm, pop voice, intelligible syllables, speech, gunshot, or explosion."
)
HISTORICAL_RESISTANCE_PROMPT = (
    "Dark instrumental orchestral resistance music for workers and militia organizing under armed "
    "encirclement. 66 BPM, D minor, gritty, tense, disciplined, defiant, urgent, and unresolved. "
    "A dry syncopated cello and contrabass ostinato drives physical forward motion. Violas and cellos "
    "repeat a compact rising three-note signal in tight minor intervals. Sparse field-drum strokes use "
    "unequal gaps. Bass trombone and stopped horns answer with clipped dissonant challenges. Active "
    "middle strings keep the ensemble lean and mobile. Pressure and coordination accumulate through "
    "44 seconds. From 44 to 48 seconds, instruments freeze on a tense held breath. At 48 seconds the "
    "syncopated ostinato and three-note signal return with greater force and denser counterpoint. From "
    "70 to 86 seconds the ensemble advances with stubborn collective resolve under tightening pressure. "
    "At 86 seconds the full ensemble cuts away, leaving the rhythmic impulse suspended on a harsh open "
    "fifth and minor second. Instrumental, acoustic orchestra, dry close recording, wide dynamics."
)
PROFILES = {
    "storm": {
        "prompt": STORM_PROMPT,
        "bpm": 58,
        "keyscale": "D Minor",
        "output_name": "candidates-storm",
        "prefix": "ace-v15-storm",
    },
    "battle-c": {
        "prompt": BATTLE_C_PROMPT,
        "bpm": 82,
        "keyscale": "D Minor",
        "output_name": "candidates-battle-c",
        "prefix": "ace-v15-battle-c",
    },
    "historical-crisis": {
        "prompt": HISTORICAL_CRISIS_PROMPT,
        "bpm": 76,
        "keyscale": "D Minor",
        "output_name": "candidates-historical-crisis",
        "prefix": "ace-v15-historical-crisis",
    },
    "historical-dread": {
        "prompt": HISTORICAL_DREAD_PROMPT,
        "bpm": 52,
        "keyscale": "D Minor",
        "output_name": "candidates-historical-dread",
        "prefix": "ace-v15-historical-dread",
    },
    "historical-dread-atonal": {
        "prompt": HISTORICAL_DREAD_ATONAL_PROMPT,
        "bpm": 46,
        "keyscale": "D Minor",
        "output_name": "candidates-historical-dread-atonal",
        "prefix": "ace-v15-historical-dread-atonal",
    },
    "historical-resistance": {
        "prompt": HISTORICAL_RESISTANCE_PROMPT,
        "bpm": 66,
        "keyscale": "D Minor",
        "output_name": "candidates-historical-resistance",
        "prefix": "ace-v15-historical-resistance",
    },
}
DEFAULT_SEEDS = [19761006, 19761007, 19761008, 19761009, 19761010, 19761011]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic instrumental score candidates with ACE-Step 1.5")
    parser.add_argument("--ace-root", type=Path, default=DEFAULT_ACE_ROOT)
    parser.add_argument("--duration", type=float, default=float(TIMELINE["duration_seconds"]))
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--seed", type=int, action="append", dest="seeds")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--download-source", choices=("auto", "huggingface", "modelscope"), default="modelscope")
    parser.add_argument("--profile", choices=tuple(PROFILES), default="storm")
    parser.add_argument("--output-name")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = PROFILES[args.profile]
    prompt = str(profile["prompt"])
    if args.profile in {"battle-c", "historical-crisis", "historical-dread", "historical-dread-atonal", "historical-resistance"}:
        scale = args.duration / float(TIMELINE["duration_seconds"])
        silence_start = float(TIMELINE["audio"]["near_silence_start"]) * scale
        silence_end = float(TIMELINE["audio"]["near_silence_end"]) * scale
        theme_end = float(TIMELINE["audio"]["controlled_climax_start"]) * scale
        climax_end = float(TIMELINE["audio"]["controlled_climax_end"]) * scale
        prompt += (
            f" Total duration {args.duration:.0f} seconds. Build until {silence_start:.1f} seconds; "
            f"near-silence from {silence_start:.1f} to {silence_end:.1f} seconds; main material from "
            f"{silence_end:.1f} to {theme_end:.1f} seconds; controlled climax from {theme_end:.1f} "
            f"to {climax_end:.1f} seconds; unresolved ending afterward."
        )
    ace_root = args.ace_root.resolve()
    if not (ace_root / "acestep").is_dir():
        raise SystemExit(f"ACE-Step checkout not found: {ace_root}")
    if not 10 <= args.duration <= 600:
        raise SystemExit("ACE-Step duration must be between 10 and 600 seconds")
    if args.count < 1:
        raise SystemExit("Count must be at least one")

    os.environ["ACESTEP_DOWNLOAD_SOURCE"] = args.download_source
    sys.path.insert(0, str(ace_root))

    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    output_name = args.output_name or str(profile["output_name"])
    output_dir = OUTPUT_ROOT / (f"smoke-test-{args.profile}" if args.smoke_test else output_name)
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    handler = AceStepHandler()
    status, success = handler.initialize_service(
        project_root=str(ace_root),
        config_path="acestep-v15-turbo",
        device="cuda",
        offload_to_cpu=True,
        prefer_source=args.download_source,
    )
    if not success:
        raise RuntimeError(status)

    seeds = args.seeds or DEFAULT_SEEDS
    if len(seeds) < args.count:
        raise SystemExit(f"Need at least {args.count} seeds, received {len(seeds)}")

    records: list[dict] = []
    for index, seed in enumerate(seeds[: args.count], start=1):
        params = GenerationParams(
            task_type="text2music",
            caption=prompt,
            lyrics="[Instrumental]",
            instrumental=True,
            vocal_language="unknown",
            bpm=int(profile["bpm"]),
            keyscale=str(profile["keyscale"]),
            timesignature="4",
            duration=args.duration,
            inference_steps=8,
            guidance_scale=1.0,
            shift=3.0,
            seed=seed,
            thinking=False,
            use_cot_metas=False,
            use_cot_caption=False,
            use_cot_language=False,
            enable_normalization=False,
        )
        config = GenerationConfig(
            batch_size=1,
            use_random_seed=False,
            seeds=[seed],
            audio_format="flac",
        )
        started = time.perf_counter()
        result = generate_music(handler, None, params, config, save_dir=str(raw_dir))
        elapsed = time.perf_counter() - started
        if not result.success or not result.audios:
            message = result.error or result.status_message or "ACE-Step returned no audio"
            raise RuntimeError(f"Candidate {index} failed: {message}")

        generated = Path(result.audios[0]["path"])
        if not generated.is_absolute():
            generated = (ace_root / generated).resolve()
        if not generated.exists():
            raise FileNotFoundError(f"ACE-Step reported a missing output: {generated}")
        prefix = f"{profile['prefix']}-smoke" if args.smoke_test else str(profile["prefix"])
        destination = output_dir / f"{prefix}-{index:02d}.flac"
        shutil.copy2(generated, destination)
        records.append(
            {
                "candidate": index,
                "seed": seed,
                "duration_seconds": args.duration,
                "elapsed_seconds": round(elapsed, 3),
                "file": str(destination.relative_to(ROOT)),
                "source_file": str(generated),
            }
        )
        print(json.dumps(records[-1], ensure_ascii=False), flush=True)

    manifest = {
        "status": "PASS",
        "engine": "ACE-Step 1.5",
        "model": "acestep-v15-turbo",
        "download_source": args.download_source,
        "profile": args.profile,
        "prompt": prompt,
        "instrumental": True,
        "bpm": profile["bpm"],
        "keyscale": profile["keyscale"],
        "timesignature": "4/4",
        "records": records,
    }
    manifest_path = output_dir / "generation-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
