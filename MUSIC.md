# 60-second music pipeline

The completed default pipeline uses the open-source ACE-Step 1.5 model locally. It needs no API key and generates four complete 60-second instrumental candidates rather than splicing separate songs.

The tested checkout is `../../ai-tools/ACE-Step-1.5`, using `acestep-v15-turbo`, ModelScope for the initial model download, and fixed seeds `19761006` through `19761009`. The generator requests a 64 BPM D-minor instrumental with no vocals, choir, speech, anthem, or trailer braams.

Run a 10-second smoke test:

~~~powershell
uv run --project ../../ai-tools/ACE-Step-1.5 python scripts/generate_music_acestep.py --duration 10 --count 1 --smoke-test
~~~

Generate all four 60-second candidates:

~~~powershell
npm run music:generate:ace
~~~

ACE-Step controls overall musical intent but does not guarantee frame-accurate energy changes. The deterministic conform stage removes the selected candidate's terminal silence, smoothly lowers the 21.5-25.5 second photograph passage, and raises the 40-52 second climax:

~~~powershell
npm run music:conform
python scripts/score_music.py output/music/shanghai-1976-score-conformed.flac
npm run music:master
~~~

The current selected source is candidate 02. Its conformed timeline score is `0.9024`, with a 4.6 dB photograph dip, a 2.9 dB late-climax margin, and no silence longer than 0.5 seconds. The final video is exactly 60 seconds with copied H.264 video and 48 kHz stereo AAC audio. The master measures approximately -16 LUFS integrated and -1 dB true peak.

The final video is written to `output/shanghai-1976-force-map-with-zhang-music.mp4`. A human listening pass should still reject any unintended voice-like texture, triumphal affect, or musically abrupt ending.

## Optional Eleven Music route

The earlier paid route remains available as a fallback. The six chunks in `music-plan.json` total exactly 60,000 ms and align with the same edit points.

Validate the local pipeline without making a paid request:

~~~powershell
python scripts/run_music_pipeline.py --validate-only
~~~

Run the complete generation, scoring, mastering, and muxing pipeline with the key injected only into the child process:

~~~powershell
cred exec --key ELEVENLABS_API_KEY -- python scripts/run_music_pipeline.py
~~~

If `cred` is not installed, set `ELEVENLABS_API_KEY` for the current process through the operating system or a secure secret manager, then run the same Python command. Do not save the key in this repository.
