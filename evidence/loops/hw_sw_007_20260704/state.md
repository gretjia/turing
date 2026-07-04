# HW-SW-007..009 — Loop State

## Checkpoint 1 — HW-SW-007 (hardware_manifest.toml + manifest.rs)

- `hardware_manifest.toml` written at worktree root with real sha256
  measurements:
  - `constitution_sha256` = sha256 of
    `turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md`
    (pinned value, matches CONTEXT.md).
  - `schema_pack_sha256` = sha256 of `crates/turing-contracts/src/jcs.rs`.
  - `predicate_pack_sha256` = sha256 of `crates/turing-predicate/src/lib.rs`.
  - `runtime_binary_sha256` = sha256 of `Cargo.lock` (P0 proxy, documented
    in-file); computed AFTER the red-first commit stabilized the toml-family
    dependency resolution, so it will not drift for the rest of this loop
    (no further Cargo.toml edits planned).
- `crates/turing-attest/src/manifest.rs`: `HardwareManifest` serde struct
  (deny_unknown_fields, sections optional at the parse layer so `validate()`
  can report a precise `MissingSection`), `ManifestError` (BadSchemaVersion,
  NonAsciiKey, BadDigestFormat, MissingSection, Parse), `validate()`.
- `cargo test -p turing-attest manifest` → 6/6 green (real file parses +
  validates; bad schema_version; missing [signing]; non-hex digest;
  uppercase-hex digest rejected; non-ASCII device.id).
- Command: `cargo test -p turing-attest manifest` — all green, no other
  test targets regressed (policy/identity/qt_quote still red as expected,
  atoms not yet implemented).

Next: HW-SW-008 (attestation_policy.toml + policy.rs, device_identity.json +
identity.rs).
