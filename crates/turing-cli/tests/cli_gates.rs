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
