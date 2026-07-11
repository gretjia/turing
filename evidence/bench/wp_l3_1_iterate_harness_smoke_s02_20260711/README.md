# WP-L3-1 real smoke: one S02 task, a real worker, an organic attempt-2

Scope: `tools/econ_lab/iterate/smoke_s02_real.py` -- 2 real `grok` CLI dispatches
(well under the WP's <=6-call budget) against `sphinx-doc__sphinx-7462` (SWE-bench
Verified shard S02, `execution_order_index: 107`, `original_manifest_index: 391`).

**SMOKE_FIXTURE -- not a certified SWE-bench solve-rate claim.** `diff_scope` here is a
cheap, honest proxy ("did the produced diff touch `sphinx/domains/python.py`, the file
the public bug report's traceback implicates") computed from the worker's real `git
diff`, never a call to the official SWE-bench docker/conda evaluation harness (out of
budget for this smoke; a separate, already-existing capability path).

## What this proves

```text
attempt 1 (bad route: worker-safe capsule omits the file/traceback hint, and the
           per-attempt turn budget is deliberately tight -- see smoke_s02_real.py's
           own --max-turns docstring for why a generous budget defeats the point)
  -> grok CLI genuinely dispatched, ran out of its turn budget before landing a patch
  -> classified CONTEXT_MISSING (fact: no patch was produced) via
     classify_stage11_observed_signals -- the same classifier the offline mock-worker
     test suite uses
  -> compose_failure_broadcast_content("CONTEXT_MISSING", route_id) -- the same
     Decision-3-scanned guidance the offline harness emits
-> attempt 2's worker-visible capsule is REMATERIALIZED FROM DISK via
   `load_worker_visible_context` (tools/bench/run_deepseek_arm_a_worker.py:606's own
   function, called fresh, not cached) with the broadcast rule from attempt 1 actually
   present in the rendered `## TuringOS Failure-Memory Broadcast Rules` section --
   see `worker_logs/attempt2_visible_prompt.txt`
  -> grok CLI genuinely dispatched a second time (organic_attempt_2_occurred: true)
```

Both attempts hit the same tight turn budget under this smoke's constrained
`--max-turns`, so the run's own `final_same_signature_streak` reaches 2 -- the
ADR-ECON-007 Decision 6a PROVISIONAL task-internal escalation threshold
(`iterate_harness.SAME_SIGNATURE_RETRY_LIMIT_FIXTURE_ADR007_DECISION_6A`) -- which is
itself an honest organic demonstration of the escalation trigger condition under real
worker load, not just the offline mock-worker unit test
(`tests/test_econ_lab_iterate_harness.py::test_escalation_case_same_signature_threshold`).

A separate real run at a generous `--max-turns=12` (not included here -- 1 real call,
not committed as evidence) solved the bug in a single attempt, confirming the tight
default is what makes the organic bad-route/retry path observable at all for this
particular instance and worker.

## Files

- `smoke_s02_real_record.json` -- the full structured record (`schema_id:
  iterate_harness.smoke_s02_real.v1`), including `repo`/`base_commit` provenance (looked
  up from the public SWE-bench Verified dataset at `original_manifest_index: 391`, see
  `smoke_s02_real.py`'s own module docstring), `real_worker_calls: 2`, and both
  attempts' `diff_scope`/`touched_files`.
- `worker_capsule.md` -- the worker-safe capsule text (no file/traceback hint) handed
  to `load_worker_visible_context` each round.
- `worker_logs/attempt{1,2}_{command,visible_prompt,stdout,stderr,diff,diff_stat}.*`
  -- per-attempt real dispatch evidence; `attempt2_visible_prompt.txt` is the
  rematerialized-with-broadcast-rule proof cited above.

## Reproduction

```bash
export TURING_JCS_BIN=<path to a built turing-cli binary, e.g. target/debug/turing>
python3 tools/econ_lab/iterate/smoke_s02_real.py \
  --out-dir evidence/bench/wp_l3_1_iterate_harness_smoke_s02_20260711 \
  --worker-timeout-s 300
```

## Status

```text
real_worker_calls: 2 (budget: <=6)
organic_attempt_2_occurred: true
scientific_status: SMOKE_FIXTURE_ORGANIC_LOOP_NOT_OFFICIAL_SWEBENCH_EVAL
```
