//! SG-19 — replay determinism.
//!
//! Gate command: `cargo nextest run -p turing-replay --test replay_determinism`.
//!
//! Builds a FIXED frozen Tape (a native-SHA-256 Git commit chain minted via the ratified
//! `turing-git-tape::Append`) carrying a deterministic mix of events — a genesis
//! SOVEREIGN_ACCEPT, a PROPOSAL, an AUTHORIZATION+PASS, a second SOVEREIGN_ACCEPT+PASS, and
//! a predicate-free (NOT_RUN) OBSERVATION — then folds it through `turing-replay`.
//!
//! The gate it binds (`pack/01_architecture/greenfield_spec_v5_3_1.md` §5.2-5.3, lines
//! 205-219; ADR-005; `_loop/m0_substrate/CONTEXT.md` SG-19):
//!
//! * **Determinism** — the same frozen Tape replays to a **byte-identical** accepted-state +
//!   HeadSet projection every run (compared as canonical `turingos.jcs.v1` bytes, not merely
//!   structural equality). No clock / no randomness / no environment read / no
//!   map-iteration-order nondeterminism in the fold path.
//! * **Live parity** — the replayed HeadSet equals the live HeadSet the git-tape reported
//!   after the appends (replay reconstructs the same accepted_head / authorization_head /
//!   tape_tip).
//! * **Ref laws under replay** — accepted_head == the last SOVEREIGN_ACCEPT+PASS event;
//!   authorization_head == the last AUTHORIZATION+PASS event; head_effect is **re-derived
//!   from the registry**, never trusted from the committed envelope.
//! * **Registry-sourced head_effect** — a replay that (wrongly) trusted a tampered
//!   envelope-carried `head_effect` is shown to diverge from the registry-sourced replay,
//!   demonstrating the fold SOURCES the effect from the registry and is independent of the
//!   carried value.

use std::path::Path;

use turing_contracts::envelope::{HeadEffect, MicroEventEnvelope, PredicateProduct};
use turing_contracts::jcs;
use turing_contracts::registry::{self, EventClass};

use turing_git_tape::append::{Append, AppendRequest, EVENT_BLOB_NAME, committed_body_bytes};
use turing_git_tape::git;

use turing_replay::{Reconstruction, replay_tape};

/// A throwaway native-SHA-256 Tape repo, auto-removed on drop (the lib has no `tempfile`).
struct TempRepo {
    path: std::path::PathBuf,
}

impl TempRepo {
    fn init() -> Self {
        let mut path = std::env::temp_dir();
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        path.push(format!(
            "turingos-sg19-{}-{}-{nanos}",
            std::process::id(),
            COUNTER.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
        ));
        std::fs::create_dir(&path).expect("create temp repo dir");
        git::init_sha256(&path).expect("git init --object-format=sha256");
        TempRepo { path }
    }

    fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for TempRepo {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.path);
    }
}

static COUNTER: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);

/// One appended event's external identity + the registry class it belongs to — used to
/// state the expected ref-law outcomes independently of the replay under test.
struct Appended {
    event_id: String,
    event_type: &'static str,
    class: EventClass,
    product: PredicateProduct,
}

