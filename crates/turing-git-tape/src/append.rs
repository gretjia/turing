//! The Tape append — STEP 6 (mint) → STEP 7 (one guarded multi-ref CAS) → STEP 8 (receipt).
//!
//! This composes [`turing_contracts`] (the `MicroEventEnvelope` body, the JCS codec, the
//! registry) and [`turing_kernel::reducer`] (the head-transition law) over the native
//! SHA-256 Git plumbing in [`crate::git`]. It implements the **success path** of
//! `pack/03_contracts/operation/append_algorithm_v5_3_1.md`: a candidate with predicate
//! product PASS, or a predicate-free event with NOT_RUN.
//!
//! Built extensibly for the hardening gates: STEP 7 already goes through a single guarded
//! transaction primitive ([`crate::git::update_refs`]) that pins all three refs, so SG-14
//! (stale-writer CAS) and SG-18 (torn-read) extend the retry/read seams rather than
//! rewrite the writer. Admission A1–A8, FAIL/failure-node construction (SG-13), and epoch
//! transfer (SG-17) are intentionally out of scope here.
//!
//! **SG-14 — stale-writer CAS.** The success-path [`Append::append`] is now the
//! *bounded FF-only re-mint retry loop* of append-algorithm STEP 7
//! (`pack/03_contracts/operation/append_algorithm_v5_3_1.md`: `if r == STALE_PRECONDITION:
//! goto STEP 1`) over the guarded ref-transaction contract
//! (`pack/03_contracts/operation/guarded_ref_transaction_v5_3_1.md`). When a concurrent
//! writer advances `tape_tip` between this writer's pre-state read and its CAS, Git rejects
//! the transaction ([`crate::git::TxnOutcome::StalePrecondition`]) and applies NOTHING; the
//! loser then **re-reads the coherent HeadSet (the new tip), rebuilds the event against the
//! NEW pre-state** (new `prev_tape_tip`, new `*_before`, `sequence = parent.sequence + 1`),
//! **re-mints a NEW non-merge commit as a direct child of the new tip**, and retries —
//! FF-only, bounded by [`MAX_APPEND_ATTEMPTS`]. Force-update, merge-commit repair, and any
//! non-FF update are FORBIDDEN; on cap exhaustion the writer returns a typed error
//! ([`StaleAppendError::ExhaustedRetries`]) and the losing minted commit is left as a
//! dangling non-state object. The single `tape_tip` CAS is the exactly-one-winner gate:
//! Git admits one writer per old-tip round, every other gets `STALE_PRECONDITION`.
//!
//! For deterministic testing the same primitives are exposed as an explicit seam:
//! [`Append::stage`] runs STEP 1–6 (read + build + mint) against a *captured* pre-state
//! WITHOUT committing, and [`StagedAppend::commit`] runs only STEP 7 — so a test can
//! interleave two writers on the same old tip without real threads. The auto-retry loop is
//! also exercised through [`Append::append_with_contention`], which fires a caller hook
//! between the pre-state read and the CAS (the production [`Append::append`] passes a
//! no-op hook).
//!
//! Storage layout: the canonical JCS envelope bytes are stored as a single blob named
//! [`EVENT_BLOB_NAME`] in the event commit's tree, so `cat-file -p <commit>:event`
//! returns the byte-identical committed body. The commit is **non-merge** (a root at
//! genesis, otherwise a single-parent child of the observed `tape_tip`). `event_id` is
//! the `mu:` form of the minted commit OID — never embedded in the body.

use std::path::{Path, PathBuf};

use serde_json::Value;

use turing_contracts::envelope::{HeadSet, MicroEventEnvelope, PredicateProduct};
use turing_contracts::jcs;
use turing_contracts::payload::ProjectLawAmended;
use turing_contracts::registry::{self, EventClass};
use turing_kernel::reducer::{self, PreState};

/// The tree-blob name that stores an event's canonical JCS envelope body.
pub const EVENT_BLOB_NAME: &str = "event";

const REF_TAPE_TIP: &str = "refs/turingos/tape_tip";
const REF_AUTHORIZATION_HEAD: &str = "refs/turingos/authorization_head";
const REF_ACCEPTED_HEAD: &str = "refs/turingos/accepted_head";

/// The bounded-backoff cap for the STEP 7 stale-precondition re-mint loop (SG-14).
///
/// Each attempt re-reads the coherent pre-state, re-mints a fresh non-merge commit against
/// the current tip, and submits one guarded FF-only CAS. Under perpetual contention the
/// loop terminates after this many attempts with [`StaleAppendError::ExhaustedRetries`] —
/// it NEVER force-updates, NEVER merges, and NEVER spins unbounded. The value is generous
/// enough that genuine (non-adversarial) concurrency converges, while still being a hard
/// ceiling that fails closed.
pub const MAX_APPEND_ATTEMPTS: u32 = 16;

/// Which single sovereign head an append moved (re-exported shape of the kernel decision,
/// for the public receipt surface).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HeadMoved {
    /// Only `tape_tip` advanced (PRESERVE class, FAIL, or NOT_RUN).
    None,
    /// `authorization_head` advanced (AUTHORIZATION + PASS).
    AuthorizationHead,
    /// `accepted_head` advanced (SOVEREIGN_ACCEPT + PASS).
    AcceptedHead,
}

