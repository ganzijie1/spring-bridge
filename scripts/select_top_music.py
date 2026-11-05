from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Select the highest technical-score music candidate")
    parser.add_argument("ranking", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = json.loads(args.ranking.read_text(encoding="utf-8"))
    if not report.get("candidates"):
        raise SystemExit("Ranking contains no candidates")
    selected = Path(report["candidates"][0]["file"])
    if not selected.exists():
        raise SystemExit(f"Ranked candidate does not exist: {selected}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(selected, args.output)
    selection = {
        "status": "PROVISIONAL_SELECTION",
        "basis": "highest technical score; human full-length listening remains required",
        "source": str(selected),
        "output": str(args.output),
        "technical_score_0_100": report["candidates"][0]["technical_score_0_100"],
        "manual_review_required": report.get("manual_review_required", []),
    }
    manifest = args.output.with_suffix(".selection.json")
    manifest.write_text(json.dumps(selection, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(selection, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
