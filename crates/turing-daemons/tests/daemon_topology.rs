use std::process::Command;

fn run(bin: &str, args: &[&str]) -> std::process::Output {
    let path = match bin {
        "turingd" => env!("CARGO_BIN_EXE_turingd"),
        "turing-execd" => env!("CARGO_BIN_EXE_turing-execd"),
        "turing-mcp" => env!("CARGO_BIN_EXE_turing-mcp"),
        "turing-marketd" => env!("CARGO_BIN_EXE_turing-marketd"),
        "turing-pputd" => env!("CARGO_BIN_EXE_turing-pputd"),
        "turing-viewd" => env!("CARGO_BIN_EXE_turing-viewd"),
        other => panic!("unknown test binary {other}"),
    };
    Command::new(path).args(args).output().expect("run daemon")
}

#[test]
fn daemon_check_reports_process_boundaries() {
    let cases = [
        ("turingd", "role=turingd", "can_move_accepted_head=true"),
        (
            "turing-execd",
            "role=turing-execd",
            "can_move_accepted_head=false",
        ),
        (
            "turing-mcp",
            "role=turing-mcp",
            "can_move_accepted_head=false",
        ),
        (
            "turing-marketd",
            "role=turing-marketd",
            "can_move_accepted_head=false",
        ),
        (
            "turing-pputd",
            "role=turing-pputd",
            "can_move_accepted_head=false",
        ),
        (
            "turing-viewd",
            "role=turing-viewd",
            "can_move_accepted_head=false",
        ),
    ];

    for (bin, role, truth_boundary) in cases {
        let output = run(bin, &["--check"]);
        assert!(output.status.success(), "{bin} --check failed: {output:?}");
        let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
        assert!(stdout.contains(role), "{bin} missing role: {stdout}");
        assert!(
            stdout.contains(truth_boundary),
            "{bin} missing truth boundary: {stdout}"
        );
        assert!(
            stdout.contains("single_loop_subroutine=true"),
            "{bin} must acknowledge Single Loop boundary: {stdout}"
        );
    }
}

#[test]
fn non_authority_daemons_reject_head_movement() {
    for bin in [
        "turing-execd",
        "turing-mcp",
        "turing-marketd",
        "turing-pputd",
        "turing-viewd",
    ] {
        let output = run(bin, &["move-accepted-head"]);
        assert!(!output.status.success(), "{bin} must reject head movement");
        let stderr = String::from_utf8(output.stderr).expect("stderr UTF-8");
        assert!(stderr.contains("cannot move accepted_head"), "{stderr}");
    }
}
