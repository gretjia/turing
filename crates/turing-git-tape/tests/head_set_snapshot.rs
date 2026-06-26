//! SG-18 — HeadSet torn-read defense.
//!
//! This test genuinely binds the ratified **coherent HeadSet read** of
//! `pack/03_contracts/operation/guarded_ref_transaction_v5_3_1.md` §4 (lines 65-77) and
//! the AUTHORITATIVE reader algorithm + acceptance predicate of
//! `pack/01_architecture/greenfield_spec_v5_3_1.md` lines 221-231 (the spec:229 form is the
//! superset and is what we bind):
//!
//! ```text
//! A = read tape_tip
//! read authorization_head and accepted_head
//! B = read tape_tip
//! require A == B
//! load event A and derive expected post-state from its pre-state + payload + registry + predicate + A
//! accept snapshot iff expected post-state == the observed refs/authority epoch AND sequence == parent.sequence + 1
//! otherwise retry with bounded backoff, then fail closed
//! ```
//!
//! Invariant under test (contract §6, line 100): **"No incoherent `Q_t` escapes, even if
//! raw refs are transiently split."** A reader may transiently observe a subset of a
//! completed transaction (tape_tip moved but a sovereign head not yet) or an `A != B`
//! split (a writer committed mid-read). The guarded read DETECTS these, RETRIES with
//! bounded backoff, and either returns a coherent `Q` (once the underlying state settles)
//! or FAILS CLOSED with a typed error — it NEVER returns the torn tuple.
//!
//! The seam: the reader is parameterised over a [`RefSource`] (a ref/commit read
//! abstraction). The production path reads real Git refs (exercised separately through the
//! live [`Append::head_set_guarded`]); this test injects a fully-scripted source so torn /
//! subset-visible reads are induced DETERMINISTICALLY (no real threads, no real races) and
//! the "no incoherent Q" invariant can be asserted exhaustively.

use std::cell::Cell;

use serde_json::{Value, json};

use turing_contracts::envelope::{
    ENVELOPE_SCHEMA_ID, HeadSet, MicroEventEnvelope, PredicateProduct,
};
use turing_contracts::jcs;
use turing_contracts::registry;
use turing_git_tape::head_set::{Backoff, RefSource, SovereignRef, TornReadError, read_head_set};

// --- a fully-scripted RefSource (the deterministic fault-injection seam) ------
//
// `tape_tip_reads` is a queue of values returned by successive `read_ref(TapeTip)` calls,
// so a single guarded attempt can observe A on its first read and B on its second (the
// A != B torn-read). `authorization_head` / `accepted_head` are the steady observed
// values for the attempt. `events` maps a `mu:` oid to the committed envelope the reader
// loads + derives from. A reader that retries pulls the NEXT pair of tape_tip reads and the
// NEXT observed-heads frame, so "the state settles on retry" is modelled by enqueuing a
// coherent frame after the torn one.

/// One observed frame for a single guarded read attempt: the two `tape_tip` reads (A then
/// B) and the two heads observed between them.
#[derive(Clone)]
struct Frame {
    tip_a: Option<String>,
    tip_b: Option<String>,
    authorization_head: Option<String>,
    accepted_head: Option<String>,
}

/// A scripted ref source: each guarded read attempt consumes the next [`Frame`]; commit
/// bodies are looked up from a fixed map. This is the test-only injection seam — the
/// production reader reads real Git refs.
struct ScriptedSource {
    frames: Vec<Frame>,
    attempt: Cell<usize>,
    // within one attempt, which tape_tip read (0 = A, 1 = B) we are serving.
    tip_read: Cell<usize>,
    events: Vec<(String, MicroEventEnvelope)>,
}

impl ScriptedSource {
    fn new(frames: Vec<Frame>, events: Vec<(String, MicroEventEnvelope)>) -> Self {
        ScriptedSource {
            frames,
            attempt: Cell::new(0),
            tip_read: Cell::new(0),
            events,
        }
    }

    fn current(&self) -> &Frame {
        let i = self.attempt.get().min(self.frames.len() - 1);
        &self.frames[i]
    }
}

