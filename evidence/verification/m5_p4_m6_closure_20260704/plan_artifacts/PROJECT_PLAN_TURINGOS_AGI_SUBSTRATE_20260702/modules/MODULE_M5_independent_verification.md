# MODULE M5 — Independent Verification & Release Machinery (G6)

- Version: 1.1.0 (2026-07-02), firm — zero PROVISIONAL content. Planning artifact; confers no CLOSED/RATIFIED status. Regenerated at M5.P0b from the landed `research/RES_M5_independent_verification.md` INCLUDING its Revision 1.1 addendum (§2.9–2.12, §4 P11–P12, §5.9–5.11, ADR-M5-006/007); supersedes v1.0.0 (sha256 `f63d7e4a…`), which predated the addendum. Re-pin via the tracker Decision Log entry of this date (the RES_M5 pin `e1c20eb5…` → on-disk Rev 1.1 `8893bd16…` re-pin rides the same entry — RES_M5 header line 10 flags it).
- Grounding: `research/RES_M5_independent_verification.md` (sha256 pinned in `PROGRESS_TRACKER.md`), Intent §2 row G6 and §5.2, audit findings F1 (the external release gate has never run externally — the program's most severe finding) and R5 (custody separation), playbook §3.4 commissioned scope.
- Red line (binding): private keys never on this host — all M5 machinery running here is signature-free; certificate authenticity comes from custody separation + out-of-band digest anchoring (RES_M5 header note, ADR-M5-001). *Verifier-side* Ed25519 signing — key generated and held in the verifier's own custody, never on this host, owner registers the public key once — is red-line compatible and is the recorded field-preserving v1.1 certificate upgrade, activatable only after the owner provisions a verifier key channel (RES_M5 §2.10, ADR-M5-006).
- Reconciliation: gate IDs/tool names here govern over `09_FINAL_CERTIFICATION_EVALS.md` §0.1 assumptions (FCE reconciliation rule). Inbound cross-reference IDs preserved from v1.0.0: §3 (Ship Gate artifact list, cited by the tracker M5.G row), §4 (Evals, same row), phase IDs M5.P0–P5/M5.G, and the FCE integration points (§10.2 builder CLI, FCE-S1 step 6, FCE-S6 fixtures, FCE §11 handoff).

## 1. Written spec

### 1.1 Functional requirements

1. **ClosureCertificate.v1 + verifier protocol (RES_M5 §2.2 candidate B, §5.1–5.2, ADR-M5-001):** unsigned JSON with subject block (gate_id, packet_sha256, repo SHA), verifier identity block, six mandatory custody booleans, commands+literal-exit-codes, verdict from the closed enum {PASS, FAIL}, hard-coded `implementer_ceiling: ADDRESSED`; validator rejects implementer-family identities, incomplete custody, subject-digest mismatches, and disjunctive-predicate strings — self-closure becomes a schema validation error, not a discovered misdeed (M5.P1). `verifier.kind` is closed over {external_human_operator, external_cross_family_model}: there is no "designated internal" value to write, killing the F1 step-13 hatch at the type level (RES_M5 §2.9).
2. **Verifier prompt templates with zero implementer context (RES_M5 §2.7, §5.5):** complete session input = gate spec + packet + runbook + drift checklist + status vocabulary + constitution/intent pointers, nothing else; lineage-scrub lint over every submission bundle; verifier-side contamination rule in the template; the EXPECTED_VERDICT exception only for packets whose historical root already published one, with the compute-your-verdict-first runbook rule (M5.P1).
3. **Custody-separation runbook (RES_M5 §2.3, §5.4, ADR-M5-002):** the six checkable properties (fresh clone, no shared conversation state, no implementer transcript, own credentials, cross-family-or-human, own-custody output with prior anchoring); tier E1 (different human operator) required for the first external audit and FCE §9 item 4, tier E2 (owner-provisioned cross-family account) acceptable for M5.P4 module closures; executable by an outsider from the packet alone (M5.P2).
4. **Negative-control corpus (RES_M5 §2.11, §5.10, ADR-M5-007):** `make_negative_controls.sh` produces five FIXTURE-labeled seeded-defect packets — NC-1 tampered bundle byte, NC-2 fabricated PASS contradicted by its own transcript, NC-3 fixture-mislabeled-REAL, NC-4 missing declared receipt, NC-5 stale repo_sha pin — digest-pinned, stored outside any real packet. The audit protocol must record 5/5 FAILs with machine-readable reasons BEFORE any real submission; one owner-selected control may be submitted blind in M5.P3 as auditor calibration; FCE-S6 reuses the corpus verbatim (M5.P2).
5. **First genuinely external exact-SHA audit (RES_M5 §2.5, §5.7, ADR-M5-004):** target = the upstream-harness qualification packet (`turing/evidence/bench/swe_bench_official_harness_qualification_20260629/`), packaged with the complete `MANIFEST.sha256` it lacks, two verification depths (digest/log-consistency without Docker; full 20-task replay, 1–3 h); FAIL is a valid phase outcome that routes to repair + NEW packet at a new SHA (M5.P3).
6. **Per-module closure verification service (RES_M5 §2.8, §5.8):** event-driven standing queue over M1.G, M2.TC5/G, M3.G, M4.G, M6.G; each job = packet build → owner-channel submission → certificate-or-FAIL recorded; queue state in the tracker M5.P4 row; the interface contract each consumer sees is §1.4 below (M5.P4).
7. **Release mechanics (RES_M5 §2.6, §5.6, ADR-M5-005):** `tools/release/assert_release_eligible.sh` is the ONLY producer of `RELEASE_ELIGIBLE.json`; three scripted refusal cases + one positive control; disjunction-hatch regex in the permanent validator self-test corpus; packet builder `tools/release/build_packet.sh` with `--root`/`--sha` CLI, manifest-written-last, and `MANIFEST.sha256` closure (RES_M5 §2.4, §5.3, ADR-M5-003), consumed by FCE §10.2 and FCE-S1 step 6 (M5.P5).
8. **Legacy release-packet skeleton subsumed, self-closure fields removed (RES_M5 §2.9, §5.9, ADR-M5-007):** `turingos.release_packet.v1` carries every load-bearing key of the never-instantiated 17-key stage skeleton (`turing/docs/handoff/STAGE12_TO_STAGE16_LOOP_ENGINEERING_EXECUTION_PLAN.md:169-193`) under mechanical validation; `release_next_stage` and packet-internal audit verdicts are REMOVED and become `build_packet.sh --validate` lint REJECTS — a packet can never carry its own release verdict (M5.P5).
9. **G12 wrapper mechanics reused, authority never imported (RES_M5 §2.10, §5.11, ADR-M5-006):** lift clean-clone discipline (`git clone --no-local`), the forbidden-claims lint, digest capture, and clean/tampered fixture self-tests from `turing/tools/headless/{grok_verify.py, claude_final_ratify.py, headless_common.py}` into M5 tooling and `REEXECUTION.md`; the locally-invoked wrappers are tier I1 (fail custody booleans 4 and 6) and confer nothing above ADDRESSED-confidence. The omega-track SIGNED ClosureCertificate.v1 (`TOP_ALIGNMENT_PROJECT_BOOK.md:166,311`) stays disjoint via `schema_id` (`turingos.closure_certificate.v1` here) and the pair is flagged into M0's document registry for G1 subordination, never merged (M5.P1).

### 1.2 Non-functional requirements

- No disjunctive escape hatches in any gate predicate — mechanically enforced by the validator regex; the literal F1 hatch at `turing/docs/handoff/STAGE12_TO_STAGE16_RECURSIVE_AUDIT_PLAN.md:78` ("external **or designated independent**", Stage Gate Contract step 13) is a permanent failing test case (RES_M5 §2.6, §2.9).
- Verifier contexts carry no implementer transcript/reasoning/summaries; fresh clone at the pinned SHA; own credentials (RES_M5 §2.3 property list).
- NOT_RUN == FAIL everywhere; a queue job with neither certificate nor FAIL artifact is a defect (RES_M5 §4 P8); a negative-control corpus that no audit ever exercises is the P12 defect, gated out by the M5.P2 5/5 requirement (RES_M5 §4 P12).
- Packets copy from evidence roots and NEVER modify them; repairs produce new packets at new SHAs (RES_M5 §2.4; FCE §11 mirror — certification runs are never patched in place).
- Verdict enums stay closed at {PASS, FAIL}; there is no "fixed and passed" state (RES_M5 §4 P6) and no SHIPPED/RELEASED value any agent can emit (RES_M5 §2.6 layer 3).

### 1.3 Performance targets

- Certificate validation: seconds (stdlib script). Packet build: minutes for evidence-root-sized packets (bundle-or-URL option keeps repo size bounded). Verifier work per closure: target ≤1 elapsed day once a packet is submitted; external-party latency recorded separately, never scored — the target is a packet-quality forcing function, not an SLA on humans (RES_M5 §2.8).

### 1.4 Interfaces (including the certification interface M5 provides to every other module gate)

**Inputs:** each module gate's §3 required-artifacts list (the builder takes the list as input, never decides it — RES_M5 §2.4); the owner-recorded auditor channel (tracker Decision Log; BLOCKED-on-owner until recorded, playbook §5.1). **Outputs:** `turingos.release_packet.v1` packets (layout RES_M5 §2.4; legacy field map §5.9), `turingos.closure_certificate.v1` JSONs (schema RES_M5 §5.1) stored verifier-side with anchored digests and in-repo mirrors, `AUDITOR_RUNBOOK.md` (RES_M5 §5.4), `validate_closure_certificate.py` + 5-case corpus (RES_M5 §5.2), `make_negative_controls.sh` + NC-1..5 corpus (RES_M5 §5.10), `assert_release_eligible.sh` + refusal fixtures (RES_M5 §5.6), `RELEASE_ELIGIBLE.json` artifacts. ADRs: plan directory `adr/ADR-M5-001..007.md` (texts in RES_M5 §6).

**Certification interface (binding contract; what "M5-class verifier" in another module's tracker row means).** For every consumer the protocol is identical (RES_M5 §5.8): when the consumer's gate reaches ADDRESSED, M5 builds a packet from that gate's §3 required-artifacts list + the pinned repo SHA, submits `packet_sha256` + runbook via the owner channel, and returns exactly one of (a) a validated `turingos.closure_certificate.v1` with verdict PASS — the ONLY artifact by which the consumer's tracker row may record EXTERNALLY_VERIFIED (playbook §6.1) — or (b) a certificate with verdict FAIL / a recorded FAIL artifact, which routes to the owning module for repair and a NEW packet. Per consumer:

| Consumer gate | What the consumer hands M5 | What M5 certifies | Verifier tier (RES_M5 §2.3) |
|---|---|---|---|
| M1.G | MODULE_M1 §3 artifact list (writer lint, cross-impl equality, real-run + receipt evidence) at a pinned SHA | G2 KPI roll-up re-executed from the packet on a fresh clone | E2 acceptable (tracker: "M5-class, custody-separated") |
| M2.TC5 | The TC-10 exact-SHA publication packet (M2.TC4 outputs) | TC-10 is RUN BY the cross-family verifier on a clean clone — never by any implementer; the certificate's `verification.commands_run` records the TC-10 invocation + exit code. M5.P1–P2 are hard dependencies of this row | E2 minimum (cross-family, fresh clone) |
| M2.G | MODULE_M2 §3 roll-up incl. the TC5 certificate path | G3 KPI + claim-language boundary | E2 acceptable |
| M3.G | MODULE_M3 §3 artifact list (pre-registration packet + digests + report) | Pre-registration conformance + recomputation of Δ/CI from the frozen script (MODULE_M3 §4.2) | E2 acceptable |
| M4.G | MODULE_M4 §3 artifact list (frozen metric machinery, H-VPPUT report, causal note) | G5 KPI roll-up; FCE-B1 check 8 later recomputes independently | E2 acceptable |
| M6.G | MODULE_M6 §3 artifact list (projection-integrity audits, head-conservation evidence) | G7 KPI roll-up on a fresh clone | E2 acceptable |
| FCE.RUN | The complete FCE evidence root at the cert SHA | The certification packet itself, built by THIS module's `build_packet.sh` (FCE §10.2 line 419) and submitted per FCE §11; only its external PASS flips `shipped_eligible` (FCE §9 item 4) | E1 REQUIRED (different human operator) |

FCE §11 handoff reconciliation (binding both ways): the FCE suite's terminal action is a submission through M5's channel, not a declaration; if the external audit returns FAIL or diverges from any recorded verdict, the divergence is a first-class finding routed to the owning module and the FCE re-runs at a NEW cert SHA as a new certification run. M5's queue treats an FCE divergence exactly like a module-closure FAIL (RES_M5 §2.8, §4 P10).

### 1.5 Agentic considerations

- M5.P0–P2 and P5 prototyping are plan-directory work (W0–W1, no repo writes); repo-side `tools/release/` lands only after owner activation (playbook §1 step 6).
- M5.P3/P4 are BLOCKED-on-owner until the auditor channel is recorded in the Decision Log (playbook §5.1) — only protocol/schema/runbook/negative-control work proceeds meanwhile.
- The P4 queue is event-driven: the orchestrator treats it as standing work whenever another module gate reaches ADDRESSED, never as a phase to "finish" (RES_M5 §2.8).
- No agent of this program may verify its own module's work; internal fresh-context sub-agents (tier I1) raise confidence but can NEVER issue a ClosureCertificate — the locally-invoked G12 wrappers are tier I1 too (RES_M5 §2.3, §2.10; playbook §2.3 ceiling discipline).
- Any agent tempted to "upgrade" the certificate to signed by placing a key on this host is committing the P9/P11 defect: verifier-side signing only, and only after the owner provisions the key channel (ADR-M5-006; FCE automatic-FAIL 5 key-material scan backstops).

### 1.6 Risks & mitigations

Adopt RES_M5 §4 P1–P12 verbatim as the risk register. Highest-severity: P1 fake externality → six-boolean custody checklist + lineage-scrub lint + identity-disjointness validation; P2 escape-hatch reintroduction → permanent regex test case; P4 implementer-forged certificate → custody schema invalidity + out-of-band anchoring precedence; P6 verifier drift into implementer → any-modification-aborts rule, no "fixed and passed" state; P9 signing-stack temptation → ADR-M5-001 rejection + FCE key-material scan; P11 schema name collision with the omega-track signed certificate → `schema_id` disambiguation + M0 registry subordination (ADR-M5-006); P12 negative-control theater → 5/5 seeded FAILs gated before any real submission, corpus digest-pinned, FCE-S6 re-runs it (ADR-M5-007).

### 1.7 Architecture guidance

All bash/jq/python-stdlib; no signing stack on this host. Follow the M0 GateVerdict.v1 pattern for tooling, but the certificate is a verifier-side schema structurally disjoint from GateVerdict.v1 (different `schema_id`, custody fields an implementer cannot truthfully populate) so self-closure is a validation error, not a discovered misdeed (RES_M5 §2.2). Attestation SHAPE follows SLSA/in-toto subject-digest binding so the verifier-side-signed v1.1 upgrade is field-preserving (RES_M5 §2.2 C, §2.12, WEB citations). Provenance-framework adoption line: data shapes yes (subject-digest binding, reproducible re-execution, per-verifier certificates over one `packet_sha256`), infrastructure no (no OIDC/Sigstore stack, no rebuilder daemons, no transparency log while the repo is private — RES_M5 §2.12). Reuse the G12 helpers (`headless_common.py` clean-clone, forbidden-claims, fixture self-test functions) rather than rewriting them (RES_M5 §5.11).

## 2. KPIs

Intent §2 row G6 (verbatim): *"End the self-closure meta-bug at the release layer — ≥1 genuinely external exact-SHA audit PASS (operator/environment with no shared session state); ClosureCertificate.v1 issued by a custody-separated cross-family verifier; RELEASED status mechanically impossible without the external artifact."*

Measurable sub-KPIs: (a) validator self-test 5/5 (1 accept, 4 rejects incl. the disjunction-hatch case) with machine-readable reasons (RES_M5 §5.2); (b) packet builder clean/tamper self-test both directions (RES_M5 §5.3); (c) runbook dry-run executed by an outsider-equivalent context from the packet alone (RES_M5 §5.4); (d) negative-control calibration 5/5 — every NC-1..5 seeded-defect packet FAILs audit with the §2.11 reason, recorded before any real submission (RES_M5 §2.11, §5.10); (e) ≥1 external exact-SHA audit artifact with all six custody booleans true (PASS or FAIL both complete M5.P3; G6/M5.G block on a PASS existing); (f) release-blocker negative tests 3/3 refusals + 1/1 positive control (RES_M5 §5.6); (g) 100% of processed module closures carry a certificate or a recorded FAIL (RES_M5 §4 P8); (h) zero implementer-written RELEASED outside `RELEASE_ELIGIBLE.json`-citing artifacts, and zero packets containing `release_next_stage` or packet-internal audit verdicts (RES_M5 §2.6, §5.9).

## 3. Ship Gate (M5.G)

**Predicate (tracker M5.G row):** G6 KPI roll-up incl. ≥1 external PASS artifact; Drift-Check 7/7. Verifier class: External (by definition). NOT_RUN == FAIL.

**Required artifacts:**
1. ADR-M5-001 through ADR-M5-007 accepted in the plan directory (texts from RES_M5 §6).
2. `turingos.closure_certificate.v1` schema + `validate_closure_certificate.py` + self-test transcript (5-case corpus incl. the disjunction-hatch reject) + zero-lineage prompt templates + lineage-scrub lint output (RES_M5 §5.1–5.2, §5.5).
3. Custody-separation runbook + outsider dry-run evidence (six properties each evidenced) (RES_M5 §5.4).
4. Negative-control corpus (NC-1..5, FIXTURE-labeled, digest-pinned via `corpus_pins.sha256`) + the 5/5 calibration-FAIL transcript with machine-readable reasons (RES_M5 §2.11, §5.10).
5. Packet builder + its clean/tamper self-test transcript + `--validate` legacy-subsumption lint evidence (removed keys REJECT); one real packet with `MANIFEST.sha256` closure verified from a scratch directory (RES_M5 §5.3, §5.9).
6. The first external exact-SHA audit artifact (certificate or FAIL) for the qualification packet, with the anchored-digest reference (RES_M5 §5.7).
7. Release-mechanics negative-test transcript (3 refusals + positive control) + `assert_release_eligible.sh` + fixtures (FCE-S6-reusable) (RES_M5 §5.6).
8. Certificate-or-FAIL record for every module closure processed so far (P4 queue state, one line per job) (RES_M5 §5.8).
9. **Mandatory `PROGRESS_TRACKER.md` update** with evidence paths per playbook §6.2. Implementer status ceiling: ADDRESSED; M5.G itself closes only on the external artifact.

## 4. Evals

### 4.1 Automated

- Certificate validator self-test: 1 well-formed FIXTURE certificate → VALID; 4 rejects (implementer-family, custody=false, subject-digest mismatch, disjunction-hatch string) → each nonzero with the correct reason (RES_M5 §5.2 corpus). Exit codes recorded.
- Packet builder self-test: build fixture packet → `sha256sum -c MANIFEST.sha256` passes from a scratch directory; corrupt one byte → fails (RES_M5 §5.3). `build_packet.sh --validate` over the fixture packet: every v1 destination present, closure holds, and a seeded `release_next_stage` key → REJECT (RES_M5 §5.9).
- Negative-control calibration: run `AUDITOR_RUNBOOK.md` against each of NC-1..5 → 5/5 FAILs, each with the RES_M5 §2.11 layer-specific reason (digest mismatch / recomputed-verdict contradiction / fixture-label lint / manifest-vs-required-list gap / repo_sha mismatch); `sha256sum -c corpus_pins.sha256` green (RES_M5 §5.10).
- Release-blocker battery: the four scripted attempts of RES_M5 §5.6 with expected exit codes.
- Lineage-scrub lint over a seeded submission bundle: planted implementer-narrative lines are caught (RES_M5 §5.5).

### 4.2 Scenario / LLM-judge

Scoped-down FCE-S6 pattern (09 §3): a fresh-context agent attempts three release bypasses (no certificate, self-issued certificate, digest-mismatched certificate) plus one positive control against the real tooling; judge rubric: 3/3 refusals + 1/1 acceptance, each backed by the mechanism's own machine-readable output (never prose), = PASS. Additionally: (i) a fresh-context agent executes the runbook end-to-end from a packet alone and reaches certificate handoff (RES_M5 §5.4 step 5) without needing any input outside the packet; (ii) a fresh-context agent given one blind negative control among real fixtures FAILs it for the seeded reason (RES_M5 §2.11 usage ii pattern).

### 4.3 Performance

Validation ≤ seconds; packet build ≤ minutes for evidence-root-sized packets (bundle-or-URL option for the repo keeps size bounded); per-closure verifier work ≤1 elapsed day target with external latency recorded separately (RES_M5 §2.8).

### 4.4 Sandboxed harness

The verification machinery itself is read-only bash/jq/python. Verifier-side re-executions of module test suites happen on fresh clones per the packet's `REEXECUTION.md` (clean-clone discipline lifted from the G12 wrappers, RES_M5 §5.11); mutation-bearing steps inherit M1d's runsc gate where applicable (RES_M1 §2.7); upstream Docker scoring stays inside its own containers (Intent §5.7).

### 4.5 Thresholds

Validator corpus 5/5; builder tamper test both directions plus `--validate` removed-key REJECT; negative-control calibration 5/5 seeded FAILs with machine-readable reasons; release negative tests 3/3 + 1/1; ≥1 external audit artifact on record with custody booleans all true; 100% of processed closures certificated-or-FAILed (no silent queue drops); zero implementer-written RELEASED outside `RELEASE_ELIGIBLE.json`-citing artifacts (claims-lint sweep); zero packets carrying `release_next_stage` or packet-internal audit verdicts.

### 4.6 Runnable instructions

RES_M5 §5 carries the command shapes: §5.1 certificate schema; §5.2 validator + self-test corpus; §5.3 packet-builder skeleton (`--root`, `--sha`; manifest written last; closure check); §5.4 auditor runbook steps; §5.5 verifier prompt template + lineage-scrub grep; §5.6 negative-test battery; §5.7 first-audit submission sequence; §5.8 closure-queue protocol; §5.9 legacy-skeleton field map + `--validate` rules; §5.10 negative-control corpus builder; §5.11 G12-mechanics reuse commands (incl. the v1.1 `ssh-keygen -Y verify` public-material check). Canonical negative-test shape:

```bash
tools/release/assert_release_eligible.sh pkt/ /dev/null                              ; test $? -ne 0
tools/release/assert_release_eligible.sh pkt/ fixtures/cert_implementer_family.json  ; test $? -ne 0
tools/release/assert_release_eligible.sh pkt/ fixtures/cert_digest_mismatch.json     ; test $? -ne 0
tools/release/assert_release_eligible.sh pkt/ fixtures/cert_valid_FIXTURE.json       ; test $? -eq 0
```

## 5. Dependencies

- Upstream: M0.G (governance chain; GateVerdict.v1 pattern from M0.P6; M0's document registry receives the P11 schema-pair flag). M5.P0/P0b have no other dependency (W0). P1 needs P0b; P2 needs P1 (the corpus atoms also need the P5-prototype builder for the base fixture packet — buildable in W0–W1 as plan-directory prototypes); P3 needs P2 + the owner-provided auditor channel (BLOCKED-on-owner until recorded — playbook §5.1); P4 needs P2 + the channel + each module gate as it reaches ADDRESSED; P5 needs P1 (+ owner activation for repo-side `tools/release/`). Packet contents come from each module's §3 required-artifacts list (RES_M5 §2.4).
- Downstream: every module closure (M1.G, M2.TC5/G, M3.G, M4.G, M6.G) and the SHIPPED definition (09 §9 item 4) run through the §1.4 certification interface; FCE-S6 reuses P5's refusal fixtures AND P2's negative-control corpus; FCE §10.2 invokes the P5 packet builder; FCE §11's handoff is M5's channel. The v1.1 signed-certificate upgrade (ADR-M5-006) waits on an owner-provisioned verifier key channel and is out of this increment's scope.

## 6. Effort estimate + parallelization

- Tiering (playbook §2.4): P0 research, protocol/schema design, and ALL verification runs = xhigh (never below); runbook + negative-control corpus design = high; packaging/fixtures = medium; tracker updates = low.
- Wall-clock estimate: P0 delivered (incl. Rev 1.1 addendum); P0b ≈ 0.25 day (this regeneration + re-pin); P1 ≈ 1–1.5 days (ADRs + schema + validator + templates + lint); P2 ≈ 0.75 day (runbook 0.5 + corpus 0.25); P3 ≈ 0.5–1 day of packet/submission work plus external-party latency; P4 ≈ 0.25 day per closure × ~6 closures spread W1→W4; P5 ≈ 0.5–0.75 day (builder + `--validate` + release gate). Module total ≈ 4.5–6 agent-days spread across the program; zero LLM spend on M5's own tooling.
- Parallelization: P0b→P1 serial (entry criterion); P1's three atoms parallelize; P2 and P5 prototyping parallelize freely with P1 in W0–W1 (the corpus needs the prototype builder first); P3 as soon as the channel exists; P4 is a standing service; repo-side tool placement waits for owner activation.

---

## Phases and atoms

Authoritative status lives in `PROGRESS_TRACKER.md` (M5 table). Atom format: description+why, inputs, outputs, acceptance criteria, methodology citation, implementation notes, sub-prompt, complexity (S/M/L), verification method. Every sub-agent executing an atom inherits the playbook §0 write-permission model, the Intent §5 red lines, the §6 status vocabulary (ceiling ADDRESSED), and reports per playbook §6.2.

### M5.P0 — Research (DELIVERED — recorded for the tracker)

Phase gate: report exists in house format with all six sections; on-disk claims carry verified absolute paths; playbook §3.4 minimum scope covered. Both atoms delivered 2026-07-02; fresh-context re-verification per playbook §2.2 step 3 remains due at the next verification pass (tracker M5.P0 note).

#### ATOM-M5.P0-1 — Produce `research/RES_M5_independent_verification.md` (initial landing)

- **Description / why:** the commissioned xhigh research atom (playbook §3.4) that makes M5 executable at all. Locates the F1 failure on disk (same-session subagent audits, the line-78 disjunctive hatch, zero external verdict artifacts, unenforced `external_exact_sha_audit_required:true`), designs ClosureCertificate.v1 + custody separation + packet format + release blocker, and selects the first audit target.
- **Inputs:** playbook §3.4 scope; Intent §2 G6; audit F1/R5; the turing repo read-only. **Outputs:** RES_M5 §1 Q1–Q8, §2.1–2.8, §3, §4 P1–P10, §5.1–5.8, ADR-M5-001..005.
- **Acceptance criteria:** house format complete; every on-disk claim carries a verified absolute path; all §3.4 scope items answered. **Methodology:** RES_M5 header + §1.
- **Implementation notes / verification:** DELIVERED 2026-07-02 and pinned (tracker Decision Log "M4/M5 repair pass EXECUTED"). Complexity: L (xhigh tier).
- **Sub-Prompt:** n/a — delivered; do not re-run. Any future amendment is append-only with a Decision Log re-pin.

#### ATOM-M5.P0-2 — RES_M5 Revision 1.1 (append-only scope completion)

- **Description / why:** completes the commissioned scope with the legacy 17-key packet-skeleton verification and subsumption (§2.9), G12-A/G12-B wrapper reuse + omega-track signed-certificate reconciliation (§2.10), the five-packet seeded-defect negative-control corpus (§2.11), the provenance adopt-vs-overkill line (§2.12), pitfalls P11–P12, §5.9–5.11 command shapes, and ADR-M5-006/007 — the parts the P1/P2/P5 atoms below are built on.
- **Inputs:** RES_M5 v1.0 + repo verification (`grok_verify.py`, `claude_final_ratify.py`, `headless_common.py`, the stage plan documents, `TOP_ALIGNMENT_PROJECT_BOOK.md`). **Outputs:** RES_M5 Rev 1.1 (append-only; all pre-existing section numbers unchanged, so every §-citation in the tracker and in this file stays resolvable).
- **Acceptance criteria:** append-only; new on-disk claims path-verified; WEB/ANALYSIS labels present. **Methodology:** RES_M5 header line 10.
- **Implementation notes / verification:** DELIVERED 2026-07-02. Consequence: RES_M5 on-disk digest is now `8893bd16…` ≠ pin `e1c20eb5…` — a tracker Decision Log re-pin entry is REQUIRED (RES_M5 flags this itself); handled at ATOM-M5.P0b-2. Complexity: M.
- **Sub-Prompt:** n/a — delivered.

### M5.P0b — Module-spec regeneration (this atom)

Phase gate: module spec regenerated firm from RES_M5 incl. Rev 1.1; pins updated via Decision Log; every M5.P1+ tracker Deliverable/Gate cell cites a specific RES_M5 section; entry criterion for M5.P1.

#### ATOM-M5.P0b-1 — Regenerate `modules/MODULE_M5_independent_verification.md` firm from RES_M5 (this file)

- **Description / why:** the v1.0.0 regeneration predated RES_M5 Rev 1.1 and carried terse atoms; running P1+ from it would miss the negative-control corpus, the legacy-skeleton subsumption rules, and the G12/omega reconciliation — improvisation playbook §3.4 forbids. This atom produces the firm spec: full 1.1–1.7 incl. the explicit §1.4 certification interface, KPIs quoting Intent §2 G6, Ship Gate with the 9-item artifact list + tracker mandate + ADDRESSED ceiling, Evals 4.1–4.6, dependencies, effort, and fully-specified atoms with sub-prompts.
- **Inputs:** RES_M5 (all sections incl. Rev 1.1), MODULE_M4 v1.1.0 atom-format exemplar (MODULE_M3 for the section frame), Intent, playbook, 09 FCE cross-references (§10.2, FCE-S1/S6, §9 item 4, §11), tracker M5 rows. **Outputs:** this file, v1.1.0.
- **Acceptance criteria:** zero PROVISIONAL markers; every RES_M5 citation resolvable; inbound cross-reference IDs preserved (§3/§4 as cited by the tracker M5.G row; phase IDs M5.P0–P5/G; FCE integration points); the certification interface to M1.G, M2.TC5/G, M3.G, M4.G, M6.G, FCE.RUN stated explicitly; every atom carries the full format. **Methodology:** playbook §3.4 P0b protocol.
- **Implementation notes / verification:** DELIVERED by this edit sequence (2026-07-02). Verification: fresh-context read confirms the acceptance list; sha256 recorded at re-pin. Complexity: M.
- **Sub-Prompt:** n/a — this file is the execution record.

#### ATOM-M5.P0b-2 — Re-pin + tracker reconciliation (Decision Log)

- **Description / why:** playbook §1 step 3 treats unlogged digest drift as a stop-work event; RES_M5's Rev 1.1 digest and this file's new digest must both be re-pinned through one Decision Log entry, and the M5.P1–P5/G tracker rows reconciled to the atom decomposition below (Rev 1.1 citations included) BEFORE any P1+ work starts.
- **Inputs:** RES_M5 on-disk sha256 `8893bd16ab7e881faf024b83c8ec11b4c552687fe8122f4bec1a967add79e869`; this file's final sha256; proposed row texts (returned by the P0b agent as `tracker_row_updates`). **Outputs:** tracker Decision Log entry; updated Pins rows; updated M5 table rows; regenerated seed per tracker convention.
- **Acceptance criteria:** `sha256sum -c` passes for both pins; every M5.P1–P5 Deliverable/Gate cell cites a specific RES_M5 section; M5.P0b row ADDRESSED citing this file. **Methodology:** playbook §1 step 3; §3.4.
- **Implementation notes:** orchestrator bookkeeping (low tier); never a silent re-pin — the Decision Log entry IS the adjudication record (LESSON from the RES_M2 drift). Complexity: S. **Verification:** bootstrap pin-check green on next session start.
- **Sub-Prompt:** *"Update PROGRESS_TRACKER.md only. Add a Decision Log entry re-pinning `research/RES_M5_independent_verification.md` (append-only Rev 1.1, new digest 8893bd16…) and `modules/MODULE_M5_independent_verification.md` v1.1.0 (digest: compute with sha256sum). Apply the M5 row updates supplied by the P0b agent verbatim after checking each RES_M5 §-citation resolves. Regenerate and re-pin the tracker seed. Status ceiling ADDRESSED; cite openable paths for every claim."*

### M5.P1 — Verifier protocol + certificate schema + ADRs

Phase gate: ADR-M5-001..007 accepted; validator self-test 1 accept + 4 rejects with machine-readable reasons; prompt templates carry zero session lineage (seeded-narrative bundle caught). All plan-directory work; needs M5.P0b + M0.G.

#### ATOM-M5.P1-1 — Author ADR-M5-001..007 in `adr/`

- **Description / why:** the seven decision records fix every contested design point (unsigned certificate + anchoring; six-property custody; packet format + builder; first-audit target; release mechanics + disjunction ban; G12 reuse without authority + verifier-side-signing v1.1 + schema_id subordination; negative-control corpus + legacy-skeleton subsumption) before code exists. ADR-M5-006/007 are Rev 1.1 additions absent from any earlier module version.
- **Inputs:** RES_M5 §6 paragraph texts; `adr/ADR_TEMPLATE.md`; playbook §0 ADR convention. **Outputs:** `adr/ADR-M5-001-closure-certificate-unsigned.md` … `adr/ADR-M5-007-negative-controls-and-skeleton-subsumption.md` (slugs at author's discretion, numbers fixed).
- **Acceptance criteria:** all seven present in extended-MADR format, decision text semantically identical to the RES_M5 §6 paragraphs, front-matter `status_ceiling: ADDRESSED`, evidence lists citing RES_M5 §6 + the verified repo paths (§2.1, §2.9, §2.10); ADR-M5-006 records the omega-track schema-pair flag for M0's document registry (RES_M5 §4 P11).
- **Methodology:** RES_M5 §6; playbook §0. **Implementation notes:** plan-directory work, no owner gate; do not paraphrase decisions. Complexity: M. **Verification:** fresh-context reader confirms decision-text identity per ADR.
- **Sub-Prompt:** *"Read `research/RES_M5_independent_verification.md` §6 and `adr/ADR_TEMPLATE.md`. Author ADR-M5-001..007 in `adr/`, one file each, expanding the §6 paragraphs into extended-MADR without altering any decision. Front matter per playbook §0 (status vocabulary, decision-makers, authority_level, constitution_articles, evidence with sha256s, status_ceiling ADDRESSED). ADR-M5-006 must include the M0 document-registry flag for the omega-track signed ClosureCertificate.v1 pair (RES_M5 §2.10, P11). Plan-directory writes only. Report per playbook §6.2."*

#### ATOM-M5.P1-2 — `turingos.closure_certificate.v1` schema + `validate_closure_certificate.py` + 5-case corpus

- **Description / why:** the F1 antidote made mechanical — implementer self-issuance becomes a schema validation error. The validator is the shared enforcement point: the release gate (P5) and FCE-S6 both call it.
- **Inputs:** RES_M5 §5.1 schema, §5.2 validator skeleton, §2.2/§2.3 design rationale; ADR-M5-001/002. **Outputs:** schema file + `validate_closure_certificate.py` + self-test corpus (1 well-formed FIXTURE cert; rejects: implementer-family, custody=false, subject-digest-mismatch, disjunction-hatch string incl. the literal "external or designated independent" text) + transcript.
- **Acceptance criteria:** 1 accept + 4 rejects, each with the correct machine-readable reason and nonzero exit; `verifier.kind` enum closed over {external_human_operator, external_cross_family_model}; `verdict_enum` = [PASS, FAIL]; `status_semantics.implementer_ceiling` hard-coded ADDRESSED; schema_id exactly `turingos.closure_certificate.v1` (RES_M5 §2.10 disambiguation).
- **Methodology:** RES_M5 §5.1–5.2. **Implementation notes:** python stdlib only; corpus files FIXTURE-labeled at creation; the hatch string is a permanent failing case, never removed. Complexity: M. **Verification:** re-run of the self-test from a fresh clone of the plan directory; exit codes match the transcript.
- **Sub-Prompt:** *"Implement the ClosureCertificate.v1 validator per RES_M5 §5.2 over the §5.1 schema. Build the 5-case FIXTURE corpus (1 accept, 4 rejects incl. a certificate embedding the literal string 'external or designated independent'). Run and archive the transcript with exit codes. Stdlib only; plan-directory writes only; label every corpus file FIXTURE. Report per playbook §6.2."*

#### ATOM-M5.P1-3 — Zero-lineage verifier prompt templates + lineage-scrub lint

- **Description / why:** the verifier session's complete input set must be closed and implementer-history-free, else custody boolean 3 is unverifiable; the lint makes lineage contamination detectable before submission (P1 fake-externality mitigation).
- **Inputs:** RES_M5 §2.7 content rules + §5.5 template text and grep; playbook §6.1 vocabulary; the constitution digest line. **Outputs:** template file(s) per verifier tier (E1/E2) + `lineage_scrub.sh` + a seeded-narrative test bundle + catch transcript.
- **Acceptance criteria:** template enumerates its six inputs and nothing else; seeded bundle's planted lines (implementer narrative, session IDs, subagent references) all caught; the EXPECTED_VERDICT exception is encoded as a compute-first runbook rule, never template content (RES_M5 §2.7).
- **Methodology:** RES_M5 §2.7, §5.5. **Implementation notes:** the lint is a heuristic backstopped by the template's verifier-side contamination rule — record that limit in the lint header (RES_M5 §5.5 ANALYSIS note). Complexity: S. **Verification:** fresh-context agent diffs template inputs against RES_M5 §5.5's list — exact.
- **Sub-Prompt:** *"From RES_M5 §5.5, write the E1 and E2 verifier prompt templates (complete closed input list; constitution pointer with digest; status vocabulary incl. the ADDRESSED ceiling sentence) and `lineage_scrub.sh` wrapping the §5.5 grep. Seed a FIXTURE submission bundle with implementer-narrative lines; show the lint catches all of them. Plan-directory writes only. Report per playbook §6.2."*

### M5.P2 — Custody-separation runbook + negative-control corpus

Phase gate: outsider-equivalent dry-run reaches certificate handoff from a packet alone; negative-control calibration records 5/5 seeded audit FAILs with machine-readable reasons BEFORE any real submission (RES_M5 §2.11 usage i). Needs M5.P1 (+ the P5-prototype builder for the corpus base packet).

#### ATOM-M5.P2-1 — `AUDITOR_RUNBOOK.md` with six-property evidence instructions

- **Description / why:** turns audit R5's custody demand into copy-paste steps an outsider executes with no program context; each custody boolean gets an explicit evidencing instruction, so the certificate's checklist is fillable truthfully or not at all.
- **Inputs:** RES_M5 §5.4 outline, §2.3 property list + evidence column; ADR-M5-002; P1 templates. **Outputs:** `AUDITOR_RUNBOOK.md` (steps 0–6 of §5.4 made executable: manifest check, bundle clone + SHA equality, ordered re-execution with recorded exit codes, compute-verdict-before-EXPECTED_VERDICT, verifier-custody-first certificate handling with anchored digest, any-modification-aborts rule) + an outsider-equivalent dry-run transcript.
- **Acceptance criteria:** dry-run by a context given ONLY a fixture packet reaches step 5 (certificate handoff) with zero out-of-packet inputs; each of the six properties has a concrete evidence instruction; abort rule present verbatim (findings-only, no verdict).
- **Methodology:** RES_M5 §2.3, §5.4. **Implementation notes:** the dry-run context is I1-tier — it validates the runbook's executability, it certifies nothing (playbook §2.3). Complexity: M. **Verification:** dry-run transcript shows no request for out-of-packet information; six-property evidence table complete.
- **Sub-Prompt:** *"Expand RES_M5 §5.4 into AUDITOR_RUNBOOK.md: every step copy-paste executable; per-custody-boolean evidence instructions from §2.3; abort-on-modification rule; verifier-custody-first + anchored-digest handoff. Then, as a separate fresh context given only the fixture packet, execute it end-to-end and archive the transcript. Plan-directory writes only. Report per playbook §6.2."*

#### ATOM-M5.P2-2 — Negative-control corpus (`make_negative_controls.sh`, NC-1..5) + 5/5 calibration

- **Description / why:** an audit that cannot fail a deliberately bad packet is not an audit (RES_M5 §2.11); this atom builds the five seeded-defect packets and proves the P2 protocol fails all of them — the anti-P12 gate, and the resurrection of the legacy `negative_controls` key as consumed artifacts.
- **Inputs:** RES_M5 §2.11 defect table (defect, construction, catching layer), §5.10 builder skeleton; the prototype `build_packet.sh` (P5-1 prototype) for the base fixture packet; ADR-M5-007. **Outputs:** `make_negative_controls.sh`; NC-1..5 packet directories (FIXTURE-labeled at creation); `corpus_pins.sha256`; the 5/5 calibration-FAIL transcript with per-control machine-readable reasons.
- **Acceptance criteria:** each NC fails at exactly its §2.11 designated layer (NC-1 manifest check; NC-2 re-execution contradiction; NC-3 fixture-label lint; NC-4 manifest-vs-required-list cross-check; NC-5 repo_sha mismatch); corpus digest-pinned; any control PASSING audit = the protocol is defective — stop and repair the protocol, not the control.
- **Methodology:** RES_M5 §2.11, §5.10. **Implementation notes:** controls are seeded post-build where the builder would refuse (NC-4); calibration blind-control usage in P3 is declared only in the calibration corpus's own `CLAIM_BOUNDARY.json`, never in a real packet's. Complexity: M. **Verification:** `sha256sum -c corpus_pins.sha256` green; transcript shows 5/5 FAILs; FCE-S6 can consume the corpus verbatim.
- **Sub-Prompt:** *"Implement make_negative_controls.sh per RES_M5 §5.10: build a base FIXTURE packet with the prototype builder, derive NC-1..5 per the §2.11 construction column, pin the corpus. Run AUDITOR_RUNBOOK.md against each control; REQUIRED result 5/5 FAILs with the §2.11 layer-specific machine-readable reasons — archive the transcript. If any control passes, stop and report the protocol defect; do not weaken the control. Plan-directory writes only; everything FIXTURE-labeled. Report per playbook §6.2."*

### M5.P3 — First external audit

Phase gate: an external PASS/FAIL artifact exists with all six custody booleans true. BLOCKED-on-owner until the auditor channel is in the Decision Log (playbook §5.1). A FAIL completes the phase honestly but does NOT satisfy G6 — repair, NEW packet at a new SHA, resubmit (RES_M5 §2.8, §4 P10).

#### ATOM-M5.P3-1 — Build the qualification-packet release packet

- **Description / why:** the first genuinely external audit should target the program's best-evidenced, most honestly-bounded claim — the upstream-harness qualification packet (genuine `swebench==4.1.0` Docker evidence, honest 19/20→repair→20/20 arc, machine-readable claim boundary), NOT the F4-tainted Stage12 counts (RES_M5 §2.5 selection table).
- **Inputs:** `turing/evidence/bench/swe_bench_official_harness_qualification_20260629/` (read-only; copy-in, never edit the root); `build_packet.sh` (P5-1); ADR-M5-004. **Outputs:** `packet_M5.G-first-audit_<date>/` with the complete `MANIFEST.sha256` the root lacks, `REEXECUTION.md` offering two depths (digest+log-consistency without Docker; full 20-task replay 1–3 h), `CLAIM_BOUNDARY.json`, `AUDITOR_RUNBOOK.md`, and the compute-verdict-first rule covering the root's pre-existing `EXTERNAL_AUDITOR_PROMPT.md` EXPECTED_VERDICT block.
- **Acceptance criteria:** `sha256sum -c MANIFEST.sha256` passes from a scratch directory; `REEXECUTION.md` complete with expected exit codes; evidence root byte-untouched (verify with a before/after digest of the root); `packet_sha256` printed and recorded.
- **Methodology:** RES_M5 §2.5, §5.7 step 1. **Implementation notes:** historical roots are never edited — the EXPECTED_VERDICT block stays, handled by the runbook rule (RES_M5 §2.7 exception). Complexity: M. **Verification:** scratch-directory manifest check + root-untouched digest comparison.
- **Sub-Prompt:** *"Run build_packet.sh --root turing/evidence/bench/swe_bench_official_harness_qualification_20260629/ --sha <pinned SHA> per RES_M5 §5.7 step 1 (copy-in only). Author REEXECUTION.md with the two verification depths and expected exit codes. Verify manifest closure from a scratch directory and that the source root is byte-identical before/after. Record packet_sha256. Report per playbook §6.2."*

#### ATOM-M5.P3-2 — Submit, receive, validate the first external certificate

- **Description / why:** the actual G6 proof-of-life: an operator/environment with no shared session state re-executes the gate and returns a certificate whose authenticity rests on custody + anchoring — the first time in program history the external letter is actually sent AND answered (RES_M5 §2.1).
- **Inputs:** the P3-1 packet + `packet_sha256`; the owner-recorded auditor channel (tier E1 for this first audit); optionally ONE owner-selected blind negative control from the P2-2 corpus as auditor calibration (RES_M5 §2.11 usage ii). **Outputs:** the external `turingos.closure_certificate.v1` (or FAIL artifact) + anchored-digest reference + validator PASS transcript + tracker record.
- **Acceptance criteria:** certificate validates (P1-2 validator); all six custody booleans true; anchored digest recorded through the owner channel BEFORE the in-repo mirror lands; if a blind control was included, the auditor FAILed it for the seeded reason; FAIL outcome → routed to the owning module with the repair/resubmit loop opened.
- **Methodology:** RES_M5 §5.7 steps 2–3, §2.3 tier E1, §2.2 B anchoring. **Implementation notes:** BLOCKED-on-owner checkpoint is hard; no internal substitute exists (tier I1 can never issue this artifact). Complexity: M (plus external latency, recorded separately). **Verification:** validator exit 0 on the received certificate; anchoring reference resolvable; tracker M5.P3 row cites the artifact path.
- **Sub-Prompt (implementer side only — the verifier gets the P1-3 template, nothing else):** *"Confirm the auditor channel exists in the tracker Decision Log; else record BLOCKED-on-owner and stop. Submit packet_sha256 + AUDITOR_RUNBOOK.md via the channel (lineage_scrub.sh clean over the submission bundle first). On return: validate the certificate with validate_closure_certificate.py, verify the anchored digest, record PASS/FAIL in the tracker with the artifact path. On FAIL: open the repair route; never patch the packet in place. Report per playbook §6.2."*

### M5.P4 — Per-module closure service (standing)

Phase gate (per job): certificate validates or FAIL artifact cited; queue line recorded in the tracker M5.P4 row's Evidence column. Standing across waves W1→W4; same BLOCKED-on-owner rule as P3.

#### ATOM-M5.P4-x — One closure job per module gate reaching ADDRESSED (M1.G, M2.TC5/G, M3.G, M4.G, M6.G)

- **Description / why:** the §1.4 certification interface executed: event-driven, one job per consumer gate, so module closures get custody-separated verification without serializing the program (RES_M5 §2.8; pitfall P7).
- **Inputs:** the consumer gate's §3 required-artifacts list + pinned SHA (the trigger is its tracker row reaching ADDRESSED); the channel; tier E2 acceptable here (ADR-M5-002). For M2.TC5 specifically: the job IS the TC-10 run — the verifier executes it on the clean clone and the certificate records the command + exit code.
- **Outputs (per job):** packet + `packet_sha256`; certificate-or-FAIL; one queue line in the tracker M5.P4 Evidence column (`gate, packet digest, status, artifact path` — RES_M5 §5.8).
- **Acceptance criteria (per job):** manifest closure verified before submission; certificate validates with custody complete, or the FAIL artifact is cited and routed to the owning module (new packet at new SHA after repair); no job left with neither artifact (RES_M5 §4 P8).
- **Methodology:** RES_M5 §2.8, §5.8. **Implementation notes:** consumers proceed to their next wave at ADDRESSED; only EXTERNALLY_VERIFIED-gated consumers (FCE E1, G6 rollup) wait. Complexity: S–M per job. **Verification:** FCE-B5-class lint finds zero closure jobs with neither certificate nor FAIL.
- **Sub-Prompt (per job):** *"Gate <ID> reached ADDRESSED. Build its packet from the MODULE_M<n> §3 required-artifacts list with build_packet.sh (--root <gate evidence root> --sha <pinned SHA>); verify manifest closure; run lineage_scrub.sh; submit via the owner channel with the E2 template. On return, validate the certificate; append the queue line to the tracker M5.P4 row. On FAIL, cite the artifact, notify the owning module row, and keep the job open for the new packet. Report per playbook §6.2."*

### M5.P5 — Release mechanics

Phase gate: builder self-test both directions + `--validate` removed-key REJECT; release-blocker battery 3/3 refusals + 1/1 positive control with machine-readable reasons, fixtures FCE-S6-reusable. Needs M5.P1; repo-side placement of `tools/release/` waits for owner activation (prototype in the plan directory is legal earlier and is what P2-2/P3-1 consume).

#### ATOM-M5.P5-1 — `tools/release/build_packet.sh` (+ `--validate` subsumption lint)

- **Description / why:** the single packet producer every consumer shares (module closures, first audit, FCE §10.2 line 419 / FCE-S1 step 6). Generalizes the verified `bundle_sha256s.txt` idiom to a CLOSED manifest, and mechanically subsumes the never-instantiated legacy 17-key skeleton with its self-closure fields killed (`release_next_stage`, packet-internal audit verdicts → lint REJECTS).
- **Inputs:** RES_M5 §5.3 skeleton, §2.4 packet layout, §5.9 field map; ADR-M5-003/007; G12 helper functions for clean-clone and fixture self-tests (RES_M5 §5.11). **Outputs:** `build_packet.sh` accepting `--root`, `--sha` (FCE CLI contract), `--gate`, `--artifact-list`, `--validate`; `PACKET_MANIFEST.json` writer (`turingos.release_packet.v1`, incl. implementer manifest); clean/tamper self-test transcript; `--validate` transcript incl. a seeded `release_next_stage` REJECT.
- **Acceptance criteria:** manifest written LAST; closure check (every packet file listed exactly once, nothing outside the manifest but MANIFEST itself); `packet_sha256` printed; self-test: fixture packet verifies clean, one flipped byte fails; `--validate` re-checks every §5.9 v1 destination and REJECTS removed legacy keys.
- **Methodology:** RES_M5 §2.4, §5.3, §5.9. **Implementation notes:** artifact list is INPUT (from the consumer's §3 list), never the builder's judgment; bundle-or-URL option for repo size. Complexity: M. **Verification:** self-test transcript + FCE §10.2 invocation shape check (`bash tools/release/build_packet.sh --root "$ROOT" --sha "$CERT_SHA"` parses).
- **Sub-Prompt:** *"Implement build_packet.sh per RES_M5 §5.3 with the §2.4 layout and the §5.9 --validate rules (removed keys release_next_stage and packet-internal audit verdicts are REJECTS, not omissions). Reuse the headless_common.py clean/tampered self-test pattern (RES_M5 §5.11) rather than rewriting it. Run and archive: clean build + scratch-dir verify, one-byte tamper FAIL, --validate PASS on a clean fixture and REJECT on a seeded release_next_stage key. Prototype in the plan directory until owner activation. Report per playbook §6.2."*

#### ATOM-M5.P5-2 — `assert_release_eligible.sh` + `RELEASE_ELIGIBLE.json` + refusal fixtures

- **Description / why:** the G6 third clause made mechanical: RELEASED is producible ONLY by this gate, which requires a validated external certificate whose subject digest matches the recomputed packet digest — the three-layer blocker with its negative tests as part of the ship gate, not documentation (RES_M5 §2.6).
- **Inputs:** P1-2 validator; RES_M5 §2.6 layers + §5.6 battery; ADR-M5-005. **Outputs:** `assert_release_eligible.sh` (sole producer of `RELEASE_ELIGIBLE.json` = `{eligible, certificate_sha256, packet_sha256}`); refusal fixtures (`cert_implementer_family.json`, `cert_digest_mismatch.json`, `cert_valid_FIXTURE.json`); the 4-case battery transcript; the claims-lint rule addition (RELEASED only inside `RELEASE_ELIGIBLE.json`-citing artifacts — M0.P6 lint class).
- **Acceptance criteria:** exits nonzero unless certificate validates AND subject digest equals the recomputed packet digest AND verdict PASS AND custody complete AND verifier identity disjoint AND anchoring present; battery: 3/3 refusals + 1/1 positive control, machine-readable reasons; fixtures consumable verbatim by FCE-S6 (09 §3).
- **Methodology:** RES_M5 §2.6, §5.6. **Implementation notes:** the disjunction-hatch regex lives in the shared validator (P1-2) — this script calls it, never reimplements it. Complexity: M. **Verification:** battery transcript archived as P5 evidence; FCE-S6 dry consumption of the fixtures.
- **Sub-Prompt:** *"Implement assert_release_eligible.sh per RES_M5 §2.6 layer 1, calling validate_closure_certificate.py and recomputing the packet digest. Build the three refusal fixtures + one FIXTURE-labeled positive control; run the §5.6 battery and archive the transcript with exit codes and machine-readable reasons. Add the release-specific claims-lint rule to the M0.P6 lint config. Plan-directory prototype until owner activation. Report per playbook §6.2."*

### M5.G — Module gate

#### ATOM-M5.G-1 — Assemble §3 artifact list; run §4 evals; Drift-Check 7/7

- **Description / why:** the roll-up. Implementer assembles the 9-item §3 list and runs the §4 evals; the module's own closure then goes through its own machinery — by definition this gate's verifier class is External, and it blocks on ≥1 external PASS artifact existing somewhere on record (G6).
- **Inputs:** all P1–P5 outputs + the P3/P4 external artifacts. **Outputs:** M5.G packet (built by P5-1's builder over this module's own §3 list) + gate verdict at implementer ceiling.
- **Acceptance criteria:** §3 items 1–9 all present at cited paths; §4.5 thresholds all green; Drift-Check 7/7; module status ADDRESSED (implementer ceiling); EXTERNALLY_VERIFIED only via a certificate over the M5.G packet itself.
- **Methodology:** MODULE_M5 §3–§4; RES_M5 §3. **Implementation notes:** eat-own-dogfood rule — M5's closure packet is built and submitted exactly like any P4 job. Complexity: M. **Verification:** external certificate or recorded FAIL for the M5.G packet, per the §1.4 interface.
- **Sub-Prompt:** *"Assemble the MODULE_M5 §3 artifact list with paths + sha256s; run every §4.1 automated eval and archive transcripts; run the Drift-Check; write the gate verdict with status ADDRESSED (never higher). Then enqueue M5.G itself as a P4-style closure job using its own tooling. Report per playbook §6.2."*
