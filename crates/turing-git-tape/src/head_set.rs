//! SG-18 — the guarded coherent HeadSet read (torn-read defense).
//!
//! This is the reader half of `pack/03_contracts/operation/guarded_ref_transaction_v5_3_1.md`
//! §4 (lines 65-77) and the AUTHORITATIVE algorithm of
//! `pack/01_architecture/greenfield_spec_v5_3_1.md` lines 221-231. Three independent raw ref
//! reads are **not** linearizable: a reader may transiently observe a subset of a completed
//! transaction (tape_tip advanced but a sovereign head not yet) or catch `tape_tip` mid-write
//! (`A != B`). This module proves coherence before releasing any HeadSet `Q`, so — per the
//! contract invariant (line 100) — **no incoherent `Q_t` escapes, even if raw refs are
//! transiently split.**
//!
//! The algorithm (one attempt):
//! ```text
//! A = read tape_tip
//! auth = read authorization_head
//! acc  = read accepted_head
//! B = read tape_tip
//! require A == B                                  (else a writer committed mid-read → retry)
//! load commit A; derive expected post-state from A's committed pre-state + payload
//!   + registry class + predicate + A (the minted OID)
//! accept Q iff  expected post-state == observed refs/authority epoch
//!          AND  sequence == parent.sequence + 1    (spec:229 — the superset clause)
//! else retry with bounded backoff, then fail closed (typed error) — NEVER return the torn tuple
//! ```
//!
//! The expected post-state is the kernel's derivation (`crate`'s [`turing_kernel::reducer`],
//! the same law the writer used to choose the ref-transaction shape), so the reader and writer
//! agree by construction. The acceptance predicate is the **spec:229** form (a superset of the
//! contract:73 form): it additionally binds `sequence == parent.sequence + 1` and the authority
//! epoch's Tape-internal coherence (A's committed `authority_epoch` must equal the parent's
//! derived post-state epoch; `0` at genesis).
//!
//! ## Fault-injection seam
//! The reader is generic over a [`RefSource`] — the only thing it touches to read refs and load
//! commits. The **production** path uses [`GitRefSource`] (real Git refs via the SHA-256
//! plumbing in [`crate::git`]); a **test** supplies a scripted source that returns torn /
//! subset-visible tuples DETERMINISTICALLY (e.g. `A != B`, or a tape_tip-advanced-but-head-stale
//! frame). The two diverge only in where the bytes come from; the guarded logic is identical.

use std::path::{Path, PathBuf};
use std::time::Duration;

use serde_json::Value;

use turing_contracts::envelope::{HeadSet, MicroEventEnvelope};
use turing_contracts::payload::ProjectLawAmended;
use turing_contracts::registry::{self, EventClass};
use turing_kernel::reducer::{self, PreState};

const REF_TAPE_TIP: &str = "refs/turingos/tape_tip";
const REF_AUTHORIZATION_HEAD: &str = "refs/turingos/authorization_head";
const REF_ACCEPTED_HEAD: &str = "refs/turingos/accepted_head";

/// The default bounded-retry cap for a guarded HeadSet read under transient ref splits.
///
/// A coherent transaction becomes fully visible within a small, bounded number of re-reads;
/// this ceiling guarantees the reader **fails closed** (never spins, never releases a torn
/// tuple) if divergence persists (e.g. a post-crash split that needs reconciliation, or an
/// adversarial flapping ref).
pub const DEFAULT_MAX_READ_ATTEMPTS: u32 = 16;

/// Which of the three sovereign refs to read. The reader reads `tape_tip` twice (A then B) and
/// each head once, between the two tape_tip reads.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SovereignRef {
    /// `refs/turingos/tape_tip`.
    TapeTip,
    /// `refs/turingos/authorization_head`.
    AuthorizationHead,
    /// `refs/turingos/accepted_head`.
    AcceptedHead,
}

