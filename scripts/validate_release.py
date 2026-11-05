from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VIDEO = ROOT / "output" / "shanghai-1976-historical-crisis-review.mp4"
REPORT = ROOT / "output" / "historical-consistency-validation.json"
KEYFRAMES = ROOT / "output" / "release-keyframes"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def probe(path: Path) -> dict:
    result = run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,nb_frames",
        "-of", "json", str(path),
    ])
    return json.loads(result.stdout)


def extract_keyframes(video: Path, seconds: list[float], keyframes_dir: Path = KEYFRAMES) -> list[dict]:
    keyframes_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for second in seconds:
        target = keyframes_dir / f"frame-{second:05.1f}s.png"
        run([
            "ffmpeg", "-y", "-loglevel", "error", "-ss", f"{second:.3f}",
            "-i", str(video), "-frames:v", "1", "-update", "1", str(target),
        ])
        image = Image.open(target).convert("RGB")
        stat = ImageStat.Stat(image)
        records.append({
            "second": second,
            "file": str(target.relative_to(ROOT)).replace("\\", "/"),
            "size": list(image.size),
            "stddev_rgb": [round(value, 2) for value in stat.stddev],
            "nonblank": max(stat.stddev) > 8,
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate technical and documentary consistency gates")
    parser.add_argument("video", nargs="?", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--keyframes", type=Path, default=KEYFRAMES)
    args = parser.parse_args()
    video = args.video.resolve()
    report_path = args.report.resolve()
    keyframes_dir = args.keyframes.resolve()
    if not video.exists():
        raise SystemExit(f"Missing review video: {video}")

    timeline = json.loads((ROOT / "src" / "timeline.json").read_text(encoding="utf-8"))
    data = json.loads((ROOT / "src" / "data.json").read_text(encoding="utf-8"))
    photo = json.loads((ROOT / "public" / "assets" / "zhang-trial-source.json").read_text(encoding="utf-8"))
    media = probe(video)
    duration = float(media["format"]["duration"])
    fps = int(timeline["fps"])
    target_duration = float(timeline["duration_seconds"])
    streams = media["streams"]
    video_stream = next((item for item in streams if item["codec_type"] == "video"), {})
    audio_stream = next((item for item in streams if item["codec_type"] == "audio"), {})
    keyframe_seconds = [1.0, 10.0, 30.0, 45.0, 55.0, 75.0, 89.0]
    keyframes = extract_keyframes(video, keyframe_seconds, keyframes_dir)

    source_ids = {item["id"] for item in data["sources"]}
    high_risk = [item for item in data["claims"] if item.get("risk") == "high"]
    source_coverage = all(item.get("source_ids") and set(item["source_ids"]) <= source_ids for item in high_risk)
    locators_present = all(item.get("locator") for item in high_risk)
    pending_locator_claims = [item["id"] for item in high_risk if "待补" in item.get("locator", "")]
    segment_claim_ids = {claim for segment in timeline["segments"] for claim in segment.get("claim_ids", [])}
    timeline_coverage = all(item["id"] in segment_claim_ids for item in high_risk)
    no_location_people = all("people" not in item for item in data["locations"])
    suppression_counts_unknown = all(item["count"] is None for item in data["regional_forces"])
    routes_are_inferential = all("示意" in item["route_status"] or "关系" in item["route_status"] for item in data["regional_forces"])
    photo_context_complete = (
        photo.get("date") == "1980-1981"
        and "特别法庭" in photo.get("subject", "")
        and bool(photo.get("retrievedFrom"))
    )
    technical_checks = {
        "duration_within_one_frame": abs(duration - target_duration) <= 1.0 / fps,
        "video_is_1920x1080": video_stream.get("width") == 1920 and video_stream.get("height") == 1080,
        "video_is_30fps": video_stream.get("r_frame_rate") == "30/1",
        "audio_is_48khz_stereo": audio_stream.get("sample_rate") == "48000" and audio_stream.get("channels") == 2,
        "all_keyframes_nonblank": all(item["nonblank"] for item in keyframes),
    }
    documentary_checks = {
        "ten_or_more_high_risk_claims": len(high_risk) >= 10,
        "all_high_risk_claims_have_known_sources": source_coverage,
        "all_high_risk_claims_have_locators": locators_present,
        "all_high_risk_claims_are_used_by_timeline": timeline_coverage,
        "no_location_level_people_invented": no_location_people,
        "suppression_force_counts_remain_unknown": suppression_counts_unknown,
        "regional_routes_are_marked_inferential": routes_are_inferential,
        "trial_photo_context_is_explicit": photo_context_complete,
    }
    technical_pass = all(technical_checks.values())
    documentary_pass = all(documentary_checks.values())
    status = "PASS" if technical_pass and documentary_pass and not pending_locator_claims else (
        "PASS_WITH_REMAINING_RISK" if technical_pass and documentary_pass else "FAIL"
    )
    report = {
        "status": status,
        "release_scope": "review draft; public release requires human listening and pending page locators",
        "video": str(video),
        "sha256": sha256(video),
        "timeline": timeline,
        "media": media,
        "technical_checks": technical_checks,
        "documentary_checks": documentary_checks,
        "high_risk_claim_count": len(high_risk),
        "pending_page_locator_claims": pending_locator_claims,
        "keyframes": keyframes,
        "manual_review_required": [
            "Music remains tense, solemn, non-triumphant, and free of intelligible pseudo-vocals",
            "The near-silence and trial photograph do not imply the photograph was taken in 1976",
            "No visual or sound effect implies unverified combat, casualties, or troop counts",
            "All routes remain visually dashed and are understood as direction or control relationships",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
