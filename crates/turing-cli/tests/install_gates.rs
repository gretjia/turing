use std::path::Path;
use std::process::Command;

fn repo_root() -> &'static Path {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("crate has crates parent")
        .parent()
        .expect("workspace root")
}

#[test]
fn install_local_wires_cli_and_daemon_binaries_into_prefix() {
    let prefix = tempfile::tempdir().expect("temp prefix");
    let script = repo_root().join("scripts").join("install-local.sh");

    let output = Command::new("bash")
        .current_dir(repo_root())
        .arg(script)
        .arg("--prefix")
        .arg(prefix.path())
        .arg("--profile")
        .arg("debug")
        .output()
        .expect("run install script");

    assert!(output.status.success(), "install failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("installed turing"));
    assert!(!stdout.contains("accepted because CI passed"));

    let bin_dir = prefix.path().join("bin");
    for name in [
        "turing",
        "turingd",
        "turing-execd",
        "turing-marketd",
        "turing-pputd",
        "turing-viewd",
        "turing-mcp",
    ] {
        let path = bin_dir.join(name);
        assert!(
            path.is_file(),
            "missing installed binary {}",
            path.display()
        );
    }

    let check = Command::new(bin_dir.join("turingd"))
        .arg("--check")
        .output()
        .expect("run installed turingd");
    assert!(
        check.status.success(),
        "installed turingd failed: {check:?}"
    );
    let stdout = String::from_utf8(check.stdout).expect("check stdout UTF-8");
    assert!(stdout.contains("role=turingd"));
    assert!(stdout.contains("can_move_accepted_head=true"));
    assert!(stdout.contains("single_loop_subroutine=true"));
}