/// The read abstraction the guarded reader is built on — and the SG-18 fault-injection seam.
///
/// `read_ref` returns the current value of a sovereign ref (`mu:`+64hex, or `None` if the ref
/// is absent). Successive calls to `read_ref(TapeTip)` are what the reader uses for its
/// double-read; a scripted test source returns A then B (possibly different) to induce a torn
/// read. `read_envelope` loads the committed `MicroEventEnvelope` of a `mu:`/bare-hex commit
/// so the reader can derive the expected post-state. The production [`GitRefSource`] reads real
/// Git; the seam never relaxes the coherence checks.
pub trait RefSource {
    /// Read the current value of `which` (`mu:`+64hex), or `None` if the ref is absent.
    fn read_ref(&self, which: SovereignRef) -> Result<Option<String>, String>;

    /// Load the committed `MicroEventEnvelope` for the commit named by `oid`
    /// (`mu:`/bare-hex). Used to read the pre-state + payload the post-state is derived from.
    fn read_envelope(&self, oid: &str) -> Result<MicroEventEnvelope, String>;
}

/// Bounded-backoff configuration for the guarded read: a hard attempt cap and the per-attempt
/// delay. The cap makes the reader **fail closed** on persistent divergence; tests use a
/// zero-delay backoff so the bound is exercised deterministically and fast.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Backoff {
    max_attempts: u32,
    delay: Duration,
}

impl Backoff {
    /// The production bounded backoff: [`DEFAULT_MAX_READ_ATTEMPTS`] attempts with a small
    /// fixed inter-attempt delay (enough to let an in-flight transaction become visible).
    #[must_use]
    pub fn bounded() -> Self {
        Backoff {
            max_attempts: DEFAULT_MAX_READ_ATTEMPTS,
            delay: Duration::from_millis(2),
        }
    }

    /// A bounded backoff with an explicit attempt cap and a fixed delay.
    #[must_use]
    pub fn new(max_attempts: u32, delay: Duration) -> Self {
        Backoff {
            max_attempts: max_attempts.max(1),
            delay,
        }
    }

    /// A zero-delay bounded backoff with `max_attempts` — for deterministic, fast tests that
    /// exercise the fail-closed bound without sleeping.
    #[must_use]
    pub fn test_zero_delay(max_attempts: u32) -> Self {
        Backoff {
            max_attempts: max_attempts.max(1),
            delay: Duration::ZERO,
        }
    }

    /// The configured attempt cap.
    #[must_use]
    pub fn max_attempts(&self) -> u32 {
        self.max_attempts
    }

    /// Sleep between attempts (a no-op for a zero delay).
    fn wait(&self) {
        if !self.delay.is_zero() {
            std::thread::sleep(self.delay);
        }
    }
}

impl Default for Backoff {
    fn default() -> Self {
        Backoff::bounded()
    }
}

/// A typed fail-closed error from the guarded read. The reader NEVER returns a torn tuple; on
/// irreconcilable divergence it returns [`Self::ExhaustedRetries`] (the contract's
/// "otherwise retry with bounded backoff, then fail closed").
#[derive(Debug)]
pub enum TornReadError {
    /// The bounded backoff was exhausted without a coherent snapshot ever proving out (the
    /// refs stayed split / subset-visible). Fail closed — no torn `Q` is ever released.
    ExhaustedRetries {
        /// How many guarded attempts were made before giving up (== the backoff cap).
        attempts: u32,
    },
    /// A ref/commit read through the [`RefSource`] failed (a real I/O / plumbing error, not a
    /// transient split). Carries the underlying message. Fail closed.
    Source(String),
}

impl std::fmt::Display for TornReadError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TornReadError::ExhaustedRetries { attempts } => write!(
                f,
                "guarded HeadSet read failed closed after {attempts} bounded attempts: the three \
                 refs stayed incoherent (torn / subset-visible); no torn Q was released"
            ),
            TornReadError::Source(m) => write!(f, "guarded HeadSet read source error: {m}"),
        }
    }
}

impl std::error::Error for TornReadError {}