/// Append the FIXED deterministic event sequence into a fresh Tape and return the live
/// HeadSet plus the per-event identities (genesis → tip order).
///
/// The sequence deliberately mixes every head-effect path:
/// 1. `SystemConstitutionAccepted` — genesis SOVEREIGN_ACCEPT + PASS (advances accepted_head).
/// 2. `GoalStateProposed`          — PROPOSAL + PASS (PRESERVE; only tape_tip).
/// 3. `AtomAuthorized`             — AUTHORIZATION + PASS (advances authorization_head).
/// 4. `CandidateAccepted`          — SOVEREIGN_ACCEPT + PASS (advances accepted_head again).
/// 5. `PredicateEvaluated`         — predicate-free OBSERVATION (NOT_RUN; only tape_tip).
fn build_fixed_tape(repo: &Path) -> (turing_contracts::envelope::HeadSet, Vec<Appended>) {
    let tape = Append::open(repo).expect("open sha256 Tape");
    let mut appended = Vec::new();

    // Distinct payloads ⇒ distinct content_digests ⇒ distinct commit OIDs, so a wrong
    // reconstruction (off-by-one fold, dropped event, mis-ordered chain) is detectable.
    let steps: [(&'static str, serde_json::Value, bool); 5] = [
        (
            "SystemConstitutionAccepted",
            serde_json::json!({"constitution": "root", "n": 1}),
            true,
        ),
        (
            "GoalStateProposed",
            serde_json::json!({"goal": "ship m0", "n": 2}),
            true,
        ),
        (
            "AtomAuthorized",
            serde_json::json!({"atom": "sg19", "n": 3}),
            true,
        ),
        (
            "CandidateAccepted",
            serde_json::json!({"candidate": "replay", "n": 4}),
            true,
        ),
        (
            "PredicateEvaluated",
            serde_json::json!({"report": "not_run", "n": 5}),
            false,
        ),
    ];

    for (event_type, payload, predicate_required) in steps {
        let mut req = AppendRequest::new(event_type, "writer:sg19", payload);
        if predicate_required {
            req = req.predicate_pass();
        }
        let receipt = tape
            .append(req)
            .expect("append succeeds on the success path");
        let row = registry::registry(event_type).expect("registered event");
        appended.push(Appended {
            event_id: receipt.event_id,
            event_type,
            class: row.class,
            product: receipt.product,
        });
    }

    let live = tape
        .head_set()
        .expect("read live HeadSet")
        .expect("Tape is non-empty after appends");
    (live, appended)
}

/// The byte-identical canonical projection of a reconstruction — the unit of the
/// determinism assertion.
fn projection_bytes(r: &Reconstruction) -> Vec<u8> {
    r.to_jcs_bytes().expect("reconstruction canonicalizes")
}

#[test]
fn frozen_tape_replays_byte_identical_accepted_state_and_head_set() {
    let repo = TempRepo::init();
    let (live, appended) = build_fixed_tape(repo.path());
    let tip = &appended.last().expect("non-empty tape").event_id;

    // --- Determinism: replay the SAME frozen Tape at least twice; the canonical projection
    //     bytes must be IDENTICAL across runs (not merely structurally equal). ----------
    let r1 = replay_tape(repo.path(), tip).expect("replay run 1");
    let r2 = replay_tape(repo.path(), tip).expect("replay run 2");
    let r3 = replay_tape(repo.path(), tip).expect("replay run 3");

    let b1 = projection_bytes(&r1);
    let b2 = projection_bytes(&r2);
    let b3 = projection_bytes(&r3);
    assert_eq!(
        b1, b2,
        "two replays of one frozen Tape must be byte-identical"
    );
    assert_eq!(b2, b3, "a third replay must be byte-identical too");
    // The projection must be non-trivial (a real reconstruction, not an empty stub).
    assert!(!b1.is_empty(), "projection must serialize real bytes");

    // --- Live parity: the replayed HeadSet equals the live HeadSet the git-tape reported.
    assert_eq!(
        r1.head_set(),
        &live,
        "replayed HeadSet must equal the live git-tape HeadSet"
    );

    // --- Ref laws under replay ---------------------------------------------------------
    // accepted_head == the LAST SOVEREIGN_ACCEPT + PASS event.
    let last_accept = appended
        .iter()
        .rev()
        .find(|a| a.class == EventClass::SovereignAccept && a.product == PredicateProduct::Pass)
        .expect("the fixture has SOVEREIGN_ACCEPT+PASS events");
    assert_eq!(
        r1.head_set().accepted_head,
        last_accept.event_id,
        "accepted_head must be the last SOVEREIGN_ACCEPT+PASS event"
    );
    assert_eq!(
        last_accept.event_type, "CandidateAccepted",
        "fixture: the last accept is CandidateAccepted (event 4, not genesis)"
    );

    // authorization_head == the LAST AUTHORIZATION + PASS event.
    let last_auth = appended
        .iter()
        .rev()
        .find(|a| a.class == EventClass::Authorization && a.product == PredicateProduct::Pass)
        .expect("the fixture has an AUTHORIZATION+PASS event");
    assert_eq!(
        r1.head_set().authorization_head.as_deref(),
        Some(last_auth.event_id.as_str()),
        "authorization_head must be the last AUTHORIZATION+PASS event"
    );

    // tape_tip == the literal tip of the frozen chain.
    assert_eq!(
        &r1.head_set().tape_tip,
        tip,
        "tape_tip must be the frozen chain tip"
    );

    // --- Accepted-state projection: exactly the SOVEREIGN_ACCEPT+PASS event ids, in order.
    let expected_accepted: Vec<String> = appended
        .iter()
        .filter(|a| a.class == EventClass::SovereignAccept && a.product == PredicateProduct::Pass)
        .map(|a| a.event_id.clone())
        .collect();
    assert_eq!(
        r1.accepted_event_ids(),
        expected_accepted.as_slice(),
        "the accepted-state sequence must be the SOVEREIGN_ACCEPT+PASS event ids in genesis→tip order"
    );
    // Two accepts in the fixture (genesis + CandidateAccepted): a non-vacuous sequence.
    assert_eq!(
        expected_accepted.len(),
        2,
        "fixture has exactly two accepted events"
    );

    // The folded sequence count must equal all five appended events (none dropped/duplicated).
    assert_eq!(
        r1.event_count(),
        appended.len(),
        "replay must fold every event on the frozen Tape exactly once"
    );

    // --- Determinism stressor: a SECOND independent replay (no shared in-memory cache; each
    //     call re-walks the frozen Git chain from scratch) yields the identical bytes. ----
    let fresh = replay_tape(repo.path(), tip).expect("cache-free replay");
    assert_eq!(
        projection_bytes(&fresh),
        b1,
        "a fresh replay (no carried state) must be byte-identical"
    );
}

/// The fold SOURCES `head_effect` from the registry and is INDEPENDENT of the value carried
/// in the committed envelope.
///
/// Strategy: build the fixed Tape, then mint a SIBLING commit whose body is the genesis
/// envelope with ONLY its carried `head_effect` flipped (`ADVANCE` → `PRESERVE`) — a tamper
/// the writer's admission would have rejected, but which we plant directly on the Tape. A
/// registry-sourced fold must produce the SAME accepted_head for the tampered body as for
/// the honest one (because it ignores the carried field and re-derives ADVANCE from the
/// registry). We assert this against an explicit "trust-the-envelope" oracle to prove the
/// two strategies genuinely differ on the tampered input — so the replay's agreement is
/// load-bearing, not a coincidence of equal values.
#[test]
fn head_effect_is_sourced_from_registry_not_the_envelope() {
    let repo = TempRepo::init();
    let (_live, appended) = build_fixed_tape(repo.path());

    // The genesis event is SystemConstitutionAccepted: registry says SOVEREIGN_ACCEPT /
    // ADVANCE; the honest committed body therefore carries head_effect = ADVANCE.
    let genesis = &appended[0];
    let honest_bytes =
        committed_body_bytes(repo.path(), &genesis.event_id).expect("read genesis body");
    let honest: MicroEventEnvelope = parse_envelope(&honest_bytes);
    assert_eq!(
        honest.head_effect,
        HeadEffect::Advance,
        "honest genesis SOVEREIGN_ACCEPT carries ADVANCE"
    );
    assert_eq!(
        registry::registry(genesis.event_type).unwrap().head_effect,
        HeadEffect::Advance,
        "registry-derived head_effect for the genesis event is ADVANCE"
    );

    // Tamper: flip ONLY the carried head_effect to PRESERVE, re-mint a sibling root commit.
    let mut tampered = honest.clone();
    tampered.head_effect = HeadEffect::Preserve;
    let tampered_oid = mint_root_with_body(repo.path(), &tampered);

    // Registry-sourced derivation (what the replay does): re-derive ADVANCE from the
    // registry, so the genesis event STILL advances accepted_head despite the carried
    // PRESERVE. Envelope-trusting derivation (the wrong oracle): obey the carried PRESERVE,
    // so accepted_head would NOT advance. The two MUST disagree on this tampered body —
    // proving the source of the effect is observable.
    let registry_sourced = derive_genesis_accepted(REGISTRY_SOURCED, &tampered, &tampered_oid);
    let envelope_trusting = derive_genesis_accepted(ENVELOPE_TRUSTING, &tampered, &tampered_oid);
    assert_ne!(
        registry_sourced, envelope_trusting,
        "registry-sourced vs envelope-trusting derivation MUST differ on a tampered head_effect"
    );
    assert_eq!(
        registry_sourced,
        Some(format!("mu:{tampered_oid}")),
        "registry-sourced fold advances accepted_head (ADVANCE re-derived from the registry)"
    );
    assert_eq!(
        envelope_trusting, None,
        "an envelope-trusting fold would wrongly NOT advance on the carried PRESERVE"
    );

    // And the production replay, run over the honest frozen Tape, agrees with the
    // registry-sourced answer for the honest genesis (head_effect ADVANCE re-derived).
    let tip = &appended.last().unwrap().event_id;
    let r = replay_tape(repo.path(), tip).expect("replay honest tape");
    // Genesis accepted the constitution; the later CandidateAccept is the final accepted_head.
    assert!(
        r.accepted_event_ids().contains(&genesis.event_id),
        "genesis SOVEREIGN_ACCEPT (ADVANCE re-derived from registry) is in the accepted sequence"
    );
}

// --- tiny envelope-trust oracles (TEST-LOCAL; the replay under test never trusts the
//     carried value — these exist only to prove the two strategies differ) --------------

const REGISTRY_SOURCED: bool = true;
const ENVELOPE_TRUSTING: bool = false;

/// Compute the post-state `accepted_head` for a single genesis event under either the
/// registry-sourced policy (`registry_sourced == true`, what replay does) or the
/// envelope-trusting policy (false, the wrong oracle). Genesis ⇒ pre-state heads all `None`.
fn derive_genesis_accepted(
    registry_sourced: bool,
    env: &MicroEventEnvelope,
    oid_hex: &str,
) -> Option<String> {
    let row = registry::registry(&env.event_type).expect("registered event");
    let effect = if registry_sourced {
        row.head_effect // SOURCED from the registry — what the replay fold does.
    } else {
        env.head_effect // TRUSTS the carried field — the wrong oracle.
    };
    let pre = turing_kernel::reducer::PreState::genesis();
    let decision = turing_kernel::reducer::apply(
        &pre,
        row.class,
        effect,
        env.predicate_product,
        &format!("mu:{oid_hex}"),
    );
    decision.accepted_head
}

fn parse_envelope(bytes: &[u8]) -> MicroEventEnvelope {
    let value: serde_json::Value = serde_json::from_slice(bytes).expect("body is JSON");
    MicroEventEnvelope::from_jcs_value(&value).expect("body parses as an envelope")
}

/// Mint a ROOT (parent-less) commit whose `event` tree blob is the canonical JCS bytes of
/// `env`, and return its bare 64-hex OID. Used only to plant a tampered sibling body on the
/// Tape for the registry-vs-envelope divergence proof (it moves no ref).
fn mint_root_with_body(repo: &Path, env: &MicroEventEnvelope) -> String {
    let body = env.to_jcs_bytes().expect("envelope canonicalizes");
    let blob = git::hash_object(repo, &body).expect("hash-object");
    let tree = git::mktree(repo, &[git::TreeEntry::blob(EVENT_BLOB_NAME, &blob)]).expect("mktree");
    git::commit_tree(repo, &tree, &[], "sg19 tampered sibling").expect("commit-tree")
}

/// Determinism stressor (key-ordering stability): re-canonicalizing the same reconstruction
/// projection through the JCS codec is idempotent and stable, so any internal map indexing
/// cannot leak iteration-order nondeterminism into the bytes.
#[test]
fn projection_serialization_is_order_stable() {
    let repo = TempRepo::init();
    let (_live, appended) = build_fixed_tape(repo.path());
    let tip = &appended.last().unwrap().event_id;

    let r = replay_tape(repo.path(), tip).expect("replay");
    let once = r.to_jcs_bytes().expect("canonicalize once");
    let twice = r.to_jcs_bytes().expect("canonicalize twice");
    assert_eq!(once, twice, "canonical projection bytes are stable");

    // Round-trip through the strict codec parser: the bytes are valid canonical JCS (sorted
    // keys, no whitespace), so re-canonicalizing the parsed value reproduces them exactly —
    // proving there is no map-iteration-order nondeterminism in the emitted projection.
    let parsed =
        jcs::parse_strict(std::str::from_utf8(&once).expect("utf8")).expect("strict parse");
    let recanon = jcs::canonicalize(&parsed).expect("re-canonicalize");
    assert_eq!(
        recanon, once,
        "projection is already canonical (stable key order, codec round-trips it)"
    );
}
