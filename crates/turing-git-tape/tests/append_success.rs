//! SG-12 — Successful append (happy path: PASS / predicate-free NOT_RUN).
//!
//! This test genuinely binds the ratified append algorithm
//! (`pack/03_contracts/operation/append_algorithm_v5_3_1.md`, STEP 1..8) and the
//! three-ref law (`greenfield_spec_v5_3_1.md` §5.2-5.3, `event_registry_v5_3_1.json`).
//! It exercises ONLY the public crate API and uses a *fresh native SHA-256* repo.
//!
//! Trajectory (each step asserts the registry-derived head movement):
//!   1. GENESIS  `SystemConstitutionAccepted` (SOVEREIGN_ACCEPT, befores=null, root
//!      commit) → exactly one non-merge commit; tape_tip AND accepted_head become its
//!      `mu:`+64hex OID; authorization_head still null.
//!   2. PROPOSAL `GoalStateProposed` (PRESERVE) → ONLY tape_tip advances; accepted_head
//!      and authorization_head byte-unchanged; one new commit; parent == prior tape_tip.
//!   3. AUTHORIZATION `AtomAuthorized` (ADVANCE) + PASS → tape_tip AND authorization_head
//!      advance; accepted_head unchanged.
//!   4. SOVEREIGN_ACCEPT `CandidateAccepted` (ADVANCE) + PASS → tape_tip AND accepted_head
//!      advance; authorization_head unchanged.
//!
//! For each step the test verifies: event_id is `mu:`+64hex; the committed body carries
//! NO `event_id` field and validates the 16-field MicroEventEnvelope shape;
//! content_digest == payload_hash == `sha256:` + sha256(JCS(payload)); the receipt fields
//! match the committed body + the new HeadSet; commits are non-merge (single parent, or
//! zero parents for genesis); and the head that moved matches the registry class.

use std::collections::BTreeSet;

use serde_json::{Value, json};

use turing_contracts::identity::is_valid_micro_oid;
use turing_git_tape::append::{Append, AppendRequest, CommittedReceipt, HeadMoved};
use turing_git_tape::git;

// --- helpers ----------------------------------------------------------------

/// A 64-char-lowercase-hex `mu:` identity.
fn assert_micro_oid(label: &str, id: &str) {
    assert!(
        is_valid_micro_oid(id),
        "{label} must be a greenfield MicroOid `mu:`+64 lowercase hex, got {id:?}"
    );
}

/// The bare 64-hex tail of a `mu:`/`sha256:` prefixed identity.
fn tail(prefixed: &str) -> &str {
    prefixed.split_once(':').map(|(_, t)| t).unwrap_or(prefixed)
}

/// Read the committed body of a Micro event commit (the JCS envelope bytes on the
/// commit's tree blob) back out of the repo, parsed as JSON. This proves what was
/// actually persisted, independent of the in-memory receipt.
fn read_committed_body(repo: &std::path::Path, event_id: &str) -> Value {
    let bytes = turing_git_tape::append::committed_body_bytes(repo, event_id)
        .expect("read committed envelope body for the event commit");
    serde_json::from_slice(&bytes).expect("committed body is valid JSON")
}

/// The 16 required MicroEventEnvelope.v1 fields. `event_id` and `head_set_after` are
/// FORBIDDEN in the committed body.
const ENVELOPE_REQUIRED: &[&str] = &[
    "schema_id",
    "event_type",
    "writer_id",
    "authority_epoch",
    "sequence",
    "prev_tape_tip",
    "authorization_head_before",
    "accepted_head_before",
    "head_effect",
    "event_schema_id",
    "predicate_product",
    "reason_digest",
    "verified",
    "content_digest",
    "payload_hash",
    "payload",
];

