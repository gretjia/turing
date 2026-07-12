"""ADR-ECON-003 Decision 2(b): "独立实现:验证器为独立 crate/binary(实验阶段落点
`tools/econ_lab/verifier/`),禁止链接、导入或复用接受谓词的实现代码;差分/性质检查器
形式。"

This module is that v0 verifier for the harness: it never imports `tools/econ_lab/arms.py`
or `tools/econ_lab/node.py` (the modules that read the fixture's "accept" outcome field),
and it computes its own verdict from an independent fixture field
(``verify_witnesses``) via a majority-vote property check -- structurally distinct code
and a distinct data subset from the accept-side judgement, satisfying the v0 "structural
independence" criterion for the harness's own self-tests. It only ever sees verify-side
cases (`split.split_side` routes verify-side case IDs here; accept-side cases never reach
this module), which is what keeps the case sets disjoint end to end.
"""
from __future__ import annotations

from typing import Sequence


def verify(witnesses: Sequence[int]) -> int:
    """Majority vote across independent witness signals. Returns 1 (pass) or 0 (fail).

    This is a differential/property checker (Decision 2(b)) in the sense required for
    the v0 harness: a candidate only earns a passing backup verdict if a *majority* of
    independently-recorded witness signals agree it passed, rather than trusting a
    single verdict field -- the same structural shape (majority-of-independent-checks)
    the ADR calls for, without depending on any acceptor-side code.
    """
    if not witnesses:
        raise ValueError("independent verifier requires at least one witness signal")
    total = sum(1 for w in witnesses if w)
    return 1 if total * 2 > len(witnesses) else 0
