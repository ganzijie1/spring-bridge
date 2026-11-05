from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output" / "music" / "shanghai-1976-score-conformed.flac"
REPORT = ROOT / "output" / "music" / "timeline-conform-report.json"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def probe_duration(path: Path) -> float:
    result = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    return float(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Conform an ACE-Step candidate to the fixed 60-second video timeline")
    parser.add_argument("input", type=Path)
    parser.add_argument("--active-end", type=float, default=58.3)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.input.resolve()
    destination = args.output.resolve()
    if not source.exists():
        raise SystemExit(f"Input does not exist: {source}")
    if not 10 < args.active_end <= probe_duration(source):
        raise SystemExit("active-end must fall inside the source audio")
    destination.parent.mkdir(parents=True, exist_ok=True)

    tempo = args.active_end / 60.0
    # Preserve a threatening opening, thin the photo passage, and let the late crisis
    # gain density without turning the whole cue into a loudness-only crescendo.
    # One-second ramps avoid audible gain discontinuities at the fixed edit boundaries.
    envelope = (
        "if(lt(t,20.5),0.84,"
        "if(lt(t,21.5),0.84-(t-20.5)*0.24,"
        "if(lt(t,25.5),0.60,"
        "if(lt(t,27),0.60+(t-25.5)*(0.24/1.5),"
        "if(lt(t,38),0.84,"
        "if(lt(t,40),0.84+(t-38)*(0.16/2),"
        "if(lt(t,52),1.0,"
        "if(lt(t,55),1.0-(t-52)*(0.11/3),0.89))))))))"
    )
    audio_filter = (
        f"atrim=start=0:end={args.active_end},asetpts=PTS-STARTPTS,"
        f"atempo={tempo:.9f},"
        f"volume='{envelope}':eval=frame,"
        "alimiter=limit=0.97:attack=5:release=50,"
        "apad=pad_dur=60,atrim=duration=60"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-i", str(source), "-vn",
        "-af", audio_filter, "-ar", "48000", "-ac", "2", "-c:a", "flac",
        str(destination),
    ])

    report = {
        "status": "PASS",
        "source": str(source),
        "output": str(destination),
        "source_active_end_seconds": args.active_end,
        "tempo_factor": round(tempo, 9),
        "output_duration_seconds": probe_duration(destination),
        "timeline": {
            "photo_dip_seconds": [21.5, 25.5],
            "late_climax_seconds": [40.0, 52.0],
            "climax_release_seconds": [52.0, 55.0],
        },
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