impl From<reducer::HeadMoved> for HeadMoved {
    fn from(m: reducer::HeadMoved) -> Self {
        match m {
            reducer::HeadMoved::None => HeadMoved::None,
            reducer::HeadMoved::AuthorizationHead => HeadMoved::AuthorizationHead,
            reducer::HeadMoved::AcceptedHead => HeadMoved::AcceptedHead,
        }
    }
}

/// The STEP 8 committed receipt: the external read identity plus the new HeadSet and the
/// predicate outcome. `head_moved` names the single sovereign head that advanced (if any).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CommittedReceipt {
    /// `mu:` + 64hex — the minted commit OID as the event's external identity.
    pub event_id: String,
    /// Post-state `tape_tip` (always equals `event_id`).
    pub tape_tip_after: String,
    /// Post-state `accepted_head` (`mu:`…).
    pub accepted_head_after: String,
    /// Post-state `authorization_head` (`mu:`…) or `None`.
    pub authorization_head_after: Option<String>,
    /// The predicate product recorded on the event.
    pub product: PredicateProduct,
    /// Whether this is a verified transition.
    pub verified: bool,
    /// `sha256:` + 64hex over the (empty, on the success path) predicate reasons.
    pub reason_digest: String,
    /// Which single sovereign head moved.
    pub head_moved: HeadMoved,
}

/// A request to append one event on the success path.
///
/// The caller supplies the registry event name, an opaque writer id, and the payload.
/// `event_schema_id`, `head_effect`, `class`, and the head movement are all derived from
/// the embedded registry — never taken from the caller. The predicate product defaults to
/// `NOT_RUN`; [`Self::predicate_pass`] sets PASS for predicate-required events and
/// [`Self::predicate_fail`] records FAIL through `FailureNode`.
#[derive(Debug, Clone)]
pub struct AppendRequest {
    event_type: String,
    writer_id: String,
    payload: Value,
    product: ProductChoice,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ProductChoice {
    /// Use the registry: PASS if predicate_required, else NOT_RUN.
    Pass,
    /// Record a predicate FAIL through the FailureNode finalization path.
    Fail,
    /// Caller did not assert PASS; predicate-free events still resolve to NOT_RUN.
    Unspecified,
}

impl AppendRequest {
    /// A new success-path request for `event_type` with `writer_id` and `payload`.
    pub fn new(
        event_type: impl Into<String>,
        writer_id: impl Into<String>,
        payload: Value,
    ) -> Self {
        AppendRequest {
            event_type: event_type.into(),
            writer_id: writer_id.into(),
            payload,
            product: ProductChoice::Unspecified,
        }
    }

    /// Assert the Candidate Predicate PASSed (for a predicate-required event). A
    /// predicate-free event ignores this and records `NOT_RUN`.
    #[must_use]
    pub fn predicate_pass(mut self) -> Self {
        self.product = ProductChoice::Pass;
        self
    }

    /// Assert the Candidate Predicate failed and route the result through `FailureNode`.
    ///
    /// Failed sovereign candidates must become failure nodes rather than non-advancing
    /// sovereign accept events. Any event type other than `FailureNode` rejects this product.
    #[must_use]
    pub fn predicate_fail(mut self) -> Self {
        self.product = ProductChoice::Fail;
        self
    }
}

/// Errors from an append on the success path.
#[derive(Debug)]
pub enum AppendError {
    /// A Git plumbing operation failed.
    Git(crate::git::GitError),
    /// The canonical codec rejected the payload or envelope bytes.
    Jcs(jcs::JcsError),
    /// `event_type` is outside the closed 46-event registry (`UNKNOWN_EVENT_TYPE`).
    UnknownEventType(String),
    /// A predicate-required event was appended without an asserted product. The success
    /// path never fabricates a verified PASS; the caller must assert the predicate result
    /// (FAIL / failure-node finalization arrives in SG-13).
    PredicateProductRequired(String),
    /// Predicate FAIL finalization is valid only for `FailureNode`.
    PredicateFailRequiresFailureNode(String),
    /// The repository's `tape_tip` exists but `accepted_head` does not (or vice-versa) —
    /// an incoherent pre-state that is not a clean genesis and not a normal post-state.
    IncoherentPreState(String),
    /// A required head was missing when the registry class needed it to advance from a
    /// known value (e.g. a SOVEREIGN_ACCEPT after genesis with no accepted_head).
    MissingHead(String),
    /// The bounded re-mint retry loop (SG-14) exhausted [`MAX_APPEND_ATTEMPTS`] without
    /// ever winning the `tape_tip` CAS (perpetual concurrent contention). Surfaced rather
    /// than force-updating; carries the number of attempts made.
    ExhaustedRetries {
        /// How many guarded-CAS attempts were made before giving up (== the cap).
        attempts: u32,
    },
}

impl std::fmt::Display for AppendError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AppendError::Git(e) => write!(f, "append git error: {e}"),
            AppendError::Jcs(e) => write!(f, "append codec error: {e}"),
            AppendError::UnknownEventType(t) => {
                write!(f, "UNKNOWN_EVENT_TYPE: {t:?} is not in the closed registry")
            }
            AppendError::PredicateProductRequired(t) => write!(
                f,
                "predicate-required event {t:?} needs an explicit predicate product (no fabricated PASS)"
            ),
            AppendError::PredicateFailRequiresFailureNode(t) => {
                write!(
                    f,
                    "event {t:?} cannot record predicate FAIL; use FailureNode"
                )
            }
            AppendError::IncoherentPreState(m) => write!(f, "incoherent pre-state: {m}"),
            AppendError::MissingHead(m) => write!(f, "missing required head: {m}"),
            AppendError::ExhaustedRetries { attempts } => {
                write!(
                    f,
                    "STALE_PRECONDITION: re-mint retry loop exhausted after {attempts} attempts \
                     (concurrent contention never cleared); refused to force-update or merge"
                )
            }
        }
    }
}

