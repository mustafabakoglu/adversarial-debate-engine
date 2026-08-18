"""FastAPI application exposing the debate engine."""

from __future__ import annotations

import json
import logging
import os
import secrets
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import config, replay
from .engine import DebateEngine, group_rounds
from .errors import DebateError, ModelRefusal, ProviderConfigError
from .providers import build_provider
from .schemas import ChallengeRequest, DebateRequest, DebateResponse, Turn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_MISSING_KEY_MESSAGE = (
    "No model API key configured. Copy backend/.env.example to backend/.env and set "
    "MODEL_API_KEY."
)


@dataclass
class Session:
    """One debate held in memory so the user can challenge its verdict.

    Deliberately not a database: a debate is only useful while the person who
    started it is still looking at it, and the challenge round is the only reason
    any state outlives a request.
    """

    claim: str
    turns: list[Turn] = field(default_factory=list)


class SessionStore:
    """Bounded, insertion-ordered session cache."""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._items: OrderedDict[str, Session] = OrderedDict()

    def create(self, claim: str) -> tuple[str, Session]:
        session_id = secrets.token_urlsafe(12)
        session = Session(claim=claim)
        self._items[session_id] = session
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
        return session_id, session

    def get(self, session_id: str) -> Session | None:
        session = self._items.get(session_id)
        if session is not None:
            self._items.move_to_end(session_id)
        return session


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine: DebateEngine | None = None
    if not config.MODEL_API_KEY:
        logger.warning(_MISSING_KEY_MESSAGE)
    else:
        try:
            provider = build_provider(
                config.MODEL_PROVIDER,
                config.MODEL_API_KEYS,
                config.MODEL_NAME,
                config.REQUEST_MIN_INTERVAL,
            )
        except ProviderConfigError as exc:
            logger.error("provider misconfigured: %s", exc)
        else:
            engine = DebateEngine(provider)
            logger.info(
                "debate engine ready (provider=%s model=%s keys=%d)",
                engine.provider_name,
                engine.model,
                len(config.MODEL_API_KEYS),
            )
    app.state.engine = engine
    app.state.sessions = SessionStore(config.MAX_SESSIONS)
    try:
        yield
    finally:
        if engine is not None:
            await engine.close()


app = FastAPI(
    title="Adversarial AI Debate Engine",
    description="Two AI agents argue opposing sides of a claim; a third judges the argumentation.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _engine(request: Request) -> DebateEngine:
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(status_code=503, detail=_MISSING_KEY_MESSAGE)
    return engine


def _validated(model_cls, **kwargs) -> object:
    try:
        return model_cls(**kwargs)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()[0]["msg"]) from exc


@app.get("/api/health")
async def health(request: Request) -> dict:
    engine: DebateEngine | None = request.app.state.engine
    return {
        "status": "ok",
        "configured": engine is not None,
        "provider": engine.provider_name if engine else config.MODEL_PROVIDER,
        "model": engine.model if engine else None,
    }


@app.post("/api/debate", response_model=DebateResponse)
async def debate(payload: DebateRequest, request: Request) -> DebateResponse:
    """Run a full debate and return it in one response."""
    engine = _engine(request)
    turns: list[Turn] = []
    verdict: dict | None = None

    try:
        async for event in engine.run(payload.claim):
            if event["type"] == "turn_end":
                turns.append(Turn(**{k: v for k, v in event.items() if k != "type"}))
            elif event["type"] == "verdict":
                verdict = {k: v for k, v in event.items() if k != "type"}
    except ModelRefusal as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DebateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if verdict is None:
        raise HTTPException(status_code=502, detail="the debate finished without a verdict")

    return DebateResponse(claim=payload.claim, rounds=group_rounds(turns), **verdict)


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _sse(payload: dict) -> str:
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


