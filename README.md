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

**It argues in whatever language you write in.** There is no language setting and no
translation step: every agent is instructed to argue in the language of the claim,
the way that language is actually spoken in an argument rather than as translated
textbook prose, and the referee and the judge answer in it too. Submit in English
and you get English; submit in Turkish, Spanish or Japanese and the whole debate,
including the verdict, comes back in that language.

## How the debate is structured

| Round | What happens |
| --- | --- |
| 1 — Opening Arguments | Both sides state their strongest case, neither able to see the other's. |
| 2 — Rebuttal | Each side must attack the opponent's opening. Introducing a new standalone argument is forbidden. |
| 3 — Cross Examination | Each side asks the opponent exactly one question. The opponent must answer it directly, first sentence first. |
| 4+ — Open Clash | Only if the referee says the disagreement is still live. Both sides get another turn, aimed at the one specific tension the referee named. Repeats until it is settled or the round cap is hit. |
| From the Bench | Optional. Before the closing statements the judge may put one question to a side, or to both, and they have to answer it. |
| Last Word | Closing statements, whenever the fight actually ends. |
| Verdict | The judge scores both sides 0–100 and names the strongest argument, the weakest argument, and the question neither side settled. |
| Challenge | Optional, and repeatable. You argue back against the verdict; both sides must answer *you*, then the debate is judged again with your argument in the transcript. |

**The length is not fixed, and that is the point.** After cross examination a
referee reads the transcript and answers one question: is this still going
somewhere? It is told to say no when the last two rounds were restatements with
fresher adjectives, and yes when a question is still hanging, when one side has
just landed something the other has not answered, or when the disagreement has
moved onto a sharper point — in which case it names that exact tension in one
sentence, and that sentence becomes the instruction for the next round. A debate
that genuinely resolves closes in four rounds; one where neither side will give
way runs to ten. The referee's call is shown in the transcript, so the reader can
see why it kept going.

Thirteen model calls for the shortest debate: ten turns, one referee check, one
bench check, one verdict. Every extra round adds two turns and one more referee check, so the
ten-round ceiling is 29. A challenge round is three more.

Rounds 1, 2 and the last word are *simultaneous* — neither side may react to the
other — enforced by controlling what transcript each side is shown, not by firing
the calls at the same time. Clash rounds are the opposite: the second speaker must
see what was just said, because answering it is the whole instruction. Turns are
always produced one at a time, so the stream reads the way an exchange reads.

## What makes it adversarial rather than decorative

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

**They argue like people, not like documents.** Two agents writing in the same
register produce parallel monologues, and a reader cannot tell that from two
opinion generators sharing a page. So the debaters are given distinct
temperaments — the prosecutor impatient and forensic, the defender dry and
sardonic — told to address each other as "you", to quote the exact phrase they are
attacking, and to be openly rude about a bad argument. Sarcasm and contempt for a
manoeuvre are allowed; slurs, identity-based insults and any attack on the person
who submitted the claim are not. The connective tissue of essay prose
("Furthermore", "My opponent argues that", "While it is true that") is banned
outright, along with opening a turn by summarising what the other side said —
which is the single biggest reason transcripts read as robotic. The judge is told
in turn that heat scores nothing by itself: a cutting phrase earns points only
when there is an argument inside it.

**The judge is not a spectator.** Before the closing statements it gets one
question — at a side, or at both — and it is told to ask only when something
load-bearing has gone undefended, an evasion went uncalled, or a distinction
nobody drew would decide the whole thing; otherwise to stay quiet, which is the
right answer more often than not. The debaters are told this is the one person in
the room they cannot out-talk, and the judge is told that a dodge to its face
costs more than a dodge to the opponent. It is the cheapest way to stop both sides
quietly agreeing to leave the weak premise alone.

**Arguing back does not buy agreement.** The challenge round is the obvious place
for the whole thing to collapse into flattery, so it is the most constrained turn
in the protocol: both sides are told not to defer to you because you are the one
asking, and the judge is told to score only the two debaters, that your argument
carries no authority from having started the debate — and that it may still
legitimately move the verdict if it is genuinely strong.

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

### One service, one URL

For anything that is not local development, the API serves the built frontend, so
the whole thing is a single process on a single port and there is no CORS to
configure:

