"""WP-L3-2 acceptance tests: `tools/econ_lab/dialectic/dialectic_smoke.py`'s own
receipt-redaction guard.

`receipts.json` is written to `tools/econ_lab/runs/...`, a committed, worker-visible
path. `SiliconFlowLLMClient.on_receipt` fires on EVERY network call, including one
`dialectic_gate._complete_with_role_retry` itself rejected and retried away for
tripping the B-zone scan -- so an unscanned `response_raw` would leak that rejected
text into a committed file even though it never reached `portfolio.json`. These tests
cover `_redact_receipt_if_bzone_leak` directly (fully offline -- no network I/O, no
`SILICONFLOW_API_KEY` required).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"
sys.path.insert(0, str(ECON_LAB))

import dialectic.dialectic_smoke as smoke  # noqa: E402


def test_clean_receipt_passes_through_unredacted():
    receipt = {
        "role": "proposer_1",
        "model_requested": "deepseek-ai/DeepSeek-V4-Flash",
        "wall_time_ms": 1234,
        "response_raw": '{"choices": [{"message": {"content": "a clean plain-English route summary"}}]}',
    }
    out = smoke._redact_receipt_if_bzone_leak(receipt)
    assert out["response_raw"] == receipt["response_raw"]
    assert out["bzone_redacted"] is False
    # the original dict passed in is never mutated
    assert "bzone_redacted" not in receipt


def test_leaking_receipt_is_redacted_but_metadata_survives():
    receipt = {
        "role": "critic",
        "model_requested": "deepseek-ai/DeepSeek-V4-Flash",
        "wall_time_ms": 5678,
        "response_raw": '{"choices": [{"message": {"content": "needs a clear failure threshold"}}]}',
    }
    out = smoke._redact_receipt_if_bzone_leak(receipt)
    assert out["response_raw"] != receipt["response_raw"]
    assert "threshold" not in out["response_raw"].lower()
    assert out["bzone_redacted"] is True
    # non-content metadata is preserved verbatim
    assert out["role"] == "critic"
    assert out["wall_time_ms"] == 5678


def test_redaction_marker_itself_passes_the_bzone_scan():
    import dialectic.dialectic_gate as dg

    dg.scan_worker_text(label="redaction_marker", text=smoke._RECEIPT_REDACTION_MARKER)


def test_receipt_with_non_string_response_raw_is_left_alone_not_crashed():
    receipt = {"role": "judge", "response_raw": None}
    out = smoke._redact_receipt_if_bzone_leak(receipt)
    assert out["response_raw"] is None
    assert out["bzone_redacted"] is False
