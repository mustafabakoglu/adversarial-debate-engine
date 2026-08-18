"""Model provider adapters.

The debate engine only needs one operation — "given a system prompt and a user
message, return text" — so each provider is a thin adapter around that, and the
provider is chosen with the MODEL_PROVIDER environment variable.

Two adapters ship:

* ``anthropic`` uses the official Anthropic SDK, with the ``effort`` control and
  native structured outputs for the judge.
* ``mistral`` talks to Mistral's chat-completions endpoint over HTTP. It has no
  effort control, and its JSON mode is schema-free, so the required keys are
  appended to the prompt instead.

Anything provider-specific belongs in here; the engine stays agnostic.

Rate limiting lives here too, for a reason worth stating: the engine expresses
*logical* concurrency (both opening statements are written without seeing each
other, so they are issued together), while the provider decides what the network
will actually tolerate. On a free tier that means serialising the calls. Keeping
the two concerns apart means the debate protocol does not have to change when the
quota does.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Protocol

import httpx

from .errors import DebateError, ModelRefusal, ProviderConfigError

logger = logging.getLogger(__name__)

# Free tiers rate-limit aggressively, so transient failures are retried with a
# generous backoff rather than surfaced.
MAX_ATTEMPTS = 6
BACKOFF_SECONDS = 3.0
MAX_BACKOFF_SECONDS = 30.0
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}

DEFAULT_MODELS = {
    "anthropic": "claude-opus-5",
    "mistral": "mistral-large-latest",
}

# Measured against Mistral's free tier. 1.3s produced sustained 429s; 4s still did
# once the referee started adding calls to longer debates, so the default is
# deliberately conservative - a stall in backoff costs more than the pacing does.
# Paid tiers can lower it with REQUEST_MIN_INTERVAL.
DEFAULT_MIN_INTERVAL = {
    "anthropic": 0.0,
    "mistral": 6.0,
}


class Provider(Protocol):
    name: str
    model: str

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: str | None = None,
        json_schema: dict | None = None,
    ) -> str: ...

    def stream(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield text fragments as the model produces them."""
        ...

    async def close(self) -> None: ...


class RateLimiter:
    """Enforce a minimum interval between requests, across all callers."""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = max(0.0, min_interval)
        self._lock = asyncio.Lock()
        self._last_start = 0.0

    async def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        # The lock is held across the sleep so concurrent callers queue up rather
        # than all measuring the same stale timestamp and firing together.
        async with self._lock:
            loop = asyncio.get_running_loop()
            wait_for = self._min_interval - (loop.time() - self._last_start)
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            self._last_start = loop.time()


def _backoff_delay(attempt: int, retry_after: float | None) -> float:
    if retry_after is not None:
        return min(MAX_BACKOFF_SECONDS, max(1.0, retry_after))
    return min(MAX_BACKOFF_SECONDS, BACKOFF_SECONDS * (2 ** (attempt - 1)))


def _parse_retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after") or response.headers.get("ratelimit-reset")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _required_keys_instruction(schema: dict) -> str:
    """Describe a JSON schema in prose, for providers without schema enforcement."""
    properties: dict[str, Any] = schema.get("properties", {})
    lines = []
    for key, spec in properties.items():
        kind = spec.get("type", "string")
        if spec.get("enum"):
            kind = "one of " + ", ".join(json.dumps(value) for value in spec["enum"])
        description = spec.get("description", "")
        lines.append(f'- "{key}" ({kind}): {description}'.rstrip())
    return (
        "Return a single JSON object and nothing else. No prose, no code fence.\n"
        "It must contain exactly these keys:\n" + "\n".join(lines)
    )


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, min_interval: float) -> None:
        from anthropic import AsyncAnthropic

        self.model = model
        self._client = AsyncAnthropic(api_key=api_key)
        self._limiter = RateLimiter(min_interval)
        # Older SDK releases do not accept output_config; detected on first use.
        self._supports_output_config = True

    async def close(self) -> None:
        await self._client.close()

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: str | None = None,
        json_schema: dict | None = None,
    ) -> str:
        output_config: dict[str, Any] = {}
        if effort:
            output_config["effort"] = effort
        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}

        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if output_config:
            params["output_config"] = output_config

        message = await self._call(params)

        if message.stop_reason == "refusal":
            raise ModelRefusal(
                "The model declined to argue this claim. Try phrasing it as a debatable "
                "proposition rather than a request about a restricted topic."
            )
        text = "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        ).strip()
        if not text:
            raise DebateError("the model returned an empty response")
        return text

    async def stream(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: str | None = None,
    ) -> AsyncIterator[str]:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if effort and self._supports_output_config:
            params["output_config"] = {"effort": effort}

        await self._limiter.acquire()
        async with self._client.messages.stream(**params) as stream:
            async for fragment in stream.text_stream:
                if fragment:
                    yield fragment
            final = await stream.get_final_message()
            if final.stop_reason == "refusal":
                raise ModelRefusal(
                    "The model declined to argue this claim. Try phrasing it as a debatable "
                    "proposition rather than a request about a restricted topic."
                )

    async def _call(self, params: dict[str, Any]) -> Any:
        import anthropic

        if not self._supports_output_config:
            params.pop("output_config", None)

        last: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            await self._limiter.acquire()
            try:
                return await self._client.messages.create(**params)
            except TypeError as exc:
                if "output_config" not in params or "output_config" not in str(exc):
                    raise
                logger.warning("this anthropic SDK rejects output_config; continuing without it")
                self._supports_output_config = False
                params.pop("output_config", None)
            except (
                anthropic.RateLimitError,
                anthropic.InternalServerError,
                anthropic.APIConnectionError,
            ) as exc:
                last = exc
                if attempt == MAX_ATTEMPTS:
                    break
                delay = _backoff_delay(attempt, None)
                logger.warning(
                    "anthropic call failed (%s); retrying in %.0fs", type(exc).__name__, delay
                )
                await asyncio.sleep(delay)
        raise DebateError(f"the model provider kept failing: {last}")


