"""turingos.dispatch_router — the smart dispatch router (cost/effort tiering for -p worker calls).

WHY: each Worker CLI defaults to the operator's OWN (expensive) model+effort — e.g. claude opus-4.8 xhigh,
codex gpt-5.5 `model_reasoning_effort=high`. Dispatching `-p` unqualified burns tokens and is NOT the fast-worker
strategy. This router picks the model + thinking/reasoning effort PER TASK and injects the right flags per CLI:

  * DEFAULT = `fast` (cheapest capable model + low effort) — most atoms.
  * escalate to `standard` / `deep` ONLY on real signals (risk_class, allowed_files breadth, retry-after-failure).

This is LAYER-4 ordinary execution (Worker selection / dispatch tuning, plan §5.1) — NOT capability ranking
between vendors (adapters stay interchangeable, S-6). It is deterministic: same capsule -> same tier.

Flag values are grounded in `agy models` / `grok models` / `codex config.toml` / `claude --help` (2026-06-20).
"""
from __future__ import annotations

TIERS = ("fast", "standard", "deep")

# Per-worker extra argv flags by tier. The cost levers:
#   claude: --model {sonnet|opus} --effort {low|medium|high}
#   codex : -c model_reasoning_effort={low|medium|high}   (model left at user default unless escalated)
#   agy   : --model "<Name (Low|High)>"  (effort baked into the model name)
#   grok  : --model <id> --effort {low|medium|high}        (default grok-composer-2.5-fast is already 'fast')
WORKER_TIER_FLAGS = {
    "claude": {
        "fast":     ["--model", "sonnet", "--effort", "low"],
        "standard": ["--model", "sonnet", "--effort", "medium"],
        "deep":     ["--model", "opus", "--effort", "high"],
    },
    "codex": {
        "fast":     ["-c", "model_reasoning_effort=low"],
        "standard": ["-c", "model_reasoning_effort=medium"],
        "deep":     ["-c", "model_reasoning_effort=high"],
    },
    "agy": {
        "fast":     ["--model", "Gemini 3.5 Flash (Low)"],
        "standard": ["--model", "Gemini 3.1 Pro (Low)"],
        "deep":     ["--model", "Gemini 3.1 Pro (High)"],
    },
    "grok": {
        "fast":     ["--model", "grok-composer-2.5-fast", "--effort", "low"],
        "standard": ["--model", "grok-composer-2.5-fast", "--effort", "medium"],
        "deep":     ["--model", "grok-build", "--effort", "high"],
    },
}


def _escalate(tier: str) -> str:
    i = TIERS.index(tier)
    return TIERS[min(i + 1, len(TIERS) - 1)]


def select_tier(capsule: dict) -> str:
    """Deterministically pick a cost/effort tier from observable capsule signals. Default = fast.

    Signals (cheap-by-default, escalate only when warranted):
      - risk_class: 'high' -> deep ; 'medium' -> standard ; else -> fast
      - allowed_files breadth: >=5 files -> deep ; >=3 -> at least standard
      - retry-after-failure: injected_rules present (prior failures on this atom) -> escalate one tier
        (it was already attempted and failed cheaply; try harder now).
    An explicit capsule['tier'] (if in TIERS) overrides the heuristic.
    """
    explicit = capsule.get("tier")
    if explicit in TIERS:
        return explicit

    risk = (capsule.get("risk_class") or "low").lower()
    n_files = len(capsule.get("allowed_files", []) or [])
    if risk == "high" or n_files >= 5:
        tier = "deep"
    elif risk == "medium" or n_files >= 3:
        tier = "standard"
    else:
        tier = "fast"

    if capsule.get("injected_rules"):   # this atom already failed once -> escalate one tier
        tier = _escalate(tier)
    return tier


def worker_flags(worker_id: str, tier: str) -> list:
    """Return the extra argv flags (model + effort) for a worker at a tier. Unknown worker -> []."""
    if tier not in TIERS:
        tier = "fast"
    return list(WORKER_TIER_FLAGS.get(worker_id, {}).get(tier, []))


def describe(worker_id: str, tier: str) -> str:
    return f"{worker_id}:{tier} {' '.join(worker_flags(worker_id, tier))}".strip()
