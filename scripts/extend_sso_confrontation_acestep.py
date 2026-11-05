from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]
ACE_ROOT = ROOT.parent / "ai-tools" / "ACE-Step-1.5"
SOURCE = ROOT / "output" / "music" / "auditions" / "sso-imminent-confrontation-18s.wav"
OUTPUT_DIR = ROOT / "output" / "music" / "auditions" / "ace-context-continuation"
PADDED_SOURCE = OUTPUT_DIR / "sso-confrontation-context-36s.wav"
DURATION = 36.0
REPAINT_START = 15.5
SEEDS = (19761031, 19761101)

PROMPT = (
    "Instrumental orchestral continuation of the supplied confrontation cue. Preserve the dry real-sample "
    "low-string tremolo, broad bowed-string weight, restrained timpani, dark register, and severe public "
    "confrontation character of the source. Continue its musical sentences naturally rather than looping a "
    "rhythm or abruptly changing key. Develop one recognizable idea with phrase-length variation, smooth "
    "voice leading, counterpoint, changing orchestral density, and a clear long-range rise in pressure. Remain "
    "mainly in D minor and Phrygian colour; allow only one prepared shift of tonal weight toward G minor before "
    "an unresolved D and E-flat ending. No chain of modulations, no random entrances, no repeated ostinato for "
    "the whole cue, no sudden genre change. Imminent battle, organized resistance, forces openly deployed. "
    "No happiness, celebration, funeral lament, stealth, comedy, heroic victory, fanfare, march, trailer braam, "
    "pop rhythm, vocals, choir, speech, gunshots, explosions, or continuous percussion."
)


def make_padded_source() -> None:
    audio, sample_rate = sf.read(SOURCE, dtype="float32", always_2d=True)
    target = round(DURATION * sample_rate)
    if len(audio) > target:
        audio = audio[:target]
    elif len(audio) < target:
        audio = np.pad(audio, ((0, target - len(audio)), (0, 0)))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sf.write(PADDED_SOURCE, audio, sample_rate, subtype="PCM_24")


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing approved context source: {SOURCE}")
    if not (ACE_ROOT / "acestep").is_dir():
        raise SystemExit(f"Missing ACE-Step checkout: {ACE_ROOT}")
    make_padded_source()

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
    raw_dir = OUTPUT_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for index, seed in enumerate(SEEDS, start=1):
        params = GenerationParams(
            task_type="repaint",
            src_audio=str(PADDED_SOURCE),
            repainting_start=REPAINT_START,
            repainting_end=DURATION,
            chunk_mask_mode="explicit",
            repaint_mode="balanced",
            repaint_strength=0.58,
            repaint_latent_crossfade_frames=18,
            repaint_wav_crossfade_sec=0.60,
            caption=PROMPT,
            lyrics="[Instrumental]",
            instrumental=True,
            bpm=64,
            keyscale="D Minor",
            timesignature="4",
            duration=DURATION,
            inference_steps=12,
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
            audio_format="wav",
        )
        started = time.perf_counter()
        result = generate_music(handler, None, params, config, save_dir=str(raw_dir))
        elapsed = time.perf_counter() - started
        if not result.success or not result.audios:
            raise RuntimeError(result.error or result.status_message or "ACE-Step repaint returned no audio")
        generated = Path(result.audios[0]["path"])
        if not generated.is_absolute():
            generated = (ACE_ROOT / generated).resolve()
        destination = OUTPUT_DIR / f"sso-context-continuation-{index:02d}.wav"
        shutil.copy2(generated, destination)
        record = {
            "candidate": index,
            "seed": seed,
            "seconds": DURATION,
            "repaint_start": REPAINT_START,
            "elapsed_seconds": round(elapsed, 3),
            "file": str(destination.relative_to(ROOT)),
        }
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)

    manifest = {
        "engine": "ACE-Step 1.5 repaint",
        "model": "acestep-v15-turbo",
        "source": str(SOURCE.relative_to(ROOT)),
        "prompt": PROMPT,
        "records": records,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