impl RefSource for ScriptedSource {
    fn read_ref(&self, which: SovereignRef) -> Result<Option<String>, String> {
        let frame = self.current();
        match which {
            SovereignRef::TapeTip => {
                // A on the first read of this attempt, B on the second; then advance to the
                // next attempt's frame (the guarded read does exactly two tape_tip reads).
                let n = self.tip_read.get();
                let value = if n == 0 { &frame.tip_a } else { &frame.tip_b };
                if n == 0 {
                    self.tip_read.set(1);
                } else {
                    self.tip_read.set(0);
                    self.attempt.set(self.attempt.get() + 1);
                }
                Ok(value.clone())
            }
            SovereignRef::AuthorizationHead => Ok(frame.authorization_head.clone()),
            SovereignRef::AcceptedHead => Ok(frame.accepted_head.clone()),
        }
    }

    fn read_envelope(&self, oid: &str) -> Result<MicroEventEnvelope, String> {
        let bare = oid.split_once(':').map(|(_, t)| t).unwrap_or(oid);
        self.events
            .iter()
            .find(|(id, _)| id.split_once(':').map(|(_, t)| t).unwrap_or(id) == bare)
            .map(|(_, env)| env.clone())
            .ok_or_else(|| format!("scripted source has no event {oid:?}"))
    }
}

// --- envelope builders -------------------------------------------------------

/// A deterministic fake `mu:` oid from a short tag (64 hex via repeating a hex nibble).
fn oid(tag: &str) -> String {
    // Map the tag's first byte into a hex nibble so distinct tags give distinct oids.
    let nibble = format!("{:x}", (tag.bytes().next().unwrap_or(b'0') as usize) % 16);
    format!("mu:{}", nibble.repeat(64))
}

fn payload_digest(payload: &Value) -> String {
    let jcs = jcs::canonicalize(payload).expect("canonicalize payload");
    format!("sha256:{}", jcs::sha256_hex(&jcs))
}

/// Build a committed envelope for `event_type` with the given pre-state, registry-derived
/// head_effect, predicate product, and sequence. This is the body the reader loads at
/// commit A and derives the expected post-state from.
fn envelope(
    event_type: &str,
    sequence: u64,
    prev_tape_tip: Option<&str>,
    authorization_head_before: Option<&str>,
    accepted_head_before: Option<&str>,
    product: PredicateProduct,
) -> MicroEventEnvelope {
    let row = registry::registry(event_type).expect("event in registry");
    let payload = json!({ "k": event_type, "seq": sequence });
    let pd = payload_digest(&payload);
    let empty_reasons = jcs::canonicalize(&Value::Array(Vec::new())).unwrap();
    let reason_digest = format!("sha256:{}", jcs::sha256_hex(&empty_reasons));
    MicroEventEnvelope {
        schema_id: ENVELOPE_SCHEMA_ID.to_string(),
        event_type: event_type.to_string(),
        writer_id: "writer:test".to_string(),
        authority_epoch: 0,
        sequence,
        prev_tape_tip: prev_tape_tip.map(str::to_string),
        authorization_head_before: authorization_head_before.map(str::to_string),
        accepted_head_before: accepted_head_before.map(str::to_string),
        head_effect: row.head_effect,
        event_schema_id: row.payload_schema_id.to_string(),
        predicate_product: product,
        reason_digest,
        verified: product == PredicateProduct::Pass,
        content_digest: pd.clone(),
        payload_hash: pd,
        payload,
    }
}

/// The fast (zero-delay) bounded backoff used in tests — caps retries deterministically.
fn fast_backoff(max_attempts: u32) -> Backoff {
    Backoff::test_zero_delay(max_attempts)
}

// =====================================================================================
//  A coherent SOVEREIGN_ACCEPT chain we re-use across the torn-read scenarios.
//
//  genesis G  = SystemConstitutionAccepted (SOVEREIGN_ACCEPT, PASS, seq 0, befores=null)
//               -> post-state: tape_tip=G, accepted_head=G, authorization_head=null
//  accept  C  = CandidateAccepted (SOVEREIGN_ACCEPT, PASS, seq 1, parent G)
//               -> post-state: tape_tip=C, accepted_head=C, authorization_head=null
// =====================================================================================

struct Chain {
    g: String,
    c: String,
    g_env: MicroEventEnvelope,
    c_env: MicroEventEnvelope,
}