/// One attempt's outcome: a coherent HeadSet, an empty (pre-genesis) Tape, or "incoherent —
/// retry".
enum Attempt {
    /// The three observed refs proved coherent: release this `Q`.
    Coherent(HeadSet),
    /// The Tape is pre-genesis (no `tape_tip`): there is no `Q` yet (caller maps to `None`).
    PreGenesis,
    /// The observed tuple was torn / subset-visible / failed the acceptance predicate; the
    /// caller must retry with backoff (and fail closed if the cap is hit).
    Retry,
}

/// Perform one guarded read attempt over `source`.
///
/// Reads `tape_tip` (A), the two heads, then `tape_tip` (B); requires `A == B`; loads commit A;
/// derives the expected post-state; and accepts iff the observed three refs equal the expected
/// post-state AND `sequence == parent.sequence + 1` AND A's committed `authority_epoch` is
/// coherent with the parent's derived epoch. Any miss ⇒ [`Attempt::Retry`].
fn read_once<R: RefSource>(source: &R) -> Result<Attempt, TornReadError> {
    let src = |e: String| TornReadError::Source(e);

    // --- A = read(tape_tip); read both heads; B = read(tape_tip) ----------------------
    let a = source.read_ref(SovereignRef::TapeTip).map_err(src)?;
    let observed_auth = source
        .read_ref(SovereignRef::AuthorizationHead)
        .map_err(src)?;
    let observed_acc = source.read_ref(SovereignRef::AcceptedHead).map_err(src)?;
    let b = source.read_ref(SovereignRef::TapeTip).map_err(src)?;

    // Pre-genesis: a clean empty Tape (no tip on either read). No Q exists yet.
    if a.is_none() && b.is_none() {
        return Ok(Attempt::PreGenesis);
    }

    // require A == B: a differing double-read means a writer committed between them — the
    // tuple straddles a transaction and is not trustworthy. Retry.
    let (Some(a_tip), Some(b_tip)) = (a.as_ref(), b.as_ref()) else {
        // exactly one of A/B is None: tape_tip appeared/disappeared mid-read (genesis racing
        // a reader, or a torn create). Not coherent — retry.
        return Ok(Attempt::Retry);
    };
    if a_tip != b_tip {
        return Ok(Attempt::Retry);
    }

    // --- load commit A and derive its expected post-state -----------------------------
    let a_env = match source.read_envelope(a_tip) {
        Ok(env) => env,
        // A's commit object not resolvable (e.g. the ref points at an object not yet visible
        // to this reader): treat as a transient split and retry rather than fail hard.
        Err(_) => return Ok(Attempt::Retry),
    };

    // The registry row is derived from the committed event type (never writer-trusted). An
    // unknown type on a committed body is a corrupt/forged tip — not coherent; retry (the
    // bound then fails closed).
    let Some(row) = registry::registry(&a_env.event_type) else {
        return Ok(Attempt::Retry);
    };

    // sequence == parent.sequence + 1 (spec:229). The parent is `prev_tape_tip`; at genesis
    // there is no parent and the sequence must be 0. We also recover the parent's derived
    // post-state authority epoch for the epoch-coherence clause.
    let (parent_sequence, parent_epoch_after) = match a_env.prev_tape_tip.as_deref() {
        None => {
            // Genesis: A must be sequence 0 with all befores null.
            if a_env.sequence != 0 {
                return Ok(Attempt::Retry);
            }
            (None, 0u64)
        }
        Some(parent_oid) => {
            let parent_env = match source.read_envelope(parent_oid) {
                Ok(env) => env,
                Err(_) => return Ok(Attempt::Retry),
            };
            // spec:229 sequence clause.
            if a_env.sequence != parent_env.sequence + 1 {
                return Ok(Attempt::Retry);
            }
            let epoch_after = derived_epoch_after(parent_oid, &parent_env);
            (Some(parent_env.sequence), epoch_after)
        }
    };

    // authority-epoch coherence: A's committed pre-state epoch must equal the parent's derived
    // post-state epoch (carried forward, or +1 on a valid authority transfer); 0 at genesis.
    if a_env.authority_epoch != parent_epoch_after {
        return Ok(Attempt::Retry);
    }

    // Build the pre-state A was appended against (from A's committed befores) and derive the
    // expected post-state via the SAME kernel reducer the writer used.
    let pre = PreState {
        tape_tip: a_env.prev_tape_tip.clone(),
        authorization_head: a_env.authorization_head_before.clone(),
        accepted_head: a_env.accepted_head_before.clone(),
        authority_epoch: a_env.authority_epoch,
        parent_sequence,
    };
    let decision = reducer::apply(
        &pre,
        row.class,
        row.head_effect,
        a_env.predicate_product,
        a_tip,
    );

    // expected post-state refs (spec:208-214):
    //   tape_tip            == A
    //   authorization_head  == A iff AUTHORIZATION + PASS, else authorization_head_before
    //   accepted_head       == A iff SOVEREIGN_ACCEPT + PASS, else accepted_head_before
    let expected_tip = &decision.tape_tip; // == a_tip
    let expected_auth = &decision.authorization_head;
    let expected_acc = &decision.accepted_head;

    // accept Q iff observed refs == expected refs (the torn-read defense). Any subset
    // visibility (tape_tip advanced but a head not yet, a head over-advanced, a head absent)
    // makes observed != expected → retry.
    let coherent =
        &observed_acc == expected_acc && &observed_auth == expected_auth && a_tip == expected_tip;
    if !coherent {
        return Ok(Attempt::Retry);
    }

    // accepted_head is non-null post-genesis (HeadSet schema). A coherent accepted post-state
    // must therefore be Some; if not, the tuple is incoherent — retry.
    let Some(accepted_head) = expected_acc.clone() else {
        return Ok(Attempt::Retry);
    };

    Ok(Attempt::Coherent(HeadSet {
        tape_tip: a_tip.clone(),
        authorization_head: expected_auth.clone(),
        accepted_head,
    }))
}

