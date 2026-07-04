# SPEC — Phase 4 HW-SW-010..013 TPM Path (combined context+predicate+capsule)

Route: turing_full / Tier 1 (high_risk, founder pre-authorized autonomous run) / horizon on.
Branch: turing/phase04-tpm-path from goal tip (has merged turing-attest crate). Draft commits only;
merge is orchestrator's on validator PASS. Ceiling: ADDRESSED. Commit subjects ≤50 chars, detail in body.

## Environment (verified by orchestrator — trust these)
- REAL vTPM 2.0 at /dev/tpmrm0 (root-only device). tpm2-tools 5.4, swtpm 0.7.1, libtss2 3.2.1 installed.
- Real TPM2_Quote already proven working on this vTPM. PCRs 0 and 7 populated.
- vTPM is hypervisor-backed, NOT silicon-rooted (no manufacturer EK cert). Receipts MUST use
  kind=Vtpm for the real device and kind=TpmSimulator for swtpm — NEVER a kind that implies silicon.

## KEY DESIGN DECISIONS (locked — do not deviate)
1. TpmAttestor shells out to tpm2-tools via std::process::Command. DO NOT add the tss-esapi crate
   (huge native-link dep tree). Document in tpm.rs: "P0 shell-backend; P1 tss-esapi in-process backend
   is a drop-in replacement behind the unchanged Attestor trait." Zero new Rust deps this phase
   (Cargo.lock diff MUST be empty — verify).
2. Automated cargo gate uses the SWTPM SIMULATOR (user-space socket, NO sudo). The real /dev/tpmrm0
   path is root-only, so it is exercised by scripts/attest-tpm.sh --real under sudo and recorded as
   EVIDENCE, not a blocking cargo test. This matches roadmap philosophy: simulator = gate, real = evidence.
3. Quotes are LOCAL evidence artifacts this phase. They do NOT enter the tape (that is Phase 6).
   TpmAttestor::quote returns AttestationQuote in-memory / writes a receipt JSON to a path.

## Atom HW-SW-010 — swtpm simulator harness
A1. scripts/attest-tpm.sh with modes --simulator and --real:
    --simulator: mktemp state dir; `swtpm socket --tpmstate dir=$D --ctrl type=unixio,path=$D/ctrl
    --server type=unixio,path=$D/sock --tpm2 --flags not-need-init &` (or the tcp/mssim variant that
    works — pick whichever tpm2-tools TCTI connects to reliably; swtpm_setup --tpm2 --tpmstate $D
    first). Export TPM2TOOLS_TCTI to the swtpm. Run full roundtrip (createprimary→createak→quote→
    checkquote) with a caller-supplied 32-byte qualifying value; emit receipt JSON
    {kind:"TpmSimulator", pcr_selection, pcr_digest, quote_sig_b64, ak_pub_b64, qualifying_hex,
    produced_at, verified:true} to evidence/loops/hw_sw_010_20260704/receipt_sim.json; tear down swtpm.
    Exit 0 iff tpm2_checkquote passes. --real: same but TPM2TOOLS_TCTI=device:/dev/tpmrm0, run under
    the script's own `sudo -n` for tpm2 calls, kind="Vtpm", receipt_real.json.
    set -euo pipefail; trap-cleanup the swtpm process + tempdir.
A2. `./scripts/attest-tpm.sh --simulator` exits 0 and produces receipt_sim.json with verified:true.

## Atom HW-SW-011 — TpmAttestor (PCR read + quote + verify)
B1. crates/turing-attest/src/tpm.rs: replace the NotYetImplemented stub with a real TpmAttestor that
    shells to tpm2-tools. Config: TpmAttestor::simulator(socket_or_tcti: String) and
    TpmAttestor::device(path: String) constructors; kind()→Vtpm|TpmSimulator accordingly. Methods:
    read_pcrs(&self, sel: &str)->Result<PcrSet,TpmError>; quote(&self, qualifying:&[u8;32])->
    Result<AttestationQuote,TpmError> (runs createprimary+createak ephemeral or reuses a cached ak
    ctx in a temp dir; returns quote msg+sig+ak_pub+pcr_digest); verify(&self, q:&AttestationQuote,
    qualifying:&[u8;32])->Result<(),TpmError> (tpm2_checkquote against ak_pub + nonce). Typed TpmError
    (ToolNotFound, TctiUnavailable, QuoteFailed{stderr}, VerifyFailed, Parse). Additive: extend
    AttestorKind with Vtpm, TpmSimulator (read existing enum in lib.rs first; keep existing variants).
    Implement Attestor trait for TpmAttestor (quote()->AttestationQuote{kind,...}).
