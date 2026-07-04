# HW-SW-010..013 — Loop State

## Checkpoint 0 — Red-first

- `crates/turing-attest/src/lib.rs`: additive `AttestorKind::{Vtpm,
  TpmSimulator}` variants (existing `Simulated`/`Tpm`/`Tee` untouched).
- New test files targeting the final HW-SW-011 API shape
  (`tests/tpm.rs`, `tests/divergence.rs`, `tests/common/mod.rs` — a
  `SwtpmGuard` helper that spawns its own swtpm), plus an updated
  `tests/attestor.rs` (old unit-struct `TpmAttestor` stub assertions
  replaced with construction-only checks against the new API; TEE stub
  test kept as-is).
- `scripts/attest-tpm.sh`: mode-dispatch skeleton, every body `TODO; exit
  1`.
- `crates/turing-attest/src/tpm.rs` deliberately left as the exact Phase-3
  stub in this commit.
- Captured red: `cargo test -p turing-attest` fails to compile (2 error
  classes: unresolved `TpmError` import, missing `simulator`/`device`
  associated fns) and `./scripts/attest-tpm.sh --simulator` exits 1 — both
  in `red_first.txt`. `git diff Cargo.lock` confirmed empty before commit.
- Commit: `316f67c` `test: hw-sw-010 red-first tpm tests`.

## Checkpoint 1 — HW-SW-010 (swtpm simulator harness)

