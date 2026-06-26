//! turing-replay — deterministic reconstruction with no SQLite/browser dependency.
//!
//! M0_SUBSTRATE ship gate owned here:
//! - SG-19  replay determinism (frozen Tape replays byte-identical accepted state and HeadSet)
//!
//! # What replay is
//!
//! A **pure fold over a frozen Tape**. The Tape is the native-SHA-256 Git commit chain
//! ([`turing_git_tape`]): every event is one non-merge commit whose tree carries the
//! canonical `turingos.jcs.v1` envelope body as a single blob named
//! [`turing_git_tape::append::EVENT_BLOB_NAME`]. Replay walks the parent chain from the
//! supplied `tape_tip` back to genesis, orders the events genesis → tip, and folds each one
//! through the kernel head-transition reducer ([`turing_kernel::reducer`]) to reconstruct the
//! accepted state + [`HeadSet`].
//!
//! # The frozen laws this binds (`greenfield_spec_v5_3_1.md` §5.2-5.3, lines 205-219; ADR-005)
//!
//! * **`head_effect` / `class` are RE-DERIVED from the registry** — never trusted from the
//!   committed envelope. For each event the fold looks up `registry(event_type)` and uses its
//!   `class` + `head_effect`; the envelope's carried `head_effect` is **ignored** by the fold.
//!   The committed body is self-reference-free (`head_set_after` is forbidden), so the
//!   post-state is *derived*, never read.
//! * **`accepted_head` advances only on registry `SOVEREIGN_ACCEPT` + `PASS`**; every accepted
//!   event id (genesis → tip) is recorded as the accepted-state sequence.
//! * **`authorization_head` advances only on registry `AUTHORIZATION` + `PASS`**.
//! * **`tape_tip` advances on every event** (including failures) to the new event OID.
//! * **`authority_epoch`** carries forward except a valid PASSed human-signed
//!   `AUTHORITY_TRANSFER` `ProjectLawAmended`, where it increments by exactly one (the same
//!   [`turing_kernel::reducer::apply_with_epoch`] rule the writer used).
//!
//! # Determinism guarantee
//!
//! The fold is a **pure function over the frozen Tape bytes**: it reads no clock, no
//! randomness, no environment, and uses no map-iteration-order-dependent state. Iteration is
//! over an ordered `Vec` (genesis → tip); the only lookup is the parsed-once registry
//! `BTreeMap`. The accepted-state + HeadSet projection serializes to **byte-identical**
//! canonical `turingos.jcs.v1` bytes ([`Reconstruction::to_jcs_bytes`]) on every run and
//! across implementations that obey the same contracts.

use std::collections::BTreeSet;
use std::path::Path;

use serde_json::{Value, json};

use turing_contracts::envelope::{HeadSet, MicroEventEnvelope};
use turing_contracts::jcs::{self, JcsError};
use turing_contracts::payload::ProjectLawAmended;
use turing_contracts::registry::{self, EventClass, RegistryRow};
use turing_git_tape::append::{commit_parents, committed_body_bytes};
use turing_git_tape::git::GitError;
use turing_kernel::reducer::{self, HeadDecision, PreState};

/// The const `schema_id` of the replay projection object (the byte-identical unit compared
/// across runs). This is a replay-owned read/diagnostic shape, not a committed Micro body.
pub const RECONSTRUCTION_SCHEMA_ID: &str = "replay_reconstruction.v1";

/// An error from replaying a frozen Tape.
#[derive(Debug)]
pub enum ReplayError {
    /// A Git plumbing read (parent walk / `cat-file` of a committed body) failed.
    Git(GitError),
    /// A committed body did not parse as a [`MicroEventEnvelope`], or its payload did not
    /// parse where required.
    Body(JcsError),
    /// A committed body carried a JSON-shape error (not parseable as the envelope at all).
    Malformed(String),
    /// A committed event's `event_type` is outside the closed 46-event registry — a corrupt
    /// or forged Tape (`unknown_event_policy = REJECT`). The fold refuses to guess.
    UnknownEventType(String),
    /// A Tape event commit had more than one parent (a merge commit). Tape commits are
    /// strictly non-merge (`[]` at genesis, exactly one otherwise); a merge is a corrupt
    /// Tape and replay fails closed rather than picking a parent.
    MergeCommit {
        /// The offending event id (`mu:`+64hex).
        event_id: String,
        /// How many parents the commit had (always > 1 on this path).
        parents: usize,
    },
    /// The walk revisited an event id — the parent chain is not acyclic. A genuine Tape is a
    /// finite acyclic chain; a cycle is corruption and replay fails closed.
    CyclicChain(String),
    /// A genesis event (no `prev_tape_tip`) carried a non-zero `sequence`, or a non-genesis
    /// event's `sequence` did not equal `parent.sequence + 1`. The chain's sequence numbering
    /// is incoherent.
    SequenceIncoherent {
        /// The offending event id.
        event_id: String,
        /// A human-readable description of the incoherence.
        detail: String,
    },
    /// A post-genesis reconstruction had no `accepted_head` (no SOVEREIGN_ACCEPT+PASS was ever
    /// folded). The HeadSet schema requires a non-null `accepted_head` post-genesis, so this is
    /// an incoherent Tape (e.g. it never opened with a SOVEREIGN_ACCEPT).
    NoAcceptedHead,
}