B2. cargo test -p turing-attest hardware_quote_roundtrip: starts a swtpm simulator (a #[cfg(test)]
    helper that spawns swtpm on a temp unix socket, or shells scripts/attest-tpm.sh internals; if
    swtpm binary absent, the test prints "SKIP: swtpm unavailable" and returns Ok — but here swtpm IS
    present so it must actually run), builds TpmAttestor::simulator, takes a quote over a fixed
    qualifying value, asserts verify() Ok, asserts a tampered qualifying value → verify() Err.
    NO sudo in cargo tests.

## Atom HW-SW-012 — seal/unseal to PCR policy
C1. scripts/attest-tpm.sh gains --seal-test mode (simulator): create a PCR policy (tpm2_createpolicy
    -L pcr on sha256:0,7), seal a secondary secret (tpm2_create with -L policy + -i secret), unseal it
    (tpm2_unseal after tpm2_policypcr) → success while PCRs match; then extend a PCR (tpm2_pcrextend)
    and assert unseal now FAILS (policy no longer satisfied). Emit seal_test.json {sealed:true,
    unseal_ok_when_matching:true, unseal_fails_after_pcr_change:true}. The sealed key is a SECONDARY
    secret, explicitly NOT the sovereign approval key (document: key custody stays with SigningBackend).
C2. `./scripts/attest-tpm.sh --seal-test` exits 0 with all three booleans true.

## Atom HW-SW-013 — real-TPM path + sim/real divergence
D1. `sudo -n ./scripts/attest-tpm.sh --real` produces receipt_real.json {kind:"Vtpm", verified:true}
    (orchestrator will run this; implementer must make it work but may not have sudo in every context
    — if sudo -n fails in the implementer's shell, still write the script correctly and note in
    state.md that the real receipt is orchestrator-produced).
D2. crates/turing-attest/tests/divergence.rs (or a test in tpm.rs): compares receipt_sim.json and
    receipt_real.json IF both exist (skip-with-note if receipt_real absent in implementer env):
    assert both verified:true, both quote the SAME pcr_selection, both structurally valid, AK differs
    (sim AK != vtpm AK), kinds differ (TpmSimulator vs Vtpm). A structural divergence beyond the
    expected (e.g. one unverified) = test failure. Document: identical qualifying data yields
    structurally-equal quotes modulo signer; that is the divergence contract.

## Phase gate
G1 cargo test -p turing-attest (all green; hardware_quote_roundtrip actually ran swtpm)
G2 ./scripts/attest-tpm.sh --simulator  (exit 0, receipt_sim.json verified)
G3 ./scripts/attest-tpm.sh --seal-test  (exit 0)
G4 ./run_test.sh --human-journey 2>/dev/null || echo "run_test.sh absent — note, non-blocking"; then
   the combined line: ./scripts/attest-tpm.sh --simulator   (SW+HW combined acceptance)
G5 ./scripts/audit-substrate-freeze.sh exit 0 (no pinned file touched — tpm.rs is in turing-attest,
   not pinned; confirm)
G6 ./scripts/audit-forbidden-files.sh --staged exit 0
G7 (cd /home/zephryj/turingos_backup/work && bash PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/governance/verify_alignment.sh) GREEN
G8 git diff <base>..HEAD -- Cargo.lock EMPTY (zero new Rust deps)

## allowed_files
crates/turing-attest/src/tpm.rs, crates/turing-attest/src/lib.rs (ADDITIVE: AttestorKind variants,
mod/re-export only — NOT the existing trait/quote/error semantics), crates/turing-attest/tests/**,
scripts/attest-tpm.sh, hardware_manifest.toml (tpm.present flips true, ADDITIVE), evidence/loops/hw_sw_010_20260704/**
## forbidden_files
**/00_authority/**, *constitution_root_law.md*, crates/turing-approval/**, crates/turing-kernel/**,
crates/turing-replay/**, crates/turing-git-tape/**, crates/turing-contracts/**, substrate_freeze_manifest.toml,
Cargo.lock (must stay zero-diff), scripts/audit-*.sh (Phase 1 audits — read/run only)

## Red-first
Commit tpm.rs tests + divergence test + script skeleton that fails (stub still NotYetImplemented) →
capture red → evidence/.../red_first.txt → implement to green. Never squash red.
## Mini-Recovery triggers
swtpm/real quote both fail; verify accepts tampered nonce; Cargo.lock non-empty; pinned-file or
constitution touch; AttestorKind existing variant changed; sudo not the cause of a logic failure
being masked (a real logic bug hiding behind "sudo unavailable" must be surfaced, not skipped).
## IPQC: calc 5400 0.05 → floor(5400*0.05)=270 → 270 steps (checkpoint after each atom).
