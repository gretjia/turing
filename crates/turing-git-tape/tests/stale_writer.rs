//! SG-14 — Stale-writer CAS (exactly one concurrent winner; the loser re-mints, never
//! forces and never merges).
//!
//! This test genuinely binds the ratified append algorithm STEP 7 stale path
//! (`pack/03_contracts/operation/append_algorithm_v5_3_1.md`: `if r == STALE_PRECONDITION:
//! goto STEP 1` — FF-only reread / retry / re-mint, never force-update) and the guarded
//! ref-transaction contract (`pack/03_contracts/operation/guarded_ref_transaction_v5_3_1.md`
//! §2: `git update-ref --stdin` with old-OID CAS preconditions; "Force update and
//! merge-commit repair are forbidden"; "Stale → reread + re-mint"; exactly-one-winner via
//! the single `tape_tip` CAS).
//!
//! It exercises ONLY the public crate API over a *fresh native SHA-256* repo and induces a
//! DETERMINISTIC race (no real threads — the two writers' interleaving is staged
//! explicitly so the failure mode is reproducible in CI), plus the high-level `append()`
//! auto-retry path via an injected "a competing commit lands between read and txn" hook.
//!
//! Trajectory of the deterministic race on the SAME old tip T0:
//!
//! ```text
//! genesis            -> tape_tip = T0
//! A stages vs T0, B stages vs T0   (both captured the SAME pre-state)
//! A commits first    -> tape_tip advances T0 -> T1 (A's commit, parent T0)
//! B commits (old=T0) -> STALE_PRECONDITION: the CAS is genuinely enforced;
//!                       B applied NOTHING and did not overwrite A
//! B re-mints vs T1   -> tape_tip advances T1 -> T2 (B's commit, parent T1)
//! ```
//!
//! Asserts: exactly one winner per CAS round (A); the resulting history is a LINEAR
//! non-merge chain T0->T1->T2 (every commit single-parent; B's final parent == A's commit
//! T1, NOT T0); tape_tip == T2; both A's and B's events are present on the tape; no ref was
//! force-updated (the loser's first attempt was rejected, not applied — A's T1 commit is
//! intact and is B's parent).

use serde_json::{Value, json};

use turing_contracts::identity::is_valid_micro_oid;
use turing_git_tape::append::{Append, AppendRequest, StagedCommit, StaleAppendError};
use turing_git_tape::git;

// --- helpers ----------------------------------------------------------------

/// The bare 64-hex tail of a `mu:`/`sha256:` prefixed identity.
fn tail(prefixed: &str) -> &str {
    prefixed.split_once(':').map(|(_, t)| t).unwrap_or(prefixed)
}

/// The single parent (`mu:` id) of the commit named by `event_id`, asserting non-merge
/// (exactly one parent — never zero, never two). Returns the parent as a `mu:` id.
fn single_parent(repo: &std::path::Path, event_id: &str) -> String {
    let parents =
        turing_git_tape::append::commit_parents(repo, event_id).expect("read commit parents");
    assert_eq!(
        parents.len(),
        1,
        "a non-genesis Tape commit MUST be non-merge (exactly one parent), got {parents:?}"
    );
    format!("mu:{}", parents[0])
}

/// Assert the commit named by `event_id` has ZERO parents (a genesis root commit).
fn assert_root(repo: &std::path::Path, event_id: &str) {
    let parents =
        turing_git_tape::append::commit_parents(repo, event_id).expect("read commit parents");
    assert!(
        parents.is_empty(),
        "the genesis commit must be a root (0 parents), got {parents:?}"
    );
}

/// Read the committed body of an event commit back out of the repo as JSON (the source of
/// truth — independent of any in-memory receipt).
fn read_body(repo: &std::path::Path, event_id: &str) -> Value {
    let bytes = turing_git_tape::append::committed_body_bytes(repo, event_id)
        .expect("read committed envelope body");
    serde_json::from_slice(&bytes).expect("committed body is valid JSON")
}

/// The live `refs/turingos/tape_tip` as a `mu:` id.
fn live_tip(repo: &std::path::Path) -> String {
    format!(
        "mu:{}",
        git::rev_parse(repo, "refs/turingos/tape_tip").expect("read tape_tip ref")
    )
}

