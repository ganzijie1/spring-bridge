# 60-second music pipeline

The completed default pipeline uses the open-source ACE-Step 1.5 model locally. It needs no API key and generates four complete 60-second instrumental candidates rather than splicing separate songs.

The tested checkout is `../../ai-tools/ACE-Step-1.5`, using `acestep-v15-turbo`, ModelScope for the initial model download, and fixed seeds `19761006` through `19761009`. The generator requests a 64 BPM D-minor instrumental with no vocals, choir, speech, anthem, or trailer braams.

Run a 10-second smoke test:

~~~powershell
uv run --project ../ai-tools/ACE-Step-1.5 python scripts/generate_music_acestep.py --duration 10 --count 1 --smoke-test
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

## Battle-C tragic combat experiment

The `battle-c` profile keeps the earlier score intact and generates a separate dark-combat experiment: low-string pulse, restrained military snare, dissonant low brass, slowly growing wordless choir, a deterministic middle break, and a post-break tragic theme. It explicitly rejects bright major harmony, victory cadences, pop vocals, narration, guitar solos, trailer braams, and nonstop percussion.

Run a short model check:

~~~powershell
uv run --project ../ai-tools/ACE-Step-1.5 python scripts/generate_music_acestep.py --profile battle-c --duration 10 --count 1 --smoke-test
~~~

The reviewed experiment used four 90-second candidates with seeds `19761006` through `19761009`. The selected source was seed `19761009`. Its conformed master is `output/music/battle-c-90-final.wav`; the 320 kbps listening copy is `output/music/battle-c-90-final.mp3`.

The 90-second structure is proportional rather than hard-coded: pressure through 44 seconds, near-silence from approximately 44 to 48 seconds, tragic theme through 70 seconds, controlled climax through 86 seconds, and unresolved aftermath. `score_battle_c.py` verifies duration, low-frequency opening weight, break depth, theme return, climax control, percussion density, and ending presence. These acoustic checks do not replace a human decision about triumph, intelligible pseudo-lyrics, or the quality of the generated melody.

## Canonical 90-second historical-crisis release pipeline

The current review build uses `src/timeline.json` as the single source of truth for the Remotion composition, score generation, deterministic conformation, mastering, muxing, and validation. The six contiguous sections are 0-8s introduction, 8-26s militia deployment, 26-44s arms and network, 44-48s turning-point near-silence and trial photograph, 48-72s suppression pressure, and 72-90s documentary aftermath.

The `historical-crisis` ACE-Step profile strengthens the pre-battle tension while explicitly rejecting gunshots, explosions, victory cadences, heroic fanfare, pop vocals, intelligible pseudo-language, trailer braams, and nonstop percussion. Four deterministic 90-second candidates are generated. The conformation stage imposes the exact timeline envelope without splicing songs. The scoring stage ranks low-frequency pressure, break depth, theme return, controlled climax, transient density, and unresolved ending.

Run the complete reproducible pipeline:

~~~powershell
npm run release:historical-crisis
~~~

The 2026-11-05 build provisionally selected candidate 02 with a technical score of 74.18. It passed every acoustic hard gate: 22.879 dB break depth, 16.834 dB theme return, 3.012 dB controlled climax growth, and a present unresolved ending. Selection remains provisional until a human listens to the full video for pseudo-vocals, accidental triumph, musical monotony, and narrative fit.

Primary outputs:

- `output/shanghai-1976-historical-crisis-review.mp4`: 90.000-second H.264/AAC review video.
- `output/music/historical-crisis-90-selected.flac`: selected 48 kHz lossless score.
- `output/music/shanghai-1976-historical-crisis-master.wav`: -16 LUFS constrained master.
- `output/music/historical-crisis-90-ranking.json`: all candidate metrics and ranking.
- `output/historical-consistency-validation.json`: technical and documentary gate report.

The validation status is `PASS_WITH_REMAINING_RISK`, not a public-release PASS. Claims C1, C5, and C6 have source-level locators but still need page-level locators. The trial image is labeled as a 1980-1981 Special Tribunal photograph and not a 1976 Shanghai scene.

## Historical-dread replacement after listening rejection

The provisional `historical-crisis` candidate above was rejected by human review because its forward motion sounded cheerful and celebratory despite passing the original acoustic gates. It must not be promoted as the final score.

The replacement route uses the `historical-dread-atonal` profile at a hidden 46 BPM grid: no tune-led writing, no conventional chord progression, no march, no victory cadence, and no post-break heroic melody. Four new candidates were generated with seeds `19761014` through `19761017`. Candidate 01 was the only file that passed all six CLAP screening windows against festive, triumphant, adventurous, upbeat-march, hopeful, and playful reference prompts. Its mean desired-minus-reject margin is `0.04746`; the worst window remains positive at `0.02058`.

The selected score also passes the deterministic acoustic gates after adding a quiet unresolved D-E-flat-A-flat low cluster to the final four seconds. The release remains subject to human listening because semantic embedding scores cannot establish emotional fit.

Primary replacement outputs:

- `output/shanghai-1976-historical-dread-review.mp4`: 90-second replacement review video.
- `output/music/historical-dread-atonal-90-selected.flac`: lossless selected score.
- `output/music/historical-dread-atonal-90-selected-semantic.json`: six-window semantic screening.
- `output/music/historical-dread-atonal-90-selected-acoustic.json`: deterministic acoustic checks.
- `output/historical-dread-validation.json`: media and documentary validation.