/// The parent's derived post-state authority epoch: carry forward, or `+1` on a valid PASSed
/// human-signed `AUTHORITY_TRANSFER` `ProjectLawAmended` (`greenfield_spec_v5_3_1.md:215-217`).
/// Mirrors the writer's epoch transition so the reader's epoch-coherence check agrees.
fn derived_epoch_after(parent_oid: &str, parent_env: &MicroEventEnvelope) -> u64 {
    // Only a ProjectLawAmended payload can move the epoch; parse it when present, else None.
    let amended: Option<ProjectLawAmended> =
        if parent_env.event_type == reducer::AUTHORITY_TRANSFER_EVENT_TYPE {
            ProjectLawAmended::from_jcs_value(&parent_env.payload).ok()
        } else {
            None
        };
    let pre = PreState {
        tape_tip: parent_env.prev_tape_tip.clone(),
        authorization_head: parent_env.authorization_head_before.clone(),
        accepted_head: parent_env.accepted_head_before.clone(),
        authority_epoch: parent_env.authority_epoch,
        parent_sequence: None,
    };
    let class = registry::registry(&parent_env.event_type)
        .map(|r| r.class)
        .unwrap_or(EventClass::Failure);
    let head_effect = registry::registry(&parent_env.event_type)
        .map(|r| r.head_effect)
        .unwrap_or(turing_contracts::envelope::HeadEffect::Preserve);
    let decision = reducer::apply_with_epoch(
        &pre,
        &parent_env.event_type,
        class,
        head_effect,
        parent_env.predicate_product,
        amended.as_ref(),
        parent_oid,
    );
    decision.authority_epoch
}