- `scripts/attest-tpm.sh --simulator` fully implemented: mktemp state dir,
  `swtpm_setup --tpm2 --createek`, `swtpm socket` on a free loopback TCP
  port pair (data + data+1 control, per `tcti-swtpm`'s convention), poll
  via `tpm2_startup -c` retries (not raw `/dev/tcp`), full
  `tpm2_createek` → `tpm2_createak` → `tpm2_quote` → `tpm2_checkquote`
  roundtrip over a fixed qualifying value, receipt written to
  `receipt_sim.json`.
- Two real bugs found and fixed during development (root cause in
  `LESSONS.md` reworks 1-2): an `EXIT` trap referencing a callee's
  `local` variable (leaked the swtpm process on every failure path,
  fixed by making cleanup state script-global) and `od`'s default
  line-collapsing corrupting hex output for repetitive PCR bytes (fixed
  with `od -v`).
- Verified: ran 3x clean, `receipt_sim.json` `verified:true`, zero leaked
  swtpm processes/temp dirs after any run (`ps aux` checked directly).
- Commit: `944d20b` `feat: hw-sw-010 swtpm simulator harness`.

## Checkpoint 2 — HW-SW-011 (TpmAttestor: PCR read + quote + verify)

- `crates/turing-attest/src/tpm.rs` replaced with a real `TpmAttestor`
  shelling to `tpm2-tools` (`std::process::Command`; no `tss-esapi`, per
  SPEC's locked design decision, documented in-file). Constructors
  `simulator(tcti)`/`device(path)`; inherent `read_pcrs`/`quote`/`verify`
  return typed `TpmError`; `Attestor` trait also implemented.
- `AttestationQuote`'s existing 3-field shape (`kind`/`qualifying`/
  `signature`) is unchanged; the raw AK public key / quote message /
  signature / PCR bytes are packed into `signature` as a small hex-field
  blob (reuses `lib.rs`'s existing `hex_lower`, zero new deps).
- The `Attestor` trait's `quote()` necessarily collapses any `TpmError`
  into the sole existing `AttestError::NotYetImplemented` variant on
  failure, since `lib.rs`'s only permitted additive surface this phase is
  `AttestorKind` variants (confirmed by the original roadmap doc's
  allowed_files note "module wiring + TpmError re-export only" and by
  `Display`'s exhaustive match — adding an `AttestError` variant would
  require touching that match too, outside the permitted diff). Rich
  errors are only available via the inherent methods. **Flagged as the
  one thing a verifier should scrutinize hardest.**
- Third bug found and fixed (`LESSONS.md` rework 3): swtpm/libtpms
  transient-object-slot exhaustion mid-roundtrip
  (`tpm:warn(2.0): out of memory for object contexts`), same root cause
  reproduced independently in the shell script and in Rust; fixed with a
  `flush_transient()` helper called between `createek`/`createak`/
  `quote` in both places.
- `cargo test -p turing-attest`: 23/23 green (includes
  `hardware_quote_roundtrip`, which spawns its own swtpm via
  `tests/common/mod.rs::SwtpmGuard` and asserts both the happy-path
  `verify() Ok` and the tampered-qualifying `Err(VerifyFailed)`
  negative). `cargo clippy -p turing-attest --all-targets`: one
  `manual_is_multiple_of` nit found and fixed, then clean.
- Commit: `b758f1c` `feat: hw-sw-011 tpm attestor shell backend`.

## Checkpoint 3 — HW-SW-012 (seal/unseal to PCR policy)

- `scripts/attest-tpm.sh --seal-test`: PCR policy (`sha256:0,7`) via
  `tpm2_startauthsession` + `tpm2_policypcr`, seals a SECONDARY demo
  secret (`tpm2_create -L policy`) under a fresh ECC primary — explicitly
  not the sovereign approval key; that custody stays with
  `SigningBackend`/`turing-approval`, untouched. Unseals successfully
  while PCRs match, `tpm2_pcrextend`s PCR 0, asserts unseal now fails
  closed (a genuine policy-check failure, `0x99D`, confirmed distinct
  from the transient-object OOM by explicitly flushing first).
- Refactored `--simulator`'s swtpm bring-up into a shared `start_swtpm()`
  helper reused by `--seal-test`; re-verified `--simulator` still passes
  after the refactor.
- `seal_test.json` `{sealed:true, unseal_ok_when_matching:true,
  unseal_fails_after_pcr_change:true}`. Ran 3x clean.
- Commit: `66b461a` `feat: hw-sw-012 seal to pcr policy`.

## Checkpoint 4 — HW-SW-013 (real vTPM path + divergence)

- `scripts/attest-tpm.sh --real`: same quote roundtrip as `--simulator`
  against the real `/dev/tpmrm0` device, every tpm2-tools call (and the
  `base64`/`od` readback of the root-owned context files `sudo` creates)
  wrapped in `sudo -n`. No PCR extend, no seal/unseal, no
  `turing-approval` touch — read-only quote only (the real device's PCR
  state is shared/persistent, unlike the simulator's throwaway state
  dir).
- `sudo -n true` succeeds in this implementer's shell (verified directly
  before relying on it), so `receipt_real.json` was produced here, not
  deferred to the orchestrator. `run_real()` still has the documented
  fallback (`NOTE: sudo -n unavailable ...; return 1`, no fabricated
  receipt) for an environment where it does not.
- Extracted a shared 32-byte `QUALIFYING_VALUE` constant used by both
  `--simulator` and `--real` (the prior `--simulator`-only inline value
  was only 31 bytes and mode-specific) so the two receipts are
  comparable.
- `hardware_manifest.toml`: `[device].tpm.present` `false` → `true`
  (additive; confirmed not in `substrate_freeze_manifest.toml`'s pinned
  set).
- `crates/turing-attest/tests/divergence.rs::sim_real_divergence` now
  runs its full structural comparison (both receipts present, no
  skip-note): both `verified:true`, same `pcr_selection`, identical
  `qualifying_hex`, kinds differ (`TpmSimulator` vs `Vtpm`), AK public
  keys differ.
- `cargo test -p turing-attest`: 23/23 green. `cargo test --workspace`
  (`--test-threads=1`): all green, no replay/tape impact. `git diff
  Cargo.lock`: empty.
- Commit: `bf68d21` `feat: hw-sw-013 real vtpm path and divergence`.

## Phase gate

G1..G8 all PASS — full transcript in `gate_receipt.txt`. Commit `2986ecc`
`docs: hw-sw-010-013 gate receipt`.

Status ceiling: **ADDRESSED**, pending sovereign accept. Not self-claimed
CLOSED/RELEASED/RATIFIED; no OG-10/genesis signature or M2 enablement
claimed.
