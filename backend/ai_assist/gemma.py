"""
Gemma 4 client — Google AI Studio.

THE ONLY PLACE GEMMA_API_KEY IS READ on Shrijib's side. Wrik's ai/client.py is
separate by design: his calls attach model_id and prompt_hash because his
outputs become immutable artifacts. Mine produce drafts a human confirms, and
forcing one abstraction over both would make the simpler case carry weight it
does not need.

TWO HARD RULES:

  1. FAILS SOFT, ALWAYS. Every function returns None on failure. Callers render
     a fallback — an empty form, a plain number — never a 500. When a judge
     asks "what happens when Gemma is down?", the answer is: "you type the
     fields yourself, which is what you'd be doing today anyway."

  2. NEVER READ os.environ AT IMPORT TIME. This repo has been bitten three
     times by that. Config is resolved lazily, inside functions.
"""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


@dataclass
class GemmaResult:
    parsed: dict | None
    text: str
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    retries: int


def _cfg() -> dict:
    return {
        "key": os.environ.get("GEMMA_API_KEY"),
        "base": os.environ.get("GEMMA_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "large": os.environ.get("GEMMA_MODEL_LARGE", "gemma-4-31b-it"),
        "vision": os.environ.get("GEMMA_MODEL_VISION", "gemma-4-12b-it"),
        "fast": os.environ.get("GEMMA_MODEL_FAST", "gemma-4-e4b-it"),
        "timeout": float(os.environ.get("GEMMA_TIMEOUT_SECONDS", "60")),
        "retries": int(os.environ.get("GEMMA_MAX_RETRIES", "3")),
    }


def is_configured() -> bool:
    return bool(_cfg()["key"])


def model_for(kind: str) -> str:
    c = _cfg()
    return {"large": c["large"], "vision": c["vision"], "fast": c["fast"]}.get(
        kind, c["fast"]
    )


async def _call(
    *,
    model: str,
    system: str,
    user: str,
    files: list[tuple[str, bytes]] | None,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> GemmaResult | None:
    cfg = _cfg()
    if not cfg["key"]:
        return None

    parts: list[dict[str, Any]] = [{"text": user}]
    for mime, raw in files or []:
        parts.append(
            {"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode()}}
        )

    body: dict[str, Any] = {
        # Gemma 4 supports a native system role — use it rather than faking a
        # preamble in the user turn.
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"

    url = f"{cfg['base']}/models/{model}:generateContent"
    started = time.time()
    retries = 0
    delay = 1.0

    async with httpx.AsyncClient(timeout=cfg["timeout"]) as client:
        while retries <= cfg["retries"]:
            try:
                r = await client.post(url, params={"key": cfg["key"]}, json=body)

                if r.status_code == 429 or r.status_code >= 500:
                    retries += 1
                    if retries > cfg["retries"]:
                        return None
                    import asyncio

                    await asyncio.sleep(delay)
                    delay *= 2
                    continue

                if r.status_code >= 400:
                    return None

                data = r.json()
                break

            except Exception:
                retries += 1
                if retries > cfg["retries"]:
                    return None
                import asyncio

                await asyncio.sleep(delay)
                delay *= 2
        else:
            return None

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return None

    usage = data.get("usageMetadata", {}) or {}

    parsed = None
    if json_mode:
        parsed = _parse_json(text)

    return GemmaResult(
        parsed=parsed,
        text=text,
        model_id=model,
        input_tokens=int(usage.get("promptTokenCount", 0)),
        output_tokens=int(usage.get("candidatesTokenCount", 0)),
        latency_ms=int((time.time() - started) * 1000),
        retries=retries,
    )


def _parse_json(text: str) -> dict | None:
    """
    Defensive. Models still emit ```json fences occasionally despite the MIME
    hint, and a fence is not a reason to lose the whole extraction.
    """
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1] if "\n" in s else s
        s = s.rsplit("```", 1)[0]
    s = s.strip().removeprefix("json").strip()
    try:
        out = json.loads(s)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def generate_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    files: list[tuple[str, bytes]] | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    session=None,
    org_id: uuid.UUID | None = None,
    vendor_id: uuid.UUID | None = None,
    operation: str = "unknown",
) -> dict | None:
    """Returns the parsed JSON object, or None on any failure."""
    result = await _call(
        model=model or model_for("fast"),
        system=system,
        user=user,
        files=files,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
    )
    if result is None:
        return None

    if session is not None:
        await _log_cost(session, result, org_id, vendor_id, operation)

    return result.parsed


async def generate_text(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    session=None,
    org_id: uuid.UUID | None = None,
    vendor_id: uuid.UUID | None = None,
    operation: str = "unknown",
) -> str | None:
    result = await _call(
        model=model or model_for("fast"),
        system=system,
        user=user,
        files=None,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=False,
    )
    if result is None:
        return None

    if session is not None:
        await _log_cost(session, result, org_id, vendor_id, operation)

    return result.text


async def _log_cost(session, result: GemmaResult, org_id, vendor_id, operation) -> None:
    """
    Cost tagging — the shared contract with Wrik. provider is EXACTLY "gemma"
    on both sides, or the dashboard reports nonsense.

    Rows are written even at zero cost. The dashboard counts events and tokens,
    not just dollars, and "N thousand calls at zero marginal cost" is a stronger
    claim than a dollar figure.
    """
    try:
        from db.models.api_key import ApiCostEvent

        session.add(
            ApiCostEvent(
                org_id=org_id,
                vendor_id=vendor_id,
                provider="gemma",
                operation=operation,
                model_id=result.model_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                request_count=1,
                cost_usd=0.0,
                detail={"latency_ms": result.latency_ms, "retries": result.retries},
            )
        )
    except Exception:
        pass  # cost logging must never fail a request


async def healthcheck() -> bool:
    if not is_configured():
        return False
    r = await generate_text(
        system="Reply with the single word OK.",
        user="ping",
        max_tokens=8,
        temperature=0.0,
    )
    return r is not None