use std::process::Command;

fn turing() -> Command {
    Command::new(env!("CARGO_BIN_EXE_turing"))
}

#[test]
fn replay_market_pput_and_audit_commands_are_executable() {
    for (args, expected) in [
        (&["replay", "--verify"][..], "replay: verified"),
        (
            &["market", "replay", "--verify"][..],
            "market replay: verified",
        ),
        (&["pput", "replay", "--verify"][..], "pput replay: verified"),
        (&["audit", "invariants"][..], "audit invariants: pass"),
        (&["audit", "market"][..], "audit market: pass"),
        (&["audit", "pput"][..], "audit pput: pass"),
    ] {
        let output = turing().args(args).output().expect("run turing command");
        assert!(
            output.status.success(),
            "command {args:?} failed: {output:?}"
        );
        let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
        assert!(
            stdout.contains(expected),
            "stdout missing {expected:?}: {stdout}"
        );
        assert!(
            !stdout.contains("accepted because CI passed"),
            "CLI must not imply macro green is truth"
        );
    }
}

#[test]
fn unknown_command_fails_closed() {
    let output = turing()
        .arg("market-loop")
        .output()
        .expect("run unknown command");
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).expect("stderr UTF-8");
    assert!(stderr.contains("unknown turing command"));
}

#[test]
fn boot_project_writes_private_local_project_metadata() {
    let dir = tempfile::tempdir().expect("temp dir");

    let output = turing()
        .args([
            "boot",
            "--project",
            dir.path().to_str().expect("UTF-8 temp path"),
        ])
        .output()
        .expect("run boot project");

    assert!(output.status.success(), "boot failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("boot: wrote"));

    let metadata_path = dir.path().join(".turingos").join("project.json");
    let text = std::fs::read_to_string(metadata_path).expect("project metadata");
    assert!(text.contains(r#""schema_id":"operator_project.v1""#));
    assert!(text.contains(r#""project_root":"#));
    assert!(text.contains(r#""truth_source":"micro_tape""#));
    assert!(text.contains(r#""credential_material_included":false"#));
    assert!(text.contains(r#""can_write_micro_truth":false"#));
}

#[test]
fn approval_preview_renders_human_card_without_writing_truth() {
    let output = turing()
        .args([
            "approval",
            "preview",
            "--approval-id",
            "ap_cli_preview",
            "--authority-epoch",
            "7",
            "--action",
            "capsule_approve",
            "--subject",
            "wc_cli",
            "--risk",
            "P2",
            "--evidence-digest",
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "--signature-route",
            "none",
        ])
        .output()
        .expect("run approval preview");

    assert!(output.status.success(), "preview failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("approval preview:"));
    assert!(stdout.contains("approval_id=ap_cli_preview"));
    assert!(stdout.contains("action=capsule_approve"));
    assert!(stdout.contains("subject=wc_cli"));
    assert!(stdout.contains("risk=P2"));
    assert!(stdout.contains("signature_route=None"));
    assert!(stdout.contains("visible_card_hash=sha256:"));
    assert!(stdout.contains("writes_micro_truth=false"));
    assert!(!stdout.contains("signature="));
    assert!(!stdout.contains("credential"));
}

#[test]
fn handoff_generate_writes_real_projection_hashes() {
    let dir = tempfile::tempdir().expect("temp dir");
    let output_path = dir.path().join("handoff.md");

    let output = turing()
        .args([
            "handoff",
            "generate",
            "--output",
            output_path.to_str().expect("UTF-8 temp path"),
        ])
        .output()
        .expect("run handoff generate");

    assert!(
        output.status.success(),
        "handoff generate failed: {output:?}"
    );
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("handoff: wrote"));

    let text = std::fs::read_to_string(&output_path).expect("handoff file");
    for label in [
        "tape_tip: mu:",
        "authorization_head:",
        "accepted_head: mu:",
        "market projection hash: sha256:",
        "wallet projection hash: sha256:",
        "PPUT projection hash: sha256:",
        "cargo test --workspace",
        "scripts/install-local.sh",
        "turing approval preview",
        "scope/budget/provenance/replay",
        "turing replay --verify",
        "Known Risks",
    ] {
        assert!(text.contains(label), "generated handoff missing {label:?}");
    }
    assert!(
        !text.contains("required final handoff field"),
        "generated handoff must replace placeholder language"
    );
}
