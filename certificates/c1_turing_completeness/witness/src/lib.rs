//! C1b — the executable witness (RES_AOC §C1, "Turing-complete under governance").
//!
//! This crate is deliberately thin: it contains NO new event types, NO new predicate
//! machinery, and NO new tape writer. Every append below goes through the real,
//! already-shipped `turing-git-tape` three-ref writer (`crates/turing-git-tape/src/
//! append.rs`), using exactly the five closed-registry event rows a prior atom (C1a /
//! module M2) already landed additively as `ADDITIVE_TC_WITNESS_V1` in
//! `pack/04_registries/event_registry_v5_3_1.json`: `SystemConstitutionAccepted` (genesis),
//! `ComputationStarted`, `InstructionAuthorized`, `InstructionApplied`,
//! `MachineStateObserved`, `ComputationHalted`. The registry itself is untouched by this
//! crate — it is read-only law here, exactly as the governance guard requires.
//!
//! What IS new here is the **Rule 110 governed cell-update loop**: for every single
//! cell-update in the elementary cellular automaton, a candidate next-cell-value is
//! *proposed* by one code path (a bit-shift lookup against the rule number) and
//! independently *validated* by a second, textually disjoint code path (an explicit
//! 8-case match on the Wolfram truth table). Only if the two agree is the step appended
//! as a `PredicateProduct::Pass` (`AppendRequest::predicate_pass()`); ties are the
//! predicate's `PASS` in the append algorithm's terms. [`rule110_predicate_selftest`]
//! demonstrates the gate has teeth: fed a deliberately corrupted proposal, the
//! independent validator disagrees, proving the check is not a rubber stamp.
//!
//! The second witness (small universal-ish TM) does not reinvent anything: it drives the
//! ALREADY-SHIPPED `turing-witness` crate's two-counter Minsky-machine interpreter/emitter
//! (`crates/turing-witness/src/lib.rs`, the C1a proof target) end-to-end on a real fixture
//! program (`multiply_small`), through the exact same governed append path.

use std::path::Path;

use serde_json::{Value, json};

use turing_contracts::jcs;
use turing_git_tape::append::{
    Append, AppendError, AppendRequest, CommittedReceipt, commit_parents, committed_body_bytes,
};
use turing_git_tape::git::GitError;

#[derive(Debug)]
pub enum WitnessError {
    Invalid(String),
    Append(AppendError),
    Git(GitError),
    Io(std::io::Error),
    Jcs(jcs::JcsError),
    Json(serde_json::Error),
}

impl std::fmt::Display for WitnessError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WitnessError::Invalid(m) => write!(f, "witness invalid: {m}"),
            WitnessError::Append(e) => write!(f, "witness append error: {e}"),
            WitnessError::Git(e) => write!(f, "witness git error: {e}"),
            WitnessError::Io(e) => write!(f, "witness I/O error: {e}"),
            WitnessError::Jcs(e) => write!(f, "witness canonicalization error: {e}"),
            WitnessError::Json(e) => write!(f, "witness JSON error: {e}"),
        }
    }
}
impl std::error::Error for WitnessError {}
impl From<AppendError> for WitnessError {
    fn from(e: AppendError) -> Self {
        WitnessError::Append(e)
    }
}
impl From<GitError> for WitnessError {
    fn from(e: GitError) -> Self {
        WitnessError::Git(e)
    }
}
impl From<std::io::Error> for WitnessError {
    fn from(e: std::io::Error) -> Self {
        WitnessError::Io(e)
    }
}
impl From<jcs::JcsError> for WitnessError {
    fn from(e: jcs::JcsError) -> Self {
        WitnessError::Jcs(e)
    }
}
impl From<serde_json::Error> for WitnessError {
    fn from(e: serde_json::Error) -> Self {
        WitnessError::Json(e)
    }
}

// --- Rule 110: the two independent code paths ------------------------------------------

