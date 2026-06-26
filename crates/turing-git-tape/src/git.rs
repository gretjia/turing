//! Narrow, structured-argv-only Git plumbing allowlist (native SHA-256 object store).
//!
//! Every Git invocation in this module is built as a **structured argument vector**
//! handed to [`std::process::Command`]. This module:
//!
//! * never spawns a shell — there is no `sh -c`, no `/bin/sh`, no shell metacharacter
//!   interpretation; argv elements are passed to `execvp` verbatim by the OS;
//! * never concatenates caller-provided options into the command line — the verb and
//!   its option flags are crate-owned string literals, and caller data only ever flows
//!   in as a *separate, positional* argv element or over stdin (so it can never be
//!   re-parsed as an option);
//! * pins the repository with `git -C <dir> …` rather than relying on the process CWD,
//!   so concurrent tests targeting different repos never race on a shared `chdir`.
//!
//! The allowlisted verbs are exactly the six-operation Tape plumbing surface plus the
//! two read/verify helpers needed by SG-09 qualification:
//! `init`, `hash-object`, `mktree`, `commit-tree`, `update-ref`, `cat-file`,
//! `rev-parse` (`--show-object-format` / ref resolution) and `fsck`.

use std::fmt;
use std::io::Write as _;
use std::path::Path;
use std::process::{Command, Stdio};

/// Error from a Git plumbing invocation.
#[derive(Debug)]
pub enum GitError {
    /// The `git` child process could not be spawned (e.g. `git` not on PATH).
    Spawn {
        /// The Git subcommand verb that was being invoked.
        verb: &'static str,
        /// Underlying I/O error.
        source: std::io::Error,
    },
    /// Writing to the child's stdin failed.
    Stdin {
        /// The Git subcommand verb that was being invoked.
        verb: &'static str,
        /// Underlying I/O error.
        source: std::io::Error,
    },
    /// `git` exited non-zero. Carries the captured `stderr` for diagnosis.
    NonZero {
        /// The Git subcommand verb that was being invoked.
        verb: &'static str,
        /// The process exit code, if the process exited normally.
        code: Option<i32>,
        /// Captured standard error (lossy UTF-8).
        stderr: String,
    },
    /// `git` produced output that violated an expected invariant (e.g. an OID that was
    /// not 64 lowercase-hex under SHA-256).
    Output {
        /// The Git subcommand verb that produced the output.
        verb: &'static str,
        /// A human-readable description of the violated invariant.
        detail: String,
    },
}

impl fmt::Display for GitError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            GitError::Spawn { verb, source } => {
                write!(f, "failed to spawn `git {verb}`: {source}")
            }
            GitError::Stdin { verb, source } => {
                write!(f, "failed to write stdin for `git {verb}`: {source}")
            }
            GitError::NonZero { verb, code, stderr } => {
                let code = code
                    .map(|c| c.to_string())
                    .unwrap_or_else(|| "signal".into());
                write!(
                    f,
                    "`git {verb}` exited with status {code}: {}",
                    stderr.trim()
                )
            }
            GitError::Output { verb, detail } => {
                write!(f, "`git {verb}` produced invalid output: {detail}")
            }
        }
    }
}

impl std::error::Error for GitError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            GitError::Spawn { source, .. } | GitError::Stdin { source, .. } => Some(source),
            _ => None,
        }
    }
}

/// An entry for [`mktree`]: a regular-file (blob) tree entry.
///
/// Only the regular-file mode (`100644`) is exposed; the Tape stores opaque event
/// blobs and never needs executables, symlinks, or sub-tree (gitlink) modes.
#[derive(Debug, Clone)]
pub struct TreeEntry {
    name: String,
    oid: String,
}

impl TreeEntry {
    /// A `100644 blob <oid>\t<name>` tree entry.
    pub fn blob(name: impl Into<String>, oid: impl Into<String>) -> Self {
        TreeEntry {
            name: name.into(),
            oid: oid.into(),
        }
    }

