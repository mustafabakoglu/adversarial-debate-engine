# Devpost submission — ready to paste

Pixel Forge AI Hackathon. Deadline 22 August 2026, 21:30 IST.

## Project name

Devil's Advocate

## Tagline (one line)

Two AI agents argue opposite sides of your claim until a referee rules the disagreement
finished — and a judge scores the argument, not the answer.

## Links

| Field | Value |
| --- | --- |
| Hosted project URL | https://adversarial-debate-engine.onrender.com/ |
| Backup, needs no key or server | https://mustafabakoglu.github.io/adversarial-debate-engine/ |
| Public repository | https://github.com/mustafabakoglu/adversarial-debate-engine |
| Licence | MIT, in the repository |
| Demo video | upload `media/demo.mp4` (2:57) to YouTube, paste the link |

## The problem

Ask any assistant whether your plan is good and it will find reasons it is good. Frame a
question and it accepts your framing. That makes the whole category useless for the one
moment you actually needed help: deciding something. The failure is not a knowledge gap,
it is a structural bias towards agreement — and you cannot prompt your way out of it,
because the thing you would be asking is the thing that agrees with you.

## What it does

You submit a claim. Two agents are assigned opposite sides and neither chooses which:

1. **Opening** — both written blind, so neither can react to the other.
2. **Rebuttal** — each side must take apart what the other actually said, quoting the exact
   phrase. Introducing a new argument of your own is forbidden.
3. **Cross examination** — one question each, and the answer has to lead with the answer.
4. **Open clash, 0 to 6 rounds** — only while a referee says the disagreement is still
   live. It names the exact tension left open, and that sentence becomes the next round's
   instruction.
5. **From the bench** — the judge may put one question to a side, or to both, and is told
   to ask only when something load-bearing has gone undefended.
6. **Last word**, then a **verdict**: both sides scored 0–100, a winner, a confidence, the
   strongest and weakest arguments quoted, and the question neither side settled.
7. **Challenge** — you argue back. Both sides must answer *you*, and the debate is judged
   again. The judge is told your argument carries no authority from you having started the
   debate, and that it may still legitimately move the verdict.

There is no language setting: it argues in the language of your claim, verdict included.

## How AI is integrated

One model behind four different system prompts, each with a different job:

- **Two debaters** stream their turns token by token over server-sent events. The prompts
  carry the product logic: distinct temperaments so the two do not sound alike, a ban on
  the essay-prose connectives that make transcripts read as machine output, a rule that
  every turn after the opening must quote and attack the opponent's actual words, and a
  reward for conceding a point that cannot be answered.
- **A referee** decides after every round whether the argument still has anywhere to go,
  as a structured output — so the debate's length is model-decided within bounds, not a
  constant in the code.
- **A judge** asks its own question before the closing statements, then returns the verdict
  as a validated object rather than prose that has to be parsed hopefully.

Two provider adapters (Anthropic, Mistral) sit behind one interface; the debate protocol
never knows which it is talking to. API keys are a rotating ring, so an exhausted free tier
moves to the next key instead of waiting out a limit it cannot get back.

## What makes it adversarial rather than decorative

- The rebuttal round is **constrained**, not suggested, so the transcript is a chain rather
  than two parallel monologues.
- Concession is **rewarded** by the judge, which is what stops both sides bluffing.
- The judge scores **argumentation, not truth**: defending a false claim skilfully beats
  defending a true one badly. It is also told that a claim having been submitted is not
  evidence for it, and that attacking is not inherently stronger than defending.
- The challenge round is the obvious place for the whole thing to collapse into flattery,
  so it is the most constrained turn in the protocol.

## Built with

Python · FastAPI · server-sent events · Pydantic · structured outputs · Anthropic and
Mistral APIs · React 19 · TypeScript · Vite · Tailwind CSS v4 · WebAudio · Docker ·
GitHub Actions · pytest

## Try it in thirty seconds

1. Open the hosted link and press a recorded debate — it starts instantly and is a real
   run of the engine, replayed down the same event stream.
2. Or submit your own claim and watch it argued live. It takes two or three minutes,
   because every turn is written while you watch.
3. When the verdict lands, argue back in **Not convinced?** and watch both sides have to
   answer you.

## Notes for judging

- **Thirty tests**, no network and no API key required: `cd backend && pytest`.
- The recorded debates in `backend/demos/` can only be produced by an actual run of the
  engine, and the page labels a replay as a replay.
- `media/` contains the demo video **and the scripts that render it**, so the film is
  reproducible rather than a dead artefact.