impl std::error::Error for AppendError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            AppendError::Git(e) => Some(e),
            AppendError::Jcs(e) => Some(e),
            _ => None,
        }
    }
}

impl From<crate::git::GitError> for AppendError {
    fn from(e: crate::git::GitError) -> Self {
        AppendError::Git(e)
    }
}
impl From<jcs::JcsError> for AppendError {
    fn from(e: jcs::JcsError) -> Self {
        AppendError::Jcs(e)
    }
}

/// Errors from the SG-14 stale-writer re-mint retry path.
///
/// This mirrors [`AppendError`] for the build/mint/CAS failure modes but separates the
/// terminal *bounded-backoff exhaustion* outcome ([`Self::ExhaustedRetries`]) so a caller
/// that drives the explicit stage/re-mint seam can distinguish "I gave up after N FF-only
/// attempts, having force-updated nothing" from an ordinary plumbing or codec error.
#[derive(Debug)]
pub enum StaleAppendError {
    /// A Git plumbing operation failed.
    Git(crate::git::GitError),
    /// The canonical codec rejected the payload or envelope bytes.
    Jcs(jcs::JcsError),
    /// `event_type` is outside the closed 46-event registry.
    UnknownEventType(String),
    /// A predicate-required event was staged without an asserted product.
    PredicateProductRequired(String),
    /// Predicate FAIL finalization is valid only for `FailureNode`.
    PredicateFailRequiresFailureNode(String),
    /// An incoherent pre-state was observed mid-retry (e.g. `tape_tip` present but
    /// `accepted_head` absent) — not a clean genesis and not a normal post-state.
    IncoherentPreState(String),
    /// A required head was missing when the registry class needed it.
    MissingHead(String),
    /// The bounded re-mint loop exhausted [`MAX_APPEND_ATTEMPTS`] without winning the
    /// `tape_tip` CAS. No ref was force-updated; the last minted commit is left dangling.
    ExhaustedRetries {
        /// How many guarded-CAS attempts were made before giving up (== the cap).
        attempts: u32,
    },
}

impl std::fmt::Display for StaleAppendError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            StaleAppendError::Git(e) => write!(f, "stale-append git error: {e}"),
            StaleAppendError::Jcs(e) => write!(f, "stale-append codec error: {e}"),
            StaleAppendError::UnknownEventType(t) => {
                write!(f, "UNKNOWN_EVENT_TYPE: {t:?} is not in the closed registry")
            }
            StaleAppendError::PredicateProductRequired(t) => write!(
                f,
                "predicate-required event {t:?} needs an explicit predicate product"
            ),
            StaleAppendError::PredicateFailRequiresFailureNode(t) => {
                write!(
                    f,
                    "event {t:?} cannot record predicate FAIL; use FailureNode"
                )
            }
            StaleAppendError::IncoherentPreState(m) => write!(f, "incoherent pre-state: {m}"),
            StaleAppendError::MissingHead(m) => write!(f, "missing required head: {m}"),
            StaleAppendError::ExhaustedRetries { attempts } => write!(
                f,
                "STALE_PRECONDITION: re-mint retry loop exhausted after {attempts} attempts \
                 (concurrent contention never cleared); refused to force-update or merge"
            ),
        }
    }
}

impl std::error::Error for StaleAppendError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            StaleAppendError::Git(e) => Some(e),
            StaleAppendError::Jcs(e) => Some(e),
            _ => None,
        }
    }
}

impl From<crate::git::GitError> for StaleAppendError {
    fn from(e: crate::git::GitError) -> Self {
        StaleAppendError::Git(e)
    }
}
impl From<jcs::JcsError> for StaleAppendError {
    fn from(e: jcs::JcsError) -> Self {
        StaleAppendError::Jcs(e)
    }
}

impl From<AppendError> for StaleAppendError {
    fn from(e: AppendError) -> Self {
        match e {
            AppendError::Git(g) => StaleAppendError::Git(g),
            AppendError::Jcs(j) => StaleAppendError::Jcs(j),
            AppendError::UnknownEventType(t) => StaleAppendError::UnknownEventType(t),
            AppendError::PredicateProductRequired(t) => {
                StaleAppendError::PredicateProductRequired(t)
            }
            AppendError::PredicateFailRequiresFailureNode(t) => {
                StaleAppendError::PredicateFailRequiresFailureNode(t)
            }
            AppendError::IncoherentPreState(m) => StaleAppendError::IncoherentPreState(m),
            AppendError::MissingHead(m) => StaleAppendError::MissingHead(m),
            AppendError::ExhaustedRetries { attempts } => {
                StaleAppendError::ExhaustedRetries { attempts }
            }
        }
    }
}

