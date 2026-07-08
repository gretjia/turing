# Independent Audit — econ_lab / turing-economy (2026-07-07)

Scope: WP1–WP9c economy work on `hci/software3-20260705` — `crates/turing-economy`,
`tools/econ_lab/**`, `tools/gates/gate_f4_econ_leakage.sh`, Stage A ops scripts, and the
associated Python/Rust test suites. Method: three independent read-only review passes
(Python core / verifier+shell / Rust), every finding re-verified against source before
action. Status ceiling for everything below: ADDRESSED (implementer; not CLOSED).

Audit context: Stage A (PREREG E-price-tau, run root `tools/econ_lab/runs/stageA_20260707`)
was LIVE during this audit. All applied fixes were therefore constrained to be
behavior-identical on well-formed/happy-path inputs, `run_stage_a.sh` /
`stage_a_health.sh` were replaced atomically (`mv`, never in-place), and no cargo build
was allowed to touch `target/{debug,release}/econ_fold_cli` (the binary the live driver
subprocess-invokes). Head-parity/replay/resume suites gate the "behavior unchanged" claim.

## A. Fixed in this pass (bugs; happy-path behavior preserved)

Fix list, each verified by targeted regression tests added in the same pass — see
`git diff` of 2026-07-07 for exact hunks:

1. `live_driver.py` resume robustness: atomic settlement-checkpoint writes
   (tmp+`os.replace`); truncated `settlement.json` / `worker_receipt.json` / aggregated
   scoring report now degrade to "no artifact → re-run" per the module's own documented
   contract instead of crashing resume with `JSONDecodeError`.
2. `live_driver.py`: driver no longer crashes at startup when
   `~/.turingos/provider-profiles.json` is absent (config only needed on the rare
   deepseek-direct fallback; fallback now reports NOT_RUN with a missing-config detail).
3. `live_driver.py`: `call_cli` 30s `TimeoutExpired` now raises the same RuntimeError
   shape as a nonzero exit instead of an uncaught traceback.
4. `live_driver.py` resume tamper guard: an existing aggregated scoring report is only
   reused after the current `candidate.patch` sha256 is cross-checked against the
   `model_patch` recorded in the report dir's predictions file; mismatch → re-score.
5. `stage_a_health.sh` (atomic replace): stall detection actually accumulates age
   (`.health_state` was previously touched unconditionally every probe, so a fully wedged
   run could never alarm); new alarm when arms are marked RUNNING but zero
   `live_driver.py` processes are alive; disk check measures the run root's filesystem,
   not `/`; tolerates the launcher's status.json write race.
6. `run_stage_a.sh` (atomic replace): status.json written atomically (tmp+mv); launcher
   exit code now aggregates arm terminal statuses instead of unconditionally exiting 0.
7. `gate_f4_econ_leakage.sh` fail-closed repairs: extractor failure no longer masked by
   `|| true` (unscanned surface can no longer yield PASS); a listed-but-missing surface
   file is NOT_RUN instead of silently narrowing scope; single-line struct fields now
   emitted for scanning; multi-line string literals no longer concatenated across
   newlines. Self-test extended for each.
8. `node.py` `Ledger.clawback`: event hash now bound to its original `(key, v)`;
   mismatched clawback raises `FoldError` instead of silently corrupting counts.
9. `selection.py`: empty route pool raises `ValueError` (was: `None` return / IndexError).
10. `runner.py` `load_stream`: duplicate `case_id` rejected at load time (was: deep
    `FoldError` mid-run).
11. `verifier/live_split_verifier.py`: test outcomes merge fail-closed across categories
    (a failure can no longer be overwritten by a later category's success on malformed
    reports).
12. `analysis/stage_a_readout.py`: per-dispatch settlement verdict aggregation no longer
    last-wins (a trailing `None` dispatch could clobber a real verdict); consistent with
    the neighboring OR-aggregation. Analysis-only file.