async def _pump(
    request: Request, events: AsyncIterator[dict], session: Session
) -> AsyncIterator[str]:
    """Forward engine events to the client, recording completed turns."""
    try:
        async for event in events:
            if await request.is_disconnected():
                logger.info("client disconnected; abandoning debate")
                return
            if event["type"] == "turn_end":
                session.turns.append(Turn(**{k: v for k, v in event.items() if k != "type"}))
            yield _sse(event)
    except ModelRefusal as exc:
        yield _sse({"type": "error", "message": str(exc), "recoverable": True})
    except DebateError as exc:
        logger.exception("debate failed")
        yield _sse({"type": "error", "message": str(exc), "recoverable": False})
    except Exception:  # noqa: BLE001 - surface a usable message to the UI
        logger.exception("unexpected failure during debate")
        yield _sse(
            {
                "type": "error",
                "message": "The debate failed unexpectedly. Check the server logs.",
                "recoverable": False,
            }
        )


@app.get("/api/debate/stream")
async def debate_stream(request: Request, claim: str = Query(...)) -> StreamingResponse:
    """Start a debate, emitting each turn token by token as it is produced."""
    engine = _engine(request)
    validated: DebateRequest = _validated(DebateRequest, claim=claim)  # type: ignore[assignment]
    session_id, session = request.app.state.sessions.create(validated.claim)

    async def source() -> AsyncIterator[str]:
        yield _sse({"type": "session", "session_id": session_id, "claim": session.claim})
        async for frame in _pump(request, engine.run(session.claim), session):
            yield frame

    return StreamingResponse(source(), media_type="text/event-stream; charset=utf-8", headers=_SSE_HEADERS)


@app.get("/api/debate/challenge")
async def debate_challenge(
    request: Request,
    session: str = Query(..., description="Session id from the debate stream"),
    argument: str = Query(..., description="Your counter-argument to the verdict"),
) -> StreamingResponse:
    """Argue back against a verdict; both sides must answer, then it is re-judged."""
    engine = _engine(request)
    validated: ChallengeRequest = _validated(ChallengeRequest, argument=argument)  # type: ignore[assignment]

    stored: Session | None = request.app.state.sessions.get(session)
    if stored is None:
        raise HTTPException(
            status_code=404,
            detail="That debate is no longer in memory. Start a new one to challenge a verdict.",
        )
    if not stored.turns:
        raise HTTPException(status_code=409, detail="That debate has not produced any turns yet.")

    async def source() -> AsyncIterator[str]:
        yield _sse({"type": "session", "session_id": session, "claim": stored.claim})
        events = engine.challenge(stored.claim, list(stored.turns), validated.argument)
        async for frame in _pump(request, events, stored):
            yield frame

    return StreamingResponse(source(), media_type="text/event-stream; charset=utf-8", headers=_SSE_HEADERS)



@app.get("/api/demos")
async def demos() -> dict:
    """Recorded debates available for replay."""
    return {"demos": replay.available()}


@app.get("/api/debate/replay")
async def debate_replay(
    request: Request,
    name: str = Query(..., description="Recording name from /api/demos"),
    gap: float | None = Query(None, ge=0, le=10, description="Seconds to hold between events"),
) -> StreamingResponse:
    """Replay a recorded debate down the live event stream.

    Needs no model key and makes no network calls, which is the point: it is what
    you show when the conference wifi or the free-tier quota decides otherwise. The
    session is registered as a real one, so a challenge round afterwards still runs
    live if a key is configured.
    """
    try:
        recording = replay.load(name)
    except DebateError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session_id, session = request.app.state.sessions.create(recording["claim"])

    async def source() -> AsyncIterator[str]:
        yield _sse(
            {
                "type": "session",
                "session_id": session_id,
                "claim": session.claim,
                "recorded": True,
                "recorded_at": recording.get("recorded_at", ""),
            }
        )
        async for frame in _pump(request, replay.play(recording, gap), session):
            yield frame

    return StreamingResponse(
        source(), media_type="text/event-stream; charset=utf-8", headers=_SSE_HEADERS
    )


# Serving the built frontend from the API is what makes a deployment one service and
# one URL - which is all a reviewer wants - while local development still runs the
# Vite dev server against this same API. Mounted last so it can never shadow /api.
if os.path.isdir(config.STATIC_DIR):
    app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="app")
    logger.info("serving the built frontend from %s", config.STATIC_DIR)
else:
    logger.info("no built frontend at %s; running API-only", config.STATIC_DIR)


@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()[0]["msg"]})
