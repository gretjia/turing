# LESSONS — HW-SW-010..013

Three targeted reworks occurred during this loop. Each is a distinct
cause, captured once, fixed once (no repeat-cause rework).

## Rework 1 — EXIT trap referencing a callee's `local` variable

**Cause:** `scripts/attest-tpm.sh`'s first working draft declared
`SWTPM_PID`/`WORKDIR` as `local` inside `run_simulator()` and defined
`cleanup()` (registered via `trap cleanup EXIT`) as a nested function in
that same scope. `trap ... EXIT` is process-global, not function-scoped:
by the time the trap actually fires (process exit), `run_simulator`'s
local-variable scope has already been popped, so `cleanup()`'s reference
to `$SWTPM_PID` hit `set -u`'s "unbound variable" and aborted the cleanup
handler itself — before it could `kill` the swtpm child or `rm -rf` the
temp state dir. Net effect: a real swtpm process (and its temp dir) leaked
on every failure path, observed directly via `ps aux | grep swtpm` after a
failed run.

**Fix:** moved the cleanup state (`SWTPM_PID`, an array `CLEANUP_DIRS`) to
script-global scope, defined `cleanup()` at top level referencing only
those globals, and set the `trap cleanup EXIT` once near the top of the
script (before any mode runs). `run_simulator` now *appends* to
`CLEANUP_DIRS` instead of holding its own local copy.

**Rule extracted:** an `EXIT` trap must only ever reference variables
whose scope outlives every possible call site of the function it's
registered from — in practice this means script-global state, never a
`local` belonging to the function that happens to call `trap ... EXIT`.
Recipients: any future script in this repo that spawns a background
process and needs teardown-on-exit (Phase 5 BootGate scripts, Phase 6
receipt tooling).

## Rework 2 — `od` collapses repeated identical lines with `*`

**Cause:** `hex_of_file()` used plain `od -An -tx1 file | tr -d ' \n'` to
hex-encode a binary file for the receipt JSON. `od`'s default behavior
collapses a run of identical 16-byte output lines into a single `*`
marker (to keep terminal output short) — POSIX/GNU `od`'s standard
space-saving behavior, not a bug in `od` itself. Any binary blob with a
repeated byte pattern longer than one `od` line (e.g. an all-zero,
not-yet-extended PCR value) silently produced a corrupted, non-hex `*`
character embedded in the "hex" string. First caught by an assertion in
`tests/divergence.rs`-adjacent manual inspection of `receipt_sim.json`'s
`pcr_digest` field, which contained literal `*` characters.

**Fix:** `od -v -An -tx1` — `-v` disables the line-collapsing behavior,
guaranteeing every byte is printed. (The equivalent Rust-side path,
`crate::hex_lower` operating directly on an in-memory byte slice via
`std::fs::read`, was never affected — this bug is specific to shelling
through `od`'s human-oriented default output mode.)

**Rule extracted:** any script that hex-encodes a file via `od` MUST pass
`-v`; the collapsing behavior is silent (no warning, no error) and only
manifests on inputs with repeated byte runs, which real PCR/quote data
frequently has (e.g. any not-yet-extended, all-zero PCR).
Recipients: any future script in this repo that hex/byte-dumps a binary
file via `od` (Phase 6 receipt tooling, Phase 7 TEE evidence scripts).

## Rework 3 — swtpm/libtpms transient-object-slot exhaustion mid-roundtrip

**Cause:** both the shell harness and the Rust `TpmAttestor::quote_in`
ran `tpm2_createek` → `tpm2_createak` → `tpm2_quote` back-to-back against
a single swtpm instance with no flushing between steps. swtpm/libtpms
provisions only a small, fixed number of transient-object slots; on a
freshly-started TPM this sequence intermittently failed at the
`tpm2_quote` step's `Esys_ContextLoad` of `ak.ctx` with `tpm:warn(2.0):
out of memory for object contexts` (`0x902`) — reproduced independently
in interactive manual testing, in the shell script, and in the Rust
`hardware_quote_roundtrip` test before the fix.

**Fix:** added a `flush_transient()` helper (`tpm2_flushcontext -t/-s/-l`,
each best-effort/non-fatal) called before `tpm2_createek` and again after
each of `tpm2_createek`/`tpm2_createak`/`tpm2_quote`, in both
`scripts/attest-tpm.sh` and `crates/turing-attest/src/tpm.rs`. Re-ran the
full roundtrip (script 3x, `cargo test -p turing-attest` with
`--test-threads=1`) with zero further OOM failures.

**Rule extracted:** any tpm2-tools shell-out sequence that chains more
than one context-creating step against the SAME live TPM instance
(simulator or real) must flush transient objects between steps; do not
assume single-shot tpm2-tools invocations always self-clean the TPM's
transient-object table. Recipients: Phase 5 BootGate (measured-boot PCR
reads), Phase 6 receipt tooling, Phase 7 TEE (if it ever chains
TPM-adjacent calls), Phase 11 silicon Q_T quote wiring.

No same-cause double failure occurred (three distinct causes, one rework
each); no pinned-file diff; no constitution touch; no Cargo.lock package
outside pre-existing turing-contracts deps (`sha2`/`hex`/toml-family, all
present before this loop); `verify()` correctly rejects a tampered
qualifying value (`hardware_quote_roundtrip`'s negative assertion);
`AttestorKind`'s three pre-existing variants (`Simulated`, `Tpm`, `Tee`)
are untouched, only `Vtpm`/`TpmSimulator` added.