/// Validate the committed body has EXACTLY the 16 envelope fields (no more, no fewer),
/// never `event_id`/`head_set_after`, and the frozen const/shape constraints.
fn assert_envelope_shape(body: &Value) {
    let obj = body.as_object().expect("committed body is a JSON object");

    let keys: BTreeSet<&str> = obj.keys().map(String::as_str).collect();
    let required: BTreeSet<&str> = ENVELOPE_REQUIRED.iter().copied().collect();
    assert_eq!(
        keys, required,
        "committed body must have EXACTLY the 16 MicroEventEnvelope.v1 fields"
    );

    assert!(
        !obj.contains_key("event_id"),
        "committed body MUST NOT contain event_id (a commit cannot embed its own OID)"
    );
    assert!(
        !obj.contains_key("head_set_after"),
        "committed body MUST NOT contain head_set_after (self-reference-free)"
    );

    assert_eq!(obj["schema_id"], json!("micro_event_envelope.v1"));
    assert!(
        obj["authority_epoch"].is_u64(),
        "authority_epoch is an integer"
    );
    assert!(obj["sequence"].is_u64(), "sequence is an integer");
    assert!(obj["verified"].is_boolean(), "verified is a bool");
    assert!(obj["payload"].is_object(), "payload is an object");

    let head_effect = obj["head_effect"].as_str().expect("head_effect string");
    assert!(
        head_effect == "ADVANCE" || head_effect == "PRESERVE",
        "head_effect ∈ {{ADVANCE, PRESERVE}}, got {head_effect:?}"
    );
    let product = obj["predicate_product"]
        .as_str()
        .expect("predicate_product");
    assert!(
        matches!(product, "PASS" | "FAIL" | "NOT_RUN"),
        "predicate_product ∈ {{PASS, FAIL, NOT_RUN}}, got {product:?}"
    );

    for k in ["content_digest", "payload_hash", "reason_digest"] {
        let v = obj[k].as_str().unwrap_or_else(|| panic!("{k} is a string"));
        assert!(
            v.starts_with("sha256:") && v.len() == "sha256:".len() + 64,
            "{k} must be `sha256:`+64hex, got {v:?}"
        );
    }
}

/// Recompute `sha256(JCS(payload))` independently (via the contracts codec) and assert
/// content_digest == payload_hash == that value.
fn assert_payload_digest(body: &Value) {
    let payload = &body["payload"];
    let jcs = turing_contracts::jcs::canonicalize(payload).expect("canonicalize payload");
    let expected = turing_contracts::jcs::sha256_hex(&jcs);

    let content_digest = body["content_digest"].as_str().unwrap();
    let payload_hash = body["payload_hash"].as_str().unwrap();
    assert_eq!(
        content_digest, payload_hash,
        "content_digest must equal payload_hash"
    );
    assert_eq!(
        tail(content_digest),
        expected,
        "content_digest must equal sha256(JCS(payload))"
    );
}

