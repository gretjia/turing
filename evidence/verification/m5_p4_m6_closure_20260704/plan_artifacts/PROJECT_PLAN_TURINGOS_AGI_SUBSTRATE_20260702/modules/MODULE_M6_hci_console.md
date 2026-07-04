# MODULE M6 — HCI-A Projection Console (G7)

- Version: 1.0.0 (2026-07-02). Planning artifact; confers no CLOSED/RATIFIED status.
- Grounding: `research/RES_M6_hci_projection_console.md` (sha256 pinned in `PROGRESS_TRACKER.md`), Intent §2 row G7 and §7 non-goals (NO HCI-C; NO HCI-B beyond dry-run previews already built), audit finding F6 (uncommitted console branch; route undecided while an HCI-B-shaped surface was built) and R6.
- Reconciliation: gate IDs/tool names here govern over `09_FINAL_CERTIFICATION_EVALS.md` §0.1 assumptions.

## 1. Written spec

### 1.1 Functional requirements

1. **Preserve (M6.P0a/P0b — urgent):** archive the uncommitted console work from the second clone (`turing-operator-hci-console`, base `6b9daad`) — tracked patch (expected sha256 `ca61116816ce7c3b661f3594fdf91b9d2ee35886aa4dfe38c5b7750e262182af` if the tree is untouched), untracked tarball, `base_sha.txt`, `MANIFEST.sha256`, and a `CLAIM_BOUNDARY.json` (`IMPLEMENTER_ADDRESSED` ceiling, FIXTURE_AND_SELF_RUN evidence kind). Two stages per the tracker: P0a archives into the always-writable plan directory (`rescue/operator_console_v1/`, W0, no owner gate — producing the patch only reads the repo); P0b copies the archive byte-identically into `turing/evidence/hci/...` per RES_M6 §5 Step 0 once repo writes are authorized. Value decays with every commit to main.
2. **Route ADRs (M6.P1):** ADR-M6-001 (HCI-A projection-only sole route; HCI-B deferred behind three verbatim preconditions — M1 canonical-writer/authorization closed, M2 witness independently audited, M5 certificate machinery live — plus new owner-approved ADR; HCI-C forbidden); ADR-M6-002 (archive-then-rebase rescue); ADR-M6-003 (16 verbs retained as schema-pinned intent-previews, `writes_truth: const false`); ADR-M6-004 (projection-integrity audit design); ADR-M6-005 (layered no-write enforcement); ADR-M6-006 (plain CLI + verbatim `--json` mode; `micro_repo` printed so demo vs real is unmistakable).
3. **Rescue commit (M6.P2):** apply the archived patch on branch `hci/operator-console-v1-rebased` at `bed75977` (apply-check verified CLEAN 2026-07-02); re-run Rust + Python test sets + existing audit scripts; commit citing the ADRs; original bundle kept as an immutable FIXTURE-labeled archive; evidence regenerated at the new base. Merge to main gated on M6.P5.
4. **Static no-write gates (M6.P3):** workspace `clippy.toml` disallowed-methods/types for the `Append` surface enforced with `-D` in CI; self-testing grep gate `tools/hci/gate_hci_no_write.sh` (gate_g10 style; bans `.append(`, `.stage(`, `AppendRequest`, `re_mint_and_commit`, `update-ref`, daemon mutation RPC names, and `#[allow(clippy::disallowed_`); `cargo metadata` dependency-direction check freezing turing-projection's writer-free dependency set.
5. **Dynamic gates (M6.P4 — the load-bearing floor):** three-head conservation test (every console command against a fixture tape, all three refs byte-identical before/after) + read-only-filesystem matrix (same commands on a `chmod -R a-w` tape; any latent write fails EACCES).
6. **Projection-integrity audit (M6.P5):** `tools/hci/audit_projection_integrity.py` — shadow rebuild, independent head derivation, provenance-manifest closure (every snapshot JSON pointer mapped to its tape derivation; unclassified fields FAIL), render fidelity, worker-leakage grep (`operator_view_snapshot` must not appear in worker-packet builders) — emitting `hci_projection_integrity_verdict.v1` with NOT_RUN==FAIL; CI job `hci-gates` green required for merge. The audit tool never imports `turing-projection`.