/// The rule number (Wolfram elementary-CA numbering), fixed to 110 — proven universal
/// (Cook 2004; Neary & Woods 2006, cited in `evidence/theory/turing_completeness_witness_20260703/THEORY.md`
/// sibling module's THEORY note — this witness does not re-derive that citation).
pub const RULE_NUMBER: u8 = 110;

/// PROPOSE: a bit-shift lookup against the 8-bit rule number. `pattern` is
/// `4*left + 2*center + right`, each of `left`/`center`/`right` in `{0,1}`.
pub fn rule110_propose(left: u8, center: u8, right: u8) -> u8 {
    let pattern = (left << 2) | (center << 1) | right;
    (RULE_NUMBER >> pattern) & 1
}

/// VALIDATE: the independent 8-case match on the same rule's truth table, written as a
/// textually disjoint code path from [`rule110_propose`] (no shared lookup, no shared
/// arithmetic) so the predicate is a genuine second implementation, not the same
/// computation re-read. Returns the value this path computes; the caller compares it
/// against the proposal — agreement is the predicate PASS.
pub fn rule110_validate(left: u8, center: u8, right: u8) -> u8 {
    match (left, center, right) {
        (1, 1, 1) => 0,
        (1, 1, 0) => 1,
        (1, 0, 1) => 1,
        (1, 0, 0) => 0,
        (0, 1, 1) => 1,
        (0, 1, 0) => 1,
        (0, 0, 1) => 1,
        (0, 0, 0) => 0,
        _ => unreachable!("left/center/right must each be 0 or 1"),
    }
}

/// The governance predicate: PASS iff the two independent code paths agree. This is the
/// exact gate the task specifies — "a predicate validates the local Rule-110 rule
/// application (the 8-case truth table)" — evaluated fresh for every single cell-update,
/// never cached, never assumed.
pub fn rule110_predicate_pass(left: u8, center: u8, right: u8, proposed: u8) -> bool {
    rule110_validate(left, center, right) == proposed
}

/// Proves the gate has teeth: feed it a deliberately WRONG proposal (the complement of
/// the true value) for every one of the 8 cases and assert the predicate rejects every
/// one. If this ever returned `false` for a genuine mismatch, the gate would be a rubber
/// stamp; this function is the mechanical proof that it is not.
pub fn rule110_predicate_selftest() -> Result<(), WitnessError> {
    for pattern in 0u8..8 {
        let left = (pattern >> 2) & 1;
        let center = (pattern >> 1) & 1;
        let right = pattern & 1;
        let true_value = rule110_propose(left, center, right);
        // Sanity: the two independent paths must agree on the TRUE proposal.
        if !rule110_predicate_pass(left, center, right, true_value) {
            return Err(WitnessError::Invalid(format!(
                "predicate self-test FAILED to accept a correct proposal at pattern {pattern:03b}"
            )));
        }
        // Teeth check: a forged (complemented) proposal MUST be rejected.
        let forged = 1 - true_value;
        if rule110_predicate_pass(left, center, right, forged) {
            return Err(WitnessError::Invalid(format!(
                "predicate self-test FAILED to reject a forged proposal at pattern {pattern:03b}"
            )));
        }
    }
    Ok(())
}

fn h(hex: char) -> String {
    format!("sha256:{}", hex.to_string().repeat(64))
}

/// STEP 0 — append the genesis `SystemConstitutionAccepted` event (SOVEREIGN_ACCEPT /
/// ADVANCE -> accepted_head), the same pattern the C1a witness append test already
/// established (`crates/turing-git-tape/tests/tc_witness_append.rs`). A fresh private
/// tape repo has no other legal first event.
pub fn append_genesis(repo: &Path) -> Result<CommittedReceipt, WitnessError> {
    let tape = Append::open(repo)?;
    Ok(tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:c1b-genesis",
            json!({"constitution_digest": h('a')}),
        )
        .predicate_pass(),
    )?)
}

fn row_state_hash(row: &[u8]) -> Result<String, WitnessError> {
    let payload = json!({ "row": row });
    let bytes = jcs::canonicalize(&payload)?;
    Ok(format!("sha256:{}", jcs::sha256_hex(&bytes)))
}

