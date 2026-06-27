use turing_execd::workers::{Provenance, WorkerKind};
use turing_execd::{FakeWorker, ManualCompletion, ManualCopyPasteWorker, WorkerRunRequest};

#[test]
fn fake_worker_receipt_full_provenance() {
    let request = WorkerRunRequest {
        capsule_id: "wc_demo".to_string(),
        grant_id: "grant_demo".to_string(),
    };

    let fake = FakeWorker::new("worker_fake");
    assert_eq!(fake.profile().kind, WorkerKind::Fake);
    assert_eq!(fake.profile().provenance, Provenance::Full);

    let receipt = fake.run(request.clone()).expect("fake receipt");
    let same_receipt = fake
        .run(request.clone())
        .expect("deterministic fake receipt");
    assert_eq!(receipt, same_receipt);
    assert_eq!(receipt.schema_id, "execution_receipt.v1");
    assert_eq!(receipt.capsule_id, "wc_demo");
    assert_eq!(receipt.worker_id, "worker_fake");
    assert_eq!(receipt.exit_code, Some(0));
    assert_eq!(receipt.timeout_class, "none");
    assert!(receipt.stdout_hash.starts_with("sha256:"));
    assert!(receipt.stderr_hash.starts_with("sha256:"));
    assert_eq!(receipt.provenance, Provenance::Full);
    assert!(receipt.credential_material_absent);
    assert!(!receipt.micro_refs_moved);

    let manual = ManualCopyPasteWorker::new("worker_manual");
    assert_eq!(manual.profile().kind, WorkerKind::Manual);
    assert_eq!(manual.profile().provenance, Provenance::Full);
    let manual_receipt = manual
        .complete(
            request,
            ManualCompletion {
                stdout: "manual output".to_string(),
                stderr: String::new(),
                diff: Some("diff --git a/file b/file".to_string()),
                done_json: Some(r#"{"status":"done"}"#.to_string()),
            },
        )
        .expect("manual receipt");
    assert_eq!(manual_receipt.worker_id, "worker_manual");
    assert_eq!(manual_receipt.provenance, Provenance::Full);
    assert!(manual_receipt.diff_hash.unwrap().starts_with("sha256:"));
    assert!(
        manual_receipt
            .done_json_hash
            .unwrap()
            .starts_with("sha256:")
    );
    assert!(manual_receipt.credential_material_absent);
    assert!(!manual_receipt.micro_refs_moved);
}