### 1.2 Non-functional requirements

- The console executes nothing and mutates nothing; `can_write_truth`/`writes_truth` remain schema constants `false`; renderers consume `operator_view_snapshot.v1` and may format but never derive.
- Reporting discipline: "zero head-moving paths" may only be claimed with static AND dynamic gates green (never static alone — RES_M6 pitfall 7), at IMPLEMENTER_ADDRESSED ceiling.
- Goodhart shielding: console output is owner-eyes material; a warning banner in `panoview` output and the worker-packet leakage grep enforce it (Art. III.4).
- Both console and `turing-viewd` must consume `turing-projection`'s builder (no second view-truth; RES_M6 pitfall 8).

### 1.3 Performance targets

- Rescue ≈ half a day (apply-check already CLEAN); gates ≈ 2–3 agent-days total (RES_M6 §3 cost note). The projection-integrity audit (~300 lines + manifest) must run over a fixture tape in ≤ 5 min so it can sit in CI; console snapshot rebuild on the FCE-B4 10k-event fixture must be deterministic (hash-equal across two runs) with wall-clock/memory recorded.

### 1.4 Interfaces

| Artifact | Path (repo `turing/` unless noted) | Schema source |
|---|---|---|
| Rescue archive | `evidence/hci/operator_console_v1_rescue_<date>/` | RES_M6 §5 Step 0 |
| Snapshot contract | `operator_view_snapshot.v1` (built by `turing-projection`) | RES_M6 §2.4/§2.7 |
| Typed commands | `typed_command.v1` (`writes_truth: const false`, `dry_run_default: true`) | RES_M6 §2.1/ADR-M6-003 |
| Grep gate | `tools/hci/gate_hci_no_write.sh` (exit 0/1/2/3, `--self-test`) | RES_M6 §5 Step 2 |
| Clippy config | workspace `clippy.toml` | RES_M6 §5 Step 2 (verbatim TOML) |
| Integrity audit | `tools/hci/audit_projection_integrity.py` → `hci_projection_integrity_verdict.v1` | ADR-M6-004 |
| ADRs | plan directory `adr/ADR-M6-001..006.md` | RES_M6 §6 |

### 1.5 Agentic considerations

- Strict ordering: ADR text accepted BEFORE the rescue commit (F6 is a sequencing complaint); archive BEFORE any rebase attempt; merge only after gates.
- M6 is the lowest-priority module and opportunistic filler in waves W2–W3 — except M6.P0, which runs at the first execution-authorized opportunity.
- Standing temptation (pre-answered in playbook §4.3): wiring any verb to a daemon write path is forbidden; the grep gate's RPC-name bans make it a CI failure, not a judgment call.
- M6 owns the console surface + `tools/hci/` in the write partition; the `TapeReader` read-only handle is coordinated with M1 (it changes `turing-git-tape`).

### 1.6 Risks & mitigations

Adopt RES_M6 §4 items 1–10 verbatim as the risk register. Highest-severity: (1) work evaporates before the ADR lands → archive first, patch digest as integrity reference; (5) stale evidence after rebase (`base_sha: 6b9daad` records a tree that no longer exists) → FIXTURE-label the original bundle, regenerate at the new base; (7) static-analysis false confidence → dynamic tests are the floor; (10) HCI-B scope creep → deferral preconditions blocking in the ADR + RPC-name grep bans.

### 1.7 Architecture guidance

`turing-projection` stays a leaf crate with no writer dependency; displayed bytes are a pure function of tape bytes, checkable by the JCS `snapshot_hash` equality plus per-field provenance manifest; the independent reference reader keeps the check non-self-referential (the F1 meta-lesson applied to HCI). Plain CLI with `--json` verbatim snapshot mode; TUI deferred; web forbidden this increment (ADR-M6-006).

## 2. KPIs

Intent §2 row G7 (verbatim): *"Operator visibility without a shadow authority — HCI-A ADR accepted; 100% of console-displayed values replayable from tape (automated audit); zero head-moving UI paths (static + dynamic check); console branch committed or archived."*