13. `turing-economy` (source only; live binary NOT rebuilt): `exp2_q32` saturation
    threshold corrected (`floor_part >= 95`; previously `base << 95` wrapped the i128 sign
    bit producing a negative "exponential", reachable via degenerate anneal configs);
    `parse_event_hash` rejects signed/uppercase hex aliases; tape-consume path re-derives
    `RoutingPriorUpdated.event_hash` from event fields and errors on mismatch (tamper
    guard); `derive_price_signals` rejects unrecognized swap `side` values instead of
    treating them as BUY_YES; `econ_fold_cli` rejects duplicate `market_id` across
    candidate routes (silent Q_eff misattribution).

## B. NOT changed — requires owner / PREREG decision (deviation & spec-intent findings)

These alter preregistered or ADR-pinned behavior; unilateral mid-experiment change would
exceed the implementer ceiling and/or pollute the live Stage A comparison.

B1. **CRITICAL — Rust seed derivation omits `trigger_event_hash` (ADR-ECON-003 Decision
    4).** — STATUS UPDATE 2026-07-08: ADDRESSED. Owner directed the remedy (option a);
    implemented after Stage A reached terminal state (5/5 arms DONE, all verdicts
    present, live binary constraint lifted). `derive_selection_seed_u64` /
    `softmax_select` / `uniform_select` / `MarketRouter::suggest` now take
    `trigger_event_hash` per the pin; CLI request bumped to
    `econ_fold_cli.fold_and_suggest.request.v2` (v1 rejected with a version diagnostic
    per ADR-ECON-003 D1 "new schema version, never implicit drift"); driver passes
    `digest("trigger-event.v1:" + instance_id)` (per-trigger, deterministic, replayable;
    ADR pins only the seed formula, not the digest derivation — documented in-source);
    the unpinned tape-fingerprint in `price_signal_hash` deliberately left untouched.
    New cross-language parity suite (`tests/test_econ_lab_selection_parity.py`, 48
    selection points across τ∈{0, 0.5, 2.0, inf} × route sets × trigger hashes) proves
    Rust↔Python seed/selection identity — previously impossible. Known-answer seed u64s
    cross-computed with the Python reference pinned in Rust unit tests. Head-parity
    tests skip against pre-B1 anchors by design (routing legitimately changes) and
    resume automatically once the B1 landing commit is the merge-base anchor; the
    Stage A comparison window still needs the owner-level PREREG amendment trail.
    Original finding (kept for the record): The ADR (line 69) pins
    `LE(SHA256("routing-select.v1" ‖ price_signal_hash ‖ pput_prior_hash ‖
    join(sorted(route_ids),"\x00") ‖ trigger_event_hash)[0..8])`. `derive_selection_seed_u64`
    in `crates/turing-economy/src/lib.rs` hashes only the first three components; the term
    appears nowhere in the crate (grep-verified 2026-07-07). Python
    (`tools/econ_lab/selection.py:34-49`) implements the full pin → Rust↔Python selection
    parity is impossible for identical trials; the CLI cross-check test never catches it
    (compares CLI against the same Rust lib). The live driver escapes deterministic seed
    collapse only because its `price_signal_hash` embeds a tape fingerprint
    (`live_driver.py:314-317`) — a derivation the ADR does not pin. The doc comment at the
    Rust site quoted the ADR formula with the term already dropped; the quote is now
    corrected and the deviation marked in-source. Remedy options: (a) coordinated
    signature/schema/driver change after Stage A completes, or (b) ADR amendment via owner
    trail. Do not rebuild `econ_fold_cli` into the live target dir until decided.

B2. **INCOMPLETE / EMPTY_PATCH / malformed-report outcomes are funneled into the pinned
    `error_ids` fail-closed path** (`live_driver.py` `_read_scoring_report` →
    `judge_harness_error`): an instance the harness never evaluated this run receives a
    fabricated definite FAIL that settles the market and biases arm pass-rates downward
    for arms with more harness incompletions — in tension with the module's own "never
    fabricate a verdict" invariant. Whether the orchestrator addendum intends
    INCOMPLETE ⊂ "harness error" needs the ADR/PREREG owner.