impl From<StaleAppendError> for AppendError {
    fn from(e: StaleAppendError) -> Self {
        match e {
            StaleAppendError::Git(g) => AppendError::Git(g),
            StaleAppendError::Jcs(j) => AppendError::Jcs(j),
            StaleAppendError::UnknownEventType(t) => AppendError::UnknownEventType(t),
            StaleAppendError::PredicateProductRequired(t) => {
                AppendError::PredicateProductRequired(t)
            }
            StaleAppendError::PredicateFailRequiresFailureNode(t) => {
                AppendError::PredicateFailRequiresFailureNode(t)
            }
            StaleAppendError::IncoherentPreState(m) => AppendError::IncoherentPreState(m),
            StaleAppendError::MissingHead(m) => AppendError::MissingHead(m),
            StaleAppendError::ExhaustedRetries { attempts } => {
                AppendError::ExhaustedRetries { attempts }
            }
        }
    }
}

/// A handle to one native-SHA-256 Tape repository.
///
/// `Append::open` does not create the repo (the caller runs `git init --object-format=
/// sha256` — see [`crate::git::init_sha256`]); it only binds the directory. The handle is
/// cheap and `Clone`-free by intent (one writer per repo on the P0 success path).
#[derive(Debug, Clone)]
pub struct Append {
    repo: PathBuf,
}

impl Append {
    /// Bind to an already-initialised SHA-256 Tape repository at `repo`.
    pub fn open(repo: &Path) -> Result<Self, AppendError> {
        // Confirm the store is native SHA-256 (fail closed otherwise).
        let fmt = crate::git::show_object_format(repo)?;
        if fmt != "sha256" {
            return Err(AppendError::IncoherentPreState(format!(
                "Tape repo must be a native SHA-256 store, got object-format {fmt:?}"
            )));
        }
        Ok(Append {
            repo: repo.to_path_buf(),
        })
    }

    /// Read the current coherent [`HeadSet`], or `None` if the Tape is pre-genesis
    /// (no `tape_tip` yet). On the success path this is the STEP 1 "receive a coherent
    /// pre-state" read; the full guarded double-read + torn-read defense is
    /// [`Self::head_set_guarded`] (SG-18).
    pub fn head_set(&self) -> Result<Option<HeadSet>, AppendError> {
        let pre = self.read_pre_state()?;
        let Some(tape_tip) = pre.tape_tip else {
            return Ok(None);
        };
        let accepted_head = pre.accepted_head.ok_or_else(|| {
            AppendError::IncoherentPreState(
                "tape_tip exists but accepted_head is absent".to_string(),
            )
        })?;
        Ok(Some(HeadSet {
            tape_tip,
            authorization_head: pre.authorization_head,
            accepted_head,
        }))
    }

    /// SG-18 — the **guarded coherent HeadSet read** (torn-read defense) over the live Git
    /// refs, returning a coherent `Q` (`Some`), a pre-genesis absence (`None`), or a typed
    /// fail-closed [`TornReadError`] — but **never** a torn tuple.
    ///
    /// This runs the double-read + derivation + acceptance-predicate algorithm of
    /// `pack/03_contracts/operation/guarded_ref_transaction_v5_3_1.md` §4 and
    /// `pack/01_architecture/greenfield_spec_v5_3_1.md` lines 221-231 against a live
    /// [`crate::head_set::GitRefSource`], with the production bounded backoff. Use this (not
    /// the single-shot [`Self::head_set`]) wherever a sovereign-state read must be defended
    /// against transient subset visibility / `A != B` splits.
    pub fn head_set_guarded(&self) -> Result<Option<HeadSet>, crate::head_set::TornReadError> {
        let source = crate::head_set::GitRefSource::new(&self.repo);
        crate::head_set::read_head_set_opt(&source, &crate::head_set::Backoff::bounded())
    }

    /// STEP 1 — read the observed pre-state from the three refs (`mu:`-prefixed) and the
    /// parent sequence. A fresh repo yields the genesis pre-state (all `None`, epoch 0).
    fn read_pre_state(&self) -> Result<PreState, AppendError> {
        let tip_oid = crate::git::rev_parse_opt(&self.repo, REF_TAPE_TIP)?;
        let auth_oid = crate::git::rev_parse_opt(&self.repo, REF_AUTHORIZATION_HEAD)?;
        let acc_oid = crate::git::rev_parse_opt(&self.repo, REF_ACCEPTED_HEAD)?;

        let parent_sequence = match &tip_oid {
            None => None,
            Some(oid) => Some(self.read_sequence(oid)?),
        };
        let authority_epoch = match &tip_oid {
            None => 0,
            Some(oid) => self.read_authority_epoch(oid)?,
        };

        Ok(PreState {
            tape_tip: tip_oid.map(mu),
            authorization_head: auth_oid.map(mu),
            accepted_head: acc_oid.map(mu),
            authority_epoch,
            parent_sequence,
        })
    }