    /// Render the `mktree --stdin` line for this entry (NUL-terminated by the caller).
    fn mktree_line(&self) -> String {
        // `<mode> SP <type> SP <oid> TAB <name>` — the format `git mktree` reads.
        format!("100644 blob {}\t{}", self.oid, self.name)
    }
}

/// Build a crate-owned `git -C <dir> <argv…>` Command with no shell involvement and a
/// hardened, reproducible environment.
fn git_command(dir: &Path, args: &[&str]) -> Command {
    let mut cmd = Command::new("git");
    // `-C <dir>` pins the working tree / repo explicitly (no reliance on process CWD).
    cmd.arg("-C").arg(dir);
    cmd.args(args);
    // Determinism + isolation: do not read user/system/global config, and pin the
    // identity so `commit-tree` never fails for want of a configured user and never
    // depends on ambient `user.*` / `gpg.*` config. These are crate-owned literals.
    cmd.env("GIT_CONFIG_NOSYSTEM", "1");
    cmd.env("GIT_CONFIG_GLOBAL", "/dev/null");
    cmd.env("GIT_TERMINAL_PROMPT", "0");
    cmd.env("GIT_AUTHOR_NAME", "turingos");
    cmd.env("GIT_AUTHOR_EMAIL", "tape@turingos.local");
    cmd.env("GIT_COMMITTER_NAME", "turingos");
    cmd.env("GIT_COMMITTER_EMAIL", "tape@turingos.local");
    // Fixed timestamps keep commit OIDs reproducible across hosts/runs.
    cmd.env("GIT_AUTHOR_DATE", "2026-01-01T00:00:00+00:00");
    cmd.env("GIT_COMMITTER_DATE", "2026-01-01T00:00:00+00:00");
    cmd
}

/// Run a Git command with no stdin, capturing stdout/stderr; return trimmed stdout.
fn run_capture(dir: &Path, verb: &'static str, args: &[&str]) -> Result<String, GitError> {
    let output = git_command(dir, args)
        .stdin(Stdio::null())
        .output()
        .map_err(|source| GitError::Spawn { verb, source })?;
    check_status(verb, &output)?;
    Ok(trim_eol(&output.stdout))
}

/// Run a Git command feeding `input` to stdin, capturing stdout/stderr; trimmed stdout.
fn run_stdin(
    dir: &Path,
    verb: &'static str,
    args: &[&str],
    input: &[u8],
) -> Result<String, GitError> {
    let mut child = git_command(dir, args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|source| GitError::Spawn { verb, source })?;
    {
        let mut stdin = child
            .stdin
            .take()
            .expect("child stdin was requested via Stdio::piped");
        stdin
            .write_all(input)
            .map_err(|source| GitError::Stdin { verb, source })?;
        // Explicit drop closes the pipe so git sees EOF.
    }
    let output = child
        .wait_with_output()
        .map_err(|source| GitError::Spawn { verb, source })?;
    check_status(verb, &output)?;
    Ok(trim_eol(&output.stdout))
}

/// Run a Git command feeding `input` to stdin but discard stdout (only success matters).
fn run_stdin_status(
    dir: &Path,
    verb: &'static str,
    args: &[&str],
    input: &[u8],
) -> Result<(), GitError> {
    run_stdin(dir, verb, args, input).map(|_| ())
}

fn check_status(verb: &'static str, output: &std::process::Output) -> Result<(), GitError> {
    if output.status.success() {
        return Ok(());
    }
    Err(GitError::NonZero {
        verb,
        code: output.status.code(),
        stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
    })
}

/// Trim a single trailing `\n` (and `\r\n`) that Git appends to single-line output.
fn trim_eol(bytes: &[u8]) -> String {
    let s = String::from_utf8_lossy(bytes);
    s.trim_end_matches('\n').trim_end_matches('\r').to_string()
}