/// The guarded coherent HeadSet read: returns a coherent `Q` or fails closed — **never** a torn
/// tuple. Retries each [`read_once`] attempt under `backoff`, and on cap exhaustion returns
/// [`TornReadError::ExhaustedRetries`].
///
/// A `Some(HeadSet)`-shaped surface (pre-genesis ⇒ no `Q`) is provided by the live wrapper
/// [`crate::append::Append::head_set_guarded`]; this lower-level entry returns the `HeadSet`
/// directly and treats a pre-genesis read as a (retryable, then fail-closed) absence — so a
/// caller that knows the Tape is non-empty gets a torn-read-defended `Q` or a typed error.
pub fn read_head_set<R: RefSource>(
    source: &R,
    backoff: &Backoff,
) -> Result<HeadSet, TornReadError> {
    for attempt in 0..backoff.max_attempts() {
        match read_once(source)? {
            Attempt::Coherent(q) => return Ok(q),
            // Pre-genesis on a reader that demands a HeadSet: there is nothing coherent to
            // return. Keep retrying (genesis may be landing) and fail closed on the bound.
            Attempt::PreGenesis | Attempt::Retry => {
                if attempt + 1 < backoff.max_attempts() {
                    backoff.wait();
                }
            }
        }
    }
    Err(TornReadError::ExhaustedRetries {
        attempts: backoff.max_attempts(),
    })
}

/// Like [`read_head_set`] but distinguishes a clean pre-genesis Tape (no `tape_tip`) from a
/// torn read: returns `Ok(None)` the first time an attempt observes a coherent empty Tape, and
/// otherwise a coherent `Some(Q)` or a fail-closed error. This is what the live
/// [`crate::append::Append::head_set_guarded`] surface uses.
pub fn read_head_set_opt<R: RefSource>(
    source: &R,
    backoff: &Backoff,
) -> Result<Option<HeadSet>, TornReadError> {
    for attempt in 0..backoff.max_attempts() {
        match read_once(source)? {
            Attempt::Coherent(q) => return Ok(Some(q)),
            // A clean empty Tape is a definitive answer, not a torn read: no Q exists.
            Attempt::PreGenesis => return Ok(None),
            Attempt::Retry => {
                if attempt + 1 < backoff.max_attempts() {
                    backoff.wait();
                }
            }
        }
    }
    Err(TornReadError::ExhaustedRetries {
        attempts: backoff.max_attempts(),
    })
}

// --- production ref source: real Git refs over the SHA-256 plumbing -------------------

/// A [`RefSource`] backed by the live Git repository (the production path). Each `read_ref`
/// resolves the real sovereign ref via `git rev-parse`; `read_envelope` reads the committed
/// body blob via `git cat-file` and parses it through the closed `MicroEventEnvelope` codec.
#[derive(Debug, Clone)]
pub struct GitRefSource {
    repo: PathBuf,
}

impl GitRefSource {
    /// A live ref source over the Tape repository at `repo`.
    #[must_use]
    pub fn new(repo: &Path) -> Self {
        GitRefSource {
            repo: repo.to_path_buf(),
        }
    }

    fn ref_name(which: SovereignRef) -> &'static str {
        match which {
            SovereignRef::TapeTip => REF_TAPE_TIP,
            SovereignRef::AuthorizationHead => REF_AUTHORIZATION_HEAD,
            SovereignRef::AcceptedHead => REF_ACCEPTED_HEAD,
        }
    }
}

impl RefSource for GitRefSource {
    fn read_ref(&self, which: SovereignRef) -> Result<Option<String>, String> {
        let name = Self::ref_name(which);
        crate::git::rev_parse_opt(&self.repo, name)
            .map(|opt| opt.map(|hex| format!("mu:{hex}")))
            .map_err(|e| e.to_string())
    }

    fn read_envelope(&self, oid: &str) -> Result<MicroEventEnvelope, String> {
        let bare = oid.split_once(':').map(|(_, t)| t).unwrap_or(oid);
        let bytes = crate::git::cat_file_path(&self.repo, bare, crate::append::EVENT_BLOB_NAME)
            .map_err(|e| e.to_string())?;
        let value: Value =
            serde_json::from_slice(&bytes).map_err(|e| format!("committed body not JSON: {e}"))?;
        MicroEventEnvelope::from_jcs_value(&value).map_err(|e| e.to_string())
    }
}
