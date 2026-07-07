"""Held-out differential verifier package (ADR-ECON-003 Decision 2; design doc §1.3).

Deliberately isolated from `tools/econ_lab/arms.py` / `tools/econ_lab/node.py`'s
accept-side ("∏p") code path: nothing in this package imports the acceptor logic, and
`independent_verifier.verify` computes its verdict from a distinct fixture-field subset
via a distinct algorithm (Decision 2(b): "独立实现...差分/性质检查器形式").
"""
