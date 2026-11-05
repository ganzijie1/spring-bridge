from __future__ import annotations

import argparse
import json
from pathlib import Path

import librosa
import numpy as np
import torch
from transformers import ClapModel, ClapProcessor


WINDOWS = [
    ("mobilisation", 8.0, 20.0),
    ("expansion", 32.0, 44.0),
    ("encirclement", 62.0, 74.0),
    ("command_break", 92.0, 104.0),
    ("transition", 103.0, 115.0),
    ("last_positions", 121.0, 133.0),
    ("ending", 137.0, 149.0),
]
DESIRED = [
    "serious dark orchestral music for a historical campaign map",
    "tense disciplined orchestral resistance under encirclement",
    "a solemn tragic last stand without victory",
    "an unresolved historical war chronicle score",
]
REJECT = [
    "cheerful festive holiday music",
    "a triumphant heroic victory fanfare",
    "an upbeat patriotic parade march",
    "playful comic adventure music",
    "a pop song with a lead singer",
    "music with choir or intelligible vocal syllables",
]


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
    raise TypeError(type(output).__name__)


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denominator) if denominator else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model", default="laion/clap-htsat-unfused")
    args = parser.parse_args()

    audio_path = args.audio.resolve()
    y, sample_rate = librosa.load(audio_path, sr=48_000, mono=True)
    duration = len(y) / sample_rate
    if duration < 149:
        raise SystemExit(f"Audio is too short: {duration:.3f}s")

    processor = ClapProcessor.from_pretrained(args.model)
    model = ClapModel.from_pretrained(args.model).eval()
    prompts = DESIRED + REJECT
    text_inputs = processor(text=prompts, return_tensors="pt", padding=True)
    with torch.inference_mode():
        text_features = pooled_tensor(model.get_text_features(**text_inputs))
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    semantic_windows = []
    acoustic_windows = []
    embeddings: list[np.ndarray] = []
    for name, start, end in WINDOWS:
        clip = y[round(start * sample_rate):round(end * sample_rate)]
        audio_inputs = processor(audio=clip.astype(np.float32), sampling_rate=sample_rate, return_tensors="pt")
        with torch.inference_mode():
            audio_features = pooled_tensor(model.get_audio_features(**audio_inputs))
            audio_features = audio_features / audio_features.norm(dim=-1, keepdim=True)
            similarities = (audio_features @ text_features.T).squeeze(0).cpu().numpy()
        desired = float(np.mean(similarities[:len(DESIRED)]))
        reject_values = similarities[len(DESIRED):]
        reject_index = int(np.argmax(reject_values))
        semantic_windows.append({
            "name": name,
            "seconds": [start, end],
            "desired_mean": round(desired, 5),
            "reject_max": round(float(reject_values[reject_index]), 5),
            "margin": round(desired - float(reject_values[reject_index]), 5),
            "highest_reject": REJECT[reject_index],
        })

        rms = librosa.feature.rms(y=clip, frame_length=2048, hop_length=512)[0]
        centroid = librosa.feature.spectral_centroid(y=clip, sr=sample_rate, n_fft=2048, hop_length=512)[0]
        onset = librosa.onset.onset_strength(y=clip, sr=sample_rate, hop_length=512)
        tempo = librosa.feature.tempo(onset_envelope=onset, sr=sample_rate, hop_length=512, aggregate=np.median)
        mfcc = librosa.feature.mfcc(y=clip, sr=sample_rate, n_mfcc=20)
        embedding = np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1)])
        embeddings.append(embedding)
        acoustic_windows.append({
            "name": name,
            "rms_db": round(float(librosa.amplitude_to_db(np.array([np.sqrt(np.mean(clip ** 2))]), ref=1.0)[0]), 2),
            "spectral_centroid_hz": round(float(np.mean(centroid)), 1),
            "onset_density_per_second": round(float(np.count_nonzero(onset > np.median(onset) + np.std(onset)) / (end - start)), 3),
            "tempo_proxy_bpm": round(float(tempo[0] if np.ndim(tempo) else tempo), 1),
        })

    non_adjacent_similarities = []
    for left in range(len(embeddings)):
        for right in range(left + 2, len(embeddings)):
            non_adjacent_similarities.append({
                "left": WINDOWS[left][0],
                "right": WINDOWS[right][0],
                "cosine": round(cosine(embeddings[left], embeddings[right]), 4),
            })
    non_adjacent_similarities.sort(key=lambda item: item["cosine"], reverse=True)

    margins = [window["margin"] for window in semantic_windows]
    voice_risks = [
        window for window in semantic_windows
        if window["highest_reject"] in REJECT[-2:]
    ]
    status = "PASS" if float(np.mean(margins)) > 0 and min(margins) > -0.03 and not voice_risks else "REVIEW"
    report = {
        "status": status,
        "audio": str(audio_path),
        "duration_seconds": round(duration, 3),
        "semantic_windows": semantic_windows,
        "acoustic_windows": acoustic_windows,
        "mean_semantic_margin": round(float(np.mean(margins)), 5),
        "worst_semantic_margin": round(float(min(margins)), 5),
        "voice_risk_windows": voice_risks,
        "highest_non_adjacent_mfcc_similarities": non_adjacent_similarities[:5],
        "limitations": [
            "CLAP is a screening model, not a substitute for human listening.",
            "MFCC similarity can flag timbral sameness but cannot prove musical looping.",
            "Tempo values are local pulse proxies and may select half-time or double-time.",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