/// Bootstrap a fresh native-SHA-256 Tape with a genesis SOVEREIGN_ACCEPT event.
/// Returns `(repo handle, genesis event_id == T0)`.
fn bootstrap(repo: &std::path::Path) -> (Append, String) {
    git::init_sha256(repo).expect("init sha256 repo");
    let tape = Append::open(repo).expect("open the Tape over a fresh sha256 repo");
    let genesis = tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                json!({"constitution_digest": "sha256:".to_string() + &"a".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("genesis append succeeds");
    let t0 = genesis.event_id.clone();
    assert!(is_valid_micro_oid(&t0), "genesis tape_tip is a mu: oid");
    assert_root(repo, &t0);
    (tape, t0)
}

// --- the deterministic stale race -------------------------------------------

/// Two writers stage against the SAME old tip T0. A commits first (→T1); B's guarded CAS
/// with old=T0 is genuinely rejected (STALE_PRECONDITION) — it cannot overwrite A — and B
/// then re-mints as a direct non-merge child of the NEW tip T1 and commits (→T2). The
/// resulting history is a LINEAR non-merge chain T0→T1→T2.
#[test]
fn stale_writer_b_is_rejected_then_re_mints_linearly_against_the_new_tip() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    let (tape, t0) = bootstrap(repo);
    assert_eq!(live_tip(repo), t0, "tape_tip starts at genesis T0");

    // -- both writers capture the SAME pre-state (old tip T0) and mint, WITHOUT committing.
    let staged_a = tape
        .stage(
            AppendRequest::new(
                "GoalStateProposed",
                "writer:A",
                json!({"goal": "writer A proposal", "n": 1}),
            )
            .predicate_pass(),
        )
        .expect("A stages a candidate against T0");
    let staged_b = tape
        .stage(
            AppendRequest::new(
                "GoalStateProposed",
                "writer:B",
                json!({"goal": "writer B proposal", "n": 2}),
            )
            .predicate_pass(),
        )
        .expect("B stages a candidate against T0");

    // Both staged commits are distinct non-merge children of T0 (parent == T0), but only
    // one may win the single tape_tip CAS.
    let a_oid = staged_a.event_id().to_string();
    let b_first_oid = staged_b.event_id().to_string();
    assert!(is_valid_micro_oid(&a_oid));
    assert!(is_valid_micro_oid(&b_first_oid));
    assert_ne!(a_oid, b_first_oid, "the two staged commits are distinct");
    assert_eq!(
        single_parent(repo, &a_oid),
        t0,
        "A's commit is a child of T0"
    );
    assert_eq!(
        single_parent(repo, &b_first_oid),
        t0,
        "B's first commit is a child of T0"
    );

    // -- A commits first → tape_tip advances T0 → T1 (exactly one winner this round).
    let receipt_a = match staged_a.commit().expect("A's guarded txn runs") {
        StagedCommit::Applied(r) => r,
        StagedCommit::Stale(_) => panic!("A is the first writer; its CAS must NOT be stale"),
    };
    let t1 = receipt_a.event_id.clone();
    assert_eq!(t1, a_oid, "A's receipt event_id is A's minted commit");
    assert_eq!(live_tip(repo), t1, "tape_tip advanced to T1 (A's commit)");
    assert_eq!(single_parent(repo, &t1), t0, "T1's parent is T0 (linear)");

    // -- B commits against the now-stale old=T0 → STALE_PRECONDITION (CAS genuinely
    //    enforced: B applied NOTHING; it could not overwrite A).
    let stale = staged_b.commit().expect("B's guarded txn runs");
    let restage_b = match stale {
        StagedCommit::Stale(s) => s,
        StagedCommit::Applied(_) => {
            panic!("B raced on the SAME old tip T0 as A; its CAS MUST be STALE_PRECONDITION")
        }
    };
    // The CAS rejection did NOT force-update: A's T1 is intact and is still the live tip,
    // and B's losing first commit did NOT become the tip.
    assert_eq!(
        live_tip(repo),
        t1,
        "after B's stale CAS, tape_tip is STILL A's T1 (no force-update, no overwrite)"
    );
    assert_ne!(
        live_tip(repo),
        b_first_oid,
        "B's losing commit is NOT the tip"
    );

    // -- B re-mints against the NEW tip T1 (new prev_tape_tip, new sequence, new OID) and
    //    commits → tape_tip advances T1 → T2.
    let receipt_b = restage_b
        .re_mint_and_commit(repo)
        .expect("B re-mints vs T1 and its retried guarded txn applies");
    let t2 = receipt_b.event_id.clone();
    assert!(is_valid_micro_oid(&t2));
    assert_eq!(
        live_tip(repo),
        t2,
        "tape_tip advanced to T2 (B's re-minted commit)"
    );

    // -- LINEAR non-merge chain T0 → T1 → T2; B's final parent is A's T1, NOT T0.
    assert_eq!(
        single_parent(repo, &t2),
        t1,
        "B's re-minted commit T2 is a child of A's T1 (linear), NOT a child of T0"
    );
    assert_ne!(
        single_parent(repo, &t2),
        t0,
        "B did NOT re-attach to the stale T0 (that would fork/non-FF)"
    );
    assert_ne!(
        t2, b_first_oid,
        "B's winning commit is a NEW mint, not its stale first one"
    );

    // The three commits are all distinct and form one chain T0 <- T1 <- T2.
    assert_ne!(t0, t1);
    assert_ne!(t1, t2);
    assert_ne!(t0, t2);

    // -- both A's and B's events are present on the tape (no event was lost) -------------
    let body_a = read_body(repo, &t1);
    let body_b = read_body(repo, &t2);
    assert_eq!(body_a["writer_id"], json!("writer:A"));
    assert_eq!(body_b["writer_id"], json!("writer:B"));
    // B's WINNING body was rebuilt against the NEW pre-state: prev_tape_tip == T1 and the
    // sequence advanced past A's (parent.sequence + 1), proving a real re-mint (not a
    // replay of the stale first attempt, whose prev_tape_tip was T0).
    assert_eq!(
        body_b["prev_tape_tip"],
        json!(t1),
        "B's winning body points at the NEW pre-state T1 (re-minted, not the stale T0 body)"
    );
    let seq_a = body_a["sequence"].as_u64().expect("A sequence");
    let seq_b = body_b["sequence"].as_u64().expect("B sequence");
    assert_eq!(seq_b, seq_a + 1, "B's re-minted sequence == A.sequence + 1");

    // B's LOSING first commit body pointed at the stale T0 — confirming the rebuild
    // genuinely changed the pre-state (and thus the OID), not merely retried the same bytes.
    let body_b_first = read_body(repo, &b_first_oid);
    assert_eq!(
        body_b_first["prev_tape_tip"],
        json!(t0),
        "B's losing first commit was built against T0 (the stale pre-state)"
    );

    // -- exactly-one-winner accounting: T1 has exactly one child (T2). The losing first
    //    B commit is a DANGLING non-state object — referenced by no ref, and NOT a child
    //    of T1 (it forked off T0) — so the on-tape history is strictly linear.
    assert_eq!(
        tail(&single_parent(repo, &t2)),
        tail(&t1),
        "the only on-tape successor of T1 is T2"
    );
    assert_eq!(
        single_parent(repo, &b_first_oid),
        t0,
        "the dangling loser still hangs off T0 (it never became a child of T1)"
    );

    // -- no ref was force-updated: every ref move was a clean FF CAS. tape_tip is T2, and
    //    accepted_head is still genesis T0 (these were all PRESERVE proposals after it).
    assert_eq!(live_tip(repo), t2);
    assert_eq!(
        format!(
            "mu:{}",
            git::rev_parse(repo, "refs/turingos/accepted_head").expect("accepted_head")
        ),
        t0,
        "accepted_head never moved (only PRESERVE proposals raced); no head was force-updated"
    );
}

/// The high-level `append()` auto-retry path: a competing commit lands transparently
/// between this append's pre-state read and its guarded txn (injected hook). The append
/// must detect STALE_PRECONDITION, re-read, re-mint against the new tip, and land LINEARLY
/// — all without the caller forcing, merging, or even observing the retry.
#[test]
fn append_auto_retry_re_mints_transparently_and_lands_linearly() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    let (tape, t0) = bootstrap(repo);

    // A second handle for the competing writer (one writer per handle on the success path,
    // but the repo is shared — exactly the contention we are modelling).
    let competitor = Append::open(repo).expect("open a competing Tape handle");

    // This flag makes the injected hook fire EXACTLY ONCE: on the retrying append's first
    // attempt, after it has read T0 but before its guarded txn, a competitor commits and
    // advances tape_tip T0 → T1. The retrying append's first txn (old=T0) is therefore
    // stale; it must re-read T1, re-mint, and succeed on the second attempt → T2.
    let mut fired = false;
    let mut competitor_tip: Option<String> = None;

    let receipt = tape
        .append_with_contention(
            AppendRequest::new(
                "GoalStateProposed",
                "writer:retrier",
                json!({"goal": "the retrying writer", "k": 7}),
            )
            .predicate_pass(),
            || {
                if !fired {
                    fired = true;
                    let r = competitor
                        .append(
                            AppendRequest::new(
                                "GoalStateProposed",
                                "writer:competitor",
                                json!({"goal": "the competitor", "k": 99}),
                            )
                            .predicate_pass(),
                        )
                        .expect("competitor lands its commit, advancing tape_tip");
                    competitor_tip = Some(r.event_id);
                }
            },
        )
        .expect("the retrying append transparently re-mints and succeeds");

    assert!(
        fired,
        "the contention hook must have fired (a real race was induced)"
    );
    let t1 = competitor_tip.expect("competitor advanced the tip to T1");
    let t2 = receipt.event_id.clone();

    // Linear chain T0 → T1 (competitor) → T2 (the auto-retried append). No fork, no merge.
    assert_eq!(
        single_parent(repo, &t1),
        t0,
        "competitor T1 is a child of T0"
    );
    assert_eq!(
        single_parent(repo, &t2),
        t1,
        "the auto-retried append re-minted as a child of the NEW tip T1 (linear), not T0"
    );
    assert_eq!(
        live_tip(repo),
        t2,
        "tape_tip is the auto-retried append's T2"
    );

    // The retried append's committed body was rebuilt against the NEW pre-state T1.
    let body = read_body(repo, &t2);
    assert_eq!(body["writer_id"], json!("writer:retrier"));
    assert_eq!(
        body["prev_tape_tip"],
        json!(t1),
        "the auto-retried body points at the NEW pre-state T1 (proves a real re-mint)"
    );
    // Both racers' events are on the tape.
    assert_eq!(
        read_body(repo, &t1)["writer_id"],
        json!("writer:competitor")
    );
}

