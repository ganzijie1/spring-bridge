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
OUTPUT_DIR = ROOT / "output" / "music" / "counterfactual-score"
FINAL_SCORE = ROOT / "output" / "music" / "shanghai-1976-counterfactual-150.wav"

CUES = (
    {
        "id": "mobilisation_and_encirclement",
        "duration": 108.0,
        "bpm": 126,
        "key": "D Minor",
        "seed": 19761026,
        "prompt": (
            "Original instrumental orchestral score for a serious animated historical campaign map. "
            "The scene begins with workers and militia openly mobilising, then a much larger force closes "
            "the rail, river, and command network. Use the disciplined forward pressure and long-form pacing "
            "of a Japanese historical war chronicle, but do not imitate or quote any existing soundtrack. "
            "126 BPM, D minor, 108 seconds, primarily 5/4 with occasional prepared 3/4 bars at phrase endings. "
            "A four-note cell D, E-flat, A, F is the unifying material. Begin with dry contrabass and cello "
            "pulses under restrained field drum. State the cell in low horns after eight bars. Develop it "
            "through inversion, augmentation, imitation, register exchange, and changing orchestration; no "
            "rhythmic or harmonic figure may repeat unchanged for more than four bars. Add bassoons, violas, "
            "stopped horns, bass trombone, and sparse timpani as the encirclement tightens. Keep melodic and "
            "harmonic transitions prepared by common tones; do not jump randomly between keys. Around the "
            "middle, thin the texture for one short breath, then return with denser counterpoint and heavier "
            "low brass. The final twenty seconds must lose confidence while retaining forward motion, ending "
            "on D, E-flat, and A without cadence so the next cue can inherit the tension. Severe, organised, "
            "threatening, historically grave, and tragic without becoming a funeral march. No vocals, choir, "
            "speech, pseudo-language, bright major section, victory cadence, heroic fanfare, celebratory march, "
            "festival instruments, comedy, trailer braams, nonstop drum barrage, EDM, pop beat, gunshots, or explosions."
        ),
    },
    {
        "id": "last_positions",
        "duration": 48.0,
        "bpm": 64,
        "key": "D Minor",
        "seed": 19761027,
        "prompt": (
            "Original instrumental orchestral final cue for the fall of the last positions in a historical "
            "campaign-map film. Continue from an unresolved D, E-flat, A sonority and reuse the same four-note "
            "cell D, E-flat, A, F in broad augmentation, but do not imitate or quote any existing score. "
            "64 BPM, D minor, 48 seconds. Begin with six seconds of reduced low strings and distant timpani, "
            "as if the earlier military motion has suddenly emptied out. Cellos and bassoons then carry a "
            "plain descending lament while violas sustain minor-second friction. Low horns answer, never "
            "fanfare. Let phrases lengthen and orchestration darken: contrabass, cello, bassoon, horn, bass "
            "trombone, restrained timpani, and only a very late high-string harmonic. The climax is resistance "
            "without hope of victory, dignified and irreversible, like a last stand rather than a private "
            "funeral. After the climax, remove percussion and leave the four-note cell unfinished over D and "
            "E-flat. Smooth voice leading, coherent tonal gravity, wide dynamics, natural room. No vocals, "
            "choir, speech, bright major harmony, triumphant cadence, heroic victory, patriotic anthem, "
            "sentimental piano, festival instruments, trailer hits, nonstop drums, EDM, pop beat, or sound effects."
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
        config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[int(cue["seed"])], audio_format="flac")
        started = time.perf_counter()
        result = generate_music(handler, None, params, config, save_dir=str(raw_dir))
        elapsed = time.perf_counter() - started
        if not result.success or not result.audios:
            raise RuntimeError(result.error or result.status_message or f"ACE-Step returned no {cue['id']} cue")
        generated = Path(result.audios[0]["path"])
        if not generated.is_absolute():
            generated = (ACE_ROOT / generated).resolve()
        destination = OUTPUT_DIR / f"{cue['id']}.flac"
        shutil.copy2(generated, destination)
        generated_cues.append(destination)
        records.append(
            {
                "cue": cue["id"],
                "duration_seconds": cue["duration"],
                "bpm": cue["bpm"],
                "key": cue["key"],
                "seed": cue["seed"],
                "elapsed_seconds": round(elapsed, 3),
                "file": str(destination.relative_to(ROOT)),
            }
        )
        print(json.dumps(records[-1], ensure_ascii=False), flush=True)

    # 108 + 48 - 6 = 150 seconds. The long equal-power overlap lets the pulse
    # dissolve into the augmented lament without an abrupt editorial cut.
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(generated_cues[0]), "-i", str(generated_cues[1]),
        "-filter_complex",
        "[0:a][1:a]acrossfade=d=6:c1=qsin:c2=qsin,"
        "highpass=f=28,lowpass=f=17500,"
        "loudnorm=I=-16:TP=-1.2:LRA=11,aresample=48000[out]",
        "-map", "[out]", "-t", "150", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le",
        str(FINAL_SCORE),
    ])

    manifest = {
        "engine": "ACE-Step 1.5",
        "model": "acestep-v15-turbo",
        "structure": "108-second mobilisation/encirclement cue + 48-second last-positions cue with 6-second crossfade",
        "reference_use": "The Satsuma War and Shiroyama references informed pacing and function only; no source audio was copied or supplied to the model.",
        "motif": ["D", "E-flat", "A", "F"],
        "records": records,
        "final_score": str(FINAL_SCORE.relative_to(ROOT)),
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
