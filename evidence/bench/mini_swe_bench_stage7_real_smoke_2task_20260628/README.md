# Stage7 Real-Worker Smoke: 2 Django SWE-bench Tasks

This is a real TuringOS + Grok worker smoke run over two Django SWE-bench-shaped
tasks. It is an execution-chain landing check, not a statistically meaningful
solve-rate claim.

Base code SHA: `2f497820b17a78fc56b47620f5ecb02b994f8098`

## Tasks

- `django__django-12039`
- `django__django-12050`

Both tasks came from:

`evidence/bench/mini_swe_bench_stage5_10task_20260627/tasks_9_10.jsonl`

## What Was Tested

- Real Grok CLI worker path (`grok-build`, `--no-plan`, `--no-memory`, `--no-subagents`)
- Real TuringOS daemon substrate:
  - `turingd`
  - `turing-execd`
  - `turing-mcp`
  - `turing-marketd`
  - `turing-pputd`
  - `turing-viewd`
- Official Django target-test evaluator
- Micro evidence import after official evaluator result
- Terminal `CandidateAccepted`
- Terminal `MarketSettled`
- `RewardDistributed` referencing terminal settlement
- Final `PPUTAccounted(accounting_stage=final)`
- MicroTape bundle export and independent replay audit

## Commands

Authorization required probe:

```bash
rm -rf /tmp/turingos_auth_required_probe
python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
  --tasks-jsonl evidence/bench/mini_swe_bench_stage5_10task_20260627/tasks_9_10.jsonl \
  --out-dir /tmp/turingos_auth_required_probe \
  --limit 1 \
  --worker-mode fake \
  --authorization-mode required \
  --worker-timeout-s 60
```

Observed result: failed because OS keyring provider `secret-tool` is unavailable
in this environment. This is why the real Grok smoke used `authorization-mode
auto` and records authorization-head as not covered.

Real TuringOS + Grok substrate smoke:

```bash
python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
  --tasks-jsonl evidence/bench/mini_swe_bench_stage5_10task_20260627/tasks_9_10.jsonl \
  --out-dir evidence/bench/mini_swe_bench_stage7_real_smoke_2task_20260628/turingos \
  --limit 2 \
  --worker-mode grok \
  --model grok-build \
  --max-turns 50 \
  --worker-timeout-s 1800 \
  --authorization-mode auto \
  --broadcast-rules-file evidence/bench/mini_swe_bench_stage5_10task_20260627/combined_broadcast_rules.json
```

Official evaluator + Micro evidence import:

```bash
python3 tools/bench/evaluate_django_swe_bench_patches.py \
  --tasks-jsonl evidence/bench/mini_swe_bench_stage5_10task_20260627/tasks_9_10.jsonl \
  --limit 2 \
  --turingos-dir evidence/bench/mini_swe_bench_stage7_real_smoke_2task_20260628/turingos \
  --direct-dir evidence/bench/mini_swe_bench_stage5_10task_20260627/direct_incremental \
  --out evidence/bench/mini_swe_bench_stage7_real_smoke_2task_20260628/patch_eval \
  --work-root /tmp/turingos_django_patch_eval_stage7_real_smoke_2task \
  --venv /tmp/turingos-django-swebench-venv \
  --substrate-coverage evidence/bench/mini_swe_bench_stage7_real_smoke_2task_20260628/turingos/substrate_coverage.json \
  --import-turingos-evidence \
  --daemon-bin-dir target/debug
```

Post-import bundle export was performed from each fresh `micro.git` and written
back to `turingos/substrate_coverage.json`.

Strict market/VPPUT replay audit:

```bash
python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --coverage evidence/bench/mini_swe_bench_stage7_real_smoke_2task_20260628/turingos/substrate_coverage.json \
  --out-dir evidence/bench/mini_swe_bench_stage7_real_smoke_2task_20260628/micro_tape_audit_strict_market_vpput
```

Authorization-head strict audit:

```bash
python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage evidence/bench/mini_swe_bench_stage7_real_smoke_2task_20260628/turingos/substrate_coverage.json \
  --out-dir evidence/bench/mini_swe_bench_stage7_real_smoke_2task_20260628/micro_tape_audit_strict_with_auth_required
```

Observed result: expected fail with `require_authorization_head`, because real
OS-keyring authorization could not run on this host.

## Results

Patch evaluation:

| Instance | TuringOS + Grok | Micro write | Direct reference |
| --- | --- | --- | --- |
| `django__django-12039` | PASS | `CandidateAccepted` | PASS |
| `django__django-12050` | PASS | `CandidateAccepted` | PASS |

Substrate coverage:

- verdict: `PASS`
- scientific status: `SUBSTRATE_COVERAGE_READY`

Strict market/VPPUT MicroTape audit:

- verdict: `PARTIAL`
- `replay_structural_integrity`: `PASS`
- `git_topology`: `PASS`
- `canonical_payload_hash`: `PASS`
- `registry_head_effect`: `PASS`
- `accepted_head_authority`: `PASS`
- `terminal_golden_path_anchors_to_accepted_head`: `PASS`
- `accepted_final_progress_one`: `PASS`
- `cost_conservation_all_branches`: `PASS`
- `vpput_accounting`: `PASS`
- `economic_timing`: `PASS`
- `market_accounting_correctness`: `PASS`
- `authorization_head`: `LEGACY_MISSING`
- `constitutional_protocol_audit`: `PARTIAL`

Authorization-head strict audit:

- verdict: `FAIL`
- strict finding: `require_authorization_head`

## Fresh Bundles

- `turingos/instances/django__django-12039/micro_tape.bundle`
  - SHA-256: `sha256:ac2a4796c55819c2bd1b333c0a07523e6bb9176d7ff9ffbe2179020d1a7637ca`
  - path class: `accepted_path`
- `turingos/instances/django__django-12050/micro_tape.bundle`
  - SHA-256: `sha256:1c12804ecbf77b906049c595ddc2e79ec1348228b6b3ebf9e87035e348f98647`
  - path class: `accepted_path`

## Observer Verdict

The real-world landing check is mixed:

- Landed in the real Grok path:
  - official evaluator evidence import;
  - terminal `CandidateAccepted`;
  - terminal market settlement;
  - reward referencing terminal settlement;
  - final PPUT after acceptance;
  - VPPUT cost conservation from tape;
  - replayable MicroTape bundle export.
- Not landed in this host environment:
  - real `authorization_head` coverage through OS keyring, because `secret-tool`
    is unavailable. Stage6 strict fixture proves the protocol shape, but this
    real worker smoke does not prove production OS-keyring authorization.

This smoke therefore supports continuing on terminal evaluator/market/PPUT work,
but it also says the next real-world closure task is an OS-keyring-backed
authorization smoke on a host with the required keyring provider.