## Deterministic resistance replacement

Human review rejected the atonal replacement as a continuous funeral mood. Two further ACE-Step resistance batches were also rejected: most candidates drifted toward bright orchestral holiday music, double-time marching, or passive mourning. The model-generated candidates are retained as experiments but are not release sources.

The accepted direction is a deterministic 66 BPM MIDI arrangement rendered with FluidSynth 2.6.2 and GeneralUser GS. The score uses an asymmetric pizzicato low-string pulse, a three-note minor/tritone signal, contrary-motion middle strings, clipped dissonant brass, irregular low drums before the turn, a 44-48 second held breath, and non-repeating calls after 80 seconds. It never resolves to a victory cadence.

The final peak-controlled v4 master passes every deterministic acoustic hard gate with a technical score of `85.74`. CLAP resistance screening also passes: mean desired-minus-reject margin `0.02290`, worst six-window margin `-0.01700`. A compressed -16 LUFS experiment was rejected because it shifted the semantic result back toward marching music. The retained master is approximately -19.4 LUFS and preserves the transient structure. These automated checks support selection but do not overrule human listening.

Primary outputs:

- `output/shanghai-1976-resistance-review.mp4`: review video with the resistance score.
- `output/music/historical-resistance-deterministic-v4.flac`: selected lossless score.
- `output/music/shanghai-1976-resistance-master.wav`: peak-controlled master; dynamics are preserved even though the peak ceiling keeps integrated loudness below the nominal target.
- `output/music/historical-resistance-deterministic-v4.mp3`: listening copy of the final master.
- `output/music/historical-resistance-deterministic-v4-acoustic.json`: acoustic gate report.
- `output/music/historical-resistance-deterministic-v4-semantic.json`: six-window resistance screening.
- `output/music/historical-resistance-deterministic.mid`: editable source arrangement.

FluidSynth comes from its official Windows release. GeneralUser GS is distributed under its included license, which permits use of rendered music; local tool and SoundFont copies live under `.tools` and are not required as release media.

## Generated-music artifact restoration

## Sampled-orchestra imminent-confrontation replacement

Human review rejected the deterministic GeneralUser GS resistance score because its short pizzicato gestures read as furtive rather than as an open confrontation. The approved replacement uses the open Sonatina Symphonic Orchestra samples directly: continuous low-string tremolo fields, broad synchronized marcato declarations, and sparse structural timpani. It contains no pizzicato, low-brass effects, vocals, gunfire, victory cadence, or continuous trailer percussion.

The 90-second arrangement follows `src/timeline.json` without looping the approved 18-second audition. Pressure rises from 0-44 seconds, falls to near-silence during the 44-48 second trial photograph, rebuilds at 48 seconds, peaks under controlled escalation from 70-86 seconds, and ends on an unresolved cluster.

Rebuild and validate the review version:

~~~powershell
npm run music:compose:imminent-confrontation
npm run release:mux:imminent-confrontation
npm run release:validate:imminent-confrontation
~~~

Primary outputs:

- `output/shanghai-1976-imminent-confrontation-review.mp4`: 90-second H.264/AAC review video.
- `output/music/shanghai-1976-imminent-confrontation-90.wav`: editable 44.1 kHz sampled-orchestra render.
- `output/music/shanghai-1976-imminent-confrontation-master.wav`: 48 kHz mastered score used by the video.
- `output/imminent-confrontation-mux-validation.json`: mux, duration, stream, loudness, and hash report.
- `output/imminent-confrontation-validation.json`: technical and documentary consistency report.

The current validation status is `PASS_WITH_REMAINING_RISK` only because claims C1, C5, and C6 still need page-level source locators. Human listening remains the final authority for emotional fit.

The restoration experiment follows the Feishu research plan and never overwrites the source master. It generates A0/A1/A2/A3/A5 branches, residual audio, per-segment diagnostics, hashes, and anonymized full-video review files.

Create the isolated environment once:

~~~powershell
python -m venv --system-site-packages .venv-audio
.\.venv-audio\Scripts\python.exe -m pip install torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
.\.venv-audio\Scripts\python.exe -m pip install demucs noisereduce
.\.venv-audio\Scripts\python.exe -m pip install gradio_client
~~~

Run the complete experiment:

~~~powershell
npm run music:restore
~~~

The default output is `../historical_models/shanghai-1976-video/output/music/restoration-2026-11-05`. Review `blind-review/candidate-*.mp4` before opening the branch mapping in `restoration-report.json`. Automatic PASS checks duration, sample rate, silence, clipping, loudness, true peak, photograph restraint, crisis growth, and ending pressure. It does not decide whether an estimated vocal stem is a real artifact or legitimate orchestration.

SonicMaster remains a separate A4 experiment because its generative output needs human review before combination with deterministic processing. The official public Space can be called without an API key:

~~~powershell
npm run music:restore:sonicmaster -- <input.wav> <output-directory>\candidates\A4-sonicmaster-raw.wav
npm run music:restore
~~~

The official Space currently returns a padded full-song result for this 60-second input. The restoration pipeline preserves that raw response, then resamples and trims the A4 review candidate to the exact source duration before validation.

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
