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

## Checkpoint 2 — HW-SW-008 (attestation_policy.toml + policy.rs, device_identity.json + identity.rs)

- `attestation_policy.toml` written at worktree root per PREDICATE B1:
  `[policy]` (schema_version="attestation_policy.v1",
  freshness_max_age_s=300, nonce_required=true), `[tpm]` (required_pcrs=[],
  allowed_banks=["sha256"], ak_cert_required=false), `[tee]`
  (allowed_enclave_measurements=[], allow_debug=false), `[degraded]`
  (simulator_allowed=true, on_fail="halt_authorization").
- `device_identity.json` written per PREDICATE B2: schema_id, device_id,
  fixed created_at, identity_route="os_keyring", public_keys=[] (empty,
  comment-free JSON), lineage={parent_device:null, enrollment_receipt:null}.
- `crates/turing-attest/src/policy.rs`: `AttestationPolicy` +
  `PolicyError` (BadSchemaVersion, MissingSection, BadOnFail,
  DebugWithoutSimulator, Parse) + `validate()`.
- `crates/turing-attest/src/identity.rs`: `DeviceIdentity` + `IdentityError`
  (BadSchemaId, UnknownIdentityRoute, NonAsciiKey, Parse) + `validate()`;
  reuses `turing_contracts::jcs::parse_strict` for the non-ASCII-key check
  (no reimplementation).
- Bug found + fixed during this atom: `jcs::parse_strict` enforces the
  canonical-envelope "no trailing newline" framing rule, which fired on the
  on-disk JSON file's normal trailing newline and was misclassified as a
  parse error rather than the framing quirk it is. Fix: both
  `identity.rs::parse` and `qt_quote.rs::parse` now call
  `jcs::parse_strict(text.trim_end_matches('\n'))` — strips one on-disk
  convention artifact before the structural check; `serde_json::from_str`
  (the actual typed decode) still runs on the untouched `text`.
- `cargo test -p turing-attest policy` → 4/4 green. `cargo test -p
  turing-attest identity` → 3/3 green.

Next: HW-SW-009 (lib.rs Attestor/SimulatedAttestor — already implemented and
green from the red-first commit; qt_quote.rs — already implemented; four
q_t_quote fixtures still to author).
