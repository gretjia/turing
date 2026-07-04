# CONTEXT — HW-SW-007..009 Hardware Manifest & Attestation Schemas (Phase 3)

Route: turing_full / plan lite / Tier 3 (no high_risk) / horizon on. Founder launched HW-SW-007
2026-07-04 after sovereign-accepting the Phase 1+2 merge (6c634f1 on goal/mini-swe-bench-grok-worker).
Branch: turing/phase03-attest-schemas from 6c634f1. Everything this phase is P0 pure software that
DEFINES the P1/P2 contract surface — no TPM/TEE code, no hardware.

## Design sources (read both before coding; they contain the annotated schemas)
- /home/zephryj/turingos_backup/work/docs/roadmap/secure_os_18_month/phases/phase_03_hardware_manifest.md
- /home/zephryj/turingos_backup/work/docs/roadmap/secure_os_18_month/06_boot_gate.md  (§b hardware_manifest.toml,
  §c attestation_policy.toml, §d device_identity.json, §e q_t_quote.json + the JCS qualifying-digest binding rule)

## Verified repo facts
- Workspace: exact-pinned (=) deps; crates live in crates/; workspace members listed in root Cargo.toml.
- turing-contracts has src/jcs.rs (JCS canonicalization — use it for the q_t_quote qualifying digest;
  read its public API before use).
- `toml` crate is NOT in Cargo.lock. DECISION (orchestrator, founder-visible): turing-attest may add
  `toml` as an exact-pinned dependency — first new external dep of the roadmap; Cargo.lock WILL change.
  The Cargo.lock diff must contain ONLY: turing-attest itself, toml and its direct transitive deps
  (serde_spanned, toml_datetime, toml_edit/winnow or similar). Nothing else. Record the exact new
  package list in the gate receipt.
- Constitution sha256 (real, goes into [measurements].constitution_sha256):
  a0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0
  (file: ../../turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md relative to workspace root
  /home/zephryj/turingos_backup/work — READ-ONLY, never write).
- Phase-0 Q1: ASCII-only load-bearing keys in all schemas. schema_version field mandatory in every file.
- Dev machine identity (P0 values for the instance files): identity_route = "os_keyring";
  no TPM enumerated yet (hardware_manifest [device] tpm.present = false until Phase 4 fills it);
  [degraded] simulator_allowed = true (P0), on_fail = "halt_authorization" (authorization freezes,
  tape appends never blocked — Art. 0.2: failure appends too).
- Freeze manifest pins 5 crate files + constitution; Phase 3 touches NONE of them → no REPIN needed;
  audit-substrate-freeze.sh must stay green untouched.
- Ceiling: ADDRESSED, pending sovereign accept. Commit style: subject ≤50 chars, details in body.
- QtQuote here = serde struct + validation + JCS qualifying-digest fn ONLY (schema layer). The TPM
  wiring of QtQuote is Phase 11; tpm.rs/tee.rs are typed NotYetImplemented stubs (never panic, never
  todo!/unimplemented!).
