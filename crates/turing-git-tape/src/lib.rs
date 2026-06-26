//! turing-git-tape — native SHA-256 Git plumbing and HeadSet reconciliation.
//!
//! M0_SUBSTRATE ship gates owned here:
//! - SG-09  native SHA-256 Git qualification (init/commit/fsck/cat-file) — host Git >= 2.47.3
//! - SG-12  successful single-event append (one commit; expected refs move by class)
//! - SG-14  stale-writer CAS (exactly one winner; loser re-mints, no force/merge)
//! - SG-18  HeadSet self-reference-free derivation + torn-read reconciliation
//!
//! Narrow six-operation Git allowlist: init, hash-object, mktree, commit-tree, update-ref, cat-file.
//! Every Git invocation is structured argv only — never a shell string, never `sh -c`, and
//! caller-provided data never reaches the command line as an option (see [`git`]).
//!
//! The single-event append (STEP 6 mint → STEP 7 one guarded multi-ref CAS → STEP 8
//! receipt) lives in [`append`]; it composes the closed contract types + the kernel
//! head-transition reducer over this Git surface.

pub mod append;
pub mod git;
pub mod head_set;

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

/// Result of [`qualify_sha256`]: evidence that the host Git provides a native SHA-256
/// object store that survives `fsck --strict`.
#[derive(Debug, Clone)]
pub struct QualificationReport {
    /// Object format reported by `git rev-parse --show-object-format` (`"sha256"`).
    pub object_format: String,
    /// OID of the qualification blob (64 lowercase-hex under SHA-256).
    pub blob_oid: String,
    /// OID of the tree referencing that blob (64 lowercase-hex).
    pub tree_oid: String,
    /// OID of the root commit over that tree (64 lowercase-hex).
    pub commit_oid: String,
    /// `true` iff `git fsck --strict` reported a clean store.
    pub fsck_clean: bool,
}

/// Error from SHA-256 qualification.
#[derive(Debug)]
pub enum QualifyError {
    /// A workspace (temp directory) operation failed.
    Workspace(std::io::Error),
    /// A Git plumbing operation failed.
    Git(git::GitError),
    /// The repository did not report the required `sha256` object format.
    NotSha256 {
        /// The object format actually reported.
        observed: String,
    },
}

impl std::fmt::Display for QualifyError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            QualifyError::Workspace(e) => write!(f, "qualification workspace error: {e}"),
            QualifyError::Git(e) => write!(f, "qualification git error: {e}"),
            QualifyError::NotSha256 { observed } => {
                write!(f, "object format must be sha256, got {observed:?}")
            }
        }
    }
}

impl std::error::Error for QualifyError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            QualifyError::Workspace(e) => Some(e),
            QualifyError::Git(e) => Some(e),
            QualifyError::NotSha256 { .. } => None,
        }
    }
}

impl From<git::GitError> for QualifyError {
    fn from(e: git::GitError) -> Self {
        QualifyError::Git(e)
    }
}

/// A throwaway directory under [`std::env::temp_dir`] that is removed on drop.
///
/// `turing-git-tape`'s library surface depends only on `std`, so qualification cannot
/// use the `tempfile` dev-dependency; this provides the same "unique dir, auto-cleaned"
/// guarantee with a process-id + monotonic-counter name so concurrent calls never
/// collide.
struct ScratchDir {
    path: PathBuf,
}

impl ScratchDir {
    fn new() -> std::io::Result<Self> {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let n = COUNTER.fetch_add(1, Ordering::Relaxed);
        let pid = std::process::id();
        // Nanosecond clock adds entropy across separate process invocations.
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        let path = std::env::temp_dir().join(format!("turingos-sg09-{pid}-{nanos}-{n}"));
        std::fs::create_dir(&path)?;
        Ok(ScratchDir { path })
    }

    fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for ScratchDir {
    fn drop(&mut self) {
        // Best-effort cleanup; a leaked temp dir must never panic a successful gate.
        let _ = std::fs::remove_dir_all(&self.path);
    }
}

/// Qualify the host Git as a native SHA-256 Tape substrate.
///
/// In a *fresh* throwaway repository this runs the full plumbing chain
/// init → hash-object → mktree → commit-tree → update-ref → cat-file → fsck, asserts
/// the object format is `sha256`, and returns the blob/tree/commit OIDs plus the
/// `fsck --strict` verdict.
///
/// The qualification blob deliberately contains a NUL byte and a `0xFF` byte so the
/// round-trip proves binary-clean storage, not merely text storage.
pub fn qualify_sha256() -> Result<QualificationReport, QualifyError> {
    let scratch = ScratchDir::new().map_err(QualifyError::Workspace)?;
    let repo = scratch.path();

    // 1. init a native SHA-256 repository.
    git::init_sha256(repo)?;

    // 2. confirm the object format is sha256 (fail closed otherwise).
    let object_format = git::show_object_format(repo)?;
    if object_format != "sha256" {
        return Err(QualifyError::NotSha256 {
            observed: object_format,
        });
    }

    // 3. hash-object: write a binary-clean qualification blob.
    let payload: &[u8] = b"turingos sg-09 native sha256 qualification \x00 \xff\n";
    let blob_oid = git::hash_object(repo, payload)?;

    // 4. mktree: a tree referencing the blob.
    let tree_oid = git::mktree(repo, &[git::TreeEntry::blob("qualify.bin", &blob_oid)])?;

    // 5. commit-tree: a root commit over that tree.
    let commit_oid = git::commit_tree(repo, &tree_oid, &[], "SG-09 sha256 qualification")?;

    // 6. update-ref (CAS create): advance a tape_tip-shaped ref to the commit.
    git::update_ref(repo, "refs/turingos/tape_tip", &commit_oid, None)?;

    // 7. cat-file: round-trip the blob byte-identically and confirm the commit type.
    let read_back = git::cat_file_content(repo, &blob_oid)?;
    if read_back != payload {
        return Err(QualifyError::Git(git::GitError::Output {
            verb: "cat-file",
            detail: "qualification blob did not round-trip byte-identically".to_string(),
        }));
    }
    let commit_type = git::cat_file_type(repo, &commit_oid)?;
    if commit_type != "commit" {
        return Err(QualifyError::Git(git::GitError::Output {
            verb: "cat-file",
            detail: format!("expected commit object, got type {commit_type:?}"),
        }));
    }

    // 8. fsck --strict: the store must be clean.
    git::fsck(repo)?;

    Ok(QualificationReport {
        object_format,
        blob_oid,
        tree_oid,
        commit_oid,
        fsck_clean: true,
    })
}
