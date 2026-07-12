//! WP6 — F4 泄漏门 unit-test wrapper.
//!
//! Spec source: research/RES_ECON_emergence_toplevel_design_20260707.md §4 (F4 row) / §7
//! (WP6 row); ADR-ECON-003 Decision 5. The gate's scan logic lives in
//! `tools/gates/gate_f4_econ_leakage.sh` (single source of truth, invoked identically from
//! CI shell and from `cargo test`); this file only wires it into `cargo test -p
//! turing-daemons` and asserts both self-test directions plus a live real-tree scan.
//!
//! This test never edits `crates/turing-economy/src/lib.rs` or any other scanned source:
//! it only invokes a read-only scan script and, for the seeded-leak direction, mutates a
//! throwaway tempdir fixture that the script itself creates and destroys.

use std::path::PathBuf;
use std::process::Command;

fn repo_root() -> PathBuf {
    // crates/turing-daemons -> repo root is two levels up.
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(std::path::Path::parent)
        .expect("repo root")
        .to_path_buf()
}

fn gate_script() -> PathBuf {
    repo_root().join("tools/gates/gate_f4_econ_leakage.sh")
}

#[test]
fn f4_leakage_gate_self_test_passes_both_directions() {
    let script = gate_script();
    assert!(script.is_file(), "gate script missing at {script:?}");

    let output = Command::new("bash")
        .arg(&script)
        .arg("--self-test")
        .output()
        .expect("run gate self-test");

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        output.status.success(),
        "F4 leakage gate self-test failed (exit {:?}); stdout={stdout} stderr={stderr}",
        output.status.code()
    );
    assert!(
        stdout.contains("F4_LEAK_SELF_TEST_PASS"),
        "self-test did not report F4_LEAK_SELF_TEST_PASS; stdout={stdout}"
    );
}

#[test]
fn f4_leakage_gate_clean_on_current_tree() {
    let script = gate_script();
    let output = Command::new("bash")
        .arg(&script)
        .output()
        .expect("run gate scan on live tree");

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        output.status.success(),
        "F4 leakage gate found a leak on the real tree (exit {:?}); stdout={stdout} stderr={stderr}",
        output.status.code()
    );
    assert!(
        stdout.contains("F4_LEAK_PASS"),
        "expected F4_LEAK_PASS on clean tree; stdout={stdout}"
    );
}
