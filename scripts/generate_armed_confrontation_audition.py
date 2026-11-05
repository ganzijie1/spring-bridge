from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACE_ROOT = ROOT.parent / "ai-tools" / "ACE-Step-1.5"
OUTPUT_DIR = ROOT / "output" / "music" / "auditions" / "armed-confrontation"
SEEDS = (19761108, 19761109)
DURATION = 34.0

PROMPT = (
    "Original instrumental war score for a historical campaign map at the final hour before armed conflict. "
    "This is organized mass confrontation, not a game, adventure, parade, stealth mission, or fantasy battle. "
    "104 BPM in D minor, heavy common time, 34 seconds. Use a grave acoustic orchestra with a strictly limited "
    "palette: contrabasses, cellos, violas, low-register French horns, tenor and bass trombones, timpani, and "
    "restrained concert bass drum only. The main theme belongs to cellos and low horns in long connected bowing. "
    "Begin with tense low-string tremolo and a two-bar harmonic preparation. State a severe four-bar theme, then "
    "develop it as a genuine musical paragraph through longer answers, contrary motion, register expansion, and "
    "one prepared move toward G minor. Return with greater orchestral weight and stop on unresolved D, E-flat, "
    "and A. Rhythmic motion must change by phrase and must never loop one ostinato throughout. Percussion marks "
    "only structural thresholds, never a dance beat. The emotional character is disciplined, dangerous, public, "
    "and irreversible: troops deployed, orders issued, both sides awaiting the first clash. "
    "ABSOLUTELY NO flutes, piccolo, oboes, clarinets, high bassoon solos, recorders, whistles, xylophone, marimba, "
    "glockenspiel, celesta, bells, harp, piano, guitar, plucked strings, pizzicato, playful staccato violins, bright "
    "trumpets, cymbal sparkle, tambourine, snare parade, taiko barrage, synths, electronic drums, vocals, choir, "
    "speech, pseudo-lyrics, major-key uplift, catchy game music, jaunty rhythm, comedy, holiday feeling, heroic "
    "victory, triumphant fanfare, funeral lament, trailer braam, gunshots, or explosions."
)


def main() -> None:
    if not (ACE_ROOT / "acestep").is_dir():
        raise SystemExit(f"Missing ACE-Step checkout: {ACE_ROOT}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = OUTPUT_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    os.environ["ACESTEP_DOWNLOAD_SOURCE"] = "modelscope"
    sys.path.insert(0, str(ACE_ROOT))
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    handler = AceStepHandler()
    status, success = handler.initialize_service(
        project_root=str(ACE_ROOT),
        config_path="acestep-v15-turbo",
        device="cuda",
        offload_to_cpu=True,
        prefer_source="modelscope",
    )
    if not success:
        raise RuntimeError(status)

    records: list[dict] = []
    for index, seed in enumerate(SEEDS, start=1):
        params = GenerationParams(
            task_type="text2music",
            caption=PROMPT,
            lyrics="[Instrumental]",
            instrumental=True,
            vocal_language="unknown",
            bpm=104,
            keyscale="D Minor",
            timesignature="4",
            duration=DURATION,
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
        config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[seed], audio_format="flac")
        started = time.perf_counter()
        result = generate_music(handler, None, params, config, save_dir=str(raw_dir))
        elapsed = time.perf_counter() - started
        if not result.success or not result.audios:
            raise RuntimeError(result.error or result.status_message or "ACE-Step returned no audio")
        generated = Path(result.audios[0]["path"])
        if not generated.is_absolute():
            generated = (ACE_ROOT / generated).resolve()
        destination = OUTPUT_DIR / f"armed-confrontation-{index:02d}.flac"
        shutil.copy2(generated, destination)
        record = {
            "candidate": index,
            "seed": seed,
            "duration_seconds": DURATION,
            "elapsed_seconds": round(elapsed, 3),
            "file": str(destination.relative_to(ROOT)),
        }
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)

    manifest = {
        "engine": "ACE-Step 1.5",
        "model": "acestep-v15-turbo",
        "prompt": PROMPT,
        "records": records,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
