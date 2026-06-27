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

DeepSeek V4 Pro is the default MetaAI provider for this benchmark track.

- MetaAI is a non-authority strategy/review layer.
- Default provider: `deepseek`.
- Default model: `deepseek-v4-pro`.
- Default base URL: `https://api.deepseek.com/v1`.
- Credential material must be supplied only through `DEEPSEEK_API_KEY`.
- The harness records the env var name, never the key value or key hash.
- MetaAI cannot move `accepted_head`, `authorization_head`, or any Micro ref.
- MetaAI output is not truth; predicate/replay evidence remains the truth gate.

If an API key has been pasted into chat or logs, rotate it before running the
benchmark and export only the replacement key in the shell that launches the
harness:

```bash
export DEEPSEEK_API_KEY=...
```

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
  --meta-provider deepseek \
  --meta-model deepseek-v4-pro \
  --meta-api-key-env DEEPSEEK_API_KEY \
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
- DeepSeek MetaAI provider contract, without credential material
- pre-registered experiment design

## Clean Auditor

Before any real model run, audit the dry-run packet with the independent clean
auditor. The auditor reads only the JSON plan and does not import the benchmark
harness.

```bash
python3 tools/bench/audit_mini_swe_bench_plan.py \
  --plan evidence/bench/mini_swe_bench_grok_headless_plan.json \
  --out evidence/bench/mini_swe_bench_grok_headless_plan_audit.json \
  --min-tasks 50
```

The auditor blocks real execution unless the plan has:

- paired within-task design: direct Grok baseline vs TuringOS + Grok worker
- minimum real sample size of 50 tasks
- pre-registered primary metric: predicate-resolved paired binary progress
- McNemar exact test for paired binary resolution
- 95% paired bootstrap confidence interval for paired differences
- no post-hoc exclusions
- no best-of-N reporting unless pre-registered
- predicate-only accepted-head policy
- no serialized API-key-shaped credential material
- MetaAI marked as non-authority

For smoke only, use `--allow-smoke --min-tasks 1`. A smoke PASS proves the
harness is runnable; it does not prove statistical power.

## Smoke Test

Run the smoke gate before preparing real tasks:

```bash
bash tools/bench/smoke_mini_swe_bench_grok_headless.sh /tmp/turingos-mini-swe-bench-smoke
```

The smoke gate creates a one-task fixture, generates a dry-run plan, audits it
with `--allow-smoke`, checks for API-key-shaped leakage, and writes:

- `/tmp/turingos-mini-swe-bench-smoke/plan.json`
- `/tmp/turingos-mini-swe-bench-smoke/audit.json`

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
