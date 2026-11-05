from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACE_ROOT = ROOT.parents[1] / "ai-tools" / "ACE-Step-1.5"
OUTPUT_ROOT = ROOT / "output" / "music"
PROMPT = (
    "Instrumental siege score, ominous stillness before battle, storm over an encircled "
    "city, solemn and threatening from first second. Contrabass and low-cello tremolo, nervous "
    "muted strings, dark low-brass clusters, distant timpani heartbeat, minor seconds, tritones. Thin "
    "percussion at 21-26s but keep unsafe low drone; rebuild after 27s; strongest harmonic and rhythmic "
    "crisis at 40-53s. Unresolved low-cluster ending. No vocals, choir, speech, heroic fanfare, march, "
    "solo-cello elegy, ambient wash or braams."
)
DEFAULT_SEEDS = [19761006, 19761007, 19761008, 19761009, 19761010, 19761011]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic instrumental score candidates with ACE-Step 1.5")
    parser.add_argument("--ace-root", type=Path, default=DEFAULT_ACE_ROOT)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--seed", type=int, action="append", dest="seeds")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--download-source", choices=("auto", "huggingface", "modelscope"), default="modelscope")
    parser.add_argument("--output-name", default="candidates-storm")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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

    output_dir = OUTPUT_ROOT / ("smoke-test-storm" if args.smoke_test else args.output_name)
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
            caption=PROMPT,
            lyrics="[Instrumental]",
            instrumental=True,
            vocal_language="unknown",
            bpm=58,
            keyscale="D Minor",
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
        prefix = "ace-v15-storm-smoke" if args.smoke_test else "ace-v15-storm"
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
        "prompt": PROMPT,
        "instrumental": True,
        "bpm": 58,
        "keyscale": "D Minor",
        "timesignature": "4/4",
        "records": records,
    }
    manifest_path = output_dir / "generation-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