#[test]
fn append_envelope_requires_seven_fields() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    git::init_sha256(repo).expect("init sha256 repo");

    let tape = Append::open(repo).expect("open the Tape over a fresh sha256 repo");
    let rcpt = tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                json!({"constitution_digest": "sha256:".to_string() + &"a".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("genesis append succeeds");

    let body = read_committed_body(repo, &rcpt.event_id);
    let obj = body.as_object().expect("committed body is an object");
    let required_append_fields = [
        "writer_id",
        "authority_epoch",
        "prev_tape_tip",
        "accepted_head_before",
        "head_effect",
        "event_schema_id",
        "payload_hash",
    ];

    for field in required_append_fields {
        assert!(
            obj.contains_key(field),
            "append envelope must carry required field {field}"
        );

        let mut tampered = body.clone();
        tampered.as_object_mut().expect("body object").remove(field);
        assert!(
            turing_contracts::envelope::MicroEventEnvelope::from_jcs_value(&tampered).is_err(),
            "missing required append field {field} must fail closed"
        );
    }

    assert_eq!(body["writer_id"], json!("writer:genesis"));
    assert_eq!(body["authority_epoch"], json!(0));
    assert_eq!(body["prev_tape_tip"], Value::Null);
    assert_eq!(body["accepted_head_before"], Value::Null);
    assert_eq!(body["head_effect"], json!("ADVANCE"));
    assert_eq!(
        body["event_schema_id"],
        json!("system_constitution_accepted.v1")
    );
    assert_payload_digest(&body);
}

#[test]
fn predicate_fail_records_failure_node_and_preserves_heads() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
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

    let failure = tape
        .append(
            AppendRequest::new(
                "FailureNode",
                "writer:predicate",
                json!({
                    "verified": false,
                    "failure_class": "SEMANTIC_FAILURE",
                    "candidate_digest": "sha256:".to_string() + &"b".repeat(64),
                    "observation_digest": "sha256:".to_string() + &"c".repeat(64),
                    "detail": "predicate failed",
                }),
            )
            .predicate_fail(),
        )
        .expect("failure node append succeeds");

    assert_eq!(failure.head_moved, HeadMoved::None);
    assert_eq!(failure.accepted_head_after, genesis.event_id);
    assert_eq!(failure.tape_tip_after, failure.event_id);

    let body = read_committed_body(repo, &failure.event_id);
    assert_eq!(body["event_type"], json!("FailureNode"));
    assert_eq!(body["predicate_product"], json!("FAIL"));
    assert_eq!(body["verified"], json!(false));
    assert_receipt_consistent(
        repo,
        &failure,
        &body,
        HeadMoved::None,
        Some(&genesis.event_id),
    );
}

/// Assert the commit named by `event_id` is non-merge: zero parents for genesis,
/// exactly one otherwise, and that single parent equals `expected_parent` (a `mu:` id,
/// or `None` for the root commit).
fn assert_non_merge_parent(repo: &std::path::Path, event_id: &str, expected_parent: Option<&str>) {
    let parents =
        turing_git_tape::append::commit_parents(repo, event_id).expect("read commit parents");
    match expected_parent {
        None => assert!(
            parents.is_empty(),
            "genesis commit must be a root (0 parents)"
        ),
        Some(p) => {
            assert_eq!(
                parents.len(),
                1,
                "a Tape commit is non-merge (exactly 1 parent)"
            );
            assert_eq!(
                format!("mu:{}", parents[0]),
                p,
                "the single parent must be the prior tape_tip"
            );
        }
    }
}

/// Cross-check a receipt against the committed body and the registry-declared movement.
fn assert_receipt_consistent(
    repo: &std::path::Path,
    rcpt: &CommittedReceipt,
    body: &Value,
    expected_move: HeadMoved,
    prev_tip: Option<&str>,
) {
    assert_micro_oid("receipt.event_id", &rcpt.event_id);
    assert_eq!(
        rcpt.tape_tip_after, rcpt.event_id,
        "tape_tip always advances to the new event_id"
    );
    assert_envelope_shape(body);
    assert_payload_digest(body);
    assert_non_merge_parent(repo, &rcpt.event_id, prev_tip);

    // The receipt's pre-state echo must equal what was committed.
    assert_eq!(
        body["prev_tape_tip"],
        prev_tip.map(Value::from).unwrap_or(Value::Null),
        "committed prev_tape_tip must equal the observed tape_tip"
    );

    assert_eq!(
        rcpt.head_moved, expected_move,
        "the moved head must match the registry class + PASS"
    );

    // tape_tip ref in the repo now equals the receipt.
    let live_tip = git::rev_parse(repo, "refs/turingos/tape_tip").expect("read tape_tip ref");
    assert_eq!(
        format!("mu:{live_tip}"),
        rcpt.tape_tip_after,
        "live tape_tip ref must equal the receipt"
    );
}

// --- the trajectory ---------------------------------------------------------