/// Validate that `oid` is a SHA-256 object name: exactly 64 lowercase-hex chars.
fn validate_oid(verb: &'static str, oid: &str) -> Result<String, GitError> {
    let ok = oid.len() == 64
        && oid
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b));
    if ok {
        Ok(oid.to_string())
    } else {
        Err(GitError::Output {
            verb,
            detail: format!(
                "expected a 64-char lowercase-hex SHA-256 OID, got {oid:?} (len {})",
                oid.len()
            ),
        })
    }
}

/// `git init --object-format=sha256 -q <dir>` — initialise a fresh native-SHA-256 repo.
pub fn init_sha256(dir: &Path) -> Result<(), GitError> {
    // `--object-format=sha256` is the SHA-256 discriminator; `-q` silences chatter.
    run_capture(
        dir,
        "init",
        &["init", "--object-format=sha256", "-q", "--", "."],
    )
    .map(|_| ())
}

/// `git rev-parse --show-object-format` — report the repository's object hash format
/// (`"sha256"` for a qualified Tape store; `"sha1"` for a legacy default repo).
pub fn show_object_format(dir: &Path) -> Result<String, GitError> {
    run_capture(dir, "rev-parse", &["rev-parse", "--show-object-format"])
}

/// `git hash-object -w --stdin` — write `content` as a blob; return its SHA-256 OID.
///
/// `content` is raw bytes on stdin, never an argv element, so arbitrary binary
/// (including NUL and `0xFF`) round-trips and can never be parsed as an option.
pub fn hash_object(dir: &Path, content: &[u8]) -> Result<String, GitError> {
    let oid = run_stdin(
        dir,
        "hash-object",
        &["hash-object", "-w", "--stdin"],
        content,
    )?;
    validate_oid("hash-object", &oid)
}

/// `git mktree` — build a tree object from `entries`; return its SHA-256 OID.
///
/// Entries are streamed over stdin as `<mode> SP <type> SP <oid> TAB <name>\n` lines.
pub fn mktree(dir: &Path, entries: &[TreeEntry]) -> Result<String, GitError> {
    let mut input = String::new();
    for e in entries {
        input.push_str(&e.mktree_line());
        input.push('\n');
    }
    let oid = run_stdin(dir, "mktree", &["mktree"], input.as_bytes())?;
    validate_oid("mktree", &oid)
}

/// `git commit-tree <tree> [-p <parent>…]` — mint a commit over `tree` with `parents`
/// and `message` (passed on stdin, never argv); return the commit's SHA-256 OID.
pub fn commit_tree(
    dir: &Path,
    tree: &str,
    parents: &[&str],
    message: &str,
) -> Result<String, GitError> {
    // Argv: the verb, the tree OID, and `-p <parent>` pairs. The message is delivered
    // over stdin (so it is never re-parsed as an option, regardless of content).
    let mut args: Vec<String> = Vec::with_capacity(2 + parents.len() * 2);
    args.push("commit-tree".to_string());
    args.push(tree.to_string());
    for p in parents {
        args.push("-p".to_string());
        args.push((*p).to_string());
    }
    let arg_refs: Vec<&str> = args.iter().map(String::as_str).collect();
    let oid = run_stdin(dir, "commit-tree", &arg_refs, message.as_bytes())?;
    validate_oid("commit-tree", &oid)
}

/// `git cat-file -t <oid>` — report the object's type (`blob` / `tree` / `commit` / `tag`).
pub fn cat_file_type(dir: &Path, oid: &str) -> Result<String, GitError> {
    // `--` terminates options so an OID can never be interpreted as a flag.
    run_capture(dir, "cat-file", &["cat-file", "-t", "--", oid])
}