#[derive(Debug, Clone)]
pub struct Rule110Report {
    pub width: usize,
    pub steps: usize,
    pub governed_cell_updates: usize,
    pub governed_tape_events: usize,
    pub tape_tip: String,
    pub accepted_head: String,
    pub authorization_head: Option<String>,
    /// generation 0 (initial row) through generation `steps`, in order.
    pub rows: Vec<Vec<u8>>,
}

/// Run Rule 110 for `steps` generations over a fixed-zero-boundary row of length `width`,
/// seeded by `initial_row`, appending EVERY cell-update as a governed tape event:
/// propose (shift lookup) -> validate (8-case truth table) -> append only on PASS.
///
/// Per cell-update this appends exactly two events (mirroring the C1a witness's
/// Authorized+Applied pairing): `InstructionAuthorized` (AUTHORIZATION/ADVANCE ->
/// authorization_head; the gated admission of this specific rule application) and
/// `InstructionApplied` (OBSERVATION/PRESERVE; the resulting state transition, carrying
/// `prev_state_hash`/`next_state_hash` over the in-progress row). One `MachineStateObserved`
/// checkpoints each completed generation. A final `ComputationHalted` closes the run.
pub fn run_rule110(
    repo: &Path,
    writer_id: &str,
    initial_row: Vec<u8>,
    steps: usize,
) -> Result<Rule110Report, WitnessError> {
    for v in &initial_row {
        if *v > 1 {
            return Err(WitnessError::Invalid(
                "initial_row cells must be 0 or 1".into(),
            ));
        }
    }
    let width = initial_row.len();
    if width == 0 {
        return Err(WitnessError::Invalid("width must be > 0".into()));
    }

    // The predicate gate is proven to have teeth BEFORE we trust a single PASS below.
    rule110_predicate_selftest()?;

    append_genesis(repo)?;
    let tape = Append::open(repo)?;

    let mut rows: Vec<Vec<u8>> = vec![initial_row.clone()];
    let initial_hash = row_state_hash(&initial_row)?;
    let program_digest = format!(
        "sha256:{}",
        jcs::sha256_hex(&jcs::canonicalize(&json!({"rule": RULE_NUMBER}))?)
    );

    tape.append(
        AppendRequest::new(
            "ComputationStarted",
            writer_id,
            json!({
                "program_id": "rule110_elementary_ca",
                "program_digest": program_digest,
                "program": [{"op": "APPLY_RULE", "rule": RULE_NUMBER, "boundary": "FIXED_ZERO"}],
                "initial_state": {"row": initial_row, "step": 0},
                "state_hash": initial_hash,
                "step_budget": width * steps,
                "instruction_registry_digest": h('d'),
            }),
        )
        .predicate_pass(),
    )?;

    let mut governed_cell_updates = 0usize;
    let mut governed_tape_events = 1usize; // genesis + ComputationStarted counted below
    governed_tape_events += 1; // ComputationStarted itself

    let mut last_authorization_head: Option<String> = None;

    let mut prev_row = initial_row;
    for step in 1..=steps {
        let mut curr_row = prev_row.clone();
        for i in 0..width {
            let left = if i == 0 { 0 } else { prev_row[i - 1] };
            let center = prev_row[i];
            let right = if i + 1 == width { 0 } else { prev_row[i + 1] };

            // --- PROPOSE (bit-shift lookup) ---
            let proposed = rule110_propose(left, center, right);
            // --- VALIDATE (independent 8-case truth table) — the predicate ---
            let pattern = ((left as u32) << 2) | ((center as u32) << 1) | right as u32;
            let predicate_pass = rule110_predicate_pass(left, center, right, proposed);
            if !predicate_pass {
                // Fail-closed: never append a mismatched proposal as an accepted
                // instruction. (Unreachable for the fixed, correct rule table; kept as a
                // real fail-closed branch, not a comment, so the gate is load-bearing.)
                return Err(WitnessError::Invalid(format!(
                    "PREDICATE FAIL at step {step} cell {i}: proposed={proposed} disagrees with validated table"
                )));
            }

            let prev_state_hash = row_state_hash(&curr_row)?;
            let budget_remaining = width * steps - governed_cell_updates;

            let authorized = tape.append(
                AppendRequest::new(
                    "InstructionAuthorized",
                    writer_id,
                    json!({
                        "program_id": "rule110_elementary_ca",
                        "step_index": governed_cell_updates,
                        "pc": i,
                        "instruction": {
                            "op": "APPLY_RULE_110",
                            "generation": step,
                            "cell_index": i,
                            "window": {"left": left, "center": center, "right": right},
                            "pattern_index": pattern,
                            "proposed_value": proposed,
                        },
                        "predicate": "RULE_110_TRUTH_TABLE_CASE_MATCH",
                        "budget_remaining": budget_remaining,
                    }),
                )
                .predicate_pass(),
            )?;
            last_authorization_head = authorized.authorization_head_after.clone();
            governed_tape_events += 1;

            curr_row[i] = proposed;
            let next_state_hash = row_state_hash(&curr_row)?;

            let applied = tape.append(
                AppendRequest::new(
                    "InstructionApplied",
                    writer_id,
                    json!({
                        "program_id": "rule110_elementary_ca",
                        "step_index": governed_cell_updates,
                        "pc_before": i,
                        "pc_after": i + 1,
                        "instruction": {
                            "op": "APPLY_RULE_110",
                            "generation": step,
                            "cell_index": i,
                            "window": {"left": left, "center": center, "right": right},
                        },
                        "prev_state_hash": prev_state_hash,
                        "next_state_hash": next_state_hash,
                    }),
                )
                .predicate_pass(),
            )?;
            governed_tape_events += 1;
            let _ = applied;
            governed_cell_updates += 1;
        }

        let row_hash = row_state_hash(&curr_row)?;
        let observed = tape.append(
            AppendRequest::new(
                "MachineStateObserved",
                writer_id,
                json!({
                    "program_id": "rule110_elementary_ca",
                    "step_index": governed_cell_updates - 1,
                    "state": {"row": curr_row, "step": step},
                    "state_hash": row_hash,
                }),
            )
            .predicate_pass(),
        )?;
        governed_tape_events += 1;
        let _ = observed;
        rows.push(curr_row.clone());
        prev_row = curr_row;
    }

    let final_row = rows.last().cloned().unwrap_or_default();
    let final_hash = row_state_hash(&final_row)?;
    let halted = tape.append(
        AppendRequest::new(
            "ComputationHalted",
            writer_id,
            json!({
                "program_id": "rule110_elementary_ca",
                "final_step_index": governed_cell_updates.saturating_sub(1),
                "final_state": {"row": final_row, "step": steps},
                "final_state_hash": final_hash,
                "halt_kind": "STEP_BUDGET_REACHED",
            }),
        )
        .predicate_pass(),
    )?;
    governed_tape_events += 1;

    let final_heads = tape
        .head_set()?
        .ok_or_else(|| WitnessError::Invalid("expected a post-genesis HeadSet".into()))?;
    debug_assert_eq!(final_heads.tape_tip, halted.event_id);

    Ok(Rule110Report {
        width,
        steps,
        governed_cell_updates,
        governed_tape_events,
        tape_tip: final_heads.tape_tip,
        accepted_head: final_heads.accepted_head,
        authorization_head: final_heads.authorization_head.or(last_authorization_head),
        rows,
    })
}

