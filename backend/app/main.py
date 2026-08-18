"""FastAPI application exposing the debate engine."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from . import config
from .engine import DebateEngine, DebateError, ModelRefusal, group_rounds
from .schemas import DebateRequest, DebateResponse, Turn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_MISSING_KEY_MESSAGE = (
    "No model API key configured. Copy backend/.env.example to backend/.env and set "
    "MODEL_API_KEY."
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = DebateEngine(config.MODEL_API_KEY, config.MODEL_NAME) if config.MODEL_API_KEY else None
    if engine is None:
        logger.warning(_MISSING_KEY_MESSAGE)
    else:
        logger.info("debate engine ready (model=%s)", config.MODEL_NAME)
    app.state.engine = engine
    try:
        yield
    finally:
        if engine is not None:
            await engine.close()


app = FastAPI(
    title="Adversarial AI Debate Engine",
    description="Two AI agents argue opposing sides of a claim; a third judges the argumentation.",
    version="0.1.0",
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


def _validate_claim(raw: str) -> str:
    try:
        return DebateRequest(claim=raw).claim
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()[0]["msg"]) from exc


@app.get("/api/health")
async def health(request: Request) -> dict:
    return {
        "status": "ok",
        "model": config.MODEL_NAME,
        "configured": request.app.state.engine is not None,
    }


@app.post("/api/debate", response_model=DebateResponse)
async def debate(payload: DebateRequest, request: Request) -> DebateResponse:
    """Run a full debate and return it in one response."""
    engine = _engine(request)
    turns: list[Turn] = []
    verdict: dict | None = None

    try:
        async for event in engine.run(payload.claim):
            if event["type"] == "turn":
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


@app.get("/api/debate/stream")
async def debate_stream(request: Request, claim: str = Query(...)) -> StreamingResponse:
    """Run a debate, emitting each turn as a server-sent event as it is produced."""
    engine = _engine(request)
    validated = _validate_claim(claim)

    async def event_source() -> AsyncIterator[str]:
        def frame(payload: dict) -> str:
            return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"

        yield frame({"type": "claim", "claim": validated})
        try:
            async for event in engine.run(validated):
                if await request.is_disconnected():
                    logger.info("client disconnected; abandoning debate")
                    return
                yield frame(event)
        except ModelRefusal as exc:
            yield frame({"type": "error", "message": str(exc), "recoverable": True})
        except DebateError as exc:
            logger.exception("debate failed")
            yield frame({"type": "error", "message": str(exc), "recoverable": False})
        except Exception:  # noqa: BLE001 - surface a usable message to the UI
            logger.exception("unexpected failure during debate")
            yield frame(
                {
                    "type": "error",
                    "message": "The debate failed unexpectedly. Check the server logs.",
                    "recoverable": False,
                }
            )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()[0]["msg"]})