impl std::fmt::Display for ReplayError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ReplayError::Git(e) => write!(f, "replay git error: {e}"),
            ReplayError::Body(e) => write!(f, "replay body error: {e}"),
            ReplayError::Malformed(m) => write!(f, "replay malformed body: {m}"),
            ReplayError::UnknownEventType(t) => {
                write!(f, "UNKNOWN_EVENT_TYPE: {t:?} is not in the closed registry")
            }
            ReplayError::MergeCommit { event_id, parents } => write!(
                f,
                "corrupt Tape: event {event_id} is a merge commit ({parents} parents); \
                 Tape commits must be non-merge"
            ),
            ReplayError::CyclicChain(id) => {
                write!(f, "corrupt Tape: parent chain revisits event {id} (cycle)")
            }
            ReplayError::SequenceIncoherent { event_id, detail } => {
                write!(f, "incoherent sequence at event {event_id}: {detail}")
            }
            ReplayError::NoAcceptedHead => write!(
                f,
                "incoherent Tape: no SOVEREIGN_ACCEPT+PASS event, so accepted_head is null \
                 post-genesis (HeadSet requires a non-null accepted_head)"
            ),
        }
    }
}

impl std::error::Error for ReplayError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            ReplayError::Git(e) => Some(e),
            ReplayError::Body(e) => Some(e),
            _ => None,
        }
    }
}

impl From<GitError> for ReplayError {
    fn from(e: GitError) -> Self {
        ReplayError::Git(e)
    }
}
impl From<JcsError> for ReplayError {
    fn from(e: JcsError) -> Self {
        ReplayError::Body(e)
    }
}

/// The deterministic reconstruction of a frozen Tape: the coherent [`HeadSet`], the
/// accepted-state sequence (the SOVEREIGN_ACCEPT+PASS event ids, genesis → tip), the
/// reconstructed authority epoch, and the count of events folded.
///
/// The byte-identical unit the SG-19 determinism property compares is
/// [`Self::to_jcs_bytes`] — the canonical `turingos.jcs.v1` projection of this whole value.
/// Same frozen Tape ⇒ identical bytes every run.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Reconstruction {
    head_set: HeadSet,
    accepted_event_ids: Vec<String>,
    authority_epoch: u64,
    event_count: usize,
}

impl Reconstruction {
    /// The reconstructed coherent [`HeadSet`] (`tape_tip`, `authorization_head`,
    /// `accepted_head`).
    #[must_use]
    pub fn head_set(&self) -> &HeadSet {
        &self.head_set
    }

    /// The accepted-state sequence: every SOVEREIGN_ACCEPT+PASS event id, in genesis → tip
    /// order. The last element is `head_set().accepted_head`.
    #[must_use]
    pub fn accepted_event_ids(&self) -> &[String] {
        &self.accepted_event_ids
    }

    /// The reconstructed authority epoch (`0` unless a valid PASSed human-signed authority
    /// transfer advanced it).
    #[must_use]
    pub fn authority_epoch(&self) -> u64 {
        self.authority_epoch
    }

    /// How many events were folded (every event on the frozen Tape, exactly once).
    #[must_use]
    pub fn event_count(&self) -> usize {
        self.event_count
    }

    /// The canonical `turingos.jcs.v1` bytes of the reconstruction projection — the
    /// byte-identical comparison unit for SG-19 determinism.
    ///
    /// The projection is a closed object with sorted keys (the codec sorts bytewise) and no
    /// whitespace, so it is reproduced byte-for-byte by any run and any conforming
    /// implementation. It carries the HeadSet, the accepted-state sequence, the authority
    /// epoch, and the event count — the complete "accepted state + HeadSet" SG-19 reconstructs.
    pub fn to_jcs_bytes(&self) -> Result<Vec<u8>, JcsError> {
        jcs::canonicalize(&self.to_projection_value())
    }