fn coherent_chain() -> Chain {
    let g = oid("Genesis");
    let c = oid("Candidate");
    let g_env = envelope(
        "SystemConstitutionAccepted",
        0,
        None,
        None,
        None,
        PredicateProduct::Pass,
    );
    let c_env = envelope(
        "CandidateAccepted",
        1,
        Some(&g),
        None,
        Some(&g),
        PredicateProduct::Pass,
    );
    Chain { g, c, g_env, c_env }
}

// --- 1. acceptance predicate: a genuinely coherent tuple IS accepted as Q --------------

#[test]
fn coherent_tuple_is_accepted_as_q() {
    let ch = coherent_chain();
    // Observed refs after C: tape_tip = accepted_head = C; authorization_head = null.
    // A == B (no concurrent writer); derivation from C's pre-state yields exactly that.
    let frame = Frame {
        tip_a: Some(ch.c.clone()),
        tip_b: Some(ch.c.clone()),
        authorization_head: None,
        accepted_head: Some(ch.c.clone()),
    };
    let source = ScriptedSource::new(
        vec![frame],
        vec![(ch.g.clone(), ch.g_env.clone()), (ch.c.clone(), ch.c_env)],
    );

    let q: HeadSet =
        read_head_set(&source, &fast_backoff(8)).expect("a coherent tuple must be released as Q");
    assert_eq!(q.tape_tip, ch.c, "Q.tape_tip == C");
    assert_eq!(
        q.accepted_head, ch.c,
        "Q.accepted_head == C (SOVEREIGN_ACCEPT)"
    );
    assert_eq!(
        q.authorization_head, None,
        "Q.authorization_head still null"
    );
}

// --- 2. A != B torn read: detected, retried, settles to a coherent Q -------------------

#[test]
fn a_ne_b_torn_read_is_detected_retried_and_settles() {
    let ch = coherent_chain();
    // Attempt 1: a writer commits between A and B — tape_tip reads G then C (A != B).
    // The reader MUST reject this attempt (it cannot trust a tuple straddling a write).
    let torn = Frame {
        tip_a: Some(ch.g.clone()),
        tip_b: Some(ch.c.clone()),
        authorization_head: None,
        accepted_head: Some(ch.g.clone()),
    };
    // Attempt 2: the state has settled at C; A == B == C and the derivation is coherent.
    let settled = Frame {
        tip_a: Some(ch.c.clone()),
        tip_b: Some(ch.c.clone()),
        authorization_head: None,
        accepted_head: Some(ch.c.clone()),
    };
    let source = ScriptedSource::new(
        vec![torn, settled],
        vec![
            (ch.g.clone(), ch.g_env.clone()),
            (ch.c.clone(), ch.c_env.clone()),
        ],
    );

    let q = read_head_set(&source, &fast_backoff(8))
        .expect("after the A!=B split settles, a coherent Q is returned");
    // The released Q is the COHERENT post-settle state, never the torn (G,?,C) tuple.
    assert_eq!(q.tape_tip, ch.c);
    assert_eq!(q.accepted_head, ch.c);
    assert_ne!(
        q.tape_tip, ch.g,
        "an incoherent Q pinned at the mid-read G is NEVER returned"
    );
}

// --- 3. subset visibility: tape_tip advanced but accepted_head not yet → rejected ------

#[test]
fn subset_visibility_tape_tip_advanced_but_head_not_yet_is_rejected_then_retried() {
    let ch = coherent_chain();
    // Attempt 1 (subset-visible / mid-application of C's txn): A == B == C (tape_tip has
    // advanced to the new commit), but accepted_head STILL reads the OLD value G — the
    // sovereign head move of the same transaction is not yet visible. Deriving from C's
    // pre-state expects accepted_head == C, so observed (G) != expected (C): REJECT.
    let subset = Frame {
        tip_a: Some(ch.c.clone()),
        tip_b: Some(ch.c.clone()),
        authorization_head: None,
        accepted_head: Some(ch.g.clone()), // stale: not yet advanced to C
    };
    // Attempt 2: the head has caught up; the tuple is now coherent.
    let settled = Frame {
        tip_a: Some(ch.c.clone()),
        tip_b: Some(ch.c.clone()),
        authorization_head: None,
        accepted_head: Some(ch.c.clone()),
    };
    let source = ScriptedSource::new(
        vec![subset, settled],
        vec![
            (ch.g.clone(), ch.g_env.clone()),
            (ch.c.clone(), ch.c_env.clone()),
        ],
    );

    let q = read_head_set(&source, &fast_backoff(8))
        .expect("after the subset visibility resolves, a coherent Q is returned");
    assert_eq!(q.tape_tip, ch.c);
    assert_eq!(
        q.accepted_head, ch.c,
        "Q.accepted_head is the DERIVED C, never the transiently-stale G"
    );
}