B3. **Readout denominator excludes no-patch outcomes** (`stage_a_readout.py` arm_stats:
    `SKIPPED_NO_PATCH` → `infra_null`, dropped from `n_settled`): under SWE-bench
    semantics an empty patch is a failed task; here it shrinks the denominator instead —
    a between-arm bias in the primary metric unless PREREG explicitly froze this
    exclusion. If not pinned, needs a dated PREREG addendum per the file's own header rule.

B4. **static_oracle calibration reads verify-side accept labels and its calibration
    trials count in `pass_at_budget`** (`arms.py:89-95,113-118`), despite the module
    docstring's "before formal counting". Corrupts cross-arm comparison if the stream
    head skews easy/hard. Needs PREREG §1 intent.

B5. **`routing_prior_event_hash` has no uniqueness component** (identity =
    (domain, scaffold, verdict, source_id, attestation_hash)): a legitimately repeated
    byte-identical re-attestation collides and hard-errors the whole fold
    (`RoutingFoldDuplicateEventHash`) rather than counting a second observation. Today
    attestations embed instance_id, so collisions require re-scoring the same instance —
    which resume paths can do. Design decision (nonce in the pinned identity vs caller
    uniqueness contract) is the owner's.

B6. **Residual resume gap**: a fresh run that ends with scoring rc≠0 *after* the harness
    wrote a report returns SCORING_FAILED (no settlement), but a later `--resume` treats
    the on-disk report as COMPLETED and settles. The new patch-hash cross-check (A4)
    closes the tamper case but not this fresh/resume divergence; closing it fully needs a
    scoring-success marker artifact (small on-disk format addition — deferred to owner
    since Stage A artifacts are mid-flight).

## C. Test evidence (final, 2026-07-07, verified twice: implementer agent + conductor)

- Python: 63 passed, 0 failed — `tests/test_econ_lab_wp7_harness.py` (10),
  `test_live_driver_head_parity.py` (2, byte-identity vs the fork-point driver the live
  arms loaded), `test_live_driver_replay.py` (4), `test_live_driver_resume.py` (7),
  `test_live_split_verifier.py` (12), new `test_live_driver_crash_hardening.py` (11),
  new `test_econ_lab_audit_fixes.py` (13, incl. readout self-test via CLI).
- Rust: `cargo test -p turing-economy` — 97 passed, 0 failed, 1 ignored (pre-existing)
  across 16 targets; `cargo test -p turing-daemons --test f4_econ_leakage_gate` — 2
  passed. All cargo runs used an isolated `CARGO_TARGET_DIR`;
  `target/debug/econ_fold_cli` mtime 2026-07-07 17:23:12 UTC unchanged throughout
  (target/release absent) — the live Stage A binary was never rebuilt.
- Gate: `gate_f4_econ_leakage.sh --self-test` PASS (extended cases incl. seeded
  single-line-struct leak → FAIL, missing surface → NOT_RUN, non-UTF-8 → NOT_RUN);
  real run `F4_LEAK_PASS (12 surface files scanned, 12 patterns)`.
- Ops: fixed `stage_a_health.sh` probed live against the running Stage A
  (2 RUNNING arms, driver_procs=2, exit 0, no false alarms);
  `run_stage_a.sh`/`stage_a_health.sh` were replaced via atomic `mv` only.
- Governance: `verify_alignment.sh` GREEN at session start.

Coordination note: the concurrent TuringLoop patrol session swept part of this work into
commit `f29ef21` (its byte-identity gate re-proof, PREREG amendment #3 re-pin of the
readout sha). Its gate runs the Python parity/offline suites + F4 only — the Rust changes
in that commit and in the working tree were additionally verified by this audit's own
`cargo test` runs above. Remaining working-tree changes (routing_fold.rs,
econ_fold_cli.rs, Rust test additions, this §C update) are left for the patrol's next
governed sweep.