```bash
cd frontend && npm run build          # writes frontend/dist
cd ../backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8123
```

Then open `http://127.0.0.1:8123`. Set `STATIC_DIR` if the build lives somewhere
else; if there is no build, the same process runs API-only.

### Deploying it

```bash
docker build -t debate-engine .
docker run -p 8123:8123 -e MODEL_API_KEY=... debate-engine
```

The [Dockerfile](Dockerfile) builds the UI with Node and runs it from Python, and
honours `$PORT`, so Render, Railway and Fly all take it unchanged;
[render.yaml](render.yaml) is a ready service definition. The key is not baked into
the image — set it in the host's dashboard. **Without a key the deployment still
works**: it serves the UI and the recorded debates, and live debates return `503`
with an explanation. That is deliberate, and it is what makes the hosted link safe
to hand to someone.

## Configuration

Set in `backend/.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MODEL_PROVIDER` | `mistral` | Which adapter to use: `mistral` or `anthropic`. |
| `MODEL_API_KEY` | — | Required. `MISTRAL_API_KEY` / `ANTHROPIC_API_KEY` are accepted as fallbacks. |
| `MODEL_API_KEYS` | — | Optional, comma-separated. The adapter rotates to the next key when one starts refusing. |
| `MODEL_NAME` | provider default | `mistral-large-latest` or `claude-opus-5`. |
| `DEBATER_EFFORT` | `medium` | Reasoning effort for the two debaters. Anthropic only. |
| `JUDGE_EFFORT` | `high` | Reasoning effort for the judge, which does the hardest work. Anthropic only. |
| `REQUEST_MIN_INTERVAL` | provider default | Seconds between provider calls (`mistral` 6, `anthropic` 0). |
| `MAX_DEBATE_ROUNDS` | `10` | Ceiling on rounds (4–12). The floor is four and structural. Lower it for a fast demo. |
| `TURN_LENGTH_HINT` | `70 to 150 words` | Turn length, injected into the debaters' rules. The biggest lever on how long a run takes. |
| `STATIC_DIR` | `frontend/dist` | Built frontend to serve. Missing means API-only. |
| `REPLAY_GAP_SECONDS` | `0.7` | Pause between events when replaying a recorded debate. |
| `CORS_ORIGINS` | localhost:5173 | Only needed if you serve the frontend from another origin. |

The three agents are one model driven by three different system prompts, so
changing `MODEL_NAME` changes all of them together.

### Providers

Everything provider-specific lives in [`providers.py`](backend/app/providers.py);
the engine only ever asks for "given a system prompt and a user message, return
text", streaming or not.

The two adapters are not equivalent, and the differences are handled there rather
than leaking into the protocol: Anthropic supports the `effort` control and native
structured outputs for the verdict, while Mistral has no effort control and only
schema-free JSON mode, so the verdict's required keys are appended to the judge's
prompt instead. Rate limiting also lives in the adapter, because free tiers need
pacing that the debate protocol should not have to know about — `mistral` defaults
to one call every 6 seconds, which is roughly what its free tier tolerates once a
long debate is making twenty-plus calls.

Keys are a ring rather than a single value. A free tier is a quota, and a quota runs
out in the middle of a debate — so when a key starts returning 429 or is rejected
outright, the adapter moves to the next one and retries immediately, because a fresh
key answers now where an exhausted one would cost thirty seconds of backoff for the
same refusal. With one key configured there is nowhere to rotate to and the backoff
behaviour is exactly as before.

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

Server-sent events carrying the same debate as it is produced, token by token.
The UI uses this one — a full debate takes long enough that a blank screen would
be the wrong experience.

| Event | Payload |
| --- | --- |
| `session` | `session_id`, `claim`. The id is what a challenge is posted against. |
| `round_start` | `number`, `name` |
| `status` | `message`, for the gaps where nothing is streaming (the judge, mainly) |
| `turn_start` | `round`, `round_name`, `speaker`, `kind` |
| `turn_delta` | `text` — one fragment of the turn being written |
| `turn_end` | the complete `Turn` |
| `referee` | `resolved`, `tension`, `note`, `rounds_left` — why the debate continues or stops |
| `verdict` | the verdict object |
| `error` | `message`, plus `recoverable`: a refused claim can be rephrased, a dead provider cannot |
| `done` | — |

