# PREDICATE — HW-SW-007..009 (commands from worktree root)

## Atom HW-SW-007 — hardware_manifest.toml + validator
A1. `hardware_manifest.toml` exists at worktree root: [device] (id, platform, tpm.present=false,
    tpm.version="2.0", tee.kind="none"), [measurements] (constitution_sha256 =
    a0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0, schema_pack_sha256,
    predicate_pack_sha256, runtime_binary_sha256 — placeholder "unmeasured" values are FORBIDDEN;
    compute real sha256s of real files and document in comments which file each measures; for
    runtime_binary use the sha256 of Cargo.lock as the P0 proxy and say so in a comment),
    [signing] (route="os_keyring", key_id, algorithm="ed25519"), [pcr_baseline] (bank="sha256",
    pcrs = {} empty with comment "populated Phase 5"), schema_version="hardware_manifest.v1".
A2. `cargo test -p turing-attest manifest` green: HardwareManifest serde struct + validate() with
    typed ManifestError (BadSchemaVersion, NonAsciiKey, BadDigestFormat{field}, MissingSection{name});
    tests: real file parses+validates; negative vectors (bad schema_version, non-hex digest,
    uppercase-hex rejected or normalized — pick one and test it) each rejected with the RIGHT variant.

## Atom HW-SW-008 — attestation_policy.toml + device_identity.json + validators
B1. `attestation_policy.toml`: [policy] (schema_version="attestation_policy.v1", freshness_max_age_s,
    nonce_required=true), [tpm] (required_pcrs=[], allowed_banks=["sha256"], ak_cert_required=false),
    [tee] (allowed_enclave_measurements=[], allow_debug=false), [degraded] (simulator_allowed=true,
    on_fail="halt_authorization"). `cargo test -p turing-attest policy` green incl. negative: 
    on_fail value other than halt_authorization|deny_boot rejected; allow_debug=true + 
    simulator_allowed=false combination rejected (debug enclave never allowed in strict mode).
B2. `device_identity.json`: schema_id="device_identity.v1", device_id, created_at (fixed ISO string,
    not generated), identity_route="os_keyring", public_keys=[] (empty, comment-free JSON — put
    explanations in the validator doc comments), lineage={parent_device:null, enrollment_receipt:null}.
    `cargo test -p turing-attest identity` green with negative vectors (unknown identity_route,
    non-ASCII key in JSON object → rejected).

## Atom HW-SW-009 — turing-attest skeleton + q_t_quote schema/fixtures
C1. Crate layout: crates/turing-attest/src/{lib.rs,manifest.rs,policy.rs,identity.rs,qt_quote.rs,
    tpm.rs,tee.rs}. lib.rs: `pub trait Attestor { fn kind(&self) -> AttestorKind; fn quote(&self,
    qualifying: &[u8; 32]) -> Result<AttestationQuote, AttestError>; }` + SimulatedAttestor
    (deterministic: quote.kind=Simulated, signature field = "simulated:" + hex(qualifying) — clearly
    fake, never mistakable for real); tpm.rs::TpmAttestor + tee.rs::TeeAttestor stubs where quote()
    returns Err(AttestError::NotYetImplemented{phase: "phase04"/"phase07"}) — grep must find NO
    todo!/unimplemented!/panic! in the crate: `! grep -rn 'todo!\|unimplemented!\|panic!' crates/turing-attest/src/`.
C2. qt_quote.rs: QtQuote serde struct per 06_boot_gate.md §e (schema_id="q_t_quote.v1", quoted{
    constitution_hash, schema_pack_hash, predicate_pack_hash, runtime_binary_hash, tape_tip,
    authorization_head, accepted_head, signer_route, policy_hash}, nonce, quote{kind, pcr_digest,
    signature, ak_pub_ref}, produced_at, verifier_hint) + `qualifying_digest()` = SHA-256 over
    JCS-canonicalized `quoted` (use turing_contracts::jcs; if contracts lacks a sha256 helper use the
    workspace's existing digest path — find it, do not add a new hash dep).
C3. Fixtures: fixtures/q_t_quote.valid.json (kind=simulated, digest self-consistent — the file's
    quote.pcr_digest equals the computed qualifying digest of its own `quoted`); at least 3 invalids:
    q_t_quote.invalid_schema.json, q_t_quote.invalid_digest.json (mismatched pcr_digest),
    q_t_quote.invalid_nonascii.json. `cargo test -p turing-attest qt_quote` green: valid parses,
    validates, digest recomputation matches; each invalid rejected with the right typed error.
C4. Workspace membership: root Cargo.toml members gains "crates/turing-attest" (only change there);
    crates/turing-attest/Cargo.toml deps: serde, serde_json (workspace-matching exact pins), toml
    (exact pin), turing-contracts path dep. NOTHING else.

## Phase gate
G1. `cargo test -p turing-attest` (all green)
G2. `./scripts/audit-substrate-freeze.sh` exit 0 (no pinned file touched)
G3. `./scripts/audit-forbidden-files.sh --staged` exit 0 on every commit
G4. `cd /home/zephryj/turingos_backup/work && bash PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/governance/verify_alignment.sh` GREEN
G5. `git diff 6c634f1..HEAD --name-only` ⊆ allowed_files; Cargo.lock diff contains ONLY turing-attest
    + toml-family packages (list them in gate receipt: `git diff 6c634f1..HEAD -- Cargo.lock | grep '^+name'`)
G6. `cargo build --workspace` green (workspace still compiles with new member; full test run not
    required — Phase 2 ran it and no existing crate is touched)

## Red-first
Fixtures + failing tests (crate skeleton with tests but empty impls that don't compile OR tests
against missing API) committed with red output → evidence/loops/hw_sw_007_20260704/red_first.txt →
implement to green. Never squash red.

## Mini-Recovery triggers
Same-cause double failure; any pinned-file diff; constitution touch; Cargo.lock gaining any package
outside the toml-family allowlist; any panic path found in turing-attest; SimulatedAttestor output
that could be mistaken for a real quote (missing "simulated" marking).
