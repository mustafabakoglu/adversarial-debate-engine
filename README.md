# Adversarial AI Debate Engine

Most AI assistants agree with you. Ask one whether your plan is good and it will
find reasons it is good; frame a question and it will accept your framing. That
makes them poor tools for the moment you actually need help — deciding something.

This engine is built to argue **against** you, and to be structurally unable to
do otherwise.

You submit a claim. Two agents are assigned opposing sides and must engage each
other's actual words, not just state their own case. A third agent scores the
argumentation — explicitly **not** whether the claim is true, and explicitly not
in favour of the person who submitted it.

## How the debate is structured

| Round | What happens |
| --- | --- |
| 1 — Opening Arguments | Both sides state their strongest case. Run in parallel, so neither can react to the other. |
| 2 — Rebuttal | Each side must attack the opponent's opening. Introducing a new standalone argument is forbidden. |
| 3 — Cross Examination | Each side asks the opponent exactly one question. The opponent must answer it directly, first sentence first. |
| 4 — Final Arguments | Each side says what survived the exchange — including on its own side. |
| Verdict | The judge scores both sides 0–100 and names the strongest argument, the weakest argument, and the question neither side settled. |

Eleven model calls per debate. Rounds 1, 2 and 4 issue their two turns
concurrently; round 3 is strictly sequential because the answer depends on the
question.

## The three things that make it adversarial rather than decorative

**The rebuttal round is constrained, not suggested.** A debate where both sides
monologue past each other is two opinion generators in a shared page. Round 2
requires each side to restate the specific claim it is attacking before
attacking it, and forbids new arguments — so the transcript is a chain rather
than two parallel lists.

**Concession is rewarded, not penalised.** Both debaters are instructed to admit
a point they cannot answer and explain what survives without it, and the judge
scores that above pretending not to hear it. Without this, both sides bluff and
the transcript stops being informative.

**The judge is scoring argumentation, not truth.** A debater who defends a false
claim well outscores one who defends a true claim badly. The judge is also told
that the claim having been submitted is not evidence for it, and that attacking
is not inherently stronger than defending — the two failure modes that would
quietly turn the verdict back into flattery.

## Running it

Two processes: a FastAPI backend and a Vite dev server.

### Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS / Linux

cp .env.example .env        # then set MODEL_API_KEY in .env
./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8123 --reload
```

A key is required for debates to run. Without one the API stays up and returns
`503` with an explanatory message, and `GET /api/health` reports
`"configured": false`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed URL. The dev server proxies `/api` to `127.0.0.1:8123`, so no
CORS configuration is needed for local development.

## Configuration

Set in `backend/.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MODEL_API_KEY` | — | Required. `ANTHROPIC_API_KEY` is accepted as a fallback. |
| `MODEL_NAME` | `claude-opus-5` | Model used for all three agents. |
| `DEBATER_EFFORT` | `medium` | Reasoning effort for the two debaters. |
| `JUDGE_EFFORT` | `high` | Reasoning effort for the judge, which does the hardest work. |
| `CORS_ORIGINS` | localhost:5173 | Only needed if you serve the frontend from another origin. |

The three agents are one model driven by three different system prompts, so
changing `MODEL_NAME` changes all of them together.

## API

### `POST /api/debate`

Runs the whole debate and returns it in one response. Simple to consume, but the
caller waits for all eleven calls.

```json
{ "claim": "Remote work is more productive than working from an office." }
```

```json
{
  "claim": "...",
  "rounds": [{ "number": 1, "name": "Opening Arguments", "turns": [] }],
  "prosecutor_score": 78,
  "defender_score": 64,
  "winner": "prosecutor",
  "confidence": 82,
  "reasoning": "...",
  "strongest_argument": "...",
  "weakest_argument": "...",
  "unresolved_question": "..."
}
```

### `GET /api/debate/stream?claim=...`

Server-sent events carrying the same debate as it is produced: `round_start`,
`status`, `turn`, `verdict`, `done`, `error`. The UI uses this one — a full
debate takes long enough that a blank screen would be the wrong experience.

### `GET /api/health`

Reports whether a model key is configured.

## Design notes

- **Scores are clamped and reconciled server-side.** A verdict naming a winner
  whose score is lower than the loser's would read as a bug, so it is corrected
  to match the scores; equal scores become a draw.
- **The judge uses structured outputs**, so the verdict is a validated object
  rather than prose that has to be parsed hopefully.
- **Thinking is never sent to the client.** The UI shows short status lines
  (`Analyzing opponent's argument...`) instead, so the reader gets progress
  without a chain-of-thought dump.
- **No database, no accounts, no vector store.** A debate is a single request.

## Licence

MIT — see [LICENSE](LICENSE).
