use std::time::Duration;

use turing_execd::process::{ProcessGroupRunner, ProcessSpec, TimeoutClass};

#[test]
fn process_group_term_then_kill_no_orphans() {
    let runner = ProcessGroupRunner::new();
    let receipt = runner
        .run(ProcessSpec {
            program: "sh".to_string(),
            args: vec!["-c".to_string(), "trap '' TERM; sleep 5".to_string()],
            timeout: Duration::from_millis(100),
            term_grace: Duration::from_millis(50),
        })
        .expect("process receipt");

    assert_eq!(receipt.timeout_class, TimeoutClass::Hard);
    assert!(receipt.term_sent);
    assert!(receipt.kill_sent);
    assert!(receipt.no_orphans);
    assert!(receipt.stdout_hash.starts_with("sha256:"));
    assert!(receipt.stderr_hash.starts_with("sha256:"));
    assert!(
        receipt.elapsed < Duration::from_secs(2),
        "timeout runner should not wait for the child sleep duration"
    );
}