Measurable sub-KPIs: (a) rescue archive complete with digest manifest; (b) ADR-M6-001..006 accepted; (c) rescue branch committed with full test sets green at the new base; (d) static gates 3/3 green each with tamper self-test; (e) dynamic gates 2/2 green (head conservation + read-only-FS matrix, full command matrix); (f) integrity-audit verdict all-PASS on the fixture tape, including 100% provenance-manifest closure and 0 worker-leakage hits; (g) CI job `hci-gates` green.

## 3. Ship Gate (M6.G)

**Predicate (tracker M6.G row):** G7 KPI — 100% displayed values replayable; zero head-moving paths (static AND dynamic); branch committed or archived; Drift-Check 7/7. Verifier class: M5-class. NOT_RUN == FAIL.

**Required artifacts:**
1. ADR-M6-001 through ADR-M6-006 accepted (plan directory), HCI-B preconditions verbatim in ADR-M6-001.
2. Rescue archive (patch + tarball + MANIFEST.sha256 + base_sha + CLAIM_BOUNDARY.json) with recorded digests.
3. Rescue-branch commit SHA + Rust/Python test transcripts + regenerated evidence package at the new base + FIXTURE label on the original bundle.
4. Static-gate outputs: clippy CI run, `gate_hci_no_write.sh` clean/tamper self-test transcript, dependency-direction check output.
5. Dynamic-gate outputs: head-conservation test transcript (refs byte-identical) + read-only-FS matrix transcript.
6. `hci_projection_integrity_verdict.v1` all-PASS + the provenance manifest + CI `hci-gates` run artifact.
7. **Mandatory `PROGRESS_TRACKER.md` update** with evidence paths per playbook §6.2.

## 4. Evals

### 4.1 Automated

```bash
tools/hci/gate_hci_no_write.sh --self-test    # clean rc=0 / tamper rc=1 required
tools/hci/gate_hci_no_write.sh                # rc 0 PASS | 1 FAIL | 3 NOT_RUN (blocks)
. ~/.cargo/env && cargo clippy -p turing-projection -p turing-cli --all-targets -- -D clippy::disallowed_methods -D clippy::disallowed_types
cargo test -p turing-cli -p turing-projection --tests --quiet          # incl. head-conservation + read-only-FS tests
PYTHONPATH=src python3 tools/hci/audit_projection_integrity.py --tape <fixture> --json   # verdict all-PASS
```

### 4.2 Scenario / LLM-judge

Scoped-down FCE-S5 pattern (09 §3): a fresh-context agent runs the full console command matrix against a fixture tape, then must answer (i) did any ref move (from its own before/after `git for-each-ref` capture) and (ii) is the rendered tape demo or real (from the `micro_repo` field). Rubric (mechanical): zero ref movement asserted from captured evidence AND correct demo/real identification = PASS; any answer sourced from console prose rather than refs/fields = FAIL.

### 4.3 Performance

Integrity audit ≤ 5 min on the fixture tape (CI budget); console snapshot over the 10k-event FCE-B4 fixture rebuilds hash-equal across two runs with wall-clock and peak memory recorded (operational data for FCE-R3).

### 4.4 Sandboxed harness

The console needs no runsc envelope (it executes and mutates nothing — RES_M6 §3); the read-only-FS dynamic test provides a physical guarantee stronger than sandbox policy. The one named side effect (bundle scratch dir in `$TMPDIR`) is asserted bounded by the dynamic test matrix.

### 4.5 Thresholds

Static gates 3/3 green + self-tests discriminating; dynamic gates 2/2 green across the FULL 16-verb command matrix; provenance closure 100% of displayed fields (any unclassified field = FAIL); worker-leakage grep 0 hits; shadow-rebuild + independent head derivation equal; rescue patch digest matches `ca611168…` or a logged explanation of tree drift.

### 4.6 Runnable instructions

RES_M6 §5 Steps 0–3 carry the exact, EXECUTED-verified command sequences (archive, rescue commit at `bed75977`, clippy TOML verbatim, gate script spec, dynamic-test sketch) with expected outcomes annotated. Execute in order; Step 0 requires only owner activation, Steps 1+ additionally require ADR-M6-001/002 accepted.