/// Render `rows` (generation 0..=N) as an ASCII spacetime diagram: `#` = 1, `.` = 0, one
/// line per generation, oldest first.
pub fn render_ascii_diagram(rows: &[Vec<u8>]) -> String {
    let mut out = String::new();
    for row in rows {
        for cell in row {
            out.push(if *cell == 1 { '#' } else { '.' });
        }
        out.push('\n');
    }
    out
}

// --- tape-only reconstruction (proves the diagram is reconstructible from tape alone) --

/// Walk the tape from `tape_tip` back to genesis (parent-only, non-merge commits — the
/// same topology every replay tool in this repo relies on) and return every committed
/// event body, GENESIS-FIRST.
pub fn walk_events_from_tip(repo: &Path, tape_tip: &str) -> Result<Vec<Value>, WitnessError> {
    let mut chain = Vec::new();
    let mut cursor = tape_tip.to_string();
    loop {
        let bytes = committed_body_bytes(repo, &cursor)?;
        let body: Value = serde_json::from_slice(&bytes)?;
        chain.push(body);
        let parents = commit_parents(repo, &cursor)?;
        match parents.as_slice() {
            [] => break,
            [parent] => cursor = parent.clone(),
            _ => {
                return Err(WitnessError::Invalid(
                    "tape commit had more than one parent (merge) — not a valid Tape".into(),
                ));
            }
        }
    }
    chain.reverse();
    Ok(chain)
}

