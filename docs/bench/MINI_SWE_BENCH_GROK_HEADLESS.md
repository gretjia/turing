# Mini SWE-bench Grok Headless Track

This track starts after the B1-B6 authority-boundary audit PASS at
`41703fada09aa6a1eb8bb91199634e0afc1d6037`.

## Contract

Grok is a Macro worker, not a Micro authority.

- Worker id is content-addressed: `worker:sha256:<64 lowercase hex>`.
- Grok sees only the visible capsule.
- Grok runs headless with planning/memory/subagents disabled.
- The current Grok CLI exposes `--reasoning-effort`, not a literal `--thinking off`.
  TuringOS maps "thinking off" to the strict headless contract:
  `--reasoning-effort low --effort low --no-plan --no-memory --no-subagents`.
- TuringOS Micro Tape is the external progress trace.
- Do not ask Grok to output chain-of-thought, private scratchpads, or hidden reasoning.
- Exit code, CI green, Grok self-report, and official benchmark labels cannot move
  `accepted_head`.

## Dry Run

Prepare a SWE-bench Verified Mini JSONL with one task per line:

```json
{"instance_id":"django__django-00001","repo":"https://github.com/django/django","base_commit":"abc123","problem_statement":"Fix the failing regression test."}
```

Generate an auditable two-arm plan:

```bash
python3 tools/bench/mini_swe_bench_grok_headless.py \
  --tasks-jsonl /path/to/verified-mini.jsonl \
  --out evidence/bench/mini_swe_bench_grok_headless_plan.json \
  --dry-run \
  --limit 50
```

The packet contains:

- direct Grok baseline plan
- TuringOS + Grok worker plan
- hash-shaped worker id
- redacted Grok argv
- prompt hashes
- truth guard
- thinking contract

## No PASS No HALT

The harness is fail-closed. Non-dry-run execution returns non-zero until the
deterministic fake-worker E2E gate is promoted into the benchmark executor path:

```text
WorkCapsuleBuilt
  -> WorkerReceiptImported
  -> MacroObservationImported
  -> candidate.verify_write
  -> CandidateAccepted or FailureNode
  -> replay verifies heads and projections
```

Only after that loop passes should this track run real task execution and compare:

- resolved percentage
- cost per resolved task
- wall time
- retries per task
- failure classes
- replay pass rate
- invalid accepted-head attempts