## 5. Dependencies

- Upstream: M0 (chain + gate machinery); owner activation for repo writes (needed by M6.P0b/P2+; M6.P0a runs in W0 unconditionally — the plan directory is always writable); ADR-M6-001 route decision is owner-accepted (tracker M6.P1 row). The `TapeReader` split coordinates with M1.
- Downstream: M6.G feeds M5.P4 certification and FCE-S5/W1/R4; HCI-B remains blocked behind M1 + M2 + M5 preconditions.

## 6. Effort estimate + parallelization

- Tiering: gate predicates, integrity audit, provenance manifest = xhigh; rescue commit + render-fidelity fix = high; archive + packaging = medium.
- Wall-clock estimate: P0 ≈ 15–30 min; P1 ≈ 0.5 day (ADR texts are ADR-ready in RES_M6 §6); P2 ≈ 0.5 day; P3 ≈ 0.5–1 day; P4 ≈ 0.5–1 day; P5 ≈ 1 day. Module total ≈ 3–4 agent-days (RES_M6 §3: rescue ~half a day, gates ~2–3 agent-days).
- Parallelization: P0 immediate; P1–P2 in W2; P3–P5 in W3 as opportunistic filler; P3 and P4 parallelize after P2.

---

## Phases and atoms

Authoritative status lives in `PROGRESS_TRACKER.md` (M6 table).

### M6.P0a — Preserve into the plan directory (urgent, W0, no owner gate)

#### ATOM-M6.P0a-1 — Archive patch + untracked tarball + base_sha + MANIFEST.sha256 + CLAIM_BOUNDARY.json into `<plan dir>/rescue/operator_console_v1/`. Gate: archive complete; patch digest recorded (expect `ca611168…`); digests in tracker.

### M6.P0b — Repo-tree copy (after owner activation)

#### ATOM-M6.P0b-1 — Copy the P0a archive into `turing/evidence/hci/...` per RES_M6 §5 Step 0. Gate: repo copy byte-identical to the P0a archive (sha256 match).

### M6.P1 — Route ADRs

#### ATOM-M6.P1-1 — Draft ADR-M6-001..006 from RES_M6 §6; HCI-B preconditions verbatim; obtain route acceptance (owner-adjacent). Gate: texts accepted; verb surface named intent-previews.

### M6.P2 — Rescue commit

#### ATOM-M6.P2-1 — Branch `hci/operator-console-v1-rebased` at `bed75977`; apply patch + untracked files; run cargo + pytest + existing audit scripts; render-fidelity fix (`micro_repo` in text renderers); commit citing ADRs. Gate: all suites green; original bundle FIXTURE-labeled; evidence regenerated at new base.

### M6.P3 — Static no-write gates

#### ATOM-M6.P3-1 — Workspace clippy.toml disallowed entries + CI `-D` enforcement. Gate: clippy green; a seeded violation fixture fails.
#### ATOM-M6.P3-2 — `gate_hci_no_write.sh` with `--self-test` + dependency-direction check. Gate: clean/tamper discrimination; writer-free dependency set frozen.

### M6.P4 — Dynamic gates

#### ATOM-M6.P4-1 — Three-head conservation test across the full command matrix. Gate: refs byte-identical before/after every command.
#### ATOM-M6.P4-2 — Read-only-FS matrix (`chmod -R a-w` tape). Gate: zero EACCES-masked writes; matrix transcript recorded.

### M6.P5 — Projection-integrity audit + CI

#### ATOM-M6.P5-1 — `audit_projection_integrity.py` (shadow rebuild, independent head derivation, provenance closure, render fidelity, worker-leakage grep; never imports turing-projection) + provenance manifest. Gate: verdict all-PASS on fixture tape.
#### ATOM-M6.P5-2 — CI job `hci-gates`; merge gate wiring. Gate: CI green required for merge to main.

### M6.G — Module gate

#### ATOM-M6.G-1 — Assemble §3 artifact list; run §4 evals; Drift-Check 7/7; hand to M5-class verifier. Gate: module ADDRESSED.