/// Reconstruct EVERY generation's row purely from the tape's `MachineStateObserved`
/// events (plus generation 0 from `ComputationStarted`'s `initial_state`) — no reliance
/// on the in-process `Rule110Report::rows` buffer. This is the mechanical proof that
/// "every signal is reconstructible from tape" (constitution Art. 0.2 item 2) for this
/// witness's own spacetime diagram.
pub fn reconstruct_rows_from_tape(
    repo: &Path,
    tape_tip: &str,
) -> Result<Vec<Vec<u8>>, WitnessError> {
    let events = walk_events_from_tip(repo, tape_tip)?;
    let mut rows: Vec<(usize, Vec<u8>)> = Vec::new();
    for event in &events {
        match event.get("event_type").and_then(Value::as_str) {
            Some("ComputationStarted")
                if event
                    .get("payload")
                    .and_then(|p| p.get("program_id"))
                    .and_then(Value::as_str)
                    == Some("rule110_elementary_ca") =>
            {
                let row = parse_row(&event["payload"]["initial_state"]["row"])?;
                rows.push((0, row));
            }
            Some("MachineStateObserved") => {
                let payload = &event["payload"];
                if payload.get("program_id").and_then(Value::as_str) != Some("rule110_elementary_ca")
                {
                    continue;
                }
                let step = payload["state"]["step"].as_u64().ok_or_else(|| {
                    WitnessError::Invalid("MachineStateObserved.state.step missing".into())
                })? as usize;
                let row = parse_row(&payload["state"]["row"])?;
                rows.push((step, row));
            }
            _ => {}
        }
    }
    rows.sort_by_key(|(step, _)| *step);
    Ok(rows.into_iter().map(|(_, row)| row).collect())
}

fn parse_row(value: &Value) -> Result<Vec<u8>, WitnessError> {
    value
        .as_array()
        .ok_or_else(|| WitnessError::Invalid("row must be a JSON array".into()))?
        .iter()
        .map(|v| {
            v.as_u64()
                .filter(|n| *n <= 1)
                .map(|n| n as u8)
                .ok_or_else(|| WitnessError::Invalid("row cell must be 0 or 1".into()))
        })
        .collect()
}

// --- second witness: reuse the existing (C1a) two-counter Minsky-machine crate ---------

#[derive(Debug, Clone)]
pub struct TmReport {
    pub program_id: String,
    pub steps_executed_hint: String,
    pub final_state_summary: String,
    pub governed_tape_events: usize,
    pub tape_tip: String,
    pub accepted_head: String,
    pub authorization_head: Option<String>,
}

