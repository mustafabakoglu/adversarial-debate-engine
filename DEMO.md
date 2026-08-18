# Demo script

Three minutes, one take, no live coding. The whole point of the product lands in the
first twenty seconds, so lead with it and let the debate run underneath while you
talk.

## The rendered video

`video/` in the scratchpad holds the pipeline that produced the submitted cut, and it
is reproducible: `keybed.py` synthesises the keyboard track, `cards.py` renders the
title, end card and captions, `assemble.py` cuts the screen capture to the narration
and concatenates the scenes. Narration is edge-tts, so re-recording a line costs
nothing.

Two deep links make capture possible without any input automation:

- `?claim=AI+will+replace+software+developers.` starts a live debate the moment the
  page loads.
- `?replay=demo-en` plays a recorded debate, challenge round included.

That is how the footage was taken: launch Chrome at the deep link, capture the screen,
never touch the keyboard.

## Before you record (if you want your own take)

```bash
# 1. Build the UI and run everything as one service, the way a reviewer will see it
cd frontend && npm run build
cd ../backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8123
# 2. Open http://127.0.0.1:8123
```

- Turn the typing sound **on** (♪ in the corner). It is a third of the atmosphere.
- Pick the theme you are recording in and leave it — switching mid-take reads as a
  glitch, unless you are deliberately showing the toggle at the end.
- Have `backend/demos/demo-tr.json` in place. If the live debate stalls on a rate
  limit mid-recording, restart the take with the recorded debate instead: it plays
  down the same stream and looks identical apart from the honest "recorded replay"
  label.
- Record a fresh recording if you want a different claim or language:
  `MAX_DEBATE_ROUNDS=5 python -m app.record my-demo "Your claim."`

## 0:00–0:20 — the problem, in one sentence

> "Ask any AI assistant whether your plan is good and it will find reasons it is
> good. That makes it useless for the one moment you actually need help: deciding
> something. So I built one that is structurally incapable of agreeing with you."

Type a claim you believe and hit start. Do not explain the UI.

## 0:20–1:10 — the debate, while it types

Point at what is happening, not at the layout:

- Two agents, assigned sides, **arguing at each other** — quoting the other's exact
  phrase and going after it. Show one card where a side concedes a point; that is
  the part nobody expects.
- Both openings are written blind, so neither can react to the other. Round 2 is
  rebuttal only — introducing a new argument of your own is forbidden.
- Round 3 is cross examination: one question each, and the answer has to lead with
  the answer.

## 1:10–1:50 — the two things that make it not a toy

**The referee.** Scroll to a referee note. "Nobody decided this debate would be six
rounds. After every round a referee reads the transcript and asks one question: is
this still going somewhere? If it is, it names the exact tension still open, and that
sentence becomes the next round's instruction. A debate that resolves closes in four
rounds. One where neither side gives way runs to ten."

**The bench.** Scroll to *From the Bench*. "Before closing statements the judge gets
one question of its own — and it is told to ask only when something load-bearing has
gone undefended. Both sides have to answer it, and a dodge to the judge's face costs
more than a dodge to the opponent."

## 1:50–2:30 — the verdict, and arguing back

Show the scores. Say the line that matters:

> "It is not scoring who is right. It is scoring who argued better — a debater who
> defends a false claim skilfully beats one who defends a true claim badly."

Then type a counter-argument into **Not convinced?** and send it.

> "This is where every product like this collapses into flattery. So both sides have
> to answer *me* specifically, the judge is told my argument carries no authority just
> because I started the debate — and it is told my argument may still legitimately
> move the verdict if it is actually strong."

## 2:30–3:00 — close

- **Language**: no language setting. It argues in the language of the claim, verdict
  included. Show a claim in a second language if you have a recording of one.
- **Under the hood**, in one breath: FastAPI, server-sent events, one model behind
  four different system prompts, structured outputs for the verdict, no database.
  Provider-agnostic — two adapters, and the debate protocol does not know which one
  it is talking to.
- Last line back to the opening: *"Most assistants tell you what you want to hear.
  This one makes you earn it."*

## Things not to do on camera

- Do not read the transcript aloud. The viewer can read faster than you can talk.
- Do not tour the settings. One theme click at the end, if at all.
- Do not apologise for the model's rate limits. If it stalls, cut to the replay.