    /// Read the `sequence` field of the committed body at commit `oid` (bare hex).
    fn read_sequence(&self, oid: &str) -> Result<u64, AppendError> {
        let bytes = crate::git::cat_file_path(&self.repo, oid, EVENT_BLOB_NAME)?;
        let value: Value = serde_json::from_slice(&bytes)
            .map_err(|e| AppendError::IncoherentPreState(format!("parent body not JSON: {e}")))?;
        let env = MicroEventEnvelope::from_jcs_value(&value)?;
        Ok(env.sequence)
    }

    /// Read the authority epoch of the committed envelope at `oid` (bare hex).
    fn read_authority_epoch(&self, oid: &str) -> Result<u64, AppendError> {
        let bytes = crate::git::cat_file_path(&self.repo, oid, EVENT_BLOB_NAME)?;
        let value: Value = serde_json::from_slice(&bytes)
            .map_err(|e| AppendError::IncoherentPreState(format!("parent body not JSON: {e}")))?;
        let env = MicroEventEnvelope::from_jcs_value(&value)?;
        if env.event_type == reducer::AUTHORITY_TRANSFER_EVENT_TYPE {
            if let Ok(amended) = ProjectLawAmended::from_jcs_value(&env.payload) {
                if amended.is_human_signed_authority_transfer() {
                    if let Some(next) = env.authority_epoch.checked_add(1) {
                        if amended.new_authority_epoch == next {
                            return Ok(next);
                        }
                    }
                }
            }
        }
        Ok(env.authority_epoch)
    }

    /// Append one event on the success path with the **bounded FF-only re-mint retry
    /// loop** (SG-14, append-algorithm STEP 7 → STEP 1 on `STALE_PRECONDITION`).
    ///
    /// Each attempt reads the coherent pre-state, builds + mints a fresh non-merge commit
    /// against the current tip, and submits one guarded multi-ref CAS. If a concurrent
    /// writer advanced `tape_tip` in between, Git rejects the transaction (applying
    /// nothing) and this re-reads, rebuilds against the NEW pre-state, re-mints, and
    /// retries — never force-updating, never merging. After [`MAX_APPEND_ATTEMPTS`] it
    /// returns [`AppendError::ExhaustedRetries`]. In the common single-writer case the
    /// first attempt wins and the behaviour is identical to a plain append.
    pub fn append(&self, req: AppendRequest) -> Result<CommittedReceipt, AppendError> {
        // Production path: no injected contention. Any race is a genuine concurrent writer.
        self.append_with_contention(req, || {})
            .map_err(AppendError::from)
    }

    /// Like [`Self::append`], but invokes `between_read_and_commit` once per attempt
    /// **after** reading the coherent pre-state and **before** submitting the guarded CAS.
    ///
    /// This is the deterministic test seam for the stale-writer race (SG-14): a test can
    /// land a competing commit inside the hook so the next CAS is genuinely stale, then
    /// assert the loop re-mints linearly. The production [`Self::append`] passes a no-op
    /// hook, so this method *is* the canonical retry loop — the hook only widens the race
    /// window; it never relaxes the FF-only / no-force / no-merge guarantees.
    pub fn append_with_contention<F: FnMut()>(
        &self,
        req: AppendRequest,
        mut between_read_and_commit: F,
    ) -> Result<CommittedReceipt, StaleAppendError> {
        for _ in 0..MAX_APPEND_ATTEMPTS {
            // STEP 1–6: read the coherent pre-state, build the final envelope against it,
            // and mint one non-merge commit child of the observed tip.
            let candidate = self.stage_internal(&req)?;

            // Test seam: a competing writer may land here, advancing tape_tip so this
            // attempt's CAS (old == the pre-state we just captured) becomes stale.
            between_read_and_commit();

            // STEP 7: one guarded multi-ref CAS. On STALE_PRECONDITION nothing was applied;
            // loop to STEP 1 and re-mint against the new tip (FF-only). The losing minted
            // commit is left dangling (a non-state object).
            match self.commit_candidate(&candidate)? {
                CommitResult::Applied(receipt) => return Ok(receipt),
                CommitResult::Stale => continue,
            }
        }
        // Bounded backoff exhausted: never force-update, never merge — fail closed.
        Err(StaleAppendError::ExhaustedRetries {
            attempts: MAX_APPEND_ATTEMPTS,
        })
    }

    /// STEP 1–6 of the append algorithm against the *currently observed* coherent
    /// pre-state, **without** committing (no ref move). The returned [`StagedAppend`]
    /// carries the captured pre-state, the registry class, the kernel head-decision, and
    /// the freshly minted (but un-referenced, therefore dangling-until-committed) commit
    /// OID. [`StagedAppend::commit`] then runs STEP 7.
    ///
    /// This is the explicit half of the SG-14 seam: a test stages two writers against the
    /// SAME old tip, commits one, and observes the other's CAS reject as stale — a
    /// deterministic interleaving with no real threads.
    pub fn stage(&self, req: AppendRequest) -> Result<StagedAppend, AppendError> {
        let candidate = self.stage_internal(&req)?;
        Ok(StagedAppend {
            repo: self.repo.clone(),
            req,
            candidate,
        })
    }