class MistralProvider:
    name = "mistral"
    endpoint = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, min_interval: float) -> None:
        self.model = model
        self._limiter = RateLimiter(min_interval)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0, connect=15.0),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: str | None = None,
        json_schema: dict | None = None,
    ) -> str:
        # Mistral has no effort control; depth is fixed by model choice.
        del effort

        system_prompt = system
        payload: dict[str, Any] = {"model": self.model, "max_tokens": max_tokens}
        if json_schema is not None:
            # JSON mode here is schema-free, so the contract goes in the prompt.
            system_prompt = system + "\n\n" + _required_keys_instruction(json_schema)
            payload["response_format"] = {"type": "json_object"}

        payload["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
        ]

        data = await self._call(payload)

        choices = data.get("choices") or []
        if not choices:
            raise DebateError("the provider returned no choices")
        choice = choices[0]
        text = ((choice.get("message") or {}).get("content") or "").strip()

        if not text:
            if choice.get("finish_reason") == "content_filter":
                raise ModelRefusal(
                    "The provider's content filter declined this claim. Try phrasing it as a "
                    "debatable proposition."
                )
            raise DebateError("the model returned an empty response")
        return text

    async def stream(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: str | None = None,
    ) -> AsyncIterator[str]:
        del effort  # no equivalent control on this provider

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        # Retry only covers the handshake. Once fragments have been delivered the
        # turn cannot be restarted without duplicating text on screen, so a
        # mid-stream failure is surfaced instead.
        last_detail = "unknown error"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            await self._limiter.acquire()
            async with self._client.stream("POST", self.endpoint, json=payload) as response:
                if response.status_code == 200:
                    async for fragment in self._read_sse(response):
                        yield fragment
                    return

                body = (await response.aread()).decode("utf-8", "replace")
                if response.status_code == 401:
                    raise DebateError(
                        "The provider rejected the API key (401). Check MODEL_API_KEY in "
                        "backend/.env."
                    )
                last_detail = f"HTTP {response.status_code}: {body[:200]}"
                if response.status_code not in RETRY_STATUS:
                    raise DebateError(f"the provider rejected the request: {last_detail}")
                retry_after = _parse_retry_after(response)

            if attempt == MAX_ATTEMPTS:
                break
            delay = _backoff_delay(attempt, retry_after)
            logger.warning("mistral stream failed (%s); retrying in %.0fs", last_detail, delay)
            await asyncio.sleep(delay)

        raise DebateError(
            "The provider kept refusing requests, most likely a free-tier rate limit. "
            f"Last error: {last_detail}"
        )

    @staticmethod
    async def _read_sse(response: httpx.Response) -> AsyncIterator[str]:
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            for choice in chunk.get("choices") or []:
                if choice.get("finish_reason") == "content_filter":
                    raise ModelRefusal(
                        "The provider's content filter declined this claim. Try phrasing it "
                        "as a debatable proposition."
                    )
                fragment = (choice.get("delta") or {}).get("content")
                if fragment:
                    yield fragment

    async def _call(self, payload: dict[str, Any]) -> dict:
        last_detail = "unknown error"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            await self._limiter.acquire()
            retry_after: float | None = None
            try:
                response = await self._client.post(self.endpoint, json=payload)
            except httpx.HTTPError as exc:
                last_detail = str(exc)
            else:
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 401:
                    raise DebateError(
                        "The provider rejected the API key (401). Check MODEL_API_KEY in "
                        "backend/.env."
                    )
                last_detail = f"HTTP {response.status_code}: {response.text[:200]}"
                if response.status_code not in RETRY_STATUS:
                    raise DebateError(f"the provider rejected the request: {last_detail}")
                retry_after = _parse_retry_after(response)

            if attempt == MAX_ATTEMPTS:
                break
            delay = _backoff_delay(attempt, retry_after)
            logger.warning("mistral call failed (%s); retrying in %.0fs", last_detail, delay)
            await asyncio.sleep(delay)

        raise DebateError(
            "The provider kept refusing requests, most likely a free-tier rate limit. "
            f"Last error: {last_detail}"
        )


def build_provider(
    provider: str, api_key: str, model: str | None, min_interval: float | None = None
) -> Provider:
    """Construct the configured provider adapter."""
    key = provider.strip().lower()
    if key not in DEFAULT_MODELS:
        raise ProviderConfigError(
            f"unknown MODEL_PROVIDER {provider!r}; supported values are 'anthropic' and 'mistral'"
        )

    resolved_model = (model or "").strip() or DEFAULT_MODELS[key]
    interval = DEFAULT_MIN_INTERVAL[key] if min_interval is None else min_interval

    if key == "anthropic":
        return AnthropicProvider(api_key, resolved_model, interval)
    return MistralProvider(api_key, resolved_model, interval)