/// `git cat-file -p <oid>` — emit the object's raw content as bytes (no trimming).
///
/// For a blob this is the byte-identical stored content; this is what proves the
/// SG-09 blob round-trip.
pub fn cat_file_content(dir: &Path, oid: &str) -> Result<Vec<u8>, GitError> {
    let output = git_command(dir, &["cat-file", "-p", "--", oid])
        .stdin(Stdio::null())
        .output()
        .map_err(|source| GitError::Spawn {
            verb: "cat-file",
            source,
        })?;
    check_status("cat-file", &output)?;
    Ok(output.stdout)
}

/// `git cat-file -p <rev>:<path>` — emit the raw bytes of the blob at `path` inside the
/// tree of commit/tree `rev` (no trimming). Used to read an event's committed body back
/// out of the Tape: the JCS envelope is stored as a single tree blob.
///
/// `rev` and `path` flow only as a single positional `rev:path` argv element after
/// `--end-of-options`; neither can be re-parsed as a flag.
pub fn cat_file_path(dir: &Path, rev: &str, path: &str) -> Result<Vec<u8>, GitError> {
    let spec = format!("{rev}:{path}");
    let output = git_command(dir, &["cat-file", "-p", "--end-of-options", &spec])
        .stdin(Stdio::null())
        .output()
        .map_err(|source| GitError::Spawn {
            verb: "cat-file",
            source,
        })?;
    check_status("cat-file", &output)?;
    Ok(output.stdout)
}

/// `git rev-list --parents -n 1 <commit>` — return the parent OIDs of `commit`.
///
/// A Tape event commit is **non-merge**: this returns `[]` for a root (genesis) commit
/// and exactly one OID otherwise. Each returned OID is validated as 64 lowercase-hex.
pub fn commit_parents(dir: &Path, commit: &str) -> Result<Vec<String>, GitError> {
    // `rev-list --parents -n 1 <c>` prints: `<c> <p1> [<p2> …]`. The first token is the
    // commit itself; the rest are parents. `--end-of-options` keeps `commit` positional.
    let line = run_capture(
        dir,
        "rev-list",
        &[
            "rev-list",
            "--parents",
            "-n",
            "1",
            "--end-of-options",
            commit,
        ],
    )?;
    let mut toks = line.split_ascii_whitespace();
    let head = toks.next().ok_or_else(|| GitError::Output {
        verb: "rev-list",
        detail: "empty rev-list output".to_string(),
    })?;
    validate_oid("rev-list", head)?;
    toks.map(|p| validate_oid("rev-list", p)).collect()
}

/// `git rev-parse --verify <rev>` — resolve a ref or revision to a single object name
/// and validate it is a 64-char lowercase-hex SHA-256 OID.
pub fn rev_parse(dir: &Path, rev: &str) -> Result<String, GitError> {
    // `--verify` requires the argument to resolve to exactly one object and errors
    // otherwise; `--end-of-options` stops flag parsing so a rev can never be a flag.
    let oid = run_capture(
        dir,
        "rev-parse",
        &["rev-parse", "--verify", "--end-of-options", rev],
    )?;
    validate_oid("rev-parse", &oid)
}

/// `git rev-parse --verify --quiet <rev>` — like [`rev_parse`] but returns `Ok(None)`
/// when the ref does not exist (rather than an error). Used to read a possibly-absent
/// sovereign ref (e.g. `authorization_head` before any AUTHORIZATION event, or any ref
/// on a fresh pre-genesis repo).
pub fn rev_parse_opt(dir: &Path, rev: &str) -> Result<Option<String>, GitError> {
    let output = git_command(
        dir,
        &["rev-parse", "--verify", "--quiet", "--end-of-options", rev],
    )
    .stdin(Stdio::null())
    .output()
    .map_err(|source| GitError::Spawn {
        verb: "rev-parse",
        source,
    })?;
    if !output.status.success() {
        // `--quiet` makes a missing ref exit non-zero with empty stdout; treat as absent.
        if trim_eol(&output.stdout).is_empty() {
            return Ok(None);
        }
        return Err(GitError::NonZero {
            verb: "rev-parse",
            code: output.status.code(),
            stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
        });
    }
    Ok(Some(validate_oid("rev-parse", &trim_eol(&output.stdout))?))
}