// --- 4. fail-closed: persistent divergence (retries exhausted) → typed error -----------

#[test]
fn persistent_subset_visibility_exhausts_retries_and_fails_closed() {
    let ch = coherent_chain();
    // EVERY attempt observes the same subset-visible split: tape_tip == C but accepted_head
    // stuck at G (never catches up). The reader must retry up to the bound and then FAIL
    // CLOSED with a typed error — it must NEVER return the torn (C, _, G) tuple as Q.
    let stuck = Frame {
        tip_a: Some(ch.c.clone()),
        tip_b: Some(ch.c.clone()),
        authorization_head: None,
        accepted_head: Some(ch.g.clone()),
    };
    let max = 5;
    let source = ScriptedSource::new(
        vec![stuck], // current() clamps to the last frame, so this repeats every attempt
        vec![
            (ch.g.clone(), ch.g_env.clone()),
            (ch.c.clone(), ch.c_env.clone()),
        ],
    );

    let result = read_head_set(&source, &fast_backoff(max));
    match result {
        Err(TornReadError::ExhaustedRetries { attempts }) => {
            assert_eq!(
                attempts, max,
                "fail-closed after exactly the bounded number of attempts"
            );
        }
        Err(other) => panic!("expected ExhaustedRetries on persistent divergence, got {other:?}"),
        Ok(q) => panic!(
            "FAIL: an incoherent torn tuple escaped as Q ({q:?}); the reader must fail closed, \
             never release a torn HeadSet"
        ),
    }
}

// --- 5. A != B that never settles also fails closed (no torn Q ever) -------------------

#[test]
fn persistent_a_ne_b_split_fails_closed() {
    let ch = coherent_chain();
    // tape_tip flaps G/C on every attempt (A != B forever): a writer is perpetually mid-
    // commit from this reader's vantage. Must fail closed, never emit a Q.
    let flapping = Frame {
        tip_a: Some(ch.g.clone()),
        tip_b: Some(ch.c.clone()),
        authorization_head: None,
        accepted_head: Some(ch.g.clone()),
    };
    let max = 4;
    let source = ScriptedSource::new(
        vec![flapping],
        vec![
            (ch.g.clone(), ch.g_env.clone()),
            (ch.c.clone(), ch.c_env.clone()),
        ],
    );

    match read_head_set(&source, &fast_backoff(max)) {
        Err(TornReadError::ExhaustedRetries { attempts }) => {
            assert_eq!(attempts, max);
        }
        Err(other) => panic!("expected ExhaustedRetries, got {other:?}"),
        Ok(q) => panic!("a perpetual A!=B split must fail closed, never return Q ({q:?})"),
    }
}

// --- 6. sequence law: A.sequence != parent.sequence + 1 is rejected (spec:229) ---------

#[test]
fn sequence_not_parent_plus_one_is_rejected_then_fails_closed() {
    let ch = coherent_chain();
    // Forge a C' whose committed sequence is 5 (parent G has sequence 0, so the law
    // requires sequence == 1). Refs are otherwise internally consistent with C', but the
    // sequence == parent.sequence + 1 acceptance clause (spec:229) must REJECT it. Since
    // this never settles, the reader fails closed — it never releases this tuple.
    let c_bad = oid("Xandidate"); // distinct oid tag
    let mut c_bad_env = envelope(
        "CandidateAccepted",
        5, // illegal: parent G.sequence (0) + 1 == 1, not 5
        Some(&ch.g),
        None,
        Some(&ch.g),
        PredicateProduct::Pass,
    );
    // keep payload digest self-consistent (envelope() already did).
    c_bad_env.sequence = 5;

    let frame = Frame {
        tip_a: Some(c_bad.clone()),
        tip_b: Some(c_bad.clone()),
        authorization_head: None,
        accepted_head: Some(c_bad.clone()),
    };
    let max = 3;
    let source = ScriptedSource::new(
        vec![frame],
        vec![(ch.g.clone(), ch.g_env.clone()), (c_bad.clone(), c_bad_env)],
    );

    match read_head_set(&source, &fast_backoff(max)) {
        Err(TornReadError::ExhaustedRetries { attempts }) => assert_eq!(attempts, max),
        Err(other) => {
            panic!("expected ExhaustedRetries on the sequence-law violation, got {other:?}")
        }
        Ok(q) => panic!(
            "a tuple violating sequence == parent.sequence + 1 must NOT be released as Q ({q:?})"
        ),
    }
}

