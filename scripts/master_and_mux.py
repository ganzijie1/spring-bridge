from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "output" / "shanghai-1976-force-map-with-zhang.mp4"
MUSIC_DIR = ROOT / "output" / "music"
MASTER = MUSIC_DIR / "shanghai-1976-score-master.wav"
FINAL = ROOT / "output" / "shanghai-1976-force-map-with-zhang-music.mp4"
REPORT = MUSIC_DIR / "music-final-validation.json"


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
    parser = argparse.ArgumentParser(description="Master a selected score and mux it with the 60-second video")
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    source = args.input.resolve()
    if not source.exists():
        raise SystemExit(f"Music file does not exist: {source}")
    if not VIDEO.exists():
        raise SystemExit(f"Video file does not exist: {VIDEO}")
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    first = loudnorm_measure(source)
    gain_db = constant_master_gain(first)
    audio_filter = (
        "aresample=48000," 
        "afade=t=in:st=0:d=0.005,"
        "afade=t=out:st=59.995:d=0.005,"
        "apad=pad_dur=60,atrim=duration=60,"
        f"volume={gain_db:.3f}dB"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-i", str(source), "-vn", "-af", audio_filter,
        "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(MASTER),
    ])
    run([
        "ffmpeg", "-y", "-hide_banner", "-i", str(VIDEO), "-i", str(MASTER),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "320k", "-ar", "48000", "-ac", "2", "-t", "60",
        "-movflags", "+faststart", str(FINAL),
    ])
    final_probe = probe(FINAL)
    final_duration = float(final_probe["format"]["duration"])
    stream_types = [stream["codec_type"] for stream in final_probe["streams"]]
    final_loudness = loudnorm_measure(MASTER)
    checks = {
        "duration_is_60s": abs(final_duration - 60.0) <= 0.05,
        "has_video": "video" in stream_types,
        "has_audio": "audio" in stream_types,
        "video_codec_h264": any(stream.get("codec_type") == "video" and stream.get("codec_name") == "h264" for stream in final_probe["streams"]),
        "audio_48khz_stereo": any(stream.get("codec_type") == "audio" and stream.get("sample_rate") == "48000" and stream.get("channels") == 2 for stream in final_probe["streams"]),
    }
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "source_music": str(source),
        "master": str(MASTER),
        "final_video": str(FINAL),
        "checks": checks,
        "probe": final_probe,
        "master_loudness": final_loudness,
        "mastering": {
            "strategy": "constant gain constrained by -16 LUFS target and -1 dBTP ceiling",
            "source_loudness": first,
            "gain_db": round(gain_db, 3),
        },
        "sha256": hash_file(FINAL),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