/// `git update-ref --stdin` with old-OID CAS preconditions.
///
/// Updates `name` to `new_oid`. If `old_oid` is `Some`, the update is applied **iff**
/// the ref currently equals that value (compare-and-swap). If `old_oid` is `None`, the
/// update requires the ref to be **newly created** (old = the all-zeros OID), so a
/// concurrent creator loses the race deterministically.
///
/// The whole update is delivered as a single `--stdin` transaction
/// (`start` / `update …` / `prepare` / `commit`) per the ratified ref-update primitive.
/// All values flow over stdin; none are argv options.
pub fn update_ref(
    dir: &Path,
    name: &str,
    new_oid: &str,
    old_oid: Option<&str>,
) -> Result<(), GitError> {
    // `-z` selects the NUL-delimited stdin format, which is unambiguous for any ref
    // name / value (no quoting, no whitespace ambiguity).
    //
    // Transaction shape (NUL-delimited):
    //   start NUL
    //   update SP <ref> NUL <new> NUL <old> NUL
    //   prepare NUL
    //   commit NUL
    //
    // For "create", <old> is the empty string, which `update-ref -z` treats as
    // "must not previously exist".
    let zero_or_empty = match old_oid {
        Some(old) => old.to_string(),
        None => String::new(),
    };
    let mut input: Vec<u8> = Vec::new();
    input.extend_from_slice(b"start\0");
    input.extend_from_slice(b"update ");
    input.extend_from_slice(name.as_bytes());
    input.push(0);
    input.extend_from_slice(new_oid.as_bytes());
    input.push(0);
    input.extend_from_slice(zero_or_empty.as_bytes());
    input.push(0);
    input.extend_from_slice(b"prepare\0");
    input.extend_from_slice(b"commit\0");

    run_stdin_status(dir, "update-ref", &["update-ref", "-z", "--stdin"], &input)
}

/// One CAS directive inside a guarded multi-ref transaction.
///
/// An `Update` moves `name` from `old` (the CAS precondition: `None` ⇒ "must not exist")
/// to `new`. A `Verify` asserts `name` currently equals `old` (or is absent for `None`)
/// **without** moving it — used to pin the sovereign heads that this append leaves
/// unchanged so the whole three-ref view is checked atomically (CONTEXT open flag #3).
#[derive(Debug, Clone)]
pub enum RefDirective {
    /// Compare-and-swap `name`: `old` → `new` (FF-only is the caller's responsibility).
    Update {
        /// The fully-qualified ref name (e.g. `refs/turingos/tape_tip`).
        name: String,
        /// The new OID (64 lowercase-hex).
        new: String,
        /// The expected current OID, or `None` to require the ref be newly created.
        old: Option<String>,
    },
    /// Assert (do not move) that `name` currently equals `old` (or is absent for `None`).
    Verify {
        /// The fully-qualified ref name.
        name: String,
        /// The expected current OID, or `None` to assert the ref is absent.
        old: Option<String>,
    },
}

impl RefDirective {
    /// A CAS update directive.
    pub fn update(name: impl Into<String>, new: impl Into<String>, old: Option<&str>) -> Self {
        RefDirective::Update {
            name: name.into(),
            new: new.into(),
            old: old.map(str::to_owned),
        }
    }

    /// A verify-only (pin) directive.
    pub fn verify(name: impl Into<String>, old: Option<&str>) -> Self {
        RefDirective::Verify {
            name: name.into(),
            old: old.map(str::to_owned),
        }
    }
}

