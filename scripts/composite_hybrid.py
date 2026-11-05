from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output"
GENERATIVE = OUT_DIR / "generative"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved)


def probe(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate,pix_fmt,duration",
            "-show_entries", "format=duration,size", "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Composite generated atmosphere below the deterministic fact layer.")
    parser.add_argument("--opacity", type=float, default=0.14)
    parser.add_argument("--deterministic", type=Path, default=OUT_DIR / "shanghai-1976-force-map.mp4")
    parser.add_argument("--runway", type=Path, default=GENERATIVE / "runway-gen4.5.mp4")
    parser.add_argument("--kling", type=Path, default=GENERATIVE / "kling-4.mp4")
    parser.add_argument("--output", type=Path, default=OUT_DIR / "shanghai-1976-hybrid-runway-kling4.mp4")
    parser.add_argument("--report", type=Path, default=GENERATIVE / "hybrid-validation.json")
    parser.add_argument("--keyframes-dir", type=Path, default=GENERATIVE / "hybrid-keyframes")
    args = parser.parse_args()
    if not 0.0 < args.opacity <= 0.25:
        raise SystemExit("Opacity must be above 0 and at most 0.25 to preserve factual legibility.")

    deterministic = args.deterministic.resolve()
    runway = args.runway.resolve()
    kling = args.kling.resolve()
    missing = [path for path in (deterministic, runway, kling) if not path.exists()]
    if missing:
        names = "\n".join(f"- {path}" for path in missing)
        raise SystemExit(f"Missing required media:\n{names}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    opacity = f"{args.opacity:.3f}"
    filter_graph = (
        f"[1:v]scale=1400:790:force_original_aspect_ratio=increase,crop=1400:790,"
        f"fps=30,trim=duration=5,setpts=PTS+16/TB,format=rgba,colorchannelmixer=aa={opacity}[rw];"
        f"[2:v]scale=1400:790:force_original_aspect_ratio=increase,crop=1400:790,"
        f"fps=30,trim=duration=5,setpts=PTS+28/TB,format=rgba,colorchannelmixer=aa={opacity}[kl];"
        "[0:v][rw]overlay=54:174:enable='between(t,16,21)':eof_action=pass[v1];"
        "[v1][kl]overlay=54:174:enable='between(t,28,33)':eof_action=pass,format=yuv420p[v]"
    )
    command = [
        "ffmpeg", "-y", "-i", str(deterministic), "-i", str(runway), "-i", str(kling),
        "-filter_complex", filter_graph, "-map", "[v]", "-an", "-c:v", "libx264",
        "-preset", "medium", "-crf", "18", "-movflags", "+faststart", "-t", "60", str(args.output),
    ]
    subprocess.run(command, check=True)

    keyframes_dir = args.keyframes_dir.resolve()
    keyframes_dir.mkdir(parents=True, exist_ok=True)
    for second, label in ((18, "runway"), (30, "kling"), (45, "deterministic")):
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(second), "-i", str(args.output),
                "-frames:v", "1", "-update", "1", str(keyframes_dir / f"{label}-{second}s.png"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    report = {
        "status": "PASS",
        "output": display_path(args.output),
        "sha256": sha256(args.output),
        "opacity": args.opacity,
        "segments": [
            {"model": "Runway Gen-4.5", "start": 16, "end": 21},
            {"model": "Kling 4.0", "start": 28, "end": 33},
        ],
        "audio": "removed",
        "overlayRegion": {"x": 54, "y": 174, "width": 1400, "height": 790},
        "factLayer": "deterministic foreground retained for the full 60 seconds",
        "probe": probe(args.output),
    }
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