### `GET /api/debate/challenge?session=...&argument=...`

Argues back against a verdict, on the same event stream. The user's argument is
emitted as a `turn_end` (nothing was streamed for it), both sides answer it, and a
fresh `verdict` follows. Repeatable: each challenge becomes round 5, 6, 7 …

Debates are kept in memory only — the last 200 — so a challenge returns `404`
once its debate has aged out, and everything is gone on restart. A debate is only
useful while the person who started it is still looking at it.

### `GET /api/demos` and `GET /api/debate/replay?name=...`

A recorded debate, replayed down the same event stream as a live one. No model key,
no network calls, no second code path in the UI — the client cannot tell the
difference, except that the `session` event carries `recorded: true` and the header
says so.

This is not decoration. A debate is twenty-odd model calls over several minutes, and
the two things most likely to fail when you finally show it to someone are a
rate-limited free tier and a conference network. A recording takes both off the
critical path, and it cannot fake anything: recordings are only ever produced by an
actual run of the engine.

```bash
cd backend
MAX_DEBATE_ROUNDS=5 ./.venv/Scripts/python.exe -m app.record demo-tr "Yapay zeka yazilimcilarin yerini alacak."
```

The recording lands in `backend/demos/` and shows up on the landing page. A
challenge round after a replay runs live if a key is configured.

### `GET /api/health`

Reports whether a model key is configured, and which provider and model are live.

## Tests

```bash
cd backend
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./.venv/Scripts/python.exe -m pytest
```

Twenty-three tests, no network and no API key: every one runs against a stub
provider, so the suite covers the parts that are actually easy to break — that a
settled debate closes in four rounds and a live one earns more, that the round cap
holds when neither side gives way, that the bench question is optional and can
target one side, that asterisks are stripped while emoji survive, that a verdict
contradicting its own scores is reconciled, that a failing referee closes the debate
instead of breaking it, and that replay works with no engine configured at all.

## Design notes

- **Scores are clamped and reconciled server-side.** A verdict naming a winner
  whose score is lower than the loser's would read as a bug, so it is corrected
  to match the scores; equal scores become a draw.
- **The judge uses structured outputs**, so the verdict is a validated object
  rather than prose that has to be parsed hopefully.
- **Thinking is never sent to the client.** Only the turn text is streamed; the
  gaps get a short status line instead, so the reader gets progress without a
  chain-of-thought dump.
- **Asterisks are stripped, not trusted.** The debaters are told to carry emphasis
  in word order rather than markdown, and a model obeys that most of the time —
  which is not good enough for something that shows up as literal `*` in the middle
  of a sentence. So the character is deleted from every fragment, every verdict
  field and the judge's question on the way out. It can never carry meaning here,
  because the debaters are speaking. Emoji are allowed, at most one per turn.
- **The client paces the typing.** The model writes a paragraph faster than anyone
  reads one, so raw SSE fragments land in bursts that look like text being pasted.
  Fragments go into a queue instead and a clock releases them a few characters at a
  time, with short pauses at sentence ends, speeding up only when the display is
  several turns behind. The queue also carries the non-text events, which is what
  keeps the order honest: a verdict cannot appear while the last word is still
  being typed.
- **The typing sound is synthesised, not sampled.** A keystroke is a filtered noise
  burst plus a low thump, built in WebAudio — no audio files to ship, and every
  keystroke can jitter its own filter, decay and level so a long turn does not turn
  into a metronome. It is off in one click and the choice is remembered.
- **Theme is three-state.** Light, dark, or following the system, persisted. The
  components carry no `dark:` variants: Tailwind's colour utilities point at CSS
  variables and only those variables are redefined per theme.
- **A dropped connection ends the debate.** `EventSource` would happily reconnect,
  but a debate cannot be resumed halfway, so the client closes the stream as soon
  as the server signals `done` or `error`. On the server side, a disconnected
  client abandons the run rather than burning the remaining calls.
- **No database, no accounts, no vector store.** The only state that outlives a
  request is the transcript a challenge round needs, and it lives in a bounded
  in-memory cache.

## Licence

MIT — see [LICENSE](LICENSE).
