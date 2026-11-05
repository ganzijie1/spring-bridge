#!/usr/bin/env python3
"""Run the official public SonicMaster Space without an API key."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


DEFAULT_PROMPT = (
    "Reduce low-frequency muddiness and digital artifacts while preserving dynamics, stereo image, "
    "instrumentation, and reverb tails. Do not add new musical content."
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = parser.parse_args()
    try:
        from gradio_client import Client, handle_file
    except ImportError as error:
        raise SystemExit("Install gradio_client in the audio environment first") from error

    source = args.input.resolve()
    destination = args.output.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    client = Client("https://amaai-lab-sonicmaster.hf.space")
    result = client.predict(handle_file(str(source)), args.prompt, api_name="/enhance_audio_ui")
    result_path = Path(result[0] if isinstance(result, (tuple, list)) else result)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(result_path, destination)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
