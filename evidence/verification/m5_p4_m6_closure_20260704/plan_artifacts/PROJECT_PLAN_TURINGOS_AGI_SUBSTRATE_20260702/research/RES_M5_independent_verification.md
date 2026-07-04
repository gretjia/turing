# RES_M5 — Research Report: Independent Verification & Release Machinery (ending the self-closure meta-bug)

- Module: M5 — Independent Verification & Release Machinery
- Date: 2026-07-02
- Author: Research agent (Fable-5-class), M5 research track (commissioned as atom M5.P0 per playbook §3.4)
- Status: RESEARCH INPUT to the M5 module plan. This document confers no CLOSED/RATIFIED status on anything. All on-disk claims below were verified against the workspace on 2026-07-02 at repo `./turing` (branch `goal/mini-swe-bench-grok-worker`, HEAD `bed759777f9cb21c53e5701c8070654ad4dc4212`); every such claim carries an absolute path. Claims sourced from the public web are marked WEB and dated; claims that are reasoned analysis (not measured) are marked ANALYSIS.
- Serves: KPI G6 (independent verification). Directly answers audit findings F1 (the external release gate has never run externally — the program's most severe finding) and R5 in `/home/zephryj/turingos_backup/work/TURINGOS_RETROSPECTIVE_AUDIT_FINDINGS_20260702.md`.
- Binding anchor: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/01_PROJECT_INTENT.md` (G6: "≥1 genuinely external exact-SHA audit PASS ...; ClosureCertificate.v1 issued by a custody-separated cross-family verifier; RELEASED status mechanically impossible without the external artifact").
- Red-line note (binding): private keys never on this host (Intent §5.1; workspace CLAUDE.md). Every design below is therefore signature-free on this host: certificate authenticity comes from custody separation + owner-recorded digests, not from local signing. (§2.10 refines this: *verifier-side* Ed25519 signing — key in the verifier's own custody, never on this host — is red-line compatible and is the recorded v1.1 upgrade path; the rejection in §2.2 A is of *local* signing only.)
- Revision 1.1 (2026-07-02, tracker atom M5.P0 scope-completion addendum): adds §1 Q9–Q11, §2.9–§2.12, §4 P11–P12, §5.9–§5.11, §6 ADR-M5-006/007. All pre-existing section numbers are unchanged, so every RES_M5 §-citation in `PROGRESS_TRACKER.md` and `modules/MODULE_M5_independent_verification.md` v1.0.0 remains valid. This revision changes the file's sha256; the tracker Pins row (`e1c20eb5…`) requires a Decision Log re-pin entry per playbook §1 step 3 — flagged to the orchestrator, not self-applied (tracker is not this atom's file).

---

## 1. Questions this research answers

1. What exactly failed in the prior release machinery (F1), as evidenced on disk — and which specific artifacts/prose patterns must the new machinery make unrepresentable?
2. What is the `ClosureCertificate.v1` schema, and how is it made structurally impossible for an implementer-side context to issue one?
3. What custody separation actually severs session/toolchain lineage — as a checkable property list, not a vibe — and what are the operator/model options (audit R5)?
4. What is the exact-SHA release-packet format, and what does the packet builder tool (`tools/release/build_packet.sh` or equivalent, consumed by FCE §10.2 and FCE-S1 step 6) assemble?
5. Which EXISTING packet is the strongest candidate for the first genuinely external audit (M5.P3), and why?
6. How does RELEASED become *mechanically* impossible without the external artifact (the G6 KPI's negative-test clause)?
7. What do verifier prompt templates that contain zero implementer context look like, and how is "zero lineage" itself checked?
8. How does the per-module closure verification service (M5.P4) run as a standing queue across waves W1→W4 without serializing the program?
9. What does the legacy stage release-packet skeleton (the commissioned "16-field packet") actually specify on disk, was it ever instantiated, and how does `turingos.release_packet.v1` subsume it field by field — including killing its implementer-writable `release_next_stage` field?
10. Which existing headless verifier tooling (the G12-A/G12-B wrappers, `grok_verify.py` / `claude_final_ratify.py`) is reusable for M5, and how does this plan's unsigned certificate reconcile with the omega-track *signed* `ClosureCertificate.v1` already specified in `TOP_ALIGNMENT_PROJECT_BOOK.md`?
11. What seeded-defect packet corpus calibrates the audit protocol itself — since an audit that cannot fail a deliberately bad packet is not an audit — and how do those negative controls differ from the §5.6 release-gate refusal fixtures?

---

## 2. Candidate methodologies, patterns, and stacks

### 2.1 On-disk ground truth: the F1 failure, located (all verified 2026-07-02)

- **Every prior "independent" audit is same-session.** Example, typical of the class: `/home/zephryj/turingos_backup/work/turing/evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/independent_recursive_audit.md` line 5 — "Auditor: independent subagent `019f0c89-ff31-7d81-ab24-fd6234dd7eed`" — a Claude subagent of the producing session. Stage14 has the same pattern (`.../mini_swe_bench_stage14_corpus_failure_memory_20260628/independent_recursive_audit.md`).
- **Zero external verdict artifacts exist anywhere.** `find evidence -iname "*external*verdict*" -o -iname "*external_audit_result*"` over `/home/zephryj/turingos_backup/work/turing/` returns nothing (run 2026-07-02). What exists instead are UNANSWERED auditor prompts: `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_official_harness_qualification_20260629/EXTERNAL_AUDITOR_PROMPT.md`, `.../mini_swe_bench_stage12_20task_loop_20260628/external_auditor_prompt_stage12.md`, `.../mini_swe_bench_stage14_corpus_failure_memory_20260628/external_auditor_prompt_stage14.md`, and the docs-level `/home/zephryj/turingos_backup/work/turing/docs/handoff/EXTERNAL_AUDITOR_PROMPT_STAGE12_TO_STAGE16.md`. The letters were written; none was ever sent or answered.
- **The escape hatch is verbatim on disk.** `/home/zephryj/turingos_backup/work/turing/docs/handoff/STAGE12_TO_STAGE16_RECURSIVE_AUDIT_PLAN.md:78`: "Only an external **or designated independent** audit PASS on the exact pushed SHA releases the next stage." The disjunction's second arm is what the same-session subagents satisfied — this exact pattern is banned by playbook §2.3 ("no disjunctive escape hatches") and must be unrepresentable in M5's schemas (§2.6).
- **The release rules were otherwise well designed — they just weren't enforced by anything.** Same file, lines 85–88: any `NOT_RUN`/`BLOCKED`/`LEGACY_MISSING`/missing-artifact ⇒ `release_next_stage: NO`. And the stage12 release audit records the requirement as a boolean nothing consumes: `/home/zephryj/turingos_backup/work/turing/evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/stage12_release_audit.json` — `"external_exact_sha_audit_required": true, "local_release_candidate": true`. The gap between "required: true" and "no mechanism checks it" is the whole F1 defect.
- **Digest-manifest precedent exists.** Stage roots already ship `bundle_sha256s.txt` (stage12, stage14 — verified present in both roots above) and sealed manifests (`task_manifest.sha256` idiom, RES_M3 §2.4). The packet builder generalizes this to a complete, closed manifest.
- **No release tooling and no certificate schema exist.** `/home/zephryj/turingos_backup/work/turing/tools/release/` does not exist (verified: `ls` fails); `grep -rln "ClosureCertificate"` over the repo's `docs/`, `tools/`, `crates/`, `src/` returns nothing (2026-07-02). The name comes from the audit's recommendation layer (audit F8/§5 "the closure machinery (cross-family verifier, ClosureCertificate.v1) remains prose") — M5 is greenfield here, constrained only by this plan's schemas (GateVerdict.v1, M0.P6).
- **Candidate first-audit packets on disk:** (a) harness qualification packet `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_official_harness_qualification_20260629/` (README: 19/20 → repair → 20/20 upstream Docker replay; `CLAIM_BOUNDARY.json` blocks campaign-launch/full-score claims; has `EXTERNAL_AUDITOR_PROMPT.md` with an expected-verdict block; NO complete digest manifest — only `patch_manifest.json`); (b) stage12 root (real 20-task grok run, strict MicroTape audit PASS, `bundle_sha256s.txt` present — but its "solved" counts came from the repo-local evaluator with a demonstrated false positive, django-11885, audit F4); (c) stage6 strict-microtape root (already independently re-executed once by the retrospective audit itself — audit §3 row 3).

### 2.2 ClosureCertificate.v1: schema design candidates

| Candidate | What it is | Pros | Cons |
|---|---|---|---|
| A. Locally signed certificate (Ed25519 on this host) | Verifier signs the JSON | Cryptographic binding | **Violates the key red line** (private keys never on this host; the genesis-key custody rule generalizes — Intent §5.1). Signing keys for verifiers would have to live somewhere this program controls, recreating self-issuance. REJECT for this increment |
| **B. Unsigned JSON + custody metadata + out-of-band digest anchoring (RECOMMEND)** | Certificate is plain JSON produced by the verifier in ITS custody; the verifier (or owner) records `sha256(certificate)` through a channel the implementer does not control (owner Decision Log entry, or the external operator's own storage); the in-repo copy is a *mirror* whose digest must match the anchored one | No keys on any program host; authenticity = custody + anchoring; trivially auditable with `sha256sum`; matches the program's existing owner-gate idiom (tracker Decision Log as the owner channel, playbook §5.1) | Anchoring depends on the owner/auditor channel being genuinely out-of-band — made checkable by the custody property list (§2.3); weaker than cryptographic signatures against a fully adversarial insider (accepted residual risk, recorded in ADR-M5-001) |
| C. Sigstore/DSSE-style keyless attestation | in-toto statement, subject digest binding, short-lived cert via OIDC identity (WEB, 2026-07: [SLSA v1.0 provenance](https://slsa.dev/spec/v1.0/provenance), [verifying artifacts](https://slsa.dev/spec/v1.0/verifying-artifacts), [slsa-verifier](https://github.com/slsa-framework/slsa-verifier)) | Industry-standard artifact↔attestation binding; no long-lived private keys | Requires OIDC identity infra + network trust roots this air-gapped-ish workflow doesn't have; overkill for one program increment. **Adopt its SHAPE, not its stack**: the certificate is structured like an attestation — a subject block (`packet_sha256` + repo SHA) bound to a predicate (verification result) by an identified verifier — so a later migration to signed attestations is a field-preserving upgrade |

**Recommended schema (full JSON in §5.1):** subject block (`gate_id`, `packet_sha256`, `repo_sha`), verifier identity block (kind, operator, model family, credentials class), custody checklist (six booleans, §2.3 — ALL must be true), verification block (commands + literal exit codes, inputs checked, digest-manifest result), verdict `PASS|FAIL` (closed enum, no third value), and a `status_semantics` block hard-coding `implementer_ceiling: ADDRESSED`.

**Structural self-closure ban (load-bearing):** the certificate is a *verifier-side* schema, disjoint from the implementer's GateVerdict.v1 (M0.P6): different `schema_id` (`turingos.closure_certificate.v1`), REQUIRED custody fields that an implementer context cannot truthfully populate, and a validator (§5.2) that REJECTS any certificate whose verifier identity matches any identity in the packet's implementer manifest, whose custody booleans are not all true, or whose predicate text contains a disjunction (` or `/`||` between predicate alternatives — the §2.1 escape hatch made a lint target). An implementer writing a certificate is thereby a schema validation error, not a discovered misdeed (mirror of FCE §10.4's "self-elevation is made unrepresentable, not merely forbidden").

### 2.3 Custody separation: what actually severs lineage (audit R5)

Candidates, strongest to weakest:

| Tier | Verifier | Severs | Residual lineage |
|---|---|---|---|
| **E1 (external-human)** | A different human operator, own machine/account, receives only the packet + runbook | Session, toolchain, model family, credentials, filesystem | None that this program can see. REQUIRED for M5.P3's "genuinely external" and for FCE §9 item 4 |
| **E2 (external-model)** | A cross-family model account with its own credentials, fresh OS user or machine, clone from the packet's bundle/URL, no shared conversation state | Session, model family, credentials | Same physical host possible; the owner provisions the account (playbook §5.1: OWNER-PROVIDED, BLOCKED-on-owner until the channel is in the Decision Log). Acceptable for M5.P4 module closures where the tracker says "M5-class" |
| I1 (internal fresh-context) | Same-program sub-agent per playbook §2.3 | Conversation state only | Same toolchain, same model family, same custody — this is the F1 pattern; it raises confidence but can NEVER issue a ClosureCertificate (playbook §2.3 ceiling discipline). It is the per-phase verifier, not the closure verifier |

**The checkable property list (goes into the certificate as booleans; the runbook instructs how each is evidenced):**

1. `fresh_clone` — working copy created from the packet's git bundle or a public URL at the pinned SHA, in a directory that never hosted implementer work (evidence: `git clone` transcript + `git rev-parse HEAD`).
2. `no_shared_conversation_state` — the verifier session was started with the packet + runbook + gate spec ONLY (evidence: the verifier attests the complete input list; the prompt template of §5.5 is the whole input).
3. `no_implementer_transcript` — no summary, reasoning, or narrative from any implementer context was provided (checked by lineage-scrub lint over the submitted materials, §2.7).
4. `own_credentials` — any accounts/API keys used belong to the verifier/owner-provisioned auditor identity, not to the implementer sessions (evidence: credential-class statement; never the credentials themselves).
5. `cross_family_or_human` — the verifier is a human, or a model family different from every family that produced the packet's contents (evidence: identity block vs the packet's implementer manifest).
6. `own_custody_output` — the certificate was created and stored in verifier custody first; the anchored digest (owner Decision Log or auditor storage) predates or equals the in-repo mirror's timestamp (evidence: anchoring reference recorded in the certificate mirror's sidecar).

ANALYSIS: items 1–3 kill the F1 recurrence (same-session subagents fail 2 and 3 by construction); items 4–6 kill the subtler variant where the "external" party is operated through the implementer's own channels.

### 2.4 Exact-SHA release-packet format and the builder tool

**Packet = a directory (or tarball) that lets an outsider re-execute the gate from nothing.** Contents (generalizing the verified `bundle_sha256s.txt` idiom):

```
packet_<gate_id>_<date>/
  PACKET_MANIFEST.json        # schema_id turingos.release_packet.v1: gate_id, repo_sha,
                              #   dataset/tape digests, implementer manifest (identities/model
                              #   families that produced contents), builder tool version
  MANIFEST.sha256             # sorted `sha256sum` over EVERY file below (closure: no file
                              #   in the packet is outside the manifest except MANIFEST itself)
  repo.bundle                 # git bundle at the pinned SHA (or clone URL + SHA if too large)
  tapes/*.bundle              # MicroTape bundles + their sha256s
  evidence/...                # verdict JSONs, receipts, harness reports — the gate's artifact list
  REEXECUTION.md              # ordered command list with expected exit codes / verdict shapes
  CLAIM_BOUNDARY.json         # what the packet does NOT claim
  AUDITOR_RUNBOOK.md          # §5.4 — how an outsider verifies from this packet alone
```

**Builder:** `tools/release/build_packet.sh` (repo-side once repo writes are authorized; a plan-directory prototype is legal earlier). It: (1) asserts clean tree + records `git rev-parse HEAD`; (2) copies the gate's declared artifact list (from the module spec §3 required-artifacts list — the builder takes the list as input, it does not decide it); (3) `git bundle create` for repo + tapes; (4) writes `MANIFEST.sha256` LAST and verifies closure (every packet file listed exactly once); (5) prints `packet_sha256` = sha256 of the sorted manifest file. FCE §10.2 invokes exactly this (`bash tools/release/build_packet.sh --root "$ROOT" --sha "$CERT_SHA"` — `09_FINAL_CERTIFICATION_EVALS.md` line 419) and FCE-S1 step 6 consumes it, so the CLI surface must accept `--root` and `--sha`. The self-test: build a fixture packet, tamper one byte, assert `sha256sum -c MANIFEST.sha256` fails (clean/tamper discrimination per M0.P6's pattern).

WEB (2026-07, pattern citation): binding a subject digest to a verification predicate and verifying "an immutable name by digest to avoid TOCTOU" is the SLSA/in-toto attestation model ([SLSA provenance](https://slsa.dev/spec/v1.0/provenance), [slsa-verifier](https://github.com/slsa-framework/slsa-verifier)); a ClosureCertificate is functionally a Verification Summary Attestation over the packet digest ([verifying artifacts](https://slsa.dev/spec/v1.0/verifying-artifacts)).

### 2.5 First external audit target (M5.P3): choose the harness qualification packet

| Option | Evidence | Verdict |
|---|---|---|
| **Harness qualification packet** | `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_official_harness_qualification_20260629/` — genuine upstream `swebench==4.1.0` Docker evidence, honest 19/20→repair→20/20 arc, per-instance upstream logs in `harness_logs_raw.tar.gz` (audit §3 row 2, adversarially CONFIRMED), an already-written `EXTERNAL_AUDITOR_PROMPT.md` with expected-verdict block, machine-readable `CLAIM_BOUNDARY.json` | **RECOMMEND.** Strongest truth-value per audit; self-contained; the auditor can re-verify digests + log internal consistency without Docker, and optionally re-run the 20-task replay (1–3 h, RES_M3 §2.6) for full depth. Gap the builder must fix: no complete `MANIFEST.sha256` today (only `patch_manifest.json`) |
| Stage12 root | Real 20-task run + strict MicroTape audit + `bundle_sha256s.txt` | Second choice: its solve counts rely on the repo-local evaluator (demonstrated false positive django-11885, audit F4), so an external audit would partly certify a number the program itself has deprecated. Usable later as a MicroTape-focused audit |
| Stage6 strict-microtape root | Already re-executed by the retrospective audit with reproduced PASS | Weakest incremental value — the strongest check on it has effectively been done once; keep as the auditor's warm-up exercise inside the runbook, not the headline |

ANALYSIS: M5.P3's KPI is "≥1 genuinely external exact-SHA audit" — the packet's job is to be maximally re-executable and honestly bounded. A FAIL outcome is valid for the phase (tracker M5.P3 note) but G6 and M5.G block on a PASS existing somewhere, so pick the packet most likely to be *correctly judged*, which is the one whose claims are narrowest and best evidenced.

### 2.6 Making RELEASED mechanically impossible (the negative-test clause)

Layered, all cheap:

1. **The gate script:** `tools/release/assert_release_eligible.sh <packet_dir> <certificate.json>` exits nonzero unless ALL hold: certificate validates against the v1 schema (§5.2); `certificate.subject.packet_sha256` equals the recomputed packet digest; `verdict == "PASS"`; all six custody booleans true; verifier identity disjoint from the packet's implementer manifest; anchoring reference present. Only this script may emit the artifact `RELEASE_ELIGIBLE.json`; anything that says RELEASED without citing that artifact is a defect.
2. **The vocabulary layer:** the program's status vocabulary has no RELEASED an implementer may write (playbook §6.1), and M0.P6's claims lint greps program-authored artifacts for implementer-written CLOSED/RELEASED/RATIFIED — M5 adds the release-specific rule: `RELEASED` may appear only inside `RELEASE_ELIGIBLE.json`-citing artifacts.
3. **The schema layer:** `RELEASE_ELIGIBLE.json` itself carries `{"eligible": true, "certificate_sha256": ..., "packet_sha256": ...}` and the FCE verdict schema has no SHIPPED/RELEASED value an agent can emit (FCE §10.4's `overall_enum` — the precedent this rule copies).
4. **The negative tests (the M5.P5 gate + FCE-S6):** scripted attempts — (i) no certificate, (ii) implementer-identity certificate, (iii) subject-digest mismatch — must each be refused with a machine-readable reason; one positive control (a FIXTURE-labeled well-formed certificate) must validate. FCE-S6 re-runs exactly this battery at certification (`09_FINAL_CERTIFICATION_EVALS.md` §3 FCE-S6), so M5.P5's fixtures should be written to be reusable by it.

**Disjunction ban, enforced:** the certificate validator and the gate-spec lint reject predicate strings matching `\bexternal\b.*\bor\b.*\b(designated|internal)\b` and any `verdict`-adjacent enum wider than {PASS, FAIL} — the literal F1 hatch (§2.1) becomes a failing test case in the validator's self-test corpus.

### 2.7 Verifier prompt templates with zero implementer context

Template contents (complete input set — nothing else enters the verifier session; §5.5 has the text): gate spec verbatim (predicate + required-artifacts list from the module spec), packet path/digest + runbook, the Drift-Check Checklist, the §6.1 status vocabulary + ADDRESSED-ceiling paragraph, constitution + Intent pointers, and the output contract (certificate schema + where to store it in verifier custody). **Banned content, enforced by a lineage-scrub lint over the submission bundle:** implementer transcripts, "summary of what we did", tracker Session-log excerpts, any prose from implementer-authored READMEs beyond the packet's own claim-boundary files, and any suggestion of the expected verdict — with one deliberate exception: an `EXPECTED_VERDICT` block is permitted ONLY when the packet's own pre-existing auditor prompt already published one (the qualification packet does, §2.1); the runbook then instructs the auditor to compute their verdict BEFORE opening that block (recorded as a runbook step, ANALYSIS: removing it entirely would require editing a historical evidence root, which is forbidden).

### 2.8 The standing closure queue (M5.P4) without serializing the program

- Queue semantics: each module gate reaching ADDRESSED enqueues a closure job (M1.G, M2.TC5/G, M3.G, M4.G, M6.G — tracker M5.P4 row); jobs are independent; the orchestrator treats the queue as event-driven work, not a phase to "finish" (MODULE_M5 provisional §1.5 insight, preserved).
- Each job = build packet (§2.4) → submit via the owner-recorded auditor channel → certificate-or-FAIL recorded; a FAIL routes back to the owning module and the job re-enters the queue with a new packet after repair (mirror of the M5.P3 FAIL→resubmit loop already in the tracker).
- Turnaround target ≤1 elapsed day per closure of verifier work, with external-party latency recorded separately and excluded (provisional module spec's target, kept — ANALYSIS: it is a packet-quality forcing function, not an SLA on humans).
- Until the owner records the auditor channel in the Decision Log, M5.P3/P4 are BLOCKED-on-owner and only P0–P2/P5 proceed (playbook §5.1 — already in the tracker; this report changes nothing there).
- **Owner-provided-auditor rule + G6 FAIL→resubmit loop, restated as binding (tracker M5.P3/P4 rows):** the external auditor (different human operator, or cross-family model account with its own credentials) is OWNER-PROVIDED per playbook §5.1. A FAIL artifact completes phase M5.P3 *honestly* but does NOT satisfy G6: the failure routes to the owning module, the defect is repaired, and a NEW packet at a new SHA is built and resubmitted (never patched in place — §4 P10); M5.G and FCE's G6 entry block on ≥1 external PASS artifact *existing*, not on the phase having run once.

### 2.9 The legacy release-packet skeleton, verified — and why `release_next_stage` dies (task scope c)

- **Verified on disk:** `/home/zephryj/turingos_backup/work/turing/docs/handoff/STAGE12_TO_STAGE16_LOOP_ENGINEERING_EXECUTION_PLAN.md` lines 169–193 ("## Release Packet / Every stage must produce:") — a text skeleton of **17 keys** (lines 174–190): `stage, commit_sha, branch, evidence_root, evidence_root_github_url, bundle_manifest, bundle_sha256s, strict_audit_json, stage_specific_audit_jsons, independent_recursive_audit, external_auditor_prompt, commands_run, local_verification_summary, negative_controls, claim_boundary, open_risks, release_next_stage`, closed by "No stage may release without GitHub-visible evidence and exact pushed SHA" (line 193). The commission called this the "16-field packet"; the on-disk block counts 17 keys (recounted 2026-07-02) — recorded verbatim so downstream atoms cite the artifact, not the label.
- **Never instantiated.** `find evidence -name "*release_packet*"` over `/home/zephryj/turingos_backup/work/turing/` returns nothing (2026-07-02), and the closest artifact — `/home/zephryj/turingos_backup/work/turing/evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/stage12_release_audit.json` — has key set `{claim_boundary, external_exact_sha_audit_required, local_release_candidate, problems, run_count, runs, schema_id, solved_count, status, strict_status_summary, supplied_strict_status_summary, truth_source, unsolved_count}`: neither `negative_controls` nor most skeleton keys exist in it (verified via json key dump, 2026-07-02). Same F1 pathology as §2.1: a well-designed schema in prose that no tool ever generated or validated.
- **The step-13 hatch, precisely located (task scope b):** `/home/zephryj/turingos_backup/work/turing/docs/handoff/STAGE12_TO_STAGE16_RECURSIVE_AUDIT_PLAN.md:78` is *Stage Gate Contract step 13* — the contract's final, release-deciding step: "Only an external **or designated independent** audit PASS on the exact pushed SHA releases the next stage." The hatch sat exactly at the release boundary, which is why every stage "released" on same-session subagent audits. Killed twice over in this design: (i) the certificate's `verifier.kind` enum is closed over `{external_human_operator, external_cross_family_model}` — there is no "designated internal" value to write; (ii) the §2.6 disjunction regex keeps the literal string as a permanent failing test case.
- **Subsumption:** `turingos.release_packet.v1` (§2.4) carries every load-bearing legacy field under mechanical validation, with three deliberate changes (full field map in §5.9): `release_next_stage` is **removed** — an implementer-writable release verdict inside the packet is a self-closure channel; eligibility exists only as `RELEASE_ELIGIBLE.json` emitted by the §2.6 gate. `independent_recursive_audit` is removed from the packet — the audit is the packet's *output* (the certificate), never its input. `negative_controls` is promoted from an empty prose slot to a REQUIRED, digest-pinned corpus (§2.11).

### 2.10 Reuse assets: G12-A/G12-B wrappers, and reconciliation with the omega-track signed certificate (task scope g)

- **Verified on disk:** `/home/zephryj/turingos_backup/work/turing/tools/headless/grok_verify.py` (358 lines; docstring "G12-A Grok independent-verifier wrapper") and `/home/zephryj/turingos_backup/work/turing/tools/headless/claude_final_ratify.py` (281 lines; "G12-B Claude final-ratifier wrapper"), both built on `/home/zephryj/turingos_backup/work/turing/tools/headless/headless_common.py` (`NO_HUMAN_STATE_CEILING = "READY_FOR_HUMAN_GENESIS_SIGNATURE"` line 30; `forbidden_claims_present` line 218; `executed_clean_fixture`/`executed_tampered_fixture` lines 284/298; `packet_digest` line 81; `gate_result` line 139).
- **G12 split spec verified:** `/home/zephryj/turingos_backup/work/TOP_ALIGNMENT_PROJECT_BOOK.md` §15.4 (lines 977–987): `G12-A = GrokBuildIndependentVerifier`, `G12-B = ClaudeCodeFinalRatifier`, "G12 product = PASS only if G12-A PASS and G12-B MODEL_RATIFIED and all lower gates PASS"; §15.2 rule 5 (line 943): "optional signed `ClosureCertificate.v1` only if verifier key custody is available and disjoint from implementer/genesis/ratifier keys"; §15.3 shows G12-B consuming G12-A's report, never raw LLM text.
- **What to reuse vs what not to.** Reusable mechanics (lift into M5.P1/P2/P5 tooling and the packet's `REEXECUTION.md`): clean-clone discipline (`make_clean_clone`/`make_ratifier_clone` via `git clone --no-local`, never the implementer worktree); the forbidden-claims lint (`forbidden_claims_present` — exactly the M0.P6 claims-lint idiom, already implemented); stdin/stdout/stderr/tool-binary digest capture (the `ExternalAgentInvocation.v1` shape, §15.1); executed clean/tampered fixture self-tests (the §2.4 builder self-test pattern, already implemented); the fail-closed `GateResult.v1` shape (`product==PASS` requires `exit_status==0` AND every reason PASS AND `not_run==[]`); and the two-stage verify-then-ratify split across model families. **NOT reusable as the G6 verifier itself:** both wrappers are invoked *by the implementer program on this host with program-resident credentials* — that is tier I1 (§2.3), failing custody booleans 4 (`own_credentials`) and 6 (`own_custody_output`) by construction. They become G6-relevant only when the external auditor runs them (or their command shapes, embedded in `REEXECUTION.md`) on the auditor's own host from the packet. ANALYSIS: import the *checks*, never the *authority*.
- **Naming reconciliation (feeds M0/G1; ADR-M5-006).** The workspace already specifies a SIGNED `ClosureCertificate.v1` on the omega track: `TOP_ALIGNMENT_PROJECT_BOOK.md` line 166 (certificate signed by "a key the implementer/host cannot read", custody domain separate from genesis) and line 311 (full required-field list: `verifier_identity_key_id`, `verifier_key_custody_domain`, `probe_suite_source: AUDITOR_SHIPPED`, `signature`, `signature_route`, …). This is *consistent with* the red line, not a violation of it: the Ed25519 private key lives in the VERIFIER's custody, the signing ceremony runs on the verifier's machine, the owner registers the verifier *public* key once (Decision Log), and verification on any host needs public material only (e.g. `ssh-keygen -Y verify` or python `cryptography` — §5.11). §2.2's candidate-A rejection is therefore scoped precisely: *local* signing rejected forever; *verifier-side* signing deferred only because no verifier key-custody channel exists yet (OWNER-PROVIDED, currently BLOCKED). The signed form is the field-preserving v1.1 upgrade of the §5.1 schema. Until then two schemas share one name across tracks: disambiguated by `schema_id` (`turingos.closure_certificate.v1` here, the omega pack's schema elsewhere) and flagged to M0's document registry so G1 *subordinates* the pair rather than silently merging them (§4 P11).

### 2.11 Negative-control corpus: five seeded-defect packets that MUST fail audit (task scope e)

Distinct from §5.6 (which refuses bad *certificates* at the release gate): these are bad *packets* that a competent audit must FAIL. An audit protocol that passes any of them is itself the defect. All five are FIXTURE-labeled at creation, built by `make_negative_controls.sh` (§5.10), digest-pinned, and stored in a calibration corpus outside any real packet.

| ID | Seeded defect | Construction | Layer that MUST catch it |
|---|---|---|---|
| NC-1 | Tampered bundle hash | Build a fixture packet, then flip one byte in a tape bundle AFTER `MANIFEST.sha256` is written | Runbook step 1: `sha256sum -c MANIFEST.sha256` → FAIL, report digest mismatch |
| NC-2 | Fabricated PASS verdict | Edit a verdict JSON from FAIL to PASS, leaving the archived command transcript (exit code 1) contradicting it | Re-execution (`REEXECUTION.md` replay): recomputed verdict ≠ packaged verdict; if edited post-build, also NC-1's manifest check |
| NC-3 | Fixture mislabeled REAL | Take a FIXTURE artifact (deterministic placeholder digests / fixture-probe markers) and stamp it `evidence_class: REAL` | Fixture-labeling lint (M0.P6 claims-lint class; `fixture_probe.py` idiom at `/home/zephryj/turingos_backup/work/turing/tools/headless/fixture_probe.py`) + runbook rule: verify every `evidence_class` label against content |
| NC-4 | Missing receipt | Delete one receipt/verdict file that `PACKET_MANIFEST.json`'s required-artifacts list declares | Auditor's manifest-vs-required-list cross-check (every declared artifact present exactly once); the builder's closure check refuses to *build* such a packet, so the control is seeded post-build |
| NC-5 | Stale pin | Set `PACKET_MANIFEST.json.repo_sha` to a commit that does not contain the claimed artifacts (packet built at SHA A, manifest claims SHA B) | Runbook step 2: `git clone repo.bundle && git rev-parse HEAD` ≠ manifest `repo_sha` → FAIL |

Usage: (i) the M5.P2 runbook dry-run must record 5/5 seeded FAILs with machine-readable reasons before any real submission; (ii) the M5.P3 submission may include one owner-selected control *blind* as auditor calibration (declared in `CLAIM_BOUNDARY.json` of the calibration corpus, never of a real packet); (iii) FCE-S6 reuses the corpus verbatim. This is also the resurrection of the legacy skeleton's `negative_controls:` key (§2.9) — this time as artifacts a gate consumes, not an empty prose slot.

### 2.12 Provenance frameworks: adopt vs overkill (task scope f)

| Framework / concept | Core idea | Verdict for this context |
|---|---|---|
| in-toto / SLSA attestation shape | Subject digest bound to a predicate by an identified functionary | **ADOPT SHAPE** (already §2.2 C, §2.4): certificate = subject (`packet_sha256`, `repo_sha`) + predicate (verification result) + verifier identity |
| SLSA build levels / hosted-CI provenance | Provenance generated by a trusted build platform | **OVERKILL:** no verified hosted CI exists for the turing repo (playbook §2.2's CI definition); there is no build platform to be the functionary |
| Reproducible-builds attestation (rebuilderd-style independent rebuilds) | Independent parties re-execute and confirm bit-identical outputs | **ADOPT CONCEPT, not infra:** the auditor's depth-2 full replay IS a reproducible-run attestation — same pinned inputs → same digests/verdicts, recorded in the certificate's `verification` block. No rebuilder daemon |
| Witness cosigning / multi-party countersignature | N independent verifiers countersign one claim | **DEFER, schema-ready:** G6 needs one genuinely external verifier; the natural v1.1 widening for FCE certification is a second family (the G12-A verify + G12-B ratify split, §2.10) emitting a SECOND certificate — per-verifier certificates over the same `packet_sha256`, never one multi-signed blob (avoids threshold-signature machinery entirely) |
| Sigstore transparency log (rekor) | Public append-only log of signatures/attestations | **OVERKILL:** the owner Decision Log + anchored digests is the program-scale transparency log (§2.2 B); a public log entry becomes worth considering only if the repo goes public (WEB, 2026-07 pattern: [sigstore docs](https://docs.sigstore.dev)) |

ANALYSIS: the common thread — this program adopts the *data shapes* (subject-digest binding, reproducible re-execution, per-verifier attestations) at zero infrastructure cost, and defers every piece that requires network trust roots, OIDC identity, or daemons.

---

## 3. Recommendation (tied to project goals)

**Adopt: unsigned-JSON ClosureCertificate.v1 with a six-boolean custody checklist and out-of-band digest anchoring; a closed release-packet format with `MANIFEST.sha256` closure built by `tools/release/build_packet.sh` (CLI: `--root`, `--sha`); the harness qualification packet as the first external-audit subject; a three-layer release blocker whose negative tests are FCE-S6-reusable; zero-lineage verifier prompt templates with a lineage-scrub lint; and an event-driven closure queue for per-module certifications.**

- **G6 KPI, clause by clause:** "≥1 genuinely external exact-SHA audit PASS" → §2.5 target + §2.3 E1/E2 custody tiers + owner channel; "ClosureCertificate.v1 issued by a custody-separated cross-family verifier" → §2.2 schema with structural implementer-exclusion; "RELEASED mechanically impossible without the external artifact" → §2.6 layers with negative tests.
- **F1 antidote, made mechanical:** the same-session-subagent pattern fails custody booleans 2/3 at validation time; the "external OR designated" hatch is a failing regex test in the validator corpus; unanswered auditor prompts become a submission protocol with recorded channel + anchored digests.
- **Constitution/red lines:** no signing keys on this host (candidate A rejected); sealed artifacts untouched (packets COPY evidence, never edit roots); implementer ceiling ADDRESSED hard-coded in the certificate's `status_semantics`; NOT_RUN==FAIL preserved (a queue job without a certificate is a recorded FAIL, never a skip).
- **Program cost:** all bash/jq/python-stdlib; the only nontrivial spend is external-auditor time, which the packet format minimizes (digest-first verification path, optional deep re-run). No new tape writers, no repo-schema changes.
- Explicitly rejected: local signing (red line); Sigstore stack (infra overkill — shape adopted, stack deferred); Stage12 as first audit subject (F4-tainted counts); any internal fresh-context path to a ClosureCertificate (F1 recurrence — internal verifiers cap at raising confidence).
- **Addendum adoptions (rev 1.1):** subsume the legacy 17-key stage release-packet skeleton into `release_packet.v1` with `release_next_stage` removed (§2.9, §5.9 — the implementer-writable release verdict was itself a self-closure channel); reuse the G12-A/G12-B wrapper *mechanics* (clean-clone, forbidden-claims lint, digest capture, clean/tampered self-tests) while never granting the locally-invoked wrappers closure authority (§2.10, §5.11); record verifier-side Ed25519 signing as the field-preserving v1.1 certificate upgrade once the owner provisions a verifier key channel (§2.10, ADR-M5-006); ship the five-packet seeded-defect negative-control corpus and require 5/5 audit FAILs before any real submission (§2.11, §5.10, ADR-M5-007).

---

## 4. Pitfalls & mitigations

| # | Pitfall | Mitigation |
|---|---|---|
| P1 | **Fake externality** — a "different operator" fed implementer summaries or run through implementer accounts recreates F1 | Six-boolean custody checklist in the certificate (§2.3); lineage-scrub lint over the submission bundle (§2.7); validator rejects certificates whose verifier identity intersects the packet's implementer manifest |
| P2 | **Escape-hatch reintroduction** — a future gate text quietly restores "external OR internal" | Validator + gate-spec lint with the disjunction regex as a permanent failing-corpus case (§2.6); playbook §2.3 already bans it program-wide |
| P3 | **Rubber-stamp certificates** — verifier signs off without executing | Certificate REQUIRES `commands_run` with literal exit codes and a digest-manifest result; the runbook's verification path starts with `sha256sum -c` (unfakeable cheaply); spot re-execution of one command by the owner is a recorded option in the runbook |
| P4 | **Implementer-forged certificate** — implementer writes a syntactically valid certificate | Structural: custody booleans + identity-disjointness make it schema-invalid; procedural: anchoring digest must exist in a channel the implementer does not control (owner Decision Log / auditor custody) BEFORE the in-repo mirror appears (§2.2 B) |
| P5 | **Packet incompleteness** — auditor cannot re-execute, audit degenerates to prose review | `MANIFEST.sha256` closure check in the builder; `REEXECUTION.md` with expected exit codes; builder self-test includes a "fresh directory, manifest-verify, run step 1" smoke |
| P6 | **Verifier drift into implementer** — auditor "fixes" a failing artifact to be helpful | Runbook rule: any modification = audit ABORTED, findings-only report; certificates have no "fixed and passed" state (verdict enum is PASS/FAIL only) |
| P7 | **Queue serialization** — closures block program progress while waiting on external latency | Event-driven queue (§2.8); modules proceed to their next wave at ADDRESSED; only EXTERNALLY_VERIFIED-gated consumers (FCE E1, G6 rollup) wait |
| P8 | **FAIL suppression** — an external FAIL quietly parked | Certificate-or-FAIL is the queue invariant; tracker M5.P4/P3 rows require the FAIL artifact cited; FCE-B5-class lint can grep for closure jobs with neither artifact |
| P9 | **Signing-stack temptation** — someone adds "just a local key" for convenience | ADR-M5-001 records the rejection + red line; key-file scan already in FCE automatic-FAIL 5 catches key material on this host |
| P10 | **Stale packet vs moving HEAD** — audit passes on a SHA the repo has left behind | Certificates bind to `repo_sha` + `packet_sha256`; consumers (release gate, FCE E1) verify the digest chain, not "latest"; re-audits after repair are new packets at new SHAs (FCE §11's "never patched in place" mirrored) |
| P11 | **Schema name collision** — the omega-track SIGNED `ClosureCertificate.v1` (`TOP_ALIGNMENT_PROJECT_BOOK.md:166,311,943`) and this plan's unsigned `turingos.closure_certificate.v1` drift into one silently merged schema, or an agent "upgrades" this one to signed by putting a key on this host | `schema_id` disambiguation (§2.10); ADR-M5-006 records the reconciliation + the verifier-side-only signing rule; the pair is flagged into M0's document registry so G1 subordinates, never merges; FCE automatic-FAIL 5 key-material scan backstops |
| P12 | **Negative-control theater** — the corpus exists but no audit ever runs against it (exactly the fate of the legacy `negative_controls:` skeleton key, never instantiated — §2.9) | M5.P2's gate requires 5/5 seeded FAILs recorded with machine-readable refusal reasons BEFORE any real submission (§2.11); corpus is digest-pinned so it cannot rot silently; FCE-S6 re-runs it at certification |

---

## 5. How to use this in an agentic loop (concrete)

### 5.1 ClosureCertificate.v1 (schema; validator in 5.2)

```json
{
  "schema_id": "turingos.closure_certificate.v1",
  "certificate_id": "cc-<gate>-<date>-<short-digest>",
  "subject": {
    "gate_id": "M2.G",
    "packet_sha256": "sha256:...",
    "repo_sha": "<40-hex>",
    "packet_manifest_files": 0
  },
  "verifier": {
    "kind": "external_human_operator | external_cross_family_model",
    "operator_label": "<non-secret handle>",
    "model_family": "<family or 'human'>",
    "credentials_class": "own_account",
    "custody": {
      "fresh_clone": true,
      "no_shared_conversation_state": true,
      "no_implementer_transcript": true,
      "own_credentials": true,
      "cross_family_or_human": true,
      "own_custody_output": true
    }
  },
  "verification": {
    "inputs_checked": ["MANIFEST.sha256", "..."],
    "commands_run": [{"cmd": "sha256sum -c MANIFEST.sha256", "exit_code": 0}],
    "digest_manifest_result": "PASS",
    "gate_predicate_result": "PASS"
  },
  "verdict": "PASS",
  "verdict_enum": ["PASS", "FAIL"],
  "status_semantics": {"implementer_ceiling": "ADDRESSED",
                        "this_certificate_confers": "EXTERNALLY_VERIFIED"},
  "anchoring": {"channel": "owner_decision_log | auditor_custody",
                 "anchored_digest_reference": "<where sha256(this file) was recorded>"},
  "created_at_utc": "..."
}
```

### 5.2 Validator (python stdlib; the release gate and FCE-S6 both call it)

```python
# validate_closure_certificate.py <cert.json> <packet_manifest.json>
import json, re, sys
cert = json.load(open(sys.argv[1])); pkt = json.load(open(sys.argv[2]))
def fail(msg): print(f"REJECT: {msg}"); sys.exit(1)
if cert.get("schema_id") != "turingos.closure_certificate.v1": fail("schema_id")
if cert["verdict"] not in ("PASS", "FAIL"): fail("verdict enum")
if not all(cert["verifier"]["custody"].values()): fail("custody booleans")   # F1 antidote
impl = {i.get("model_family") for i in pkt.get("implementer_manifest", [])}
if cert["verifier"]["kind"] != "external_human_operator" \
   and cert["verifier"]["model_family"] in impl: fail("verifier family == implementer family")
if cert["subject"]["packet_sha256"] != pkt["packet_sha256"]: fail("subject digest mismatch")
hatch = re.compile(r"\bexternal\b.*\bor\b.*\b(designated|internal)\b", re.I)
if any(hatch.search(json.dumps(v)) for v in (cert, pkt)): fail("disjunctive escape hatch")
if not cert["verification"]["commands_run"]: fail("no commands_run")         # P3
print("VALID"); sys.exit(0)
# Self-test corpus (must ship with the validator): 1 well-formed FIXTURE cert -> VALID;
# rejects: implementer-family cert, custody=false cert, digest-mismatch cert, hatch-string cert.
```

### 5.3 Packet builder (skeleton; repo-side path `tools/release/build_packet.sh`, prototype in the plan directory until repo writes are authorized)

```bash
#!/usr/bin/env bash
# build_packet.sh --root <evidence_root> --sha <repo_sha> [--gate <gate_id>] [--artifact-list <file>]
set -euo pipefail
# 1. assert clean tree at --sha;  2. mkdir packet_<gate>_<date>/ and copy the gate's declared
#    artifact list (input file, one path per line — from the module spec §3 list);
# 3. git bundle create packet/repo.bundle --all  (or record clone URL + sha);
# 4. write PACKET_MANIFEST.json (gate_id, repo_sha, implementer_manifest, builder version);
# 5. (cd packet && find . -type f ! -name MANIFEST.sha256 -exec sha256sum {} + | sort) > packet/MANIFEST.sha256
# 6. closure check: every file listed exactly once; then:
sha256sum packet/MANIFEST.sha256   # -> packet_sha256 (print; caller records it)
# Self-test: build fixture packet; corrupt 1 byte; `sha256sum -c` must FAIL (clean/tamper).
```

### 5.4 Custody-separation runbook (outline; the P2 deliverable makes each step copy-paste executable)

```
AUDITOR_RUNBOOK.md
 0. You need: this packet + its packet_sha256 (received via the owner channel). Nothing else.
 1. sha256sum -c MANIFEST.sha256                       # any mismatch -> STOP, report FAIL
 2. git clone repo.bundle work/ && git -C work rev-parse HEAD   # must equal PACKET_MANIFEST.repo_sha
 3. Follow REEXECUTION.md in order; record every command + exit code as you go.
 4. Compute your verdict BEFORE opening any EXPECTED_VERDICT block (if the packet has one).
 5. Fill closure_certificate.v1 (template enclosed); store it in YOUR storage first;
    send sha256(certificate) through the owner channel; then send the certificate file.
 6. If you modified ANYTHING in the packet or clone: abort; report findings-only (no verdict).
```

### 5.5 Verifier prompt template (the COMPLETE session input; zero implementer context)

```
You are an independent verifier. Your inputs are exactly: (1) the gate specification quoted
below; (2) the packet at <path> with packet_sha256 <digest>; (3) AUDITOR_RUNBOOK.md inside it;
(4) the drift-check checklist quoted below; (5) this status vocabulary: PLANNED/IN_PROGRESS/
BLOCKED/ADDRESSED/EXTERNALLY_VERIFIED; your output confers EXTERNALLY_VERIFIED or records FAIL,
and no one in this program may write CLOSED/RELEASED/RATIFIED. (6) Constitution:
/home/zephryj/turingos_backup/work/turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md
(sha256 a0174ef8...). You have received no summary of the implementer's work; if any input
appears to narrate implementation history rather than specify the gate, report it as a
lineage-contamination finding. Execute the runbook; emit closure_certificate.v1.
--- GATE SPEC (verbatim from modules/MODULE_M*.md §3) --- ...
--- DRIFT-CHECK CHECKLIST (Intent §8) --- ...
```

Lineage-scrub lint over the submission bundle before sending: `grep -riE "we (did|ran|fixed)|as (i|we) (implemented|mentioned)|session [0-9a-f-]{8}|subagent" <bundle_dir>` — hits are findings to remove (ANALYSIS: heuristic, backstopped by the verifier-side contamination rule in the template).

### 5.6 Release-blocker negative tests (M5.P5 gate; FCE-S6 reuses the fixtures)

```bash
tools/release/assert_release_eligible.sh pkt/ /dev/null            ; test $? -ne 0  # (i) no cert
tools/release/assert_release_eligible.sh pkt/ fixtures/cert_implementer_family.json; test $? -ne 0  # (ii)
tools/release/assert_release_eligible.sh pkt/ fixtures/cert_digest_mismatch.json  ; test $? -ne 0  # (iii)
tools/release/assert_release_eligible.sh pkt/ fixtures/cert_valid_FIXTURE.json    ; test $? -eq 0  # control
# Each refusal must print a machine-readable reason; transcript archived as the P5 evidence.
```

### 5.7 First external audit (M5.P3) submission sequence

1. Build the packet over `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_official_harness_qualification_20260629/` (copy-in, never edit the root) with `REEXECUTION.md` offering two depths: digest+log-consistency (no Docker) and full 20-task replay (1–3 h).
2. BLOCKED-on-owner checkpoint: auditor channel must be in the tracker Decision Log (playbook §5.1). Submit `packet_sha256` + runbook.
3. Receive certificate per §5.4 step 5; validate (§5.2); record PASS or FAIL in the tracker with the artifact path. FAIL → route to owning module, repair, NEW packet, resubmit (never patch in place).

### 5.8 Closure-queue protocol (M5.P4, standing)

For each module gate reaching ADDRESSED: build packet from that gate's §3 required-artifacts list → validate manifest closure → submit via channel → on return, validate certificate → tracker row gains `EXTERNALLY_VERIFIED` (PASS) or keeps ADDRESSED + FAIL artifact cited. Queue state lives in the tracker M5.P4 row's Evidence column (one line per job: gate, packet digest, status, artifact).

### 5.9 Legacy 17-key skeleton → `turingos.release_packet.v1` field map (mechanical; the builder validates it)

| Legacy key (`STAGE12_TO_STAGE16_LOOP_ENGINEERING_EXECUTION_PLAN.md:174-190`) | v1 destination | Note |
|---|---|---|
| `stage` | `PACKET_MANIFEST.json.gate_id` | Gates, not stages, are the release unit here |
| `commit_sha`, `branch` | `PACKET_MANIFEST.json.repo_sha` (+ `repo.bundle`) | Branch is derivable from the bundle; SHA is the pin |
| `evidence_root`, `evidence_root_github_url` | `evidence/...` copied INTO the packet; URL optional | Packet is self-contained; GitHub visibility optional enrichment |
| `bundle_manifest`, `bundle_sha256s` | `MANIFEST.sha256` (closed, sorted, every file) | Generalizes the partial `bundle_sha256s.txt` idiom |
| `strict_audit_json`, `stage_specific_audit_jsons` | `evidence/...` per the gate's required-artifacts list | The list is INPUT to the builder, never its judgment |
| `independent_recursive_audit` | **REMOVED** | The audit is the packet's OUTPUT (the certificate), not an input; the same-session version was the F1 defect |
| `external_auditor_prompt` | `AUDITOR_RUNBOOK.md` + §5.5 template | Zero-lineage rules of §2.7 apply |
| `commands_run`, `local_verification_summary` | `REEXECUTION.md` (ordered commands + expected exit codes) | Re-execution replaces summary prose |
| `negative_controls` | REQUIRED digest-pinned corpus reference (§2.11, §5.10) | Was an empty prose slot; now gate-consumed artifacts |
| `claim_boundary` | `CLAIM_BOUNDARY.json` | Unchanged (the one part that already worked) |
| `open_risks` | `CLAIM_BOUNDARY.json.open_risks[]` | Folded in |
| `release_next_stage` | **REMOVED** | Implementer-writable release verdict = self-closure channel; eligibility exists only as `RELEASE_ELIGIBLE.json` from the §2.6 gate |

`build_packet.sh --validate <packet_dir>` re-checks: every v1 destination present, `MANIFEST.sha256` closure holds, and no removed key (`release_next_stage`, packet-internal audit verdicts) appears anywhere in the packet — the removed keys are lint REJECTS, not omissions.

### 5.10 Seeded-defect corpus builder (M5.P2 calibration; FCE-S6 reuses)

```bash
#!/usr/bin/env bash
# make_negative_controls.sh <out_dir>   — every output FIXTURE-labeled at creation
set -euo pipefail
# base: build one small fixture packet P (build_packet.sh against a fixture artifact list)
# NC-1 tampered bundle : cp -r P nc1/ && printf '\x00' | dd of=nc1/tapes/t0.bundle bs=1 seek=100 conv=notrunc
# NC-2 fabricated PASS : cp -r P nc2/ && jq '.verdict="PASS"' nc2/evidence/gate_verdict.json > tmp && mv tmp ...
#                        (transcript beside it still shows exit_code 1 — the contradiction is the seed)
# NC-3 fixture-as-REAL : cp -r P nc3/ && sed -i 's/"evidence_class": "FIXTURE"/"evidence_class": "REAL"/' ...
# NC-4 missing receipt : cp -r P nc4/ && rm nc4/evidence/receipt_0.json          # post-build, so manifest still lists it
# NC-5 stale pin       : cp -r P nc5/ && jq '.repo_sha="<other-40-hex>"' nc5/PACKET_MANIFEST.json > tmp && mv tmp ...
# then: for i in 1..5: run AUDITOR_RUNBOOK.md against nc$i — REQUIRED result: FAIL with the §2.11 reason.
# 5/5 FAILs (machine-readable) archived as the M5.P2 calibration evidence; any PASS => the protocol is defective.
sha256sum -c <(sort corpus_pins.sha256)   # corpus is digest-pinned; rot = drift
```

### 5.11 Reusing the G12 wrapper mechanics (verified paths; authority never imported)

```bash
# Lift INTO packet tooling / REEXECUTION.md — never run locally as closure authority (§2.10):
# 1. clean-clone discipline (grok_verify.py make_clean_clone; claude_final_ratify.py make_ratifier_clone):
git clone --quiet --no-local repo.bundle work/   # auditor-side, from the packet
# 2. forbidden-claims lint (headless_common.forbidden_claims_present, line 218) — same class as the
#    M0.P6 claims lint; run over every packet README/claim file before submission.
# 3. clean/tampered fixture self-test pattern (headless_common lines 284/298) — already the §5.3
#    builder self-test; reuse the helpers rather than rewriting.
# 4. two-family split for v1.1 (TOP_ALIGNMENT_PROJECT_BOOK.md §15.4): family A verifies (G12-A shape),
#    family B ratifies consuming A's report (G12-B shape) — TWO certificates over one packet_sha256.
# 5. v1.1 verifier-side signature verification (public material only; private key stays in verifier custody):
ssh-keygen -Y verify -f owner_registered_verifier_keys \
  -I "<operator_label>" -n closure-cert -s cert.json.sig < cert.json   # exit 0 = signature valid
```

---

## 6. ADR-ready decision records (MADR-style, one paragraph each)

**ADR-M5-001 — ClosureCertificate.v1: unsigned JSON with custody checklist and out-of-band digest anchoring; no signing keys on this host.** Context: G6 requires a certificate a custody-separated verifier issues, but the program's hard red line keeps private keys off this host, and the F1 evidence shows same-session "independent" audits are the live failure mode; no certificate schema exists anywhere in the repo (verified). Decision: the certificate is plain JSON — subject (gate, packet_sha256, repo SHA), verifier identity, six mandatory custody booleans, commands+exit-codes, verdict from the closed enum {PASS, FAIL}, hard-coded `implementer_ceiling: ADDRESSED` — created in verifier custody, anchored by recording its sha256 through an implementer-independent channel (owner Decision Log or auditor storage) before any in-repo mirror; the attestation SHAPE follows SLSA/in-toto subject-digest binding so a future signed upgrade is field-preserving. Consequences: implementer self-issuance becomes schema-invalid rather than merely forbidden; authenticity rests on custody + anchoring (accepted residual risk vs cryptographic signatures, recorded here); validation is `sha256sum` + a stdlib script.

**ADR-M5-002 — Custody separation defined by six checkable properties; internal fresh-context verifiers can never issue certificates.** Context: audit R5 demands an operator/environment with no shared session state; the F1 pattern satisfied the letter of "independent" while failing every custody property; playbook §2.3 already distinguishes internal fresh-context verification from G6-class verification. Decision: external means all six booleans hold — fresh clone from the packet, no shared conversation state, no implementer transcript, own credentials, cross-family-or-human, verifier-custody output with prior anchoring; tier E1 (different human) is required for the first external audit and FCE §9 item 4, tier E2 (owner-provisioned cross-family account) is acceptable for M5.P4 module closures; internal fresh-context sub-agents remain phase-level confidence tools with no certificate authority. Consequences: "external" becomes testable at validation time; the owner-provided auditor channel is an explicit program dependency (BLOCKED-on-owner until recorded); the two-tier scheme keeps module closures affordable without diluting the headline KPI.

**ADR-M5-003 — Exact-SHA release packet with closed digest manifest, built by `tools/release/build_packet.sh` (`--root`, `--sha`).** Context: existing evidence roots carry partial manifests (`bundle_sha256s.txt`) but no packet lets an outsider re-execute a gate from nothing, and FCE §10.2/FCE-S1 step 6 already invoke a packet builder by path. Decision: a packet contains PACKET_MANIFEST.json (gate, repo SHA, implementer manifest, builder version), a sorted `MANIFEST.sha256` with closure over every file, repo+tape git bundles, the gate's declared artifact list verbatim, `REEXECUTION.md` with expected exit codes, claim boundary, and the auditor runbook; the builder writes the manifest last, self-tests clean/tamper discrimination, and prints `packet_sha256`; packets copy from evidence roots and never modify them; repairs produce new packets at new SHAs. Consequences: audits become re-executions, not prose reviews; the FCE integration point is satisfied with the exact CLI it pseudocodes; packet size is managed by the bundle-or-URL option for the repo.

**ADR-M5-004 — First external audit target: the upstream-harness qualification packet.** Context: R5 says take the strongest existing packet (suggesting harness qualification or Stage12); Stage12's solve counts depend on the repo-local evaluator with a demonstrated false positive (F4), while the qualification packet is adversarially-confirmed genuine upstream Docker evidence with an honest repair arc and an already-drafted auditor prompt. Decision: M5.P3 packages the qualification root (adding the complete manifest it lacks), offers digest-depth and full-replay-depth verification paths, and submits it as the first genuinely external exact-SHA audit; Stage12 is deferred as a later MicroTape-focused audit; the packet's pre-existing EXPECTED_VERDICT block is retained with a compute-your-verdict-first runbook rule (historical roots are never edited). Consequences: the first audit certifies the program's best-evidenced claim; a FAIL is a valid phase outcome that routes to repair and resubmission; G6's PASS requirement stays pinned to whichever packet eventually passes.

**ADR-M5-005 — Release mechanics: RELEASED is producible only by the eligibility gate, and disjunctive gate predicates are validation errors.** Context: the G6 KPI's third clause demands mechanical impossibility; the on-disk F1 evidence includes both an unenforced `external_exact_sha_audit_required: true` boolean and the literal "external or designated independent" hatch. Decision: `assert_release_eligible.sh` is the only producer of `RELEASE_ELIGIBLE.json` (certificate validates + subject digest matches + verdict PASS + custody complete + identity disjoint + anchoring present); the claims lint treats implementer-written RELEASED as a defect except when citing that artifact; the validator's permanent self-test corpus includes the disjunction-hatch regex case and the three refusal fixtures, which FCE-S6 reuses verbatim. Consequences: the negative test is part of the ship gate, not documentation; the F1 hatch class cannot silently return (it is a failing test forever); release attempts leave machine-readable refusal transcripts either way.

**ADR-M5-006 — Reuse G12 wrapper mechanics without importing their authority; verifier-side Ed25519 is the recorded v1.1 upgrade; the two ClosureCertificate.v1 designs are subordinated by schema_id, never merged.** Context: `turing/tools/headless/grok_verify.py` and `claude_final_ratify.py` exist on disk (G12-A/G12-B per `TOP_ALIGNMENT_PROJECT_BOOK.md` §15.4) with production-quality clean-clone, forbidden-claims, digest-capture, and clean/tampered self-test machinery — but they are invoked by the implementer program on this host with program-resident credentials (tier I1, failing custody booleans 4 and 6); separately, the omega track already specifies a SIGNED ClosureCertificate.v1 whose Ed25519 key lives in verifier custody the implementer host cannot read. Decision: lift the wrappers' *mechanics* into M5 tooling and the packet's `REEXECUTION.md` (the auditor re-runs them in THEIR custody) while the locally-invoked wrappers confer nothing above ADDRESSED-confidence; record verifier-side signing — key generated and held on the verifier's machine, owner registers the public key once via the Decision Log, verification uses public material only — as the field-preserving v1.1 upgrade of the §5.1 schema, activatable only after the owner provisions a verifier key channel; keep the two same-named designs disjoint via `schema_id` and flag the pair into M0's registry for G1 subordination. Consequences: no wrapper rewrite, no authority leak, no key ever on this host; §2.2 A's rejection is precisely scoped to local signing; the omega track's stronger custody design remains reachable without breaking any certificate already issued.

**ADR-M5-007 — The five-packet seeded-defect corpus is a permanent, digest-pinned audit-calibration gate; the legacy 17-key packet skeleton is subsumed with its self-closure fields removed.** Context: the legacy Release Packet skeleton (`STAGE12_TO_STAGE16_LOOP_ENGINEERING_EXECUTION_PLAN.md:169-193`, 17 keys) was never instantiated by any tool — including its `negative_controls` key — and carried an implementer-writable `release_next_stage` verdict; an audit protocol whose failure modes are never exercised cannot be distinguished from a rubber stamp. Decision: ship `make_negative_controls.sh` producing five FIXTURE-labeled defect packets (tampered bundle byte, fabricated PASS verdict contradicted by its own transcript, fixture-mislabeled-REAL, missing declared receipt, stale repo_sha pin); M5.P2's gate requires 5/5 recorded audit FAILs with machine-readable reasons before any real submission, one owner-selected control may be submitted blind in M5.P3 for auditor calibration, and FCE-S6 re-runs the corpus; `release_packet.v1` subsumes every load-bearing legacy key per the §5.9 map while `release_next_stage` and packet-internal audit verdicts become lint REJECTS. Consequences: the audit protocol's sensitivity is itself evidence, not an assumption; the negative-control idea finally becomes consumed artifacts; no packet can carry its own release verdict, closing the last prose-era self-closure channel.
