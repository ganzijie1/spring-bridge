from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "music-plan.json"
OUT_DIR = ROOT / "output" / "music" / "candidates"
API_URL = "https://api.elevenlabs.io/v1/music"


def load_plan() -> dict:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    chunks = plan["composition_plan"]["chunks"]
    total = sum(int(chunk["duration_ms"]) for chunk in chunks)
    if total != int(plan["duration_ms"]):
        raise ValueError(f"Chunk duration sum is {total} ms, expected {plan['duration_ms']} ms")
    if total != 60000:
        raise ValueError("This project requires exactly 60000 ms")
    for index, chunk in enumerate(chunks, start=1):
        if not 3000 <= int(chunk["duration_ms"]) <= 120000:
            raise ValueError(f"Chunk {index} duration is outside the API limits")
        if "vocals" not in chunk.get("negative_styles", []):
            raise ValueError(f"Chunk {index} must explicitly reject vocals")
    return plan


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def compose(api_key: str, plan: dict, seed: int, target: Path) -> dict:
    body = {
        "composition_plan": plan["composition_plan"],
        "model_id": plan["model_id"],
        "seed": seed,
        "respect_sections_durations": True,
        "sign_with_c2pa": True,
    }
    query = urllib.parse.urlencode({"output_format": plan["output_format"]})
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            audio = response.read()
            song_id = response.headers.get("song-id")
            content_type = response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"Eleven Music returned HTTP {exc.code}: {details}") from exc
    if len(audio) < 10000:
        raise RuntimeError(f"Eleven Music response was unexpectedly small ({len(audio)} bytes)")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(audio)
    duration = probe_duration(target)
    if not 59.0 <= duration <= 61.0:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Generated audio duration was {duration:.3f}s, expected about 60s")
    return {
        "file": str(target.relative_to(ROOT)),
        "seed": seed,
        "model_id": plan["model_id"],
        "output_format": plan["output_format"],
        "song_id": song_id,
        "content_type": content_type,
        "duration_seconds": duration,
        "bytes": len(audio),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate complete 60-second Eleven Music candidates")
    parser.add_argument("--count", type=int, default=4, help="Number of candidates, maximum 4")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    plan = load_plan()
    seeds = plan["candidate_seeds"][: max(1, min(args.count, 4))]
    if args.validate_only:
        print(json.dumps({"status": "PASS", "duration_ms": plan["duration_ms"], "chunks": len(plan["composition_plan"]["chunks"]), "seeds": seeds}, indent=2))
        return

    api_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_API_KEY")
    if not api_key:
        raise SystemExit("ELEVENLABS_API_KEY is required. Inject it into this process; do not save it in the project.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for index, seed in enumerate(seeds, start=1):
        target = OUT_DIR / f"eleven-v25-candidate-{index:02d}.mp3"
        metadata_path = target.with_suffix(".json")
        if target.exists() and metadata_path.exists() and not args.overwrite:
            records.append(json.loads(metadata_path.read_text(encoding="utf-8")))
            print(f"Reusing {target.name}")
            continue
        print(f"Generating candidate {index}/{len(seeds)} with seed {seed}...")
        record = compose(api_key, plan, seed, target)
        metadata_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        records.append(record)
        if index < len(seeds):
            time.sleep(1)

    manifest = {
        "status": "COMPLETE",
        "provider": "ElevenLabs",
        "request_contains_secret": False,
        "candidates": records,
    }
    (OUT_DIR.parent / "generation-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
