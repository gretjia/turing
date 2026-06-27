//! SG-09 — Git SHA-256 qualification.
//!
//! This test genuinely qualifies a *native SHA-256* Git object store. It runs the
//! narrow six-operation plumbing allowlist (init / hash-object / mktree / commit-tree
//! / update-ref / cat-file) plus `rev-parse --show-object-format` and `fsck --strict`
//! inside a *fresh* temp repository and asserts the SHA-256 discriminators:
//!
//! * `git rev-parse --show-object-format` reports exactly `sha256`.
//! * the blob, tree, and commit OIDs are EACH 64 lowercase-hex chars (NOT 40 — the
//!   sha1-vs-sha256 discriminator). A SHA-1 repo would emit 40-hex and fail here.
//! * `cat-file -t` on the commit reports `commit`, and a written blob round-trips
//!   byte-identically through `cat-file -p`.
//! * `git fsck --strict` reports a clean object store (no corruption / dangling error).
//!
//! All Git invocations are structured argv only (no shell string, no `sh -c`, no
//! caller-controlled option concatenation): that surface lives in the crate, and this
//! test only exercises the crate's public API.

use turing_git_tape::git;
use turing_git_tape::{QualificationReport, qualify_sha256};

/// A hex OID must be exactly 64 lowercase-hex chars under SHA-256.
/// (40 hex => SHA-1: the discriminator we are guarding against.)
fn assert_sha256_oid(label: &str, oid: &str) {
    assert_eq!(
        oid.len(),
        64,
        "{label} OID must be 64 hex chars (SHA-256), got {} ({oid:?}); 40 would mean SHA-1",
        oid.len()
    );
    assert!(
        oid.chars()
            .all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase()),
        "{label} OID must be lowercase hex, got {oid:?}"
    );
}

#[test]
fn init_sha256_micro_git() {
    let report: QualificationReport = qualify_sha256().expect("SHA-256 micro.git init qualifies");

    assert_eq!(
        report.object_format, "sha256",
        "micro.git must use native SHA-256 object format"
    );
    assert_sha256_oid("commit", &report.commit_oid);
    assert!(
        report.fsck_clean,
        "initialized SHA-256 micro.git must pass git fsck --strict"
    );
}

#[test]
fn qualifies_native_sha256_object_store() {
    let report: QualificationReport = qualify_sha256().expect("SHA-256 qualification must succeed");

    // object format must be sha256 (the whole point of the gate).
    assert_eq!(
        report.object_format, "sha256",
        "object format must be sha256, got {:?}",
        report.object_format
    );

    // The blob, tree, and commit OIDs are each 64 lowercase-hex (NOT 40).
    assert_sha256_oid("blob", &report.blob_oid);
    assert_sha256_oid("tree", &report.tree_oid);
    assert_sha256_oid("commit", &report.commit_oid);

    // The three OIDs must be distinct objects.
    assert_ne!(report.blob_oid, report.tree_oid);
    assert_ne!(report.tree_oid, report.commit_oid);
    assert_ne!(report.blob_oid, report.commit_oid);

    // fsck --strict must have reported a clean store.
    assert!(
        report.fsck_clean,
        "git fsck --strict must report a clean object store"
    );
}

/// End-to-end exercise of the low-level allowlist directly against a fresh repo,
/// independent of `qualify_sha256`, asserting the SHA-256 discriminators and a
/// byte-identical blob round-trip.
#[test]
fn plumbing_allowlist_roundtrips_under_sha256() {
    let dir = tempfile::tempdir().expect("create temp dir");
    let repo = dir.path();

    // init --object-format=sha256
    git::init_sha256(repo).expect("git init --object-format=sha256");

    // The store must self-report sha256 (would be sha1 on a default repo).
    let fmt = git::show_object_format(repo).expect("rev-parse --show-object-format");
    assert_eq!(fmt, "sha256", "fresh repo must be a SHA-256 object store");

    // hash-object -w --stdin : write a blob whose bytes we control and round-trip.
    let payload: &[u8] = b"turingos sg-09 \x00 native sha256 \xff round-trip\n";
    let blob = git::hash_object(repo, payload).expect("hash-object -w --stdin");
    assert_sha256_oid("blob", &blob);

    // mktree : a tree referencing the blob.
    let tree = git::mktree(repo, &[git::TreeEntry::blob("payload.bin", &blob)]).expect("mktree");
    assert_sha256_oid("tree", &tree);
    assert_ne!(tree, blob, "tree OID must differ from blob OID");

    // commit-tree : a root (parentless) commit over that tree.
    let commit =
        git::commit_tree(repo, &tree, &[], "SG-09 sha256 qualification").expect("commit-tree");
    assert_sha256_oid("commit", &commit);

    // cat-file -t : the commit object is of type `commit`.
    let commit_type = git::cat_file_type(repo, &commit).expect("cat-file -t commit");
    assert_eq!(commit_type, "commit", "committed object must be a commit");

    let blob_type = git::cat_file_type(repo, &blob).expect("cat-file -t blob");
    assert_eq!(blob_type, "blob", "written object must be a blob");

    // cat-file -p : the blob content round-trips byte-identically.
    let read_back = git::cat_file_content(repo, &blob).expect("cat-file -p blob");
    assert_eq!(
        read_back, payload,
        "blob content must round-trip byte-identically"
    );

    // update-ref --stdin with CAS: point a ref at the commit (old = zero / create).
    let refname = "refs/turingos/tape_tip";
    git::update_ref(repo, refname, &commit, None).expect("update-ref create");

    // Re-reading the ref must resolve to the commit OID.
    let resolved = git::rev_parse(repo, refname).expect("rev-parse refname");
    assert_eq!(resolved, commit, "ref must resolve to the commit OID");

    // A stale CAS old-OID must be REJECTED (CAS precondition actually enforced).
    let bogus_old = "0".repeat(64);
    let stale = git::update_ref(repo, refname, &commit, Some(&bogus_old));
    assert!(
        stale.is_err(),
        "update-ref with a wrong old-OID must fail the CAS precondition"
    );

    // fsck --strict : the store is clean.
    git::fsck(repo).expect("git fsck --strict must be clean");
}
