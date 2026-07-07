# Stage6 Strict MicroTape Qualification

This directory contains fresh Stage6 MicroTape protocol fixtures generated after
the terminal market, final PPUT, terminal accepted-head golden path, and
authorization-head auditor fixes. This is a protocol qualification run, not a
SWE-bench solve-rate claim.

Old Stage4/Stage5 bundles are intentionally not rewritten. They remain legacy
PARTIAL/WARN artifacts and must fail strict mode.

## Fresh Bundles

- `instances/django__django-12039/micro_tape.bundle`
  - SHA-256: `sha256:ca2403fb61b85a523836769071d0b3b978b885d838f5129b40ebc4c2677c1117`
  - path class: `accepted_path`
- `instances/django__django-12050/micro_tape.bundle`
  - SHA-256: `sha256:9547af44a94381360bac7bd6cf953ddc056612d8c73769bcb04cc6afd71e5c02`
  - path class: `failed_path`

## Reproduce

From the repository root:

```bash
python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
  --strict-microtape-fixture \
  --authorization-mode required \
  --tasks-jsonl evidence/bench/mini_swe_bench_stage5_10task_20260627/tasks_9_10.jsonl \
  --limit 2 \
  --out-dir evidence/bench/mini_swe_bench_stage6_strict_microtape_20260628
```

```bash
python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage evidence/bench/mini_swe_bench_stage6_strict_microtape_20260628/substrate_coverage.json \
  --out-dir evidence/bench/mini_swe_bench_stage6_strict_microtape_20260628/micro_tape_audit_strict
```

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path("evidence/bench/mini_swe_bench_stage6_strict_microtape_20260628/micro_tape_audit_strict/micro_tape_decision_dag_audit.json")
data = json.loads(p.read_text())
summary = data["status_summary"]
required = {
    "overall": "PASS",
    "replay_structural_integrity": "PASS",
    "bundle_accessibility": "PASS",
    "basic_ref_reconstruction": "PASS",
    "git_topology": "PASS",
    "canonical_payload_hash": "PASS",
    "registry_head_effect": "PASS",
    "accepted_head_authority": "PASS",
    "authorization_head": "PASS",
    "terminal_golden_path_anchors_to_accepted_head": "PASS",
    "failed_progress_zero": "PASS",
    "accepted_final_progress_one": "PASS",
    "cost_conservation_all_branches": "PASS",
    "vpput_accounting": "PASS",
    "economic_timing": "PASS",
    "market_accounting_correctness": "PASS",
    "constitutional_protocol_audit": "PASS",
}
failures = {k: {"expected": v, "got": summary.get(k)} for k, v in required.items() if summary.get(k) != v}
if failures:
    raise SystemExit(f"strict audit status mismatch: {failures}")
print("STRICT_STAGE6_MICROTAPE_PASS")
PY
```

## Legacy Strict Expected Fail

This command must exit non-zero because the old bundles predate terminal
market/reward, final PPUT, and real authorization-head coverage.

```bash
python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --out-dir /tmp/turingos_legacy_strict_expected_fail \
  --bundle evidence/bench/mini_swe_bench_stage4_8task_20260627/recovery/turingos/instances/django__django-11964/micro_tape.bundle \
  --bundle evidence/bench/mini_swe_bench_stage4_8task_20260627/turingos/instances/django__django-11790/micro_tape.bundle \
  --bundle evidence/bench/mini_swe_bench_stage4_8task_20260627/turingos/instances/django__django-11815/micro_tape.bundle \
  --bundle evidence/bench/mini_swe_bench_stage4_8task_20260627/turingos/instances/django__django-11848/micro_tape.bundle \
  --bundle evidence/bench/mini_swe_bench_stage4_8task_20260627/turingos/instances/django__django-11880/micro_tape.bundle \
  --bundle evidence/bench/mini_swe_bench_stage4_8task_20260627/turingos/instances/django__django-11885/micro_tape.bundle \
  --bundle evidence/bench/mini_swe_bench_stage4_8task_20260627/turingos/instances/django__django-11951/micro_tape.bundle \
  --bundle evidence/bench/mini_swe_bench_stage4_8task_20260627/turingos/instances/django__django-11964/micro_tape.bundle \
  --bundle evidence/bench/mini_swe_bench_stage4_8task_20260627/turingos/instances/django__django-11999/micro_tape.bundle \
  --bundle evidence/bench/mini_swe_bench_stage5_10task_20260627/turingos_incremental/instances/django__django-12039/micro_tape.bundle \
  --bundle evidence/bench/mini_swe_bench_stage5_10task_20260627/turingos_incremental/instances/django__django-12050/micro_tape.bundle
```

Observed legacy strict findings:

- `strict_vpput`
- `strict_terminal_market`
- `require_authorization_head`
