use turing_execd::macro_anchor::{MacroAnchor, MacroAnchorError, MacroAnchorKind};

#[test]
fn macro_anchor_never_micro_identity() {
    let diff = MacroAnchor::new(
        MacroAnchorKind::Diff,
        "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    .expect("diff anchor");
    assert_eq!(
        diff.as_str(),
        "macro:diff:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    );
    assert!(!diff.as_str().starts_with("mu:"));
    assert!(!diff.is_micro_identity());

    assert_eq!(
        MacroAnchor::parse("mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
        Err(MacroAnchorError::MicroIdentityRejected)
    );
    assert_eq!(
        MacroAnchor::parse("macro:ci:green")
            .expect("macro anchor")
            .kind(),
        MacroAnchorKind::Ci
    );
    assert_eq!(
        MacroAnchor::parse("diff:sha256:abc"),
        Err(MacroAnchorError::MissingMacroPrefix(
            "diff:sha256:abc".to_string()
        ))
    );
}
