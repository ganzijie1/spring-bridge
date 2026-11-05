from __future__ import annotations

import argparse
import json
from pathlib import Path

import librosa
import numpy as np
import torch
from transformers import ClapModel, ClapProcessor


DESIRED_DREAD = [
    "an ominous and oppressive political crisis soundtrack",
    "a solemn funeral dirge filled with grief",
    "psychological dread before an irreversible catastrophe",
    "a dark unresolved historical tragedy",
]
REJECT_DREAD = [
    "cheerful festive holiday music",
    "a triumphant heroic battle victory soundtrack",
    "an exciting adventurous action soundtrack",
    "an upbeat military march",
    "a hopeful inspirational melody",
    "playful bouncy dance music",
]
DESIRED_RESISTANCE = [
    "dark tense orchestral resistance music with driving strings",
    "urgent militant minor-key action score with unresolved tension",
    "defiant tragic orchestral music with a syncopated rhythm",
    "gritty suspenseful battle-preparation music with collective resolve",
]
REJECT_RESISTANCE = [
    "slow solemn orchestral funeral music with sustained mournful chords",
    "static dark ambient drone music without rhythm",
    "bright cheerful festive orchestral holiday music",
    "triumphant heroic orchestral victory fanfare",
    "upbeat patriotic military parade march",
    "exciting glossy orchestral adventure soundtrack",
]
WINDOWS = [(2, 12), (14, 24), (30, 40), (49, 59), (70, 80), (80, 90)]


def pooled_tensor(output: object) -> torch.Tensor:
    if isinstance(output, torch.Tensor):
        return output
    pooler = getattr(output, "pooler_output", None)
    if isinstance(pooler, torch.Tensor):
        return pooler
    for name in ("text_embeds", "audio_embeds"):
        embeds = getattr(output, name, None)
        if isinstance(embeds, torch.Tensor):
            return embeds
    raise TypeError(f"Unsupported CLAP feature output: {type(output).__name__}")


def load_window(path: Path, start: float, end: float) -> np.ndarray:
    audio, _ = librosa.load(path, sr=48000, mono=True, offset=start, duration=end - start)
    target = round((end - start) * 48000)
    if len(audio) < target:
        audio = np.pad(audio, (0, target - len(audio)))
    return audio.astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reject cheerful or triumphant score candidates with CLAP")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--model", default="laion/clap-htsat-unfused")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("dread", "resistance"), default="dread")
    args = parser.parse_args()

    desired_prompts = DESIRED_RESISTANCE if args.mode == "resistance" else DESIRED_DREAD
    reject_prompts = REJECT_RESISTANCE if args.mode == "resistance" else REJECT_DREAD

    processor = ClapProcessor.from_pretrained(args.model)
    model = ClapModel.from_pretrained(args.model).eval()
    prompts = desired_prompts + reject_prompts
    text_inputs = processor(text=prompts, return_tensors="pt", padding=True)
    with torch.inference_mode():
        text_features = pooled_tensor(model.get_text_features(**text_inputs))
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    results = []
    for path in args.files:
        window_records = []
        for start, end in WINDOWS:
            audio = load_window(path, start, end)
            audio_inputs = processor(audio=audio, sampling_rate=48000, return_tensors="pt")
            with torch.inference_mode():
                audio_features = pooled_tensor(model.get_audio_features(**audio_inputs))
                audio_features = audio_features / audio_features.norm(dim=-1, keepdim=True)
                similarities = (audio_features @ text_features.T).squeeze(0).cpu().numpy()
            desired = float(np.mean(similarities[: len(desired_prompts)]))
            reject = float(np.max(similarities[len(desired_prompts) :]))
            reject_index = int(np.argmax(similarities[len(desired_prompts) :]))
            window_records.append({
                "seconds": [start, end],
                "desired_mean": round(desired, 5),
                "reject_max": round(reject, 5),
                "margin": round(desired - reject, 5),
                "highest_reject_prompt": reject_prompts[reject_index],
            })
        mean_margin = float(np.mean([item["margin"] for item in window_records]))
        worst_margin = float(min(item["margin"] for item in window_records))
        results.append({
            "file": str(path.resolve()),
            "status": "PASS" if mean_margin > 0 and worst_margin > -0.025 else "REJECT_CHEERFULNESS_RISK",
            "mean_desired_minus_reject_margin": round(mean_margin, 5),
            "worst_window_margin": round(worst_margin, 5),
            "windows": window_records,
        })
    results.sort(key=lambda item: (item["status"] == "PASS", item["mean_desired_minus_reject_margin"]), reverse=True)
    report = {
        "status": "PASS" if any(item["status"] == "PASS" for item in results) else "NO_PASS",
        "model": args.model,
        "scope": "semantic candidate screening; human listening remains authoritative",
        "mode": args.mode,
        "desired_prompts": desired_prompts,
        "reject_prompts": reject_prompts,
        "ranking": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