    /// The JSON projection value (pre-canonicalization). Field order here is irrelevant — the
    /// codec sorts keys — but the *content* is the reconstruction's whole observable state.
    fn to_projection_value(&self) -> Value {
        let accepted: Vec<Value> = self
            .accepted_event_ids
            .iter()
            .map(|id| Value::String(id.clone()))
            .collect();
        json!({
            "schema_id": RECONSTRUCTION_SCHEMA_ID,
            "head_set": {
                "tape_tip": self.head_set.tape_tip,
                "authorization_head": self.head_set.authorization_head,
                "accepted_head": self.head_set.accepted_head,
            },
            "accepted_event_ids": accepted,
            "authority_epoch": self.authority_epoch,
            "event_count": self.event_count,
        })
    }
}

/// Replay a frozen Tape: reconstruct the accepted state + [`HeadSet`] from the Git commit
/// chain whose tip is `tape_tip_event_id` (a `mu:`/bare-hex commit id).
///
/// The function is a **pure fold over frozen bytes** — no clock, no randomness, no
/// environment read, no iteration-order nondeterminism — so the same Tape yields a
/// byte-identical [`Reconstruction`] every call (and across conforming implementations).
///
/// Steps:
/// 1. Walk the parent chain from `tape_tip_event_id` back to genesis (each commit is
///    non-merge: `[]` at genesis, exactly one parent otherwise). Reject merge commits and
///    cycles — a corrupt Tape fails closed.
/// 2. Order the collected events genesis → tip.
/// 3. Fold each event: read its committed `event` blob, parse the [`MicroEventEnvelope`],
///    **re-derive its `class` + `head_effect` from the registry** (never the carried value),
///    and apply [`turing_kernel::reducer::apply_with_epoch`] to advance the HeadSet +
///    authority epoch. Record each SOVEREIGN_ACCEPT+PASS event id in the accepted sequence.
///
/// # Errors
/// Returns [`ReplayError`] on a Git read failure, a malformed/unknown committed body, a merge
/// commit, a chain cycle, incoherent sequence numbering, or a post-genesis Tape that never
/// produced an `accepted_head`.
pub fn replay_tape(repo: &Path, tape_tip_event_id: &str) -> Result<Reconstruction, ReplayError> {
    // --- 1+2: walk parents tip → genesis, then reverse to genesis → tip ---------------
    let ordered = walk_to_genesis(repo, tape_tip_event_id)?;

    // --- 3: fold genesis → tip through the kernel reducer, registry-sourcing the effect.
    let mut pre = PreState::genesis();
    let mut accepted_event_ids: Vec<String> = Vec::with_capacity(ordered.len());
    let mut prev_sequence: Option<u64> = None;

    for event_id in &ordered {
        let env = read_envelope(repo, event_id)?;

        // sequence coherence (genesis ⇒ 0; otherwise parent.sequence + 1). This is a frozen
        // chain invariant; a violation means the Tape is corrupt, so we fail closed rather
        // than fold an incoherent body.
        check_sequence(event_id, env.sequence, prev_sequence)?;

        // RE-DERIVE class + head_effect from the registry — NEVER the carried envelope value.
        // A name outside the closed 46 is a forged/corrupt Tape (unknown_event_policy=REJECT).
        let row: RegistryRow = registry::registry(&env.event_type)
            .ok_or_else(|| ReplayError::UnknownEventType(env.event_type.clone()))?;

        // The authority-epoch transition needs the parsed ProjectLawAmended payload (only for
        // that one event type); every other event carries the epoch forward.
        let amended: Option<ProjectLawAmended> =
            if env.event_type == reducer::AUTHORITY_TRANSFER_EVENT_TYPE {
                ProjectLawAmended::from_jcs_value(&env.payload).ok()
            } else {
                None
            };

        // The fold step: the SAME kernel reducer the writer used, sourcing class + effect from
        // the registry. `apply_with_epoch` derives the post-state HeadSet AND the authority
        // epoch (carry-forward, or +1 on a valid PASSed authority transfer).
        let decision: HeadDecision = reducer::apply_with_epoch(
            &pre,
            &env.event_type,
            row.class,
            row.head_effect, // SOURCED from the registry, not env.head_effect.
            env.predicate_product,
            amended.as_ref(),
            event_id,
        );

        // Record the accepted-state sequence: a SOVEREIGN_ACCEPT that actually advanced
        // accepted_head (i.e. ADVANCE-from-registry + PASS) appends its event id.
        if decision.head_moved == reducer::HeadMoved::AcceptedHead {
            debug_assert_eq!(row.class, EventClass::SovereignAccept);
            accepted_event_ids.push(event_id.clone());
        }

        // Advance the pre-state to this event's derived post-state for the next fold step.
        prev_sequence = Some(env.sequence);
        pre = PreState {
            tape_tip: Some(decision.tape_tip.clone()),
            authorization_head: decision.authorization_head.clone(),
            accepted_head: decision.accepted_head.clone(),
            authority_epoch: decision.authority_epoch,
            parent_sequence: Some(env.sequence),
        };
    }

    // --- assemble the coherent HeadSet from the final derived post-state ----------------
    let tape_tip = pre.tape_tip.clone().expect("a non-empty Tape has a tip");
    let accepted_head = pre
        .accepted_head
        .clone()
        .ok_or(ReplayError::NoAcceptedHead)?;

    Ok(Reconstruction {
        head_set: HeadSet {
            tape_tip,
            authorization_head: pre.authorization_head.clone(),
            accepted_head,
        },
        accepted_event_ids,
        authority_epoch: pre.authority_epoch,
        event_count: ordered.len(),
    })
}