/// Run one fixture program from the ALREADY-SHIPPED `turing-witness` crate
/// (`crates/turing-witness/src/lib.rs::tc3_program_fixtures`) end-to-end through the same
/// governed append path, on a fresh tape repo at `repo`. This crate does not reimplement
/// the two-counter Minsky-machine interpreter, emitter, or reducer — it only reads the
/// public API, which is the "coordinate with nothing else / read-only w.r.t. other atoms'
/// files" discipline applied to code reuse.
pub fn run_tm_program(
    repo: &Path,
    writer_id: &str,
    program_id: &str,
) -> Result<TmReport, WitnessError> {
    append_genesis(repo)?;

    let fixtures = turing_witness::tc3_program_fixtures()
        .map_err(|e| WitnessError::Invalid(format!("tc3_program_fixtures: {e}")))?;
    let fixture = fixtures
        .into_iter()
        .find(|f| f.program_id == program_id)
        .ok_or_else(|| WitnessError::Invalid(format!("unknown TM fixture {program_id:?}")))?;

    let run = turing_witness::emit_witness_run(
        repo,
        writer_id,
        &fixture.program_id,
        &fixture.program,
        fixture.initial_state,
        fixture.step_budget,
    )
    .map_err(|e| WitnessError::Invalid(format!("emit_witness_run: {e}")))?;

    let tape = Append::open(repo)?;
    let final_heads = tape
        .head_set()?
        .ok_or_else(|| WitnessError::Invalid("expected a post-genesis HeadSet".into()))?;

    // events.len() (from emit_witness_run) + genesis, mirroring the counting convention
    // used for the Rule 110 report above.
    let governed_tape_events = run.events.len() + 1;

    Ok(TmReport {
        program_id: run.program_id,
        steps_executed_hint: format!("step_budget={}", fixture.step_budget),
        final_state_summary: format!("{:?}", run.final_state),
        governed_tape_events,
        tape_tip: final_heads.tape_tip,
        accepted_head: final_heads.accepted_head,
        authorization_head: final_heads.authorization_head,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rule110_matches_the_standard_wolfram_table() {
        // 111,110,101,100,011,010,001,000 -> 0,1,1,0,1,1,1,0
        let expect = [
            ((1, 1, 1), 0u8),
            ((1, 1, 0), 1),
            ((1, 0, 1), 1),
            ((1, 0, 0), 0),
            ((0, 1, 1), 1),
            ((0, 1, 0), 1),
            ((0, 0, 1), 1),
            ((0, 0, 0), 0),
        ];
        for ((l, c, r), v) in expect {
            assert_eq!(rule110_propose(l, c, r), v, "propose {l}{c}{r}");
            assert_eq!(rule110_validate(l, c, r), v, "validate {l}{c}{r}");
            assert!(rule110_predicate_pass(l, c, r, v));
        }
    }

    #[test]
    fn predicate_selftest_passes() {
        rule110_predicate_selftest().expect("predicate self-test must pass");
    }

    #[test]
    fn predicate_rejects_a_forged_proposal() {
        // 000 truly maps to 0; a forged proposal of 1 must be rejected.
        assert!(!rule110_predicate_pass(0, 0, 0, 1));
        // 011 truly maps to 1; a forged proposal of 0 must be rejected.
        assert!(!rule110_predicate_pass(0, 1, 1, 0));
    }

    #[test]
    fn run_and_replay_small_rule110_governed_tape() {
        let dir = tempfile::tempdir().expect("tempdir");
        let repo = dir.path();
        turing_git_tape::git::init_sha256(repo).expect("init sha256 repo");
        let report =
            run_rule110(repo, "writer:test", vec![0, 0, 0, 1, 0, 0, 0], 4).expect("run rule110");
        assert_eq!(report.width, 7);
        assert_eq!(report.steps, 4);
        assert_eq!(report.governed_cell_updates, 7 * 4);
        assert_eq!(report.rows.len(), 5); // generation 0..=4

        let reconstructed = reconstruct_rows_from_tape(repo, &report.tape_tip)
            .expect("reconstruct rows from tape");
        assert_eq!(reconstructed, report.rows, "tape reconstruction must match live run");
    }

    #[test]
    fn run_and_replay_tm_multiply_small() {
        let dir = tempfile::tempdir().expect("tempdir");
        let repo = dir.path();
        turing_git_tape::git::init_sha256(repo).expect("init sha256 repo");
        let report =
            run_tm_program(repo, "writer:test", "multiply_small").expect("run multiply_small");
        assert_eq!(report.program_id, "multiply_small");
        assert!(report.governed_tape_events > 1);
    }
}
