"""turingos.registry — the 18-event registry loader + class / head_effect lookup.

Frozen Stage-0 interface (contracts/INTERFACES.md, registry.py section). The machine-readable
source of truth is contracts/event_registry.json; this module is a thin, closed-world accessor.

Invariants enforced here:
  * Closed-world: an unknown event_type is REJECTED (event_class / head_effect / is_predicate_gated
    raise errors.RejectedAppend; is_known returns False and never raises).
  * head_effect is REGISTRY-DERIVED, never writer-trusted: derived from the event class
    (SOVEREIGN_ACCEPT -> ADVANCE, else PRESERVE). At load we assert the derived value agrees with
    the head_effect field declared in the JSON, so a drifting contract fails loudly.
"""
from __future__ import annotations

from pathlib import Path
import json
import threading

from . import errors

# Frozen default path. Resolve robustly relative to the repo root:
#   src/turingos/registry.py -> parents[2] == repo root.
REGISTRY_PATH = Path(__file__).resolve().parents[2] / "contracts" / "event_registry.json"

# Per the registry contract: only SOVEREIGN_ACCEPT advances accepted_head; everything else preserves.
_ADVANCE_CLASS = "SOVEREIGN_ACCEPT"
_VALID_CLASSES = frozenset({"SOVEREIGN_ACCEPT", "PROPOSAL", "OBSERVATION"})


def _derive_head_effect(event_class: str) -> str:
    """Derive head_effect from the event class (the single source of truth for ADVANCE/PRESERVE)."""
    return "ADVANCE" if event_class == _ADVANCE_CLASS else "PRESERVE"


# --- cache of the parsed + indexed registry -------------------------------------------------------
# {"raw": <dict>, "by_name": {name: {"class","head_effect","predicate_gated"}}, "names": frozenset}
_cache: dict | None = None
_cache_key: str | None = None
_lock = threading.Lock()


def _index(raw: dict, src: str) -> dict:
    events = raw.get("events")
    if not isinstance(events, list):
        raise errors.RejectedAppend(f"registry {src}: missing or malformed 'events' list")

    by_name: dict[str, dict] = {}
    for ev in events:
        name = ev["name"]
        ev_class = ev["class"]
        if ev_class not in _VALID_CLASSES:
            raise errors.RejectedAppend(
                f"registry {src}: event {name!r} has unknown class {ev_class!r}"
            )
        if name in by_name:
            raise errors.RejectedAppend(f"registry {src}: duplicate event name {name!r}")

        derived = _derive_head_effect(ev_class)
        declared = ev.get("head_effect")
        # head_effect is registry-DERIVED; the JSON field is a redundant cross-check that must agree.
        if declared != derived:
            raise errors.RejectedAppend(
                f"registry {src}: head_effect mismatch for {name!r}: "
                f"declared {declared!r} != derived {derived!r}"
            )

        by_name[name] = {
            "class": ev_class,
            "head_effect": derived,
            "predicate_gated": bool(ev.get("predicate_gated", ev_class == _ADVANCE_CLASS)),
        }

    return {"raw": raw, "by_name": by_name, "names": frozenset(by_name)}


def load_registry(path: str | Path = REGISTRY_PATH) -> dict:
    """Load (and cache) the event registry JSON, returning the raw parsed dict.

    Caching is keyed by the resolved path; loading a different path re-reads from disk.
    The returned dict is the raw JSON document (as in the contract).
    """
    global _cache, _cache_key
    resolved = str(Path(path).resolve())
    with _lock:
        if _cache is None or _cache_key != resolved:
            try:
                text = Path(resolved).read_text(encoding="utf-8")
            except OSError as exc:
                raise errors.RejectedAppend(f"registry: cannot read {resolved}: {exc}") from exc
            try:
                raw = json.loads(text)
            except json.JSONDecodeError as exc:
                raise errors.RejectedAppend(f"registry: invalid JSON in {resolved}: {exc}") from exc
            _cache = _index(raw, resolved)
            _cache_key = resolved
        return _cache["raw"]


def _indexed() -> dict:
    """Ensure the default registry is loaded and return the indexed cache."""
    load_registry()  # populates _cache for the default path if not already loaded
    assert _cache is not None  # load_registry guarantees this
    return _cache


def _entry(event_type: str) -> dict:
    entry = _indexed()["by_name"].get(event_type)
    if entry is None:
        raise errors.RejectedAppend(f"unknown event_type {event_type!r} (closed-world)")
    return entry


def event_names() -> frozenset:
    """The frozenset of all known event names (exactly 18 in the 1.0 registry)."""
    return _indexed()["names"]


def event_class(event_type: str) -> str:
    """Return the event class. Unknown event_type -> errors.RejectedAppend (closed-world)."""
    return _entry(event_type)["class"]


def head_effect(event_type: str) -> str:
    """Return 'ADVANCE' | 'PRESERVE', registry-derived. Unknown -> errors.RejectedAppend."""
    return _entry(event_type)["head_effect"]


def is_predicate_gated(event_type: str) -> bool:
    """Whether this event type gates accepted_head advance on a deterministic Predicate PASS.

    True iff the event is a SOVEREIGN_ACCEPT. Unknown -> errors.RejectedAppend.
    """
    return _entry(event_type)["predicate_gated"]


def is_known(event_type: str) -> bool:
    """Closed-world membership test: unknown event_type => False. Never raises."""
    return event_type in _indexed()["names"]
