from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_BASE = "https://api.dev.runwayml.com"
API_VERSION = "2024-11-06"
OUT_DIR = ROOT / "output" / "generative"
TASKS_PATH = OUT_DIR / "tasks.json"
PLAN_PATH = OUT_DIR / "generation-plan.json"

JOBS = [
    {
        "id": "runway-gen4.5",
        "model": "gen4.5",
        "ratio": "1280:720",
        "duration": 5,
        "seed": 19761008,
        "timelineStart": 16,
        "credits": 60,
        "output": "runway-gen4.5.mp4",
        "prompt": (
            "Locked overhead 2D archival cartographic plate of 1970s Shanghai. "
            "Preserve exact geometry and framing. Subtle paper fibers, faint projector gate weave, "
            "restrained red and blue indicator glows breathing slowly, gentle river-light shimmer, "
            "slow controlled push-in under two percent. No text, no labels, no numbers, no icons, "
            "no people, no vehicles, no explosions, no smoke, no new roads, no topology changes, "
            "no map deformation, no camera rotation."
        ),
    },
    {
        "id": "kling-4",
        "model": "kling_4",
        "ratio": "auto_720p",
        "duration": 5,
        "seed": 19761020,
        "timelineStart": 28,
        "credits": 64,
        "output": "kling-4.mp4",
        "prompt": (
            "Locked overhead 2D archival paper map. Preserve exact river and road geometry. "
            "Mechanical projector jitter under one pixel, mild ink diffusion, faint directional "
            "light traveling west to east, red and blue indicator glows pulse once, documentary "
            "restraint. No text, labels, numbers, icons, people, vehicles, explosions, smoke, "
            "new roads, topology changes, map deformation, or camera rotation."
        ),
    },
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_json(method: str, path: str, secret: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        API_BASE + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {secret}",
            "X-Runway-Version": API_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Runway API returned HTTP {exc.code}: {detail}") from exc


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def sanitized_plan(input_path: Path, status: str) -> dict[str, Any]:
    return {
        "createdAt": now(),
        "status": status,
        "api": {"base": API_BASE, "version": API_VERSION, "endpoint": "/v1/image_to_video"},
        "input": str(input_path.relative_to(ROOT)).replace("\\", "/"),
        "factualLayerPolicy": (
            "Generated clips are atmosphere-only. All text, dates, locations, counts, routes, and "
            "force labels remain in the deterministic foreground."
        ),
        "jobs": [
            {
                key: job[key]
                for key in (
                    "id", "model", "ratio", "duration", "seed", "timelineStart", "credits", "output", "prompt"
                )
            }
            for job in JOBS
        ],
        "estimatedCredits": sum(job["credits"] for job in JOBS),
        "estimatedUsd": round(sum(job["credits"] for job in JOBS) * 0.01, 2),
        "notes": [
            "Kling 4.0 may return generated audio; the compositor always strips it.",
            "The data URI and API credential are never written to disk or logs.",
        ],
    }


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_tasks() -> dict[str, Any]:
    if TASKS_PATH.exists():
        return json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    return {"updatedAt": now(), "jobs": {}}


def task_id_from(response: dict[str, Any]) -> str:
    task_id = response.get("id") or response.get("taskId")
    if not task_id:
        raise RuntimeError(f"Task response did not contain an id. Keys: {sorted(response.keys())}")
    return str(task_id)


def output_url_from(response: dict[str, Any]) -> str:
    output = response.get("output")
    if isinstance(output, list) and output:
        return str(output[0])
    if isinstance(output, str) and output:
        return output
    for key in ("outputUrl", "url"):
        if response.get(key):
            return str(response[key])
    raise RuntimeError(f"Successful task did not contain an output URL. Keys: {sorted(response.keys())}")


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Shanghai1976Hybrid/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response, destination.open("wb") as handle:
        while chunk := response.read(1024 * 1024):
            handle.write(chunk)


def submit(input_path: Path, secret: str, state: dict[str, Any]) -> None:
    encoded_input = data_uri(input_path)
    for job in JOBS:
        existing = state["jobs"].get(job["id"], {})
        if existing.get("taskId"):
            print(f"{job['id']}: reusing task {existing['taskId']}")
            continue
        payload = {
            "model": job["model"],
            "promptImage": encoded_input,
            "promptText": job["prompt"],
            "ratio": job["ratio"],
            "duration": job["duration"],
            "seed": job["seed"],
        }
        print(f"{job['id']}: submitting {job['duration']}s {job['model']} task")
        response = request_json("POST", "/v1/image_to_video", secret, payload)
        state["jobs"][job["id"]] = {
            "taskId": task_id_from(response),
            "model": job["model"],
            "submittedAt": now(),
            "status": "SUBMITTED",
        }
        state["updatedAt"] = now()
        save_json(TASKS_PATH, state)


def poll(secret: str, state: dict[str, Any], timeout_minutes: int) -> None:
    deadline = time.monotonic() + timeout_minutes * 60
    pending = {job["id"] for job in JOBS}
    while pending:
        if time.monotonic() > deadline:
            raise TimeoutError(f"Timed out with pending jobs: {sorted(pending)}")
        for job in JOBS:
            job_id = job["id"]
            if job_id not in pending:
                continue
            saved = state["jobs"].get(job_id)
            if not saved or not saved.get("taskId"):
                raise RuntimeError(f"Missing task id for {job_id}")
            response = request_json("GET", f"/v1/tasks/{saved['taskId']}", secret)
            status = str(response.get("status", "UNKNOWN")).upper()
            saved["status"] = status
            saved["lastCheckedAt"] = now()
            state["updatedAt"] = now()
            save_json(TASKS_PATH, state)
            print(f"{job_id}: {status}")
            if status in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
                destination = OUT_DIR / job["output"]
                download(output_url_from(response), destination)
                saved["downloadedAt"] = now()
                saved["output"] = str(destination.relative_to(ROOT)).replace("\\", "/")
                save_json(TASKS_PATH, state)
                pending.remove(job_id)
            elif status in {"FAILED", "CANCELED", "CANCELLED"}:
                saved["failure"] = response.get("failure") or response.get("error") or "Unknown failure"
                save_json(TASKS_PATH, state)
                raise RuntimeError(f"{job_id} ended with status {status}: {saved['failure']}")
        if pending:
            time.sleep(10)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Runway Gen-4.5 and Kling 4.0 atmosphere clips.")
    parser.add_argument("--submit", action="store_true", help="Authorize paid API submissions.")
    parser.add_argument("--resume", action="store_true", help="Resume polling saved task ids without resubmitting.")
    parser.add_argument("--timeout-minutes", type=int, default=30)
    parser.add_argument(
        "--input",
        type=Path,
        default=OUT_DIR / "inputs" / "shanghai-clean-plate-1280x720.png",
    )
    args = parser.parse_args()
    input_path = args.input.resolve()
    if not input_path.exists():
        raise SystemExit(f"Missing input image: {input_path}. Run prepare_generative_inputs.py first.")

    secret = os.environ.get("RUNWAYML_API_SECRET", "")
    status = "READY_TO_SUBMIT" if secret else "BLOCKED_MISSING_RUNWAYML_API_SECRET"
    plan = sanitized_plan(input_path, status)
    save_json(PLAN_PATH, plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2))

    if not args.submit and not args.resume:
        print("Dry run only. Add --submit to authorize the estimated paid requests.")
        return
    if not secret:
        raise SystemExit("RUNWAYML_API_SECRET is not set. No paid request was sent.")

    state = load_tasks()
    if not args.resume:
        submit(input_path, secret, state)
    poll(secret, state, args.timeout_minutes)


if __name__ == "__main__":
    main()