#[test]
fn three_refs_advance_rules() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    git::init_sha256(repo).expect("init sha256 repo");

    let tape = Append::open(repo).expect("open the Tape over a fresh sha256 repo");

    // Before genesis there is no HeadSet (no non-null accepted_head can exist).
    assert!(
        tape.head_set().expect("read head set").is_none(),
        "a fresh repo has no coherent HeadSet until genesis"
    );

    // -- 1. GENESIS: SystemConstitutionAccepted (SOVEREIGN_ACCEPT, root, befores=null) --
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

    assert_micro_oid("genesis.event_id", &genesis.event_id);
    let g_body = read_committed_body(repo, &genesis.event_id);
    assert_receipt_consistent(repo, &genesis, &g_body, HeadMoved::AcceptedHead, None);

    // Genesis befores are all null in the committed body.
    assert_eq!(g_body["prev_tape_tip"], Value::Null);
    assert_eq!(g_body["accepted_head_before"], Value::Null);
    assert_eq!(g_body["authorization_head_before"], Value::Null);
    assert_eq!(g_body["sequence"], json!(0), "genesis sequence is 0");

    let hs = tape
        .head_set()
        .expect("head set after genesis")
        .expect("a coherent HeadSet now exists");
    assert_eq!(hs.tape_tip, genesis.event_id, "tape_tip == genesis");
    assert_eq!(
        hs.accepted_head, genesis.event_id,
        "accepted_head == genesis"
    );
    assert_eq!(hs.authorization_head, None, "authorization_head still null");
    assert_eq!(genesis.accepted_head_after, genesis.event_id);
    assert_eq!(genesis.authorization_head_after, None);

    // -- 2. PROPOSAL: GoalStateProposed (PRESERVE) → only tape_tip moves --
    let prev_tip = genesis.event_id.clone();
    let prev_accepted = hs.accepted_head.clone();
    let proposal = tape
        .append(
            AppendRequest::new(
                "GoalStateProposed",
                "writer:planner",
                json!({"goal": "ship M0", "n": 1}),
            )
            .predicate_pass(),
        )
        .expect("proposal append succeeds");

    let p_body = read_committed_body(repo, &proposal.event_id);
    assert_receipt_consistent(repo, &proposal, &p_body, HeadMoved::None, Some(&prev_tip));
    assert_eq!(p_body["head_effect"], json!("PRESERVE"));
    assert_eq!(p_body["sequence"], json!(1), "sequence increments to 1");
    // Heads carried forward unchanged.
    assert_eq!(
        proposal.accepted_head_after, prev_accepted,
        "accepted_head unchanged"
    );
    assert_eq!(
        proposal.authorization_head_after, None,
        "authorization_head unchanged"
    );
    assert_ne!(proposal.tape_tip_after, prev_tip, "tape_tip advanced");
    // Live refs: tape_tip moved, accepted_head pinned at genesis.
    assert_eq!(
        format!(
            "mu:{}",
            git::rev_parse(repo, "refs/turingos/accepted_head").unwrap()
        ),
        prev_accepted,
        "accepted_head ref must NOT have moved"
    );

    // -- 3. AUTHORIZATION: AtomAuthorized (ADVANCE) + PASS → authorization_head moves --
    let prev_tip = proposal.event_id.clone();
    let auth = tape
        .append(
            AppendRequest::new(
                "AtomAuthorized",
                "writer:authority",
                json!({"atom_digest": "sha256:".to_string() + &"b".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("authorization append succeeds");

    let a_body = read_committed_body(repo, &auth.event_id);
    assert_receipt_consistent(
        repo,
        &auth,
        &a_body,
        HeadMoved::AuthorizationHead,
        Some(&prev_tip),
    );
    assert_eq!(a_body["head_effect"], json!("ADVANCE"));
    assert_eq!(
        auth.authorization_head_after,
        Some(auth.event_id.clone()),
        "auth head == this event"
    );
    assert_eq!(
        auth.accepted_head_after, prev_accepted,
        "accepted_head still genesis"
    );
    // The committed pre-state must carry the prior (null) authorization head.
    assert_eq!(a_body["authorization_head_before"], Value::Null);

    // -- 4. SOVEREIGN_ACCEPT: CandidateAccepted (ADVANCE) + PASS → accepted_head moves --
    let prev_tip = auth.event_id.clone();
    let prev_auth = auth.authorization_head_after.clone();
    let accept = tape
        .append(
            AppendRequest::new(
                "CandidateAccepted",
                "writer:authority",
                json!({"candidate_digest": "sha256:".to_string() + &"c".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("sovereign-accept append succeeds");

    let c_body = read_committed_body(repo, &accept.event_id);
    assert_receipt_consistent(
        repo,
        &accept,
        &c_body,
        HeadMoved::AcceptedHead,
        Some(&prev_tip),
    );
    assert_eq!(
        accept.accepted_head_after, accept.event_id,
        "accepted_head == this event"
    );
    assert_eq!(
        accept.authorization_head_after, prev_auth,
        "authorization_head carried forward (unchanged) on a SOVEREIGN_ACCEPT"
    );
    // The committed pre-state carries the prior authorization head (the AtomAuthorized OID).
    assert_eq!(
        c_body["authorization_head_before"]
            .as_str()
            .map(|s| s.to_string()),
        prev_auth.as_ref().map(|m| m.to_string()),
        "committed accepted_head_before/authorization_head_before echo the pre-state"
    );
    assert_eq!(
        c_body["accepted_head_before"],
        json!(prev_accepted),
        "accepted_head_before == genesis"
    );

    // Final coherent HeadSet: three distinct heads, all derived (never writer-trusted).
    let final_hs = tape.head_set().unwrap().expect("final HeadSet");
    assert_eq!(final_hs.tape_tip, accept.event_id);
    assert_eq!(final_hs.accepted_head, accept.event_id);
    assert_eq!(final_hs.authorization_head, prev_auth);
    // The last event is a SOVEREIGN_ACCEPT+PASS, so tape_tip AND accepted_head both moved
    // to *this same* event OID (one commit advanced both refs in one txn).
    assert_eq!(
        final_hs.tape_tip, final_hs.accepted_head,
        "tape == accepted here (same event)"
    );
    // But authorization_head is a DISTINCT earlier event (the AtomAuthorized commit), so
    // the three refs are not all collapsed onto one OID.
    assert_ne!(
        Some(final_hs.tape_tip.clone()),
        final_hs.authorization_head,
        "authorization_head is the earlier AtomAuthorized event, not the latest tip"
    );
}

/// A predicate-free event (`predicate_required == false`) appends with NOT_RUN and moves
/// no head beyond tape_tip — exercising STEP 3's NOT_RUN branch on the success path.
#[test]
fn predicate_free_event_appends_not_run_and_moves_only_tape_tip() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    git::init_sha256(repo).expect("init sha256 repo");
    let tape = Append::open(repo).expect("open tape");

    // Genesis first so there is a coherent pre-state.
    let genesis = tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                json!({"constitution_digest": "sha256:".to_string() + &"a".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("genesis");

    // PredicateEvaluated is the one OBSERVATION with predicate_required == false.
    let observed = tape
        .append(AppendRequest::new(
            "PredicateEvaluated",
            "writer:kernel",
            json!({"product": "PASS"}),
        ))
        .expect("predicate-free append");

    let body = read_committed_body(repo, &observed.event_id);
    assert_eq!(
        body["predicate_product"],
        json!("NOT_RUN"),
        "a predicate-free event records NOT_RUN"
    );
    assert_eq!(body["head_effect"], json!("PRESERVE"));
    assert_eq!(observed.head_moved, HeadMoved::None);
    assert_eq!(
        observed.accepted_head_after, genesis.event_id,
        "accepted_head stays at genesis under NOT_RUN"
    );
}
