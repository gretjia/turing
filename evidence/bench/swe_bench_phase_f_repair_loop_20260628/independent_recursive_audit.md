# Phase F Repair Loop Recursive Audit

Verdict: BLOCKED / NO-RELEASE ARTIFACT ACCEPTED

The Phase F repair-loop packet is safe to publish as a blocked, no-release
artifact. It does not release Phase G, does not claim full SWE-bench status,
does not rewrite old Stage16R MicroTape, and does not permit dataset gold
patches as candidate repair artifacts.

Findings:

- PASS: `phase_f_repair_loop_audit.json` reports `status: BLOCKED` and
  `release_next_phase_g: false`.
- PASS: `phase_f_evaluator_proof_required: true` and
  `phase_g_release_requires_phase_f_evaluator_proof_pass: true` are present.
- PASS: Exactly seven Stage16R repair targets are identified:
  `django__django-11790`, `django__django-11815`, `django__django-11964`,
  `django__django-12209`, `django__django-12273`, `django__django-12308`, and
  `django__django-12325`.
- PASS: Existing Stage16R artifacts are hash-bound but not replayable unified
  diffs; `replayable_repair_bundle_count: 0`.
- PASS: Dataset gold patch shortcut is rejected and old MicroTape rewrite is
  forbidden.
- PASS: The next contract requires fresh Stage16R-real evaluator bundles with
  worker-derived unified diffs, official evaluator logs, stdout/stderr digests,
  environment/harness/dataset descriptors, fresh MicroTape evidence, and bundle
  SHA.
- PASS: No full dataset, full SWE-bench score, leaderboard equivalence, or Phase
  G release claim appears in the repair-loop packet.

Hardening note:

The repair-loop auditor now treats a future structural repair-loop PASS as only
permission to rerun Phase F evaluator proof. It does not directly release Phase
G. A Phase G release still requires `audit_phase_f_evaluator_proof` to report
PASS with executable official evaluator replay.

Independent verification commands:

```bash
python3 -m py_compile \
  tools/bench/audit_phase_f_repair_loop.py \
  tools/bench/build_phase_f_repair_loop.py \
  tools/bench/audit_phase_f_evaluator_proof.py \
  tools/bench/build_phase_f_evaluator_proof.py

pytest tests/test_phase_f_repair_loop.py tests/test_phase_f_evaluator_proof.py -q

python3 - <<'PY'
import json
from pathlib import Path
root = Path("evidence/bench/swe_bench_phase_f_repair_loop_20260628")
audit = json.loads((root / "phase_f_repair_loop_audit.json").read_text())
assert audit["status"] == "BLOCKED"
assert audit["release_next_phase_g"] is False
assert audit["phase_f_evaluator_proof_required"] is True
assert audit["phase_g_release_requires_phase_f_evaluator_proof_pass"] is True
assert audit["repair_target_count"] == 7
assert audit["replayable_repair_bundle_count"] == 0
assert audit["required_next_action"] == "fresh_stage16r_real_evaluator_bundles"
assert not audit["problems"]
print("PHASE_F_REPAIR_LOOP_HARDENED_BLOCKED_PACKET_VERIFIED")
PY
```

Observed result:

```text
phase_f_repair_loop_status: BLOCKED
release_next_phase_g: NO
phase_f_evaluator_proof_required: YES
repair_target_count: 7
replayable_repair_bundle_count: 0
problems: []
focused_tests: PASS
```

Conclusion:

This packet remains the correct loop stop condition. It must not be interpreted
as Phase F PASS or Phase G release. The required next action is still fresh
Stage16R-real evaluator bundles that supersede, rather than rewrite, the
previous Stage16R evidence.
