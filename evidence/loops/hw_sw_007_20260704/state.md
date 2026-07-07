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

## Checkpoint 3 — HW-SW-009 (turing-attest skeleton + q_t_quote fixtures)

- `lib.rs`: `Attestor` trait, `AttestorKind`, `AttestationQuote`,
  `AttestError::NotYetImplemented`, `SimulatedAttestor` (signature always
  `"simulated:" + hex(qualifying)` via a local `hex_lower` helper — no `hex`
  crate added, since `turing-attest`'s only allowed deps are
  serde/serde_json/toml/turing-contracts). `tpm.rs::TpmAttestor` and
  `tee.rs::TeeAttestor` stubs return `AttestError::NotYetImplemented { phase:
  "phase04" }` / `{ phase: "phase07" }`. These were already implemented in
  the red-first commit and passed immediately (no external data file
  needed); this checkpoint is their gate confirmation.
- `qt_quote.rs`: `QtQuote`/`Quoted`/`Quote` serde structs, `QtQuoteError`,
  `qualifying_digest()` = `sha256_hex(canonicalize(quoted))` via
  `turing_contracts::jcs` (reused, not reimplemented), `validate()`.
- Four fixtures authored under `fixtures/`:
  - `q_t_quote.valid.json` — kind=simulated; `quote.pcr_digest` computed via
    a throwaway test invoking the real `qualifying_digest()` function (value
    a02529a2d625f18ca9708c756fb407b70787e33453db3abaf0ae4aafd23aae46),
    confirmed self-consistent by `qt_quote_valid_parses_and_digest_self_consistent`;
    `policy_hash` = real sha256 of the committed `attestation_policy.toml`.
  - `q_t_quote.invalid_schema.json` — `schema_id = "q_t_quote.v0"`.
  - `q_t_quote.invalid_digest.json` — `quote.pcr_digest` deliberately zeroed.
  - `q_t_quote.invalid_nonascii.json` — the `quote.kind` key renamed to a
    non-ASCII variant (`"kìnd"`).
- Gate-relevant fix: doc comments in `lib.rs`/`tpm.rs`/`tee.rs` originally
  spelled out the literal macro names (`` `panic!`/`todo!`/`unimplemented!` ``)
  to describe the "never panics" contract; PREDICATE G's grep
  (`grep -rn 'todo!\|unimplemented!\|panic!' crates/turing-attest/src/`) is a
  plain string match with no comment awareness, so those doc comments were
  themselves false-positive hits. Reworded to describe the constraint in
  prose without the literal macro-with-bang substrings. Re-ran the grep after
  the edit: zero matches.
- `cargo test -p turing-attest` (whole crate): 19/19 green
  (2 attestor + 3 identity + 6 manifest + 4 policy + 4 qt_quote).
- `grep -rn 'todo!\|unimplemented!\|panic!' crates/turing-attest/src/` →
  clean (no output).

Next: Phase gate G1..G6.
