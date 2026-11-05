from __future__ import annotations

import argparse
import glob
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "output" / "music" / "candidates-battle-c-conformed"
TIMELINE = json.loads((ROOT / "src" / "timeline.json").read_text(encoding="utf-8"))


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    return result


def probe_duration(path: Path) -> float:
    result = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    return float(result.stdout.strip())


def conform(source: Path, destination: Path, active_end: float, target_duration: float) -> dict:
    tempo = active_end / target_duration
    scale = target_duration / float(TIMELINE["duration_seconds"])
    silence_start = float(TIMELINE["audio"]["near_silence_start"]) * scale
    silence_end = float(TIMELINE["audio"]["near_silence_end"]) * scale
    pre_silence_ramp = silence_start - min(0.75, target_duration * 0.0083)
    post_silence_ramp = silence_end + min(0.75, target_duration * 0.0083)
    early_build = 12.0 * scale
    middle_build = 30.0 * scale
    theme_end = float(TIMELINE["audio"]["controlled_climax_start"]) * scale
    climax_end = float(TIMELINE["audio"]["controlled_climax_end"]) * scale
    # Keep the generated orchestration intact while imposing the documented dramatic arc.
    # The 31-34 second break is near-silence rather than digital zero so the preceding
    # reverb can decay naturally and the post-break theme still enters cleanly.
    envelope = (
        f"if(lt(t,{early_build:.6f}),0.68+(t/{early_build:.6f})*0.08,"
        f"if(lt(t,{middle_build:.6f}),0.76+(t-{early_build:.6f})*(0.10/{middle_build-early_build:.6f}),"
        f"if(lt(t,{pre_silence_ramp:.6f}),0.86+(t-{middle_build:.6f})*(0.08/{pre_silence_ramp-middle_build:.6f}),"
        f"if(lt(t,{silence_start:.6f}),0.94-(t-{pre_silence_ramp:.6f})*(0.88/{silence_start-pre_silence_ramp:.6f}),"
        f"if(lt(t,{silence_end:.6f}),0.06,"
        f"if(lt(t,{post_silence_ramp:.6f}),0.06+(t-{silence_end:.6f})*(0.72/{post_silence_ramp-silence_end:.6f}),"
        f"if(lt(t,{theme_end:.6f}),0.78+(t-{post_silence_ramp:.6f})*(0.14/{theme_end-post_silence_ramp:.6f}),"
        f"if(lt(t,{climax_end:.6f}),0.92+(t-{theme_end:.6f})*(0.08/{climax_end-theme_end:.6f}),"
        f"1.0-(t-{climax_end:.6f})*(0.10/{target_duration-climax_end:.6f})))))))))"
    )
    audio_filter = (
        f"atrim=start=0:end={active_end},asetpts=PTS-STARTPTS,"
        f"atempo={tempo:.9f},"
        f"volume='{envelope}':eval=frame,"
        "alimiter=limit=0.97:attack=5:release=80,"
        f"apad=pad_dur={target_duration},atrim=duration={target_duration}"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-hide_banner", "-i", str(source), "-vn",
        "-af", audio_filter, "-ar", "48000", "-ac", "2", "-c:a", "flac",
        str(destination),
    ])
    return {
        "source": str(source),
        "output": str(destination),
        "source_active_end_seconds": active_end,
        "tempo_factor": round(tempo, 9),
        "output_duration_seconds": probe_duration(destination),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Conform score candidates to the canonical timeline")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--active-end", type=float)
    parser.add_argument("--duration", type=float, default=float(TIMELINE["duration_seconds"]))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    candidates: list[Path] = []
    for value in args.inputs:
        matches = [Path(item) for item in sorted(glob.glob(value))]
        candidates.extend(matches or [Path(value)])
    records = []
    for candidate in candidates:
        source = candidate.resolve()
        if not source.exists():
            raise SystemExit(f"Input does not exist: {source}")
        duration = probe_duration(source)
        active_end = args.active_end if args.active_end is not None else min(duration, args.duration * (89.0 / 90.0))
        if not 10 < active_end <= duration:
            raise SystemExit(f"active-end must fall inside {source.name} ({duration:.3f}s)")
        destination = args.output_dir.resolve() / f"{source.stem}-conformed.flac"
        records.append(conform(source, destination, active_end, args.duration))

    report = {
        "status": "PASS",
        "profile": "battle-c",
        "timeline": {
            "low_string_pulse_seconds": [0.0, TIMELINE["audio"]["near_silence_start"]],
            "near_silence_seconds": [TIMELINE["audio"]["near_silence_start"], TIMELINE["audio"]["near_silence_end"]],
            "tragic_theme_seconds": [TIMELINE["audio"]["tragic_theme_start"], TIMELINE["audio"]["controlled_climax_start"]],
            "controlled_climax_seconds": [TIMELINE["audio"]["controlled_climax_start"], TIMELINE["audio"]["controlled_climax_end"]],
            "unresolved_ending_seconds": [TIMELINE["audio"]["controlled_climax_end"], args.duration],
        },
        "records": records,
    }
    report_path = args.output_dir.resolve() / "conform-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
