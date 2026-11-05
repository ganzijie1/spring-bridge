from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MUSIC_DIR = ROOT / "output" / "music"


def invoke(script: str, *args: str) -> None:
    subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete 60-second music generation pipeline")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--selected", type=Path, help="Manually selected complete candidate")
    args = parser.parse_args()

    invoke("generate_music.py", "--validate-only")
    if args.validate_only:
        return
    if not (os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_API_KEY")):
        raise SystemExit(
            "ELEVENLABS_API_KEY is required. Inject it into this process; do not save it in the project."
        )
    invoke("generate_music.py", "--count", str(args.count))
    invoke("score_music.py")
    report = json.loads((MUSIC_DIR / "candidate-scores.json").read_text(encoding="utf-8"))
    selected = args.selected or (ROOT / report["selected_technical_candidate"])
    invoke("master_and_mux.py", str(selected))


if __name__ == "__main__":
    main()
