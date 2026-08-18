"""Key rotation: what happens when a free tier's quota runs out mid-debate."""

from __future__ import annotations

import httpx
import pytest

from app.errors import DebateError, ProviderConfigError
from app.providers import KeyRing, MistralProvider, build_provider


def keys_used(requests: list[httpx.Request]) -> list[str]:
    return [request.headers["authorization"].removeprefix("Bearer ") for request in requests]


def provider_with(handler, keys: list[str]) -> MistralProvider:
    """A Mistral adapter whose transport is a stub, so nothing leaves the machine."""
    provider = MistralProvider(keys, "stub-model", 0.0)
    provider._client = httpx.AsyncClient(  # noqa: SLF001 - the seam this test needs
        transport=httpx.MockTransport(handler),
        headers={"Content-Type": "application/json"},
    )
    return provider


def reply(text: str) -> dict:
    return {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}


def test_key_ring_needs_at_least_one_key():
    with pytest.raises(ProviderConfigError):
        KeyRing([" ", ""])


def test_key_ring_ignores_duplicates_of_nothing_and_cycles():
    ring = KeyRing(["a", "b"])
    assert (ring.current, ring.position) == ("a", 1)
    assert ring.rotate() is True
    assert (ring.current, ring.position) == ("b", 2)
    assert ring.rotate() is True
    assert ring.current == "a"


def test_a_single_key_has_nowhere_to_rotate():
    assert KeyRing(["only"]).rotate() is False


@pytest.mark.asyncio
async def test_exhausted_key_rotates_instead_of_waiting():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.headers["authorization"].endswith("spent"):
            return httpx.Response(429, json={"message": "Rate limit exceeded"})
        return httpx.Response(200, json=reply("argument"))

    provider = provider_with(handler, ["spent", "fresh"])
    try:
        text = await provider.complete(system="s", user="u", max_tokens=10)
    finally:
        await provider.close()

    assert text == "argument"
    # One try on the exhausted key, then straight onto the fresh one - no backoff.
    assert keys_used(seen) == ["spent", "fresh"]


@pytest.mark.asyncio
async def test_rejected_key_rotates_and_the_last_one_is_reported():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    provider = provider_with(handler, ["dead", "also-dead"])
    try:
        with pytest.raises(DebateError, match="401"):
            await provider.complete(system="s", user="u", max_tokens=10)
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_streaming_rotates_on_a_spent_key():
    seen: list[httpx.Request] = []
    body = 'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n'

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.headers["authorization"].endswith("spent"):
            return httpx.Response(429, json={"message": "Rate limit exceeded"})
        return httpx.Response(200, text=body)

    provider = provider_with(handler, ["spent", "fresh"])
    try:
        fragments = [
            fragment async for fragment in provider.stream(system="s", user="u", max_tokens=10)
        ]
    finally:
        await provider.close()

    assert fragments == ["hello"]
    assert keys_used(seen) == ["spent", "fresh"]


def test_build_provider_accepts_one_key_or_several():
    single = build_provider("mistral", "one", None)
    several = build_provider("mistral", ["one", "two"], None)
    assert len(single._ring) == 1  # noqa: SLF001
    assert len(several._ring) == 2  # noqa: SLF001

    with pytest.raises(ProviderConfigError):
        build_provider("gpt-9", "one", None)