/// Outcome of [`update_refs`]: applied, or rejected because a CAS precondition was stale.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TxnOutcome {
    /// The whole transaction committed; every ref now holds its new value.
    Applied,
    /// At least one `old`/`verify` precondition did not match the live ref. NOTHING was
    /// applied (the transaction is all-or-nothing); the caller must reread and re-mint.
    StalePrecondition,
}

/// Submit one guarded multi-ref CAS transaction in a **single** `git update-ref --stdin`
/// invocation (`start` / `update|verify …` / `prepare` / `commit`).
///
/// This is the STEP 7 writer primitive of the append algorithm and the
/// `guarded_ref_transaction_v5_3_1.md` contract: `tape_tip` plus at most one sovereign
/// head are moved together, never as two independent calls (INV-2). The directives are
/// streamed NUL-delimited so any ref name/value is unambiguous; nothing is a shell
/// string and no value is an argv option.
///
/// A failed precondition surfaces as [`TxnOutcome::StalePrecondition`] (Git applies none
/// of the updates) rather than an error, so the caller can deterministically reread and
/// re-mint. Any other Git failure is a hard [`GitError`].
pub fn update_refs(dir: &Path, directives: &[RefDirective]) -> Result<TxnOutcome, GitError> {
    let mut input: Vec<u8> = Vec::new();
    input.extend_from_slice(b"start\0");
    for d in directives {
        match d {
            RefDirective::Update { name, new, old } => {
                input.extend_from_slice(b"update ");
                input.extend_from_slice(name.as_bytes());
                input.push(0);
                input.extend_from_slice(new.as_bytes());
                input.push(0);
                input.extend_from_slice(old.as_deref().unwrap_or("").as_bytes());
                input.push(0);
            }
            RefDirective::Verify { name, old } => {
                // `verify <ref> NUL <old> NUL` asserts the ref equals <old> (empty = absent)
                // and moves nothing.
                input.extend_from_slice(b"verify ");
                input.extend_from_slice(name.as_bytes());
                input.push(0);
                input.extend_from_slice(old.as_deref().unwrap_or("").as_bytes());
                input.push(0);
            }
        }
    }
    input.extend_from_slice(b"prepare\0");
    input.extend_from_slice(b"commit\0");

    let output = git_command(dir, &["update-ref", "-z", "--stdin"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|source| GitError::Spawn {
            verb: "update-ref",
            source,
        })
        .and_then(|mut child| {
            {
                let mut stdin = child
                    .stdin
                    .take()
                    .expect("child stdin was requested via Stdio::piped");
                stdin.write_all(&input).map_err(|source| GitError::Stdin {
                    verb: "update-ref",
                    source,
                })?;
            }
            child.wait_with_output().map_err(|source| GitError::Spawn {
                verb: "update-ref",
                source,
            })
        })?;

    if output.status.success() {
        return Ok(TxnOutcome::Applied);
    }
    // A stale CAS precondition is the expected concurrent-loser path. Git reports it on
    // stderr (e.g. "reference already exists" / "is at … but expected …" / "cannot lock
    // ref"); classify those as StalePrecondition so the writer rereads/re-mints. The
    // transaction is atomic, so on this path NO ref moved.
    let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
    let lower = stderr.to_ascii_lowercase();
    let is_cas_failure = lower.contains("but expected")
        || lower.contains("already exists")
        || lower.contains("cannot lock ref")
        || lower.contains("reference already exists")
        || lower.contains("unable to resolve reference");
    if is_cas_failure {
        Ok(TxnOutcome::StalePrecondition)
    } else {
        Err(GitError::NonZero {
            verb: "update-ref",
            code: output.status.code(),
            stderr,
        })
    }
}

/// `git fsck --strict --no-progress` — verify the object store has no corruption or
/// strict-mode error. Returns `Ok(())` only on a clean store.
pub fn fsck(dir: &Path) -> Result<(), GitError> {
    run_capture(dir, "fsck", &["fsck", "--strict", "--no-progress"]).map(|_| ())
}
