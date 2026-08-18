# The demo video, and how it was made

[`demo.mp4`](demo.mp4) — 2:55, 1080p. A real debate, captured from the running app.

Everything here is reproducible, which is the only reason it is in the repository: a
demo video is usually a dead artefact you cannot re-cut when the product moves. This
one re-renders from four scripts.

| File | What it does |
| --- | --- |
| [`intro.py`](intro.py) | Draws the intro animation and the story cards frame by frame with PIL, in the app's own palette. |
| [`keybed.py`](keybed.py) | Synthesises the keyboard track — the same bandpassed noise burst plus low thump the app plays in WebAudio. The screen capture is silent, so the sound the product is known for is rebuilt rather than lost. |
| [`cards.py`](cards.py) | The lower-third captions. |
| [`cut.py`](cut.py) | Cuts the capture to the timeline, overlays captions, mixes the bed, concatenates. |
| [`script.json`](script.json) | The narration text. Only the hook and the sign-off are spoken; the rest is carried by the cards. |

## Rebuilding it

```bash
# 1. one service, so the capture shows what a reviewer would see
cd frontend && npm run build
cd ../backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8123

# 2. record a debate to replay, so the capture cannot stall on a rate limit
MAX_DEBATE_ROUNDS=5 ./.venv/Scripts/python.exe -m app.record demo-en "AI will replace software developers."
./.venv/Scripts/python.exe -m app.record --extend demo-en "You both treated 'developer' as one job."

# 3. capture the window playing it, with no input automation needed
#    chrome --app="http://127.0.0.1:8123/?replay=demo-en"
#    ffmpeg -f gdigrab -framerate 24 -video_size 2560x1440 -i desktop -t 400 clean.mp4

# 4. render
python keybed.py keybed.wav 190
python cards.py
python intro.py
python cut.py
```

Voiceover for the two spoken lines is [edge-tts](https://github.com/rany2/edge-tts),
free and offline-installable:

```bash
python -m edge_tts --voice en-US-AndrewNeural --text "..." --write-media vo/01_hook.mp3
```

## Two notes on honesty

The footage is a **replay of a real debate**, and the app says so on screen while it
plays. Nothing in the transcript was written by hand: recordings can only be produced
by an actual run of the engine.

The capture was trimmed to the region that contains only the app window. Screen capture
grabs whatever else is on the desktop, so that trim is not tidying — it is the whole
reason the file is safe to publish.