    /// STEP 1–6: read the coherent pre-state, derive the product + envelope, and mint one
    /// non-merge commit child of the observed tip. Pure of any ref move.
    fn stage_internal(&self, req: &AppendRequest) -> Result<Candidate, AppendError> {
        // --- registry-derived row (A2/A4): unknown event ⇒ reject ----------------------
        let row = registry::registry(&req.event_type)
            .ok_or_else(|| AppendError::UnknownEventType(req.event_type.clone()))?;

        // --- STEP 1: observe a coherent pre-state -------------------------------------
        let pre = self.read_pre_state()?;

        // --- STEP 3: predicate product (registry-derived) ----------------------------
        // A predicate-free event (predicate_required == false) ALWAYS records NOT_RUN,
        // regardless of any caller assertion (the product is registry-derived, not
        // writer-trusted). A predicate-required event on THIS success-path API must have
        // an explicitly asserted PASS — we never silently fabricate a verified PASS for a
        // predicate-required event. (FAIL / failure-node finalization is SG-13.)
        let product = if row.predicate_required {
            match req.product {
                ProductChoice::Pass => PredicateProduct::Pass,
                ProductChoice::Unspecified => {
                    return Err(AppendError::PredicateProductRequired(
                        req.event_type.clone(),
                    ));
                }
                ProductChoice::Fail => {
                    return Err(AppendError::PredicateFailRequiresFailureNode(
                        req.event_type.clone(),
                    ));
                }
            }
        } else if req.product == ProductChoice::Fail {
            if req.event_type == "FailureNode" {
                PredicateProduct::Fail
            } else {
                return Err(AppendError::PredicateFailRequiresFailureNode(
                    req.event_type.clone(),
                ));
            }
        } else {
            PredicateProduct::NotRun
        };
        let verified = product == PredicateProduct::Pass;

        // reason_digest over the (empty on the success path) sorted reason list:
        // sha256(JCS([])).
        let empty_reasons = jcs::canonicalize(&Value::Array(Vec::new()))?;
        let reason_digest = format!("sha256:{}", jcs::sha256_hex(&empty_reasons));

        // --- STEP 4/5: build EXACTLY ONE final envelope (head_effect is registry-derived)
        // Built against THIS captured pre-state: prev_tape_tip, *_before, and sequence all
        // come from `pre`. A re-mint (after a stale CAS) calls this again with the fresh
        // pre-state, so prev_tape_tip/sequence/OID all change — the linear-chain guarantee.
        let payload_hash = self.payload_digest(&req.payload)?;
        let envelope = MicroEventEnvelope {
            schema_id: turing_contracts::envelope::ENVELOPE_SCHEMA_ID.to_string(),
            event_type: req.event_type.clone(),
            writer_id: req.writer_id.clone(),
            authority_epoch: pre.authority_epoch,
            sequence: pre.next_sequence(),
            prev_tape_tip: pre.tape_tip.clone(),
            authorization_head_before: pre.authorization_head.clone(),
            accepted_head_before: pre.accepted_head.clone(),
            head_effect: row.head_effect,
            event_schema_id: row.payload_schema_id.to_string(),
            predicate_product: product,
            reason_digest: reason_digest.clone(),
            verified,
            content_digest: payload_hash.clone(),
            payload_hash: payload_hash.clone(),
            payload: req.payload.clone(),
        };

        // STEP 5 envelope admission: round-trip the canonical body through the closed
        // parser (rejects event_id/head_set_after and any unknown field) before minting.
        let body = envelope.to_jcs_bytes()?;
        let body_value: Value = serde_json::from_slice(&body)
            .map_err(|e| AppendError::Jcs(jcs::JcsError::Malformed(e.to_string())))?;
        let _ = MicroEventEnvelope::from_jcs_value(&body_value)?;

        // --- STEP 6: mint ONE non-merge commit child of the observed tape_tip ---------
        let parent_hex = pre.tape_tip.as_deref().map(strip_mu);
        let new_oid = self.mint_commit(&body, parent_hex)?;
        let event_id = mu(new_oid.clone());

        // STEP 7 decision (computed now; applied at commit time): the kernel is the sole
        // authority for which single head moves.
        let decision = reducer::apply(&pre, row.class, row.head_effect, product, &event_id);

        Ok(Candidate {
            pre,
            class: row.class,
            decision,
            new_oid,
            event_id,
            product,
            verified,
            reason_digest,
        })
    }

