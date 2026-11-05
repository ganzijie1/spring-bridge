from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMELINE = json.loads((ROOT / "src" / "timeline.json").read_text(encoding="utf-8"))
VIDEO = ROOT / "output" / "shanghai-1976-force-map.mp4"
MUSIC_DIR = ROOT / "output" / "music"
MASTER = MUSIC_DIR / "shanghai-1976-historical-crisis-master.wav"
FINAL = ROOT / "output" / "shanghai-1976-historical-crisis-review.mp4"
REPORT = ROOT / "output" / "release-validation.json"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def loudnorm_measure(path: Path) -> dict:
    result = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
        "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json", "-f", "null", "-",
    ])
    matches = re.findall(r"\{\s*\"input_i\".*?\}", result.stderr, flags=re.DOTALL)
    if not matches:
        raise RuntimeError("Could not parse loudnorm measurement")
    return json.loads(matches[-1])


def constant_master_gain(measurement: dict, target_i: float = -16.0, target_tp: float = -1.0) -> float:
    """Return a constant gain that satisfies both loudness and true-peak ceilings."""
    gain_for_loudness = target_i - float(measurement["input_i"])
    gain_for_peak = target_tp - float(measurement["input_tp"])
    return min(gain_for_loudness, gain_for_peak)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def probe(path: Path) -> dict:
    result = run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ])
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Master a selected score and mux it to the canonical timeline")
    parser.add_argument("input", type=Path)
    parser.add_argument("--video", type=Path, default=VIDEO)
    parser.add_argument("--output", type=Path, default=FINAL)
    parser.add_argument("--master", type=Path, default=MASTER)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    source = args.input.resolve()
    video = args.video.resolve()
    final = args.output.resolve()
    master = args.master.resolve()
    report_path = args.report.resolve()
    duration = float(TIMELINE["duration_seconds"])
    fps = int(TIMELINE["fps"])
    target_i = float(TIMELINE["audio"]["target_lufs"])
    target_tp = float(TIMELINE["audio"]["true_peak_dbtp"])
    if not source.exists():
        raise SystemExit(f"Music file does not exist: {source}")
    if not video.exists():
        raise SystemExit(f"Video file does not exist: {video}")
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    final.parent.mkdir(parents=True, exist_ok=True)
    master.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    first = loudnorm_measure(source)
    gain_db = constant_master_gain(first, target_i=target_i, target_tp=target_tp)
    audio_filter = (
        "aresample=48000," 
        "afade=t=in:st=0:d=0.005,"
        f"afade=t=out:st={duration - 0.005:.3f}:d=0.005,"
        f"apad=pad_dur={duration},atrim=duration={duration},"
        f"volume={gain_db:.3f}dB"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-i", str(source), "-vn", "-af", audio_filter,
        "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(master),
    ])
    run([
        "ffmpeg", "-y", "-hide_banner", "-i", str(video), "-i", str(master),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "320k", "-ar", "48000", "-ac", "2", "-t", f"{duration:.3f}",
        "-movflags", "+faststart", str(final),
    ])
    final_probe = probe(final)
    final_duration = float(final_probe["format"]["duration"])
    stream_types = [stream["codec_type"] for stream in final_probe["streams"]]
    final_loudness = loudnorm_measure(master)
    checks = {
        "duration_matches_timeline_within_one_frame": abs(final_duration - duration) <= 1.0 / fps,
        "has_video": "video" in stream_types,
        "has_audio": "audio" in stream_types,
        "video_codec_h264": any(stream.get("codec_type") == "video" and stream.get("codec_name") == "h264" for stream in final_probe["streams"]),
        "audio_48khz_stereo": any(stream.get("codec_type") == "audio" and stream.get("sample_rate") == "48000" and stream.get("channels") == 2 for stream in final_probe["streams"]),
    }
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "source_music": str(source),
        "master": str(master),
        "timeline": str((ROOT / "src" / "timeline.json").relative_to(ROOT)),
        "video": str(video),
        "final_video": str(final),
        "checks": checks,
        "probe": final_probe,
        "master_loudness": final_loudness,
        "mastering": {
            "strategy": f"constant gain constrained by {target_i:g} LUFS target and {target_tp:g} dBTP ceiling",
            "source_loudness": first,
            "gain_db": round(gain_db, 3),
        },
        "sha256": hash_file(final),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
