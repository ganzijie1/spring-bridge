from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACE_ROOT = ROOT.parent / "ai-tools" / "ACE-Step-1.5"
OUTPUT_DIR = ROOT / "output" / "music" / "map-chronicle-dual-cue"
FINAL_SCORE = ROOT / "output" / "music" / "shanghai-1976-map-chronicle-90.wav"

CUES = (
    {
        "id": "deployment",
        "duration": 48.0,
        "bpm": 126,
        "key": "D Minor",
        "seed": 19761106,
        "prompt": (
            "Original instrumental orchestral score for an animated historical campaign map. Serious forward "
            "motion in the manner of a Japanese historical strategy chronicle, without imitating any existing "
            "soundtrack. 126 BPM, D minor, 48 seconds. This must be a complete musical composition, not an "
            "atmospheric drone. Open with four bars of disciplined low strings, then state a clear eight-bar "
            "cello and restrained horn theme. Let violas and woodwinds answer it. Develop the idea through "
            "counterpoint, phrase extension, register changes, and displaced accents. A rhythmic figure may "
            "remain recognizable but must not repeat unchanged for more than four bars. Use smooth voice leading "
            "and a prepared shift of tonal weight toward G minor in the middle before returning to an unresolved "
            "D-minor field. Timpani and low drums mark phrase boundaries rather than every beat. Organized forces "
            "deploy openly and a confrontation becomes imminent. Dark, controlled, alert, martial in subject but "
            "not a parade march. No vocals, choir, speech, pseudo-lyrics, funeral lament, stealth music, comedy, "
            "festival feeling, bright triumph, heroic victory cadence, trailer braam, nonstop percussion, EDM, "
            "pop beat, gunshots, or explosions."
        ),
    },
    {
        "id": "encirclement",
        "duration": 46.0,
        "bpm": 132,
        "key": "C Minor",
        "seed": 19761107,
        "prompt": (
            "Original second orchestral cue for an animated historical campaign map as suppression forces begin "
            "to move. It must connect naturally from an earlier D-minor cue but introduce a genuinely new musical "
            "paragraph. 132 BPM, C minor with G-minor gravitational pull, 46 seconds. Begin with a two-bar bridge "
            "of reduced strings, then reveal a severe but memorable rising-and-falling theme in cellos, violas, "
            "bassoons, and restrained horns. Maintain continuous forward movement while changing rhythm and "
            "orchestration every phrase: imitation between sections, asymmetric phrase endings, brief suspension, "
            "then denser counterpoint. Do not loop one ostinato and do not hop through a chain of unrelated keys. "
            "From the midpoint, tighten harmony and orchestral density without becoming faster or celebratory. "
            "The closing eight bars must feel irreversible and unresolved, ending on C, D-flat, and G tension "
            "with motion cut off rather than cadenced. No vocals, choir, speech, pseudo-lyrics, funeral procession, "
            "stealth music, comedy, festival feeling, bright major resolution, heroic victory, patriotic march, "
            "trailer braam, nonstop drums, EDM, pop beat, gunshots, or explosions."
        ),
    },
)


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


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
    generated_cues: list[Path] = []
    for cue in CUES:
        params = GenerationParams(
            task_type="text2music",
            caption=str(cue["prompt"]),
            lyrics="[Instrumental]",
            instrumental=True,
            vocal_language="unknown",
            bpm=int(cue["bpm"]),
            keyscale=str(cue["key"]),
            timesignature="4",
            duration=float(cue["duration"]),
            inference_steps=8,
            guidance_scale=1.0,
            shift=3.0,
            seed=int(cue["seed"]),
            thinking=False,
            use_cot_metas=False,
            use_cot_caption=False,
            use_cot_language=False,
            enable_normalization=False,
        )
        config = GenerationConfig(
            batch_size=1,
            use_random_seed=False,
            seeds=[int(cue["seed"])],
            audio_format="flac",
        )
        started = time.perf_counter()
        result = generate_music(handler, None, params, config, save_dir=str(raw_dir))
        elapsed = time.perf_counter() - started
        if not result.success or not result.audios:
            raise RuntimeError(result.error or result.status_message or f"ACE-Step returned no {cue['id']} cue")
        generated = Path(result.audios[0]["path"])
        if not generated.is_absolute():
            generated = (ACE_ROOT / generated).resolve()
        destination = OUTPUT_DIR / f"{cue['id']}-{cue['duration']:.0f}s.flac"
        shutil.copy2(generated, destination)
        generated_cues.append(destination)
        record = {
            "cue": cue["id"],
            "duration_seconds": cue["duration"],
            "bpm": cue["bpm"],
            "key": cue["key"],
            "seed": cue["seed"],
            "elapsed_seconds": round(elapsed, 3),
            "file": str(destination.relative_to(ROOT)),
        }
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)

    # Four seconds of equal-power overlap: the trial photograph becomes a musical
    # bridge rather than the dead stop used in earlier drafts.
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(generated_cues[0]), "-i", str(generated_cues[1]),
        "-filter_complex", "[0:a][1:a]acrossfade=d=4:c1=qsin:c2=qsin,aresample=48000[out]",
        "-map", "[out]", "-t", "90", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le",
        str(FINAL_SCORE),
    ])

    manifest = {
        "engine": "ACE-Step 1.5",
        "model": "acestep-v15-turbo",
        "structure": "48-second deployment cue + 46-second encirclement cue with 4-second equal-power crossfade",
        "reference_use": "structural analysis only; no source audio was copied or supplied to the model",
        "records": records,
        "final_score": str(FINAL_SCORE.relative_to(ROOT)),
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