    /// STEP 7 + STEP 8: submit the one guarded multi-ref CAS for a staged candidate and,
    /// if it applies, build the committed receipt. A stale precondition is reported as
    /// [`CommitResult::Stale`] (the caller re-mints) — never as an error.
    fn commit_candidate(&self, c: &Candidate) -> Result<CommitResult, AppendError> {
        let outcome = self.commit_refs(&c.pre, &c.new_oid, c.class, &c.decision)?;
        if outcome == crate::git::TxnOutcome::StalePrecondition {
            // Nothing was applied (the txn is all-or-nothing). The minted commit is now a
            // dangling non-state object; the caller re-reads and re-mints.
            return Ok(CommitResult::Stale);
        }

        // --- STEP 8: committed receipt ------------------------------------------------
        let accepted_head_after = c
            .decision
            .accepted_head
            .clone()
            .ok_or_else(|| AppendError::MissingHead("accepted_head after append".into()))?;
        Ok(CommitResult::Applied(CommittedReceipt {
            event_id: c.event_id.clone(),
            tape_tip_after: c.decision.tape_tip.clone(),
            accepted_head_after,
            authorization_head_after: c.decision.authorization_head.clone(),
            product: c.product,
            verified: c.verified,
            reason_digest: c.reason_digest.clone(),
            head_moved: c.decision.head_moved.into(),
        }))
    }

    /// `sha256:` + `sha256(JCS(payload))` — the content_digest / payload_hash.
    fn payload_digest(&self, payload: &Value) -> Result<String, AppendError> {
        let jcs_bytes = jcs::canonicalize(payload)?;
        Ok(format!("sha256:{}", jcs::sha256_hex(&jcs_bytes)))
    }

    /// STEP 6 — write the JCS body as a single tree blob and mint a non-merge commit over
    /// it (root at genesis, else single-parent child of `parent_hex`). Returns the bare
    /// 64-hex commit OID.
    fn mint_commit(&self, body: &[u8], parent_hex: Option<&str>) -> Result<String, AppendError> {
        let blob = crate::git::hash_object(&self.repo, body)?;
        let tree = crate::git::mktree(
            &self.repo,
            &[crate::git::TreeEntry::blob(EVENT_BLOB_NAME, &blob)],
        )?;
        let parents: Vec<&str> = parent_hex.into_iter().collect();
        // The commit message is non-load-bearing; the body is the tree blob.
        let oid = crate::git::commit_tree(&self.repo, &tree, &parents, "turingos micro event")?;
        Ok(oid)
    }

    /// STEP 7 — one guarded multi-ref CAS transaction: move `tape_tip` (always) and the
    /// single head the kernel decided, pinning the unchanged heads with `verify` lines so
    /// the whole three-ref view is checked atomically (INV-2 / INV-3 / contract §2).
    fn commit_refs(
        &self,
        pre: &PreState,
        new_oid: &str,
        class: EventClass,
        decision: &reducer::HeadDecision,
    ) -> Result<crate::git::TxnOutcome, AppendError> {
        use crate::git::RefDirective;

        let pre_tip = pre.tape_tip.as_deref().map(strip_mu);
        let pre_auth = pre.authorization_head.as_deref().map(strip_mu);
        let pre_acc = pre.accepted_head.as_deref().map(strip_mu);

        let moved_auth = decision.head_moved == reducer::HeadMoved::AuthorizationHead;
        let moved_acc = decision.head_moved == reducer::HeadMoved::AcceptedHead;

        let mut directives = Vec::with_capacity(3);
        // tape_tip ALWAYS advances (CAS on the observed tip; create at genesis).
        directives.push(RefDirective::update(REF_TAPE_TIP, new_oid, pre_tip));

        // authorization_head: move iff the kernel said so, else pin it unchanged.
        if moved_auth {
            directives.push(RefDirective::update(
                REF_AUTHORIZATION_HEAD,
                new_oid,
                pre_auth,
            ));
        } else {
            directives.push(RefDirective::verify(REF_AUTHORIZATION_HEAD, pre_auth));
        }

        // accepted_head: move iff the kernel said so, else pin it unchanged.
        if moved_acc {
            directives.push(RefDirective::update(REF_ACCEPTED_HEAD, new_oid, pre_acc));
        } else {
            directives.push(RefDirective::verify(REF_ACCEPTED_HEAD, pre_acc));
        }

        // INV-3 sanity: a moved head must match the registry class.
        debug_assert!(
            !(moved_acc && class != EventClass::SovereignAccept),
            "accepted_head moved for a non-SOVEREIGN_ACCEPT class"
        );
        debug_assert!(
            !(moved_auth && class != EventClass::Authorization),
            "authorization_head moved for a non-AUTHORIZATION class"
        );

        Ok(crate::git::update_refs(&self.repo, &directives)?)
    }
}

// --- staged-append seam (SG-14 deterministic stale-race + the auto-retry building block) -

/// The product of STEP 1–6: a minted-but-uncommitted candidate plus everything STEP 7/8
/// need. Internal — the public surface is [`StagedAppend`].
#[derive(Debug, Clone)]
struct Candidate {
    /// The coherent pre-state this candidate was built against (the CAS old-OIDs).
    pre: PreState,
    /// The registry-derived event class.
    class: EventClass,
    /// The kernel's post-state head decision (the sole head-move authority).
    decision: reducer::HeadDecision,
    /// The freshly minted commit OID (bare 64-hex), dangling until committed.
    new_oid: String,
    /// `mu:` form of `new_oid` — the event's external identity.
    event_id: String,
    /// The recorded predicate product.
    product: PredicateProduct,
    /// Whether this is a verified transition.
    verified: bool,
    /// `sha256:`+64hex over the (empty) success-path reasons.
    reason_digest: String,
}