/// Walk the parent chain from `tip` back to genesis and return the event ids in genesis → tip
/// order. Each commit is non-merge; a merge commit or a cycle is a corrupt Tape (fail closed).
fn walk_to_genesis(repo: &Path, tip: &str) -> Result<Vec<String>, ReplayError> {
    let mut chain_tip_first: Vec<String> = Vec::new();
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let mut cursor = normalize_id(tip);

    loop {
        if !seen.insert(cursor.clone()) {
            return Err(ReplayError::CyclicChain(cursor));
        }
        let parents = commit_parents(repo, &cursor)?;
        chain_tip_first.push(cursor.clone());
        match parents.as_slice() {
            // Genesis: a root commit has no parents — the walk is complete.
            [] => break,
            // The normal case: exactly one parent (a non-merge child). Continue upward.
            [parent] => cursor = normalize_id(parent),
            // More than one parent ⇒ a merge commit ⇒ a corrupt Tape. Fail closed.
            many => {
                return Err(ReplayError::MergeCommit {
                    event_id: cursor,
                    parents: many.len(),
                });
            }
        }
    }

    // Reverse to genesis → tip — the fold order.
    chain_tip_first.reverse();
    Ok(chain_tip_first)
}

/// Read and parse the committed `MicroEventEnvelope` body of `event_id` (a `mu:`/bare-hex id).
/// The committed body is the byte-identical source of truth — independent of any receipt.
fn read_envelope(repo: &Path, event_id: &str) -> Result<MicroEventEnvelope, ReplayError> {
    let bytes = committed_body_bytes(repo, event_id)?;
    let value: Value = serde_json::from_slice(&bytes).map_err(|e| {
        ReplayError::Malformed(format!("committed body of {event_id} not JSON: {e}"))
    })?;
    MicroEventEnvelope::from_jcs_value(&value).map_err(ReplayError::Body)
}

/// Enforce the frozen sequence numbering: a genesis event (`prev == None`) must be `0`; a
/// non-genesis event must be `parent.sequence + 1`.
fn check_sequence(
    event_id: &str,
    sequence: u64,
    prev_sequence: Option<u64>,
) -> Result<(), ReplayError> {
    match prev_sequence {
        None => {
            if sequence != 0 {
                return Err(ReplayError::SequenceIncoherent {
                    event_id: event_id.to_string(),
                    detail: format!("genesis event must have sequence 0, got {sequence}"),
                });
            }
        }
        Some(prev) => {
            let expected = prev + 1;
            if sequence != expected {
                return Err(ReplayError::SequenceIncoherent {
                    event_id: event_id.to_string(),
                    detail: format!("expected sequence {expected} (parent + 1), got {sequence}"),
                });
            }
        }
    }
    Ok(())
}

/// Normalize an event id to the canonical `mu:`+64hex form the HeadSet/PreState use. The Git
/// plumbing returns bare 64-hex OIDs; the contracts identity is `mu:`-prefixed.
fn normalize_id(id: &str) -> String {
    match id.split_once(':') {
        Some((_, tail)) => format!("mu:{tail}"),
        None => format!("mu:{id}"),
    }
}