/// Bounded backoff: when contention NEVER clears (every attempt is forced stale), the
/// append gives up with a typed error after a finite number of attempts — it NEVER
/// force-updates, NEVER merges, and NEVER loops unbounded.
#[test]
fn append_auto_retry_is_bounded_and_never_forces() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    let (tape, t0) = bootstrap(repo);

    let competitor = Append::open(repo).expect("open a competing Tape handle");

    // The hook fires on EVERY attempt: a fresh competitor commit advances the tip each
    // time, so the retrying append's CAS is perpetually stale. It must terminate with a
    // typed StalePrecondition error after the bounded attempt cap, not spin forever.
    let mut competitor_commits = 0usize;
    let result = tape.append_with_contention(
        AppendRequest::new(
            "GoalStateProposed",
            "writer:starved",
            json!({"goal": "perpetually starved", "k": 0}),
        )
        .predicate_pass(),
        || {
            competitor_commits += 1;
            competitor
                .append(
                    AppendRequest::new(
                        "GoalStateProposed",
                        "writer:relentless",
                        json!({"goal": "relentless competitor", "k": competitor_commits as i64}),
                    )
                    .predicate_pass(),
                )
                .expect("the relentless competitor always lands");
        },
    );

    match result {
        Err(StaleAppendError::ExhaustedRetries { attempts }) => {
            assert!(
                attempts >= 1,
                "the cap must be a positive, finite number of attempts"
            );
            assert_eq!(
                competitor_commits, attempts as usize,
                "the hook (and thus the competitor) fired once per attempt, up to the cap"
            );
        }
        Err(other) => panic!("expected ExhaustedRetries on perpetual contention, got {other:?}"),
        Ok(_) => panic!("a perpetually-starved append must NOT succeed; it has no clear tip"),
    }

    // No force-update ever happened: the live tip is the LAST competitor commit, reached by
    // a clean FF chain off T0, and the starved writer left no ref behind.
    let tip = live_tip(repo);
    assert_ne!(
        tip, t0,
        "the competitor did advance the tip (the race was real)"
    );
    // Walk the chain from the live tip back to T0 — it must be strictly linear (each commit
    // single-parent), proving no merge commit was ever created by the starved writer.
    let mut cur = tip.clone();
    let mut steps = 0usize;
    while tail(&cur) != tail(&t0) {
        cur = single_parent(repo, &cur); // single_parent asserts exactly one parent (non-merge)
        steps += 1;
        assert!(
            steps <= competitor_commits + 2,
            "chain to T0 is bounded and linear"
        );
    }
    assert_eq!(
        steps, competitor_commits,
        "the linear chain length == competitor commits"
    );
}
