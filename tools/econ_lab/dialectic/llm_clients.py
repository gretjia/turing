"""WP-L3-2 -- LLM client implementations for the GRILL-ME route dialectic gate
(`dialectic_gate.py`). Two implementations of the same tiny `LLMClient` protocol
(`complete(role, system, user) -> str`):

  * `MockLLMClient` -- fully offline, deterministic, table-driven by `role`. Used by
    every offline test in `tests/test_dialectic_gate.py` (this WP's own red line:
    "mock LLM 全离线"). Never performs network I/O.
  * `SiliconFlowLLMClient` -- a real OpenAI-compatible `/chat/completions` caller,
    self-contained (duplicated rather than imported from `live_driver.py`, mirroring
    `depthk/route_market.py`'s own "duplicated rather than imported across a
    file-partition boundary" precedent for the same reason: this package must not
    import from `tools/econ_lab/monitor/` or `tools/econ_lab/depthk/` internals it
    does not need, and must stay independently testable). Same NOT_RUN-on-missing-
    credential honesty discipline as `live_driver.py::dispatch_via_siliconflow`: it
    never fabricates a completion when `SILICONFLOW_API_KEY` is unset -- it raises
    `MissingCredentialError`, a typed, catchable condition the caller (the smoke
    driver) turns into an honest `NOT_RUN` verdict rather than a bare crash or a
    silently-skipped step.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol

SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
SILICONFLOW_API_KEY_ENV = "SILICONFLOW_API_KEY"
DEFAULT_MODEL_ID = "deepseek-ai/DeepSeek-V4-Flash"


class LLMClient(Protocol):
    """The one method `dialectic_gate.py` calls. `role` is a bookkeeping label only
    (e.g. "proposer_1", "critic", "judge") -- implementations may use it to pick a
    canned response (`MockLLMClient`) or purely for their own receipt logging
    (`SiliconFlowLLMClient`); it carries no schema meaning to the caller."""

    def complete(self, *, role: str, system: str, user: str) -> str: ...


class MissingCredentialError(RuntimeError):
    """Raised by `SiliconFlowLLMClient.complete` when its required API-key
    environment variable is unset -- a typed condition distinct from a bare
    `RuntimeError`, so a caller can catch it specifically and degrade to an honest
    `NOT_RUN` verdict (mirrors `live_driver.py::dispatch_via_siliconflow`'s own
    dict-shaped NOT_RUN return, translated here into an exception type because this
    client's contract is "return a completion string or raise", not "return a status
    dict")."""


@dataclass(frozen=True)
class MockLLMClient:
    """Deterministic, offline, table-driven mock (WP-L3-2 red line: "mock LLM 全离线").

    `responses` maps `role` -> either a literal JSON response string, or a
    zero-argument callable returning one (the callable form lets a test compute a
    response that depends on what was already asked, e.g. echoing route labels seen
    in the critic's own user prompt back into the judge's response, without this
    class itself doing any prompt parsing). A role with no matching entry raises
    `KeyError` -- this mock never silently guesses a default reply.
    """

    responses: Dict[str, Any] = field(default_factory=dict)
    calls: list = field(default_factory=list)

    def complete(self, *, role: str, system: str, user: str) -> str:
        self.calls.append({"role": role, "system": system, "user": user})
        if role not in self.responses:
            raise KeyError(f"MockLLMClient has no canned response for role={role!r}")
        entry = self.responses[role]
        return entry() if callable(entry) else entry


def _call_openai_compatible(
    *, base_url: str, api_key: str, request_payload: Dict[str, Any], timeout_s: int
) -> tuple[Dict[str, Any], str, int]:
    """Generic OpenAI-compatible `/chat/completions` POST -- self-contained duplicate
    of `live_driver.py::_call_openai_compatible`'s own shape (see module docstring)."""
    data = json.dumps(request_payload, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=data,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        raw_bytes = response.read()
    wall_time_ms = int((time.monotonic() - start) * 1000)
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    parsed = json.loads(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError("provider response must be a JSON object")
    return parsed, raw_text, wall_time_ms


@dataclass
class SiliconFlowLLMClient:
    """Real LLM client, SiliconFlow's OpenAI-compatible endpoint (same provider path
    `live_driver.py` uses for all four lineages). `model_id` defaults to the same
    DeepSeek lineage `live_driver.py::LINEAGE_CONFIGS["deepseek"]` names.
    `on_receipt` (optional): called with a small per-call receipt dict after every
    successful completion -- the smoke driver uses this to log real provider receipts
    without this client itself owning any file I/O."""

    model_id: str = DEFAULT_MODEL_ID
    base_url: str = SILICONFLOW_BASE_URL
    api_key_env: str = SILICONFLOW_API_KEY_ENV
    timeout_s: int = 120
    max_tokens: int = 4000
    on_receipt: Optional[Callable[[Dict[str, Any]], None]] = None

    def complete(self, *, role: str, system: str, user: str) -> str:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise MissingCredentialError(
                f"{self.api_key_env} is unset; SiliconFlowLLMClient cannot make a real call "
                f"(role={role!r})"
            )
        request_payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "max_tokens": self.max_tokens,
        }
        response, response_raw, wall_time_ms = _call_openai_compatible(
            base_url=self.base_url,
            api_key=api_key,
            request_payload=request_payload,
            timeout_s=self.timeout_s,
        )
        choices = response.get("choices") or []
        if not choices:
            raise ValueError(f"provider response for role={role!r} carries no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError(f"provider response for role={role!r} has no string content")
        if self.on_receipt is not None:
            self.on_receipt(
                {
                    "role": role,
                    "model_requested": self.model_id,
                    "model_reported": str(response.get("model") or ""),
                    "wall_time_ms": wall_time_ms,
                    "content_length_chars": len(content),
                    "response_sha256_prefix": None,  # filled by caller if it wants a digest
                    "response_raw": response_raw,
                }
            )
        return content


__all__ = [
    "SILICONFLOW_BASE_URL",
    "SILICONFLOW_API_KEY_ENV",
    "DEFAULT_MODEL_ID",
    "LLMClient",
    "MissingCredentialError",
    "MockLLMClient",
    "SiliconFlowLLMClient",
]
