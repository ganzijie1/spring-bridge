from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "narration-plan.json"
OUTPUT = ROOT / "output" / "narration"
SEGMENTS = OUTPUT / "segments"
NARRATION = OUTPUT / "narration-master.wav"
MIX = OUTPUT / "music-narration-mix.wav"
VIDEO = ROOT / "output" / "shanghai-1976-force-map-with-zhang.mp4"
MUSIC = ROOT / "output" / "music" / "shanghai-1976-score-master.wav"
FINAL = ROOT / "output" / "shanghai-1976-force-map-contextual-narration.mp4"
REPORT = OUTPUT / "contextual-tts-validation.json"
MANIFEST = OUTPUT / "generation-manifest.json"
SPEECH_EXE = Path(os.environ.get(
    "SPEECH_CPP_EXE",
    r"C:\Users\Administrator\AppData\Local\Programs\speech.cpp\current\speech.exe",
))
DEFAULT_MODEL = Path(os.environ.get(
    "SPEECH_CPP_MODEL",
    r"C:\Users\Administrator\AppData\Local\speech.cpp\models\sakasegawa--Qwen3-TTS-12Hz-1.7B-CustomVoice-GGUF\1bc0ef69547c003507b6536639a6080c8856382f4d0963b15d4475528330592d\Qwen3-TTS-12Hz-1.7B-CustomVoice-Q8_0.gguf",
))


def run(command: list[str], capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=capture, text=True)


def probe(path: Path) -> dict:
    result = run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,sample_rate,channels",
        "-of", "json", str(path),
    ])
    return json.loads(result.stdout)


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_plan() -> dict:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    previous_end = 0.0
    photo_start, photo_end = plan["meta"]["photo_silence"]
    for segment in plan["segments"]:
        start = float(segment["start"])
        end = float(segment["end"])
        if start < previous_end or end <= start:
            raise ValueError(f"Invalid or overlapping segment: {segment['id']}")
        if start < photo_end and end > photo_start:
            raise ValueError(f"Narration overlaps photo silence: {segment['id']}")
        previous_end = end
    if previous_end > float(plan["meta"]["duration_seconds"]):
        raise ValueError("Narration exceeds video duration")
    return plan


def build_instruction(plan: dict, segment: dict) -> str:
    return " ".join([
        plan["global_context"],
        f"前一幅画面：{segment['context_before']}",
        f"随后画面：{segment['context_after']}",
        f"本句表演：{segment['instruction']}",
    ])


def generate(plan: dict, model_path: Path, force: bool) -> list[dict]:
    if not SPEECH_EXE.exists():
        raise FileNotFoundError(f"speech.cpp executable is missing: {SPEECH_EXE}")
    if not model_path.exists():
        raise FileNotFoundError(f"Qwen3-TTS model is missing: {model_path}")

    speaker = plan["meta"]["speaker"].lower()
    language = plan["meta"]["language"].lower()
    generated = []
    for index, segment in enumerate(plan["segments"]):
        target = SEGMENTS / f"{segment['id']}-raw.wav"
        if force or not target.exists():
            result = run([
                str(SPEECH_EXE), "tts", str(model_path),
                "--device", "Vulkan0",
                "--voice", speaker,
                "--language", language,
                "--seed", str(19761008 + index),
                "--top-k", "40",
                "--top-p", "0.92",
                "--temperature", "0.85",
                "--repetition-penalty", "1.08",
                "--max-seconds", "30",
                "--instructions", build_instruction(plan, segment),
                "-o", str(target),
                segment["text"],
            ])
            if not target.exists() or target.stat().st_size == 0:
                raise RuntimeError(f"TTS produced no audio for {segment['id']}: {result.stderr}")
        generated.append({
            "id": segment["id"],
            "file": str(target),
            "sha256": sha256(target),
            "raw_duration": duration(target),
            "instruction": build_instruction(plan, segment),
            "seed": 19761008 + index,
        })
    return generated


def atempo_chain(speed: float) -> str:
    filters = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.6f}")
    return ",".join(filters)


def conform_segments(plan: dict, generated: list[dict]) -> list[dict]:
    by_id = {item["id"]: item for item in generated}
    conformed = []
    for segment in plan["segments"]:
        item = by_id[segment["id"]]
        source = Path(item["file"])
        target = SEGMENTS / f"{segment['id']}-conformed.wav"
        slot = float(segment["end"]) - float(segment["start"])
        raw_duration = float(item["raw_duration"])
        speed = max(1.0, raw_duration / max(0.25, slot - 0.12))
        filters = ["highpass=f=70", "lowpass=f=15000"]
        if speed > 1.001:
            filters.append(atempo_chain(speed))
        filters.extend([
            "loudnorm=I=-19:TP=-2:LRA=7",
            "afade=t=in:st=0:d=0.03",
            f"apad=pad_dur={slot:.3f}",
            f"atrim=duration={slot:.3f}",
            f"afade=t=out:st={max(0.0, slot - 0.05):.3f}:d=0.05",
        ])
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-af", ",".join(filters), "-ar", "48000", "-ac", "1",
            "-c:a", "pcm_s24le", str(target),
        ])
        conformed.append({
            **item,
            "start": float(segment["start"]),
            "end": float(segment["end"]),
            "slot_duration": slot,
            "speed_factor": speed,
            "conformed_file": str(target),
            "conformed_sha256": sha256(target),
        })
    return conformed


def assemble_narration(conformed: list[dict], total_duration: float) -> None:
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for item in conformed:
        command.extend(["-i", item["conformed_file"]])
    chains = []
    labels = []
    for index, item in enumerate(conformed):
        delay = round(float(item["start"]) * 1000)
        label = f"s{index}"
        chains.append(f"[{index}:a]adelay={delay}|{delay}[{label}]")
        labels.append(f"[{label}]")
    chains.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0,"
        f"apad=pad_dur={total_duration},atrim=duration={total_duration}[narration]"
    )
    command.extend([
        "-filter_complex", ";".join(chains), "-map", "[narration]",
        "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(NARRATION),
    ])
    run(command)


def mix_and_mux(total_duration: float) -> None:
    mix_filter = (
        "[0:a]aresample=48000,volume=0.88[music];"
        "[1:a]aresample=48000,asplit=2[narr_side][narr];"
        "[music][narr_side]sidechaincompress="
        "threshold=0.018:ratio=10:attack=18:release=420:makeup=1[ducked];"
        "[ducked][narr]amix=inputs=2:weights='1 1.05':normalize=0,"
        "alimiter=limit=0.891:attack=5:release=80,"
        f"apad=pad_dur={total_duration},atrim=duration={total_duration}[mix]"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(MUSIC),
        "-i", str(NARRATION), "-filter_complex", mix_filter, "-map", "[mix]",
        "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(MIX),
    ])
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(VIDEO),
        "-i", str(MIX), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2",
        "-t", f"{total_duration:.3f}", "-movflags", "+faststart", str(FINAL),
    ])


def loudness(path: Path) -> dict:
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
        "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json", "-f", "null", "-",
    ], check=True, capture_output=True, text=True)
    matches = re.findall(r"\{\s*\"input_i\".*?\}", result.stderr, flags=re.DOTALL)
    return json.loads(matches[-1]) if matches else {}


def volume_window(path: Path, start: float, end: float) -> dict:
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start:.3f}",
        "-t", f"{end - start:.3f}", "-i", str(path), "-vn",
        "-af", "volumedetect", "-f", "null", "-",
    ], check=True, capture_output=True, text=True)

    def read_db(name: str) -> float:
        match = re.search(rf"{name}:\s*(-?inf|-?[\d.]+)\s+dB", result.stderr)
        if not match or match.group(1) == "-inf":
            return -120.0
        return float(match.group(1))

    return {
        "start": start,
        "end": end,
        "mean_dbfs": read_db("mean_volume"),
        "max_dbfs": read_db("max_volume"),
    }


def validate(plan: dict, conformed: list[dict], model_path: Path) -> dict:
    total = float(plan["meta"]["duration_seconds"])
    media = probe(FINAL)
    final_duration = float(media["format"]["duration"])
    streams = media["streams"]
    photo_start, photo_end = map(float, plan["meta"]["photo_silence"])
    photo_volume = volume_window(NARRATION, photo_start, photo_end)
    segment_volumes = {
        item["id"]: volume_window(NARRATION, item["start"], item["end"])
        for item in conformed
    }
    checks = {
        "duration_is_60s": abs(final_duration - total) <= 0.08,
        "has_h264_video": any(
            x.get("codec_type") == "video" and x.get("codec_name") == "h264"
            for x in streams
        ),
        "has_48khz_audio": any(
            x.get("codec_type") == "audio" and x.get("sample_rate") == "48000"
            for x in streams
        ),
        "all_segments_generated": len(conformed) == len(plan["segments"]) and all(
            Path(x["conformed_file"]).exists() for x in conformed
        ),
        "photo_interval_is_silent": photo_volume["max_dbfs"] <= -80.0,
        "all_narration_segments_are_audible": all(
            stats["max_dbfs"] >= -45.0 for stats in segment_volumes.values()
        ),
        "no_extreme_time_stretch": all(
            float(x["speed_factor"]) <= 1.35 for x in conformed
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "runtime": "speech.cpp",
        "model": str(model_path),
        "model_sha256": sha256(model_path),
        "strategy": plan["meta"]["strategy"],
        "checks": checks,
        "segments": conformed,
        "measured_windows": {
            "photo_silence": photo_volume,
            "narration_segments": segment_volumes,
        },
        "loudness": {
            "narration": loudness(NARRATION),
            "music_narration_mix": loudness(MIX),
        },
        "outputs": {
            "narration": str(NARRATION),
            "mix": str(MIX),
            "video": str(FINAL),
            "video_sha256": sha256(FINAL),
        },
        "media": media,
        "remaining_validation": [
            "人工复核中文读音、数字停顿与史料限定语是否准确。",
            "在完整视频中盲听旁白是否遮挡地图信息。",
            "如需自动 CER，需另接中文 ASR 与人工校订文本。",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and mix context-planned Chinese narration")
    parser.add_argument("--model", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--mix-only", action="store_true")
    args = parser.parse_args()

    plan = load_plan()
    model_path = Path(args.model).resolve() if args.model else DEFAULT_MODEL
    OUTPUT.mkdir(parents=True, exist_ok=True)
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    if not VIDEO.exists() or not MUSIC.exists():
        raise SystemExit("Required video or music master is missing")

    if args.mix_only:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest.setdefault("generation_plan_sha256", manifest.get("plan_sha256"))
        manifest["conform_plan_sha256"] = sha256(PLAN_PATH)
        MANIFEST.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        generated = manifest["segments"]
    else:
        generated = generate(plan, model_path, args.force)
        MANIFEST.write_text(json.dumps({
            "runtime": "speech.cpp",
            "executable": str(SPEECH_EXE),
            "model": str(model_path),
            "model_sha256": sha256(model_path),
            "python": sys.version,
            "generation_plan_sha256": sha256(PLAN_PATH),
            "conform_plan_sha256": sha256(PLAN_PATH),
            "segments": generated,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    conformed = conform_segments(plan, generated)
    total = float(plan["meta"]["duration_seconds"])
    assemble_narration(conformed, total)
    mix_and_mux(total)
    report = validate(plan, conformed, model_path)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