/// Internal STEP 7 outcome: applied (with the receipt) or stale (re-mint).
enum CommitResult {
    Applied(CommittedReceipt),
    Stale,
}

/// A staged (minted-but-uncommitted) append: STEP 1–6 are done; STEP 7 has not run, so no
/// ref has moved and the minted commit is still dangling.
///
/// This is the explicit SG-14 seam. [`Self::commit`] runs the one guarded multi-ref CAS:
/// if the captured pre-state still matches the live refs it applies and yields a
/// [`CommittedReceipt`]; if a concurrent writer advanced `tape_tip` in the meantime the CAS
/// is rejected (Git applies nothing) and a [`RestageNeeded`] is returned so the caller can
/// re-mint against the new tip — FF-only, never forcing, never merging.
#[derive(Debug, Clone)]
pub struct StagedAppend {
    repo: PathBuf,
    req: AppendRequest,
    candidate: Candidate,
}

impl StagedAppend {
    /// The `mu:`+64hex event id of the staged (minted, not yet committed) commit.
    #[must_use]
    pub fn event_id(&self) -> &str {
        &self.candidate.event_id
    }

    /// The bare 64-hex tail of the staged commit OID.
    #[must_use]
    pub fn oid(&self) -> &str {
        &self.candidate.new_oid
    }

    /// Run STEP 7 — the single guarded multi-ref CAS — for this staged candidate.
    ///
    /// Returns [`StagedCommit::Applied`] with the receipt if the captured pre-state still
    /// holds, or [`StagedCommit::Stale`] with a [`RestageNeeded`] if a concurrent writer
    /// won the `tape_tip` CAS first (nothing was applied; no force-update).
    pub fn commit(self) -> Result<StagedCommit, AppendError> {
        let tape = Append {
            repo: self.repo.clone(),
        };
        match tape.commit_candidate(&self.candidate)? {
            CommitResult::Applied(receipt) => Ok(StagedCommit::Applied(receipt)),
            CommitResult::Stale => Ok(StagedCommit::Stale(RestageNeeded { req: self.req })),
        }
    }
}

/// The outcome of [`StagedAppend::commit`]: exactly one of the two CAS results.
#[derive(Debug)]
pub enum StagedCommit {
    /// This writer won its `tape_tip` CAS round; the refs moved and here is the receipt.
    Applied(CommittedReceipt),
    /// A concurrent writer advanced `tape_tip` first; this CAS was rejected (STALE_
    /// PRECONDITION) and applied nothing. Re-mint against the new tip via the carried
    /// [`RestageNeeded`].
    Stale(RestageNeeded),
}

/// A stale loser's re-mint ticket: rebuild the event against the NEW tip and retry.
///
/// Holds only the original (pre-state-free) [`AppendRequest`]; the new pre-state, new
/// `prev_tape_tip`, new `sequence`, and a NEW commit OID are all derived freshly from the
/// live refs when [`Self::re_mint_and_commit`] runs. This is append-algorithm STEP 7's
/// `goto STEP 1`: FF-only, bounded, never a force-update or merge.
#[derive(Debug, Clone)]
pub struct RestageNeeded {
    req: AppendRequest,
}

impl RestageNeeded {
    /// Re-read the coherent pre-state, re-mint a fresh non-merge commit as a direct child
    /// of the NEW tip, and retry the guarded CAS — looping (bounded by
    /// [`MAX_APPEND_ATTEMPTS`]) until it applies or the cap is hit. Never force-updates,
    /// never merges; on exhaustion returns [`StaleAppendError::ExhaustedRetries`].
    ///
    /// `repo` must be the same Tape repository the original stage came from.
    pub fn re_mint_and_commit(self, repo: &Path) -> Result<CommittedReceipt, StaleAppendError> {
        let tape = Append::open(repo)?;
        // The bounded FF-only retry loop, re-minting against the live tip each attempt.
        tape.append_with_contention(self.req, || {})
    }
}

// --- read helpers (used by replay/tests; the committed body is the source of truth) ----

/// Read the canonical JCS envelope bytes committed for `event_id` (a `mu:`/bare-hex id).
/// This is the byte-identical committed body — the source of truth, independent of any
/// in-memory receipt.
pub fn committed_body_bytes(repo: &Path, event_id: &str) -> Result<Vec<u8>, crate::git::GitError> {
    crate::git::cat_file_path(repo, strip_mu(event_id), EVENT_BLOB_NAME)
}

/// The parent OIDs (bare hex) of the commit named by `event_id` (a `mu:`/bare-hex id).
/// A Tape event commit is non-merge: `[]` for genesis, exactly one otherwise.
pub fn commit_parents(repo: &Path, event_id: &str) -> Result<Vec<String>, crate::git::GitError> {
    crate::git::commit_parents(repo, strip_mu(event_id))
}

// --- identity helpers --------------------------------------------------------

/// Prefix a bare 64-hex OID with `mu:`.
fn mu(hex: String) -> String {
    format!("mu:{hex}")
}

/// Strip a leading `mu:` (or `sha256:`) prefix, returning the bare hex tail.
fn strip_mu(id: &str) -> &str {
    id.split_once(':').map(|(_, t)| t).unwrap_or(id)
}