// --- 7. exhaustive: across MANY injected torn states, no incoherent Q ever escapes -----

#[test]
fn no_incoherent_q_ever_escapes_across_injected_torn_states() {
    let ch = coherent_chain();
    // The full coherent post-state for C, used to check every released Q against the ONE
    // legitimate answer.
    let coherent = HeadSet {
        tape_tip: ch.c.clone(),
        authorization_head: None,
        accepted_head: ch.c.clone(),
    };

    // A battery of single-frame (never-settling) torn injections. Each must fail closed —
    // none may release a HeadSet at all, and certainly not an incoherent one.
    let torn_frames: Vec<Frame> = vec![
        // A != B (writer mid-commit)
        Frame {
            tip_a: Some(ch.g.clone()),
            tip_b: Some(ch.c.clone()),
            authorization_head: None,
            accepted_head: Some(ch.c.clone()),
        },
        // tape_tip at C but accepted_head stale at G (subset visibility, head lagging)
        Frame {
            tip_a: Some(ch.c.clone()),
            tip_b: Some(ch.c.clone()),
            authorization_head: None,
            accepted_head: Some(ch.g.clone()),
        },
        // tape_tip at C but accepted_head absent entirely (post-crash split)
        Frame {
            tip_a: Some(ch.c.clone()),
            tip_b: Some(ch.c.clone()),
            authorization_head: None,
            accepted_head: None,
        },
        // tape_tip at C but a phantom authorization_head appears (head over-advanced)
        Frame {
            tip_a: Some(ch.c.clone()),
            tip_b: Some(ch.c.clone()),
            authorization_head: Some(ch.c.clone()),
            accepted_head: Some(ch.c.clone()),
        },
    ];

    for (i, torn) in torn_frames.into_iter().enumerate() {
        let source = ScriptedSource::new(
            vec![torn],
            vec![
                (ch.g.clone(), ch.g_env.clone()),
                (ch.c.clone(), ch.c_env.clone()),
            ],
        );
        match read_head_set(&source, &fast_backoff(3)) {
            Err(TornReadError::ExhaustedRetries { .. }) => { /* correct: failed closed */ }
            Err(other) => panic!("torn frame {i}: expected ExhaustedRetries, got {other:?}"),
            Ok(q) => {
                assert_ne!(
                    q, coherent,
                    "torn frame {i}: a torn read coincidentally matched the coherent state — \
                     impossible by construction; the injection was not actually torn"
                );
                panic!("torn frame {i}: an incoherent Q escaped ({q:?}) — INVARIANT VIOLATED");
            }
        }
    }
}

// --- 8. the LIVE production reader over real Git refs returns the same coherent Q ------
//
// This proves the production path (real Git refs, not the scripted seam) is wired to the
// SAME guarded reader and returns the coherent HeadSet for an un-torn store.

#[test]
fn live_guarded_reader_over_real_git_returns_coherent_q() {
    use turing_git_tape::append::{Append, AppendRequest};
    use turing_git_tape::git;

    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    git::init_sha256(repo).expect("init sha256 repo");
    let tape = Append::open(repo).expect("open tape");

    // pre-genesis: no coherent HeadSet yet.
    assert!(
        tape.head_set_guarded()
            .expect("guarded read on empty repo")
            .is_none(),
        "a pre-genesis store has no coherent HeadSet"
    );

    let genesis = tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                json!({"constitution_digest": "sha256:".to_string() + &"a".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("genesis append");

    let q = tape
        .head_set_guarded()
        .expect("guarded read succeeds")
        .expect("a coherent HeadSet exists after genesis");
    assert_eq!(q.tape_tip, genesis.event_id, "live Q.tape_tip == genesis");
    assert_eq!(
        q.accepted_head, genesis.event_id,
        "live Q.accepted_head == genesis"
    );
    assert_eq!(q.authorization_head, None);
}
