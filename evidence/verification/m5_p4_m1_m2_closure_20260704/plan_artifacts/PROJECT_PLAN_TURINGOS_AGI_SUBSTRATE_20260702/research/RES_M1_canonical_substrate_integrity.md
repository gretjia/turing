# RES_M1 — Research Report: Canonical Substrate Integrity (Single Owner, Real Authorization, Tape-Canonical Cost)

- Module: M1 — Canonical Substrate Integrity
- Date: 2026-07-02
- Author: Research agent (Fable-5-class), TuringOS AGI-Substrate Convergence Program
- Serves: KPI G2 (single canonical-bytes owner; real-run authorization; tape-canonical cost). Prerequisite for trustworthy G4/G5 measurements (uplift and self-improvement experiments are only as good as their cost/identity provenance).
- Closes audit findings: F3 (canonical second owner, C02 recurrence; authorization never real), F5 (worker attribution not machine-verifiable), F7 (cost estimated, not billing-complete), and implements recommendations R4 and R9 of `/home/zephryj/turingos_backup/work/TURINGOS_RETROSPECTIVE_AUDIT_FINDINGS_20260702.md`.
- Grounding anchors: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/01_PROJECT_INTENT.md`; the audit findings file above; constitution (READ-ONLY) `/home/zephryj/turingos_backup/work/turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md`.
- Evidence discipline: every claim below is labeled **ON-DISK** (file path opened during this research), **EXECUTED** (command actually run on this host, omega-vm, during this research, 2026-07-02), **WEB** (URL), or **REASONED** (analysis with no external artifact). Nothing in this report confers CLOSED/RATIFIED status on anything; the two EXECUTED environment probes are research-grade smoke evidence, not gate evidence.

---

## 1. Questions this research answers

1. How many canonical-bytes implementations actually exist in the active `turing` repo, which are load-bearing, and which bytes are they load-bearing FOR (payload digests vs committed git blobs vs display output)?
2. Should the program adopt an external RFC 8785 (JCS) library, or keep the in-house restricted `turingos.jcs.v1` profile — and why does the restricted profile make cross-language byte-equality tractable?
3. Which single-writer architecture should own canonical bytes: formal designation + cross-checked derived views, Python-calls-Rust via CLI subprocess, PyO3/FFI in-process binding, or a sidecar daemon — evaluated for auditability, failure isolation, determinism, performance, and what already exists on disk?
4. What does a recurrence-proof CI lint gate look like (grep-based vs AST-based; how to keep it self-testing and convergent, per the proven `gate_g10_provenance.sh` pattern), and what exactly must it ban?
5. How can `--require-authorization-head` pass on a REAL worker run on a headless Linux host — is the OS-keyring path (secret-tool / gnome-keyring) actually workable on omega-vm today, and what are the alternatives (file-based Ed25519, TPM, systemd-creds)?
6. How should provider billing receipts and worker identity (model ID/version/API receipt) be captured and bound to tape events for OpenAI, Anthropic, xAI, and DeepSeek workers — per-call response `usage` fields vs organization-level Usage/Cost APIs — and what is the explicit, honest fallback when receipts are unavailable (CLI workers, individual-plan accounts)?
7. How should the existing runsc environment probe be promoted to a mutation-boundary GATE with a `HOST_ASSUMED` fallback recorded on tape, and which execution pattern (`runsc do`, OCI bundle, Docker runtime plug-in) fits the patch-apply/test-run loop?
8. What schema constraints does the codec itself impose on cost events (spoiler: the codec rejects floats, so money must be integer micro-units)?

---

## 2. Candidate methodologies, patterns, and stacks

### 2.1 On-disk ground truth (all verified 2026-07-02)

**(A) Canonical-bytes implementations in the active repo — there are at least six, three of them load-bearing:**

1. **ON-DISK** `/home/zephryj/turingos_backup/work/turing/src/turingos/codec.py` (97 lines) — `canonical_bytes()` at lines 66–80: `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` guarded by `assert_ascii_keys` and `assert_no_floats`. This produces the `payload_hash` embedded in every tape envelope (`tape.py:240` calls `codec.content_digest(payload)`). Load-bearing.
2. **ON-DISK** `/home/zephryj/turingos_backup/work/turing/src/turingos/tape.py:308–312` — the `node.json` blob bytes: `json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`. These bytes are staged and committed into the SHA-256 micro git repo; **the commit OID over these bytes IS the event_id** (`mu:` + OID, `tape.py:318–327`). This is the most load-bearing serialization in the system: change one byte of the serialization policy and every future event ID changes.
3. **ON-DISK** `/home/zephryj/turingos_backup/work/turing/src/turingos/cli.py:69` (`_print`, stdout lines consumed by scripts) and `cli.py:148` (`replay_state.json` output). Semi-load-bearing (downstream tools digest these outputs).
4. **ON-DISK** `/home/zephryj/turingos_backup/work/turing/crates/turing-contracts/src/jcs.rs` (620 lines) — the audited Rust `turingos.jcs.v1` owner: strict parse rejecting duplicate keys / floats / non-ASCII keys / BOM / trailing newline (`parse_strict`, lines 206–218), `canonicalize` (lines 253–304), `semantic_digest` (lines 562–576), plus closed-world payload guards (`reject_forbidden_payload_fields`, `reject_unknown_self_digest_fields`). Its module doc declares byte-for-byte equality with the frozen pack oracle `pack/12_tools/jcs_v5_3_1.py` as the SG-10 cross-implementation property.
5. **ON-DISK** `/home/zephryj/turingos_backup/work/turing/tools/bench/audit_micro_tape_decision_dag.py:91–108` — the strict auditor's own `canonical_bytes` (same recipe as codec.py, with its own ASCII/no-float refusals). **Deliberately independent by design** — the auditor must not consume the implementation it audits. This is a legitimate cross-CHECK, not a second OWNER, and the singleton gate must whitelist it explicitly (see §2.4) or it becomes a false positive that pressures someone to delete the auditor's independence.
6. **ON-DISK** `/home/zephryj/turingos_backup/work/turing/tools/headless/headless_common.py:37–38` — `canonical_json_bytes()` uses `json.dumps(value, sort_keys=True, separators=(",", ":"))` **without `ensure_ascii=False`**. Python's default is `ensure_ascii=True`, so any non-ASCII string value serializes as `\uXXXX` escapes here but as raw UTF-8 in codec.py. **This is a live, silent byte-divergence between two "canonical" helpers in the same repo** — concrete proof that prose discipline does not prevent C02 recurrence; only a gate does.
7. **EXECUTED** `grep -rln "sort_keys=True" turing/tools/ --include="*.py" | wc -l` → **49 files** under `tools/` serialize with sorted keys; most are receipt/digest renderers. Not all are canonical owners, but each is a latent divergence site the lint gate must classify (allowlist or route).

**(B) There are also two divergent TAPE FORMATS and three tape-append implementations — "single canonical owner" is not only about bytes, it is about who may move refs:**

- Python `Tape` (`src/turingos/tape.py`): blob named `node.json`; 7-field envelope; **exactly two refs** — its own docstring (lines 12–16, 49–51, 323) says "There is NO `refs/turingos/authorization_head` in 1.0".
- Rust `turing-git-tape` (`crates/turing-git-tape/src/append.rs:55–60`): blob named `event` holding canonical JCS envelope bytes; **three refs** including `REF_AUTHORIZATION_HEAD = refs/turingos/authorization_head`.
- The bench harness is a THIRD writer: `tools/bench/run_mini_swe_bench_substrate_smoke.py:1463–1486` appends events and moves `refs/turingos/authorization_head` directly with `git update-ref` from Python (`append_stage6_event` path), and `append_test_local_authorization` (lines 604–660) mints AUTHORIZATION events with `signature_route=test_local_authority`.

So the benchmark evidence tapes were produced by a Python harness writer whose format (three refs, auditor-derived head effects) matches the Rust crate's model, while the `src/turingos` kernel implements a two-ref model. Any "single owner" ADR must name which head-set model is canonical going forward, not just which serializer.

**(C) Cross-implementation byte-equality is already PROVEN on the payload domain (the omega track):**

- **ON-DISK** `/home/zephryj/turingos_backup/work/turingos_research/F1/xcheck/RESULT_CROSS_IMPL.md`: Rust `turing_contracts::jcs::parse_strict→canonicalize` vs Python `canonical_dumps` — **8/8 vectors byte-identical** on omega-vm (2026-06-26), including the adversarial vector 6 (`café 😀 ✓ U+2028 DEL /` — raw UTF-8, no escaping on both sides). Harness: `F1/xcheck/xcheck_emit.py` (Python side, emits corpus JSONL + `<idx>\t<hex>` lines) + `F1/xcheck/src/main.rs` (Rust side); verdict = empty `diff`.
- **ON-DISK** `/home/zephryj/turingos_backup/work/turingos_research/F1/gates/gate_g10_provenance.sh`: the v2 second-owner detector — grep-based, fail-closed, **self-testing** (`--self-test` proves clean fixture rc=0 and tampered fixture rc=1, "the gate has teeth"), with exit codes 0 PASS / 1 FAIL / 2 self-test fail / 3 NOT_RUN (never rolls up to PASS), and a `--wide` audit mode. This is the house-style gate design M1 should port to the turing repo.
- **ON-DISK** `/home/zephryj/turingos_backup/work/turingos_research/F1/F1.1_ROUTING_MAP.md`: the omega track's surgical routing plan (26 producer sites classified into authority/tools/legitimate-oracle) — the classification method (A: must-route producers; B: tools; C: legitimate independent oracles to KEEP) is directly reusable for the turing repo's 49 `sort_keys=True` files.

**(D) The authorization gap and its environment — the blocking condition no longer exists on this host:**

- **ON-DISK** `/home/zephryj/turingos_backup/work/turing/evidence/bench/mini_swe_bench_stage7_real_smoke_2task_20260628/README.md` lines 47–53, 105–111, 141, 147: the only real worker run among stages 6–11 recorded "failed because OS keyring provider `secret-tool` is unavailable in this environment", fell back to `authorization-mode auto`, and its strict audit records `authorization_head: LEGACY_MISSING` with finding `require_authorization_head`. This is audit F3's "authorization_head has never passed outside fixtures".
- **ON-DISK** production signing path: `crates/turing-approval/src/lib.rs` — `OsKeyringSigningBackend` (lines 204–241) shells out to `secret-tool lookup/store` (lines 447–511); on miss it generates an Ed25519 `SigningKey` and stores the seed hex in the keyring. A `LocalFileSigningBackend` also exists (lines 283–425): JSON key record under `~/.turingos/approval_local_file_keys/`, written with `create_new` and chmod 0600. An `InMemoryTestSigningBackend` covers tests. The daemon RPC surface that consumes this: `crates/turing-daemons/src/lib.rs:248–300` — `approval.authorize_atom`, `capsule.approve`, `event.append_preserve`, `grant.authorize` (turing-execd role), etc. The Python harness talks to these daemons over Unix sockets (`run_mini_swe_bench_substrate_smoke.py:189–233`, binaries `turingd`, `turing-execd`, `turing-mcp`, `turing-marketd`, `turing-pputd`, `turing-viewd`, `turing` at line 168).
- **EXECUTED (research probe, this host, 2026-07-02):** `/usr/bin/secret-tool` and `gnome-keyring-daemon` 42.1 are installed. The full headless round-trip works:
  ```
  dbus-run-session -- sh -c '
    printf "test-master-pass" | gnome-keyring-daemon --unlock --components=secrets >/dev/null 2>&1
    sleep 1
    printf "s3cret-probe-value" | secret-tool store --label="m1probe" m1probe key1
    secret-tool lookup m1probe key1     # printed: s3cret-probe-value
    secret-tool clear m1probe key1'     # RC=0
  ```
  Store → lookup → clear all succeeded (lookup returned the exact stored value; final RC=0). **The "host with a working OS keyring" required by audit R9 is this host**; closing the real-run authorization gap requires no new hardware or provider — only wrapping the real worker run in an unlocked keyring session.
- **EXECUTED (research probe):** `runsc --rootless --network=none do /bin/echo runsc-ok` → printed `runsc-ok`. `runsc version release-20260608.0, spec 1.2.1`, present at `/home/zephryj/.local/bin/runsc` and `/usr/local/bin/runsc`. Rootless gVisor execution works on omega-vm (Debian 12, kernel 6.1) today.

**(E) Cost and worker-identity ground truth (what F5/F7 look like in code):**

- **ON-DISK** `tools/bench/run_mini_swe_bench_substrate_smoke.py:498–500`: the "token estimates" are literally word counts — `"prompt_tokens_estimate": len(prompt.split())`, `"completion_tokens_estimate": len(proc.stdout.split())`. A word count is neither a token count nor a bound on one; audit F7's "estimated tokens with `cost_source_kind: unspecified`" is generous — the current estimator has no defined relationship to billable tokens.
- **ON-DISK** `tools/bench/audit_micro_tape_decision_dag.py:738–776` (`cost_conservation_status`): the strict auditor checks that final `PPUTAccounted.total_run_token_count` equals the sum of matching `CostEvent.total_tokens` (and wall-time likewise). It checks CONSERVATION only — it has no notion of cost SOURCE, provider receipts, or worker identity. Extending this auditor (not replacing it) is the natural insertion point for receipt provenance checks.
- **ON-DISK** `src/turingos/worker/adapter.py`: the `WorkerAdapter` seam produces `turingos.receipt.v1` receipts carrying `worker_id` (a short string like "fake"/"claude") — no model ID, no model version, no API request ID. `src/turingos/worker/cli.py:59–60`: the grok CLI worker is invoked with `--output-format plain`, which discards any usage metadata the underlying API returned. This is exactly why audit F5 found worker attribution unverifiable: the predictions file said `turingos-internal-rehearsal` while prose claimed a frontier worker.

### 2.2 Canonical codec: keep the restricted in-house profile; do NOT adopt a full RFC 8785 library

**The option space:**

| Option | What it is | Pros | Cons |
|---|---|---|---|
| Full RFC 8785 via libraries | Rust: `serde_json_canonicalizer` or `vr-jcs`; Python: `rfc8785` (Trail of Bits) or `jcs` | Standard; external test vectors exist | Imports the ES6 IEEE-754 number-serialization surface — the single largest cross-language divergence risk (the reference project ships a 100-million-value number corpus just to test it); adds third-party supply chain to the trust base; would have to be byte-checked against ALL existing digests anyway |
| Keep restricted `turingos.jcs.v1` (integers only, ASCII keys, no floats, raw-UTF-8 string values) | What `codec.py` + `jcs.rs` already implement | Floats — the hard part of JCS — are REJECTED, not canonicalized, so byte equality across languages reduces to key sorting + string escaping + integer rendering, all already proven 8/8; zero new dependencies; existing digests/event IDs preserved | Not "full" RFC 8785 (irrelevant: interop with external JCS consumers is a non-goal); the restriction must stay enforced in both implementations |

**WEB evidence on the library landscape** (for the record, and for why "just use a library" is worse here): `serde_jcs` appears abandoned with documented RFC deviations; `serde_json_canonicalizer` is the maintained Rust option but explicitly converts arbitrary-precision numbers to doubles (lossy — a correctness hazard for a substrate whose codec bans floats precisely to avoid this); Python `rfc8785` (Trail of Bits, pure Python, Apache-2.0) is the best-packaged Python implementation; the cyberphone `json-canonicalization` repo is the canonical cross-language test-vector source, including `es6testfile100m.txt.gz` for number serialization. Sources: [serde_json_canonicalizer docs](https://docs.rs/serde_json_canonicalizer/latest/serde_json_canonicalizer/), [serde_jcs](https://docs.rs/serde_jcs), [rfc8785 on PyPI](https://pypi.org/project/rfc8785/), [cyberphone/json-canonicalization testdata](https://github.com/cyberphone/json-canonicalization/tree/master/testdata), [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html).

**REASONED conclusion:** the restricted profile is a feature, not a gap. The correct move is to designate ONE existing implementation as owner and gate the rest — not to introduce a seventh implementation via pip/cargo. The only place external JCS artifacts help: borrow the *string-escaping* test vectors from the cyberphone corpus (control characters 0x00–0x1F, surrogate pairs, U+2028/U+2029) to extend the xcheck corpus, which `RESULT_CROSS_IMPL.md` itself lists as remaining work.

### 2.3 Single-writer architecture: four candidates

**Option 1 — Formal designation + cross-checked derived views (gate-enforced duplication).**
Declare `turing-contracts::jcs` (Rust) the singleton canonical-bytes owner by ADR; demote `src/turingos/codec.py` to a "derived view" that must byte-match the owner over a corpus in CI on every commit; ban all other canonicalization sites via lint.
- Pros: zero runtime coupling (pure-Python paths keep working offline); cheapest to land; the 8/8 xcheck proof means the gate starts GREEN; failure isolation is total (nothing new can crash).
- Cons: the duplicate logic still exists — drift is *caught within one CI cycle*, not *prevented*; two codebases must evolve in lockstep for any codec change (mitigated by the frozen-policy reality: the codec is contractually frozen, changes are rare and constitutional-review-worthy anyway).
- Auditability: good — the CI job's corpus + diff output is itself an evidence artifact.

**Option 2 — Python routes through the Rust owner via CLI subprocess.**
Add a `turing jcs canonicalize` verb (or a tiny `turing-jcs` binary) reading JSON on stdin, writing canonical bytes (or `<idx>\t<hex>` batch lines, like the xcheck harness) on stdout; `codec.canonical_bytes()` becomes a thin client.
- Pros: one owner in fact, not just in law; process boundary = clean failure isolation (non-zero exit → fail-closed `RejectedAppend`); superb auditability — the harness can record the binary's sha256 (`which_digest` already exists in `headless_common.py:99–104`) and argv digest on tape, so *which code produced the bytes* is itself tape-reconstructible.
- Cons: ~1–10 ms process spawn per call — for tape appends (tens per task) this is negligible; for bulk digesting use batch mode over stdin. Requires the Rust toolchain/binary to be present wherever Python runs (pin by digest; fall back to fail-closed, never to a silent Python reimplementation).
- **ON-DISK precedent:** the Python `Tape._git` already shells out to `git` for every operation (`tape.py:111–123`) — subprocess-per-operation is the established house pattern, not a novelty.

**Option 3 — PyO3/FFI in-process binding (maturin wheel wrapping turing-contracts).**
- Pros: microsecond calls; single owner in fact.
- Cons: **EXECUTED** `grep -rn "pyo3|maturin" turing/ --include="*.toml"` → no hits; this would be a brand-new build system (abi3 wheels, cross-version CPython concerns) for a repo that is deliberately "stdlib only" on the Python side (`tape.py` docstring). Shared address space blurs the failure boundary (a Rust panic can abort the Python process); binary provenance is harder to attest than a standalone binary's sha256 (the loaded .so must be digested too, and import-time magic makes "which code ran" less legible to an auditor). REASONED: rejected for this program increment; the performance win serves nothing (LLM calls dominate latency by 4–6 orders of magnitude).

**Option 4 — Sidecar daemon ownership (route appends through turingd / turing-git-tape).**
The infrastructure already exists: turingd exposes `event.append_preserve` and approval RPCs over a Unix socket, and the Python bench harness already launches and speaks to all six daemons (`run_mini_swe_bench_substrate_smoke.py:168–233`). Routing Python tape appends through turingd makes the Rust crate simultaneously the single canonical-bytes owner AND the single head-set writer — collapsing both duplication axes (§2.1-B) in one move.
- Pros: strongest ownership story; the authorization_head model (three refs) that the Rust side and the strict auditor already share becomes the single tape format; single place to enforce single-writer/FF guards server-side (the seam `tape.py`'s own docstring says belongs to a server hook, lines 21–24).
- Cons: daemon lifecycle in every context that appends (tests, tiny tools); the Python `Tape` class and its 589-test suite would need a client-mode or fixture-mode split; larger blast radius than Option 2.

**REASONED recommendation (see §3):** sequence 1 → 2 → 4. Designation + gates now (days, unblocks the C02-class finding mechanically); CLI routing of the load-bearing byte producers next (the F1.1_ROUTING_MAP method, applied to the turing repo); daemon-routed appends as the M1 end-state for NEW tapes, with the Python Tape demoted to test fixture. Historical tapes are never rewritten — the strict auditor (independent by design) continues to read them.

### 2.4 CI lint gate: grep + AST + byte-equality, all self-testing

Three complementary jobs (each cheap, each with a tamper self-test per the `gate_g10_provenance.sh` pattern):

1. **Byte-equality xcheck (cross-impl gate).** Port `F1/xcheck` into the turing repo: Python emits `<idx>\t<hex>` of `codec.canonical_bytes` over a corpus; the Rust harness (a 30-line binary over `turing_contracts::jcs`) emits the same; `diff` must be empty. Extend the 8-vector corpus with: full control-character table (0x00–0x1F), surrogate-pair boundaries (U+10000, U+10FFFF), U+2028/U+2029, DEL, solidus, empty string/object/array keys and values, deep nesting (≥32 levels), 10^15-scale integers and i64 boundaries, and **non-ASCII string values** (the `headless_common.py` divergence class — this corpus entry would have caught it).
2. **Singleton lint, grep layer.** Fail if `json.dumps` with `sort_keys=True` appears outside an explicit allowlist: `src/turingos/codec.py` (until routed), `tools/bench/audit_micro_tape_decision_dag.py` (the deliberately independent auditor — allowlisted BY NAME with a comment stating why). Also fail on any new `def canonical_bytes|canonical_dumps|canonical_json_bytes` outside the owner. Include `--self-test` (temp dirs with clean and tampered fixtures, expect rc 0 and 1) and `--wide` audit mode, exit code 3 = NOT_RUN, exactly like gate_g10.
3. **Singleton lint, AST layer (evasion resistance).** A ~60-line stdlib-`ast` walker over `src/` and `tools/` that flags any `Call` whose func resolves to `json.dumps` (including `from json import dumps` aliasing) carrying a `sort_keys` keyword of truthy value, outside the allowlist. Grep catches renames of wrappers; AST catches aliased/wrapped calls grep misses. REASONED: prefer stdlib `ast` over semgrep/libcst — zero new supply chain, and the check is simple enough that a dependency buys nothing.
4. **Tape-writer ref lint (the head-set axis).** Fail on `update-ref refs/turingos/` or `REF_AUTHORIZATION_HEAD`-equivalent string literals outside the designated writer (turing-git-tape crate + explicitly allowlisted harness shims until they are routed). This is what makes "single owner" cover refs, not just bytes — audit F3's three-owner finding includes the harness moving `authorization_head` by hand (`run_mini_swe_bench_substrate_smoke.py:1485`).

CI wiring: all four run in the same job stage as the existing Python tests; any FAIL blocks merge; NOT_RUN blocks merge (never rolls up to PASS — Project Intent §5.2 discipline applied to CI).

### 2.5 OS keyring on headless Linux — options and the proven path

| Option | Mechanism | Pros | Cons | Verdict |
|---|---|---|---|---|
| **gnome-keyring + secret-tool under dbus-run-session** | `dbus-run-session -- sh -c 'printf "$PASS" \| gnome-keyring-daemon --unlock --components=secrets; <real run>'` | **EXECUTED — works on omega-vm today** (§2.1-D); exercises the EXACT production code path (`OsKeyringSigningBackend` → `secret-tool`), which is what R9 demands; secrets encrypted at rest under `~/.local/share/keyrings` | Keyring master passphrase must be fed to the session (env/file handling discipline needed); the D-Bus session dies with the wrapper — every run needs the wrapper; a LOCKED keyring makes secret-tool hang waiting for a prompt (must always use the `--unlock` flow headlessly) | **Recommended for the R9 real run** |
| File-based Ed25519, 0600 perms | `LocalFileSigningBackend` — already implemented, `crates/turing-approval/src/lib.rs:283–425` (create_new + chmod 0600, schema-checked key record) | Zero session management; deterministic; already tested | Does NOT close R9 as stated — the audit's gap is specifically that the *os-keyring route* never ran real; a file-backend PASS would be a different (weaker) claim and must be labeled as a distinct `signature_route` on tape | Keep as explicit fallback tier, never silently substituted |
| TPM 2.0 (tpm2-tools / PKCS#11) | Key sealed in hardware | Strongest custody | Cloud-VM TPM availability unverified here; large integration surface; nothing on disk targets it | Defer (2.x roadmap note only) |
| systemd-creds | Host-key/TPM-encrypted service credentials | Simple for service secrets | Not a Secret Service implementation — does not satisfy the secret-tool code path | Rejected for this purpose |

Custody note (red line): the keys involved here are **approval/authorization keys minted on this host by the signing backend** — they are NOT the genesis Ed25519 key, which stays on the local Mac and never appears on omega (Project Intent §5.1). The ADR must state this distinction so no agent conflates "unlock the keyring for approval signing" with "move the genesis key".

### 2.6 LLM provider receipts and worker identity on tape

**Layer 1 — per-call response `usage` (the primary receipt; capture at the adapter seam):**

- OpenAI-compatible (OpenAI, xAI/Grok): `usage: {prompt_tokens, completion_tokens, total_tokens, prompt_tokens_details.cached_tokens}`; response `model` field returns the RESOLVED model version; `x-request-id` response header is the per-call receipt anchor. xAI is explicitly OpenAI/Anthropic-SDK-compatible. WEB: [xAI docs overview](https://docs.x.ai/overview), [xAI prompt-caching best practices](https://docs.x.ai/developers/advanced-api-usage/prompt-caching/best-practices).
- Anthropic: `usage: {input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens}`; `request-id` response header; response `model` is the resolved model ID.
- DeepSeek: OpenAI-compatible plus top-level `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` (different unit prices per class — cache-hit vs cache-miss pricing differs by ~50x, so recording only `prompt_tokens` mis-costs DeepSeek runs badly). WEB: [DeepSeek context-caching announcement](https://api-docs.deepseek.com/news/news0802), [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing).

**Layer 2 — organization-level Usage/Cost APIs (reconciliation, not the primary record):**

- OpenAI: `GET /v1/organization/usage/completions` (buckets with `input_tokens`, `output_tokens`, `input_cached_tokens`, `num_model_requests`, groupable by `api_key_id`/`project_id`/`model`) and `GET /v1/organization/costs` (daily buckets, monetary amounts) — both require an **Admin API key**, distinct from inference keys. WEB: [OpenAI Usage/Cost API cookbook](https://developers.openai.com/cookbook/examples/completions_usage_api), [Costs API reference](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs).
- Anthropic: `GET /v1/organizations/usage_report/messages` and `GET /v1/organizations/cost_report` — require an Admin key (`sk-ant-admin…`) and an org on **Team/Enterprise plan; individual accounts cannot access these**. WEB: [Usage & Cost API docs](https://platform.claude.com/docs/en/manage-claude/usage-cost-api), [Cost Report reference](https://platform.claude.com/docs/en/api/admin/cost_report).
- REASONED consequence: Layer 2 may be unavailable for this program's accounts. Therefore the schema must treat Layer 1 (inline usage) as the load-bearing receipt and Layer 2 as an optional reconciliation pass — never a hard dependency of G2's "100% of LLM calls carry provider receipts or an explicit estimated-cost boundary".

**Binding receipts to tape — schema design constraints:**

1. **No floats on tape.** The codec rejects floats (`codec.py:50–63`, `jcs.rs:132–135`). All monetary amounts must be integers: recommend `cost_microusd` (integer micro-USD) plus `price_table_digest` referencing a pinned, dated unit-price table (itself a tape-adjacent artifact with a sha256). Token counts are already integers.
2. **No secrets on tape.** Record `api_key_id`-style identifiers only if they are non-secret handles; never the key. Request IDs, model IDs, usage integers, and header digests are safe.
3. **Worker identity fields** (fixes F5): extend the receipt/cost schema with `model_id_requested`, `model_id_resolved` (from the response body), `provider`, `endpoint`, `request_id` (from `x-request-id`/`request-id` header), `response_sha256` (digest of the raw response body stored in the evidence root), and `adapter_kind` (`native_api` | `cli` | `fake`).
4. **`cost_source_kind` enum**, one per CostEvent: `provider_receipt_inline` (usage from the response body — the normal case), `provider_usage_api_reconciled` (Layer 2 match found; carries the bucket reference), `bounded_estimate` (see below), `fixture` (deterministic tests). The strict auditor gains a `--require-cost-provenance` mode: FAIL if any CostEvent on a REAL run lacks `provider_receipt_inline`/`bounded_estimate`, and FAIL if a `bounded_estimate` lacks its bound derivation.
5. **Bounded estimates must actually bound.** The current `len(prompt.split())` word count (**ON-DISK** `run_mini_swe_bench_substrate_smoke.py:498–500`) is not a bound. An honest fallback for CLI workers that hide usage: `ceil(len(utf8_bytes)/B)` with a per-provider conservative bytes-per-token floor B (e.g. B=2 overestimates tokens for English text under BPE tokenizers — REASONED, must be stated as an assumption in the schema field `bound_kind: upper_bound_bytes_over_2`), or better, run the provider's tokenizer offline where licensed. The point is not precision; it is that the tape says *what kind of number this is and why it cannot be an undercount*.
6. **CLI workers (grok `--output-format plain`) cannot produce receipts.** Options: (i) prefer native-API adapters for uplift-experiment arms (a stage13 "native_api_worker" evidence root already exists: `turing/evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/` — the harness lineage supports this); (ii) if a CLI worker must be used, use its JSON output mode if it exposes usage; else (iii) label every such call `bounded_estimate`. The G4 experiment design should REQUIRE native-API adapters for all measured arms, reserving CLI workers for smoke only — this is the single highest-leverage policy for making H-VPPUT measurable (F7).

### 2.7 runsc/gVisor mutation-boundary enforcement

**Current state:** `tools/headless/headless_common.py:223–240` only *detects* runsc (`platform_not_run()` appends `runsc_missing`; `runsc_version()`); nothing in `src/` or `crates/` invokes runsc (**EXECUTED** grep: no hits outside `tools/headless/`). Sandboxing is currently an environment observation, not a boundary.

**Execution pattern options:**

| Pattern | Command shape | Pros | Cons |
|---|---|---|---|
| `runsc do` (ad-hoc) | `runsc --rootless --network=none --TESTONLY-unsafe-nonroot=false do <argv>` | **EXECUTED — works rootless on omega-vm now**; zero OCI ceremony; overlay keeps host FS unmutated by default for `do` | Uses host rootfs (toolchain leakage into the sandbox image is possible — acceptable for patch/test loops that intentionally need the repo toolchain) |
| Full OCI bundle | `runsc run` with `config.json` + pinned rootfs | Strongest reproducibility (image digest on tape) | Requires building/pinning rootfs images — significant new scope; the omega track's C18/E0 work targets this level, do not duplicate it here |
| Docker `--runtime=runsc` | Register runsc as a Docker runtime | Integrates with Docker-based flows | **Must NOT be applied to the upstream SWE-bench scorer** — the official harness's stock Docker environment is the sole official scorer (Project Intent §5.7); changing its runtime would invalidate the qualification |

**Gate design (promote probe → gate, with HOST_ASSUMED fallback):**

1. Self-test at run start: execute `runsc --rootless --network=none do /bin/true`; record `{runsc_present, runsc_version, runsc_binary_sha256 (which_digest), selftest_exit}`.
2. If self-test passes → every mutation step (patch apply, test run) executes as `runsc --rootless --network=none do <argv>`; the tape event for the step carries `sandbox: {kind: "runsc_rootless_do", runsc_version, runsc_binary_sha256, network: "none"}`.
3. If self-test fails → the run MAY proceed (constitution allows it) but MUST append a `SandboxBoundaryAssumed` (PRESERVE) event first: `{sandbox: {kind: "HOST_ASSUMED", reason: <probe output digest>, host: <platform digest>}}` — making the exception tape-reconstructible per Project Intent §5.6.
4. Auditor extension: a `--require-sandbox-provenance` flag that FAILs any mutation-class event lacking a `sandbox` block, and reports `HOST_ASSUMED` counts in the verdict summary (visible, never silently equal to sandboxed).

REASONED caveats: rootless runsc needs unprivileged user namespaces (kernel 6.1 on this host has them — proven by the probe); `--network=none` is the right default for patch/test loops (Goodhart shielding side benefit: a sandboxed worker cannot fetch gold data); wall-clock overhead of gVisor on syscall-heavy test suites is real (typically tens of percent) — record wall time inside vs outside so G4 cost accounting is not confounded silently.

---

## 3. Recommendation (tied to project goals)

**R-M1-1. Designate `turing-contracts::jcs` (Rust, `crates/turing-contracts/src/jcs.rs`) as the single canonical-bytes owner by ADR; demote every Python implementation to cross-checked derived view; land the four CI gates of §2.4 in the same change.** Rationale: replayability (bytes provably stable — the 8/8 xcheck means designation costs zero byte churn); long-running autonomy (agents drift; only mechanical gates persist across sessions — the `headless_common.py` ensure_ascii divergence is on-disk proof); modularity (the codec becomes a port with one adapter); cost (days of work, no new dependencies). This closes the C02-class finding *mechanically* the way audit R4 demands.

**R-M1-2. Route load-bearing Python byte-producers through the owner in two steps: first the tape append path (`codec.canonical_bytes` + `tape.py:310` node bytes) via a batch-capable `turing jcs` CLI verb (Option 2), then tape appends themselves through turingd `event.append_preserve` (Option 4) so the Rust crate owns bytes AND refs for all NEW tapes.** Rationale: sandboxed execution and failure isolation favor the process boundary over FFI; auditability favors a digestable standalone binary; the daemon infrastructure and the three-ref tape model already exist and already match what the strict auditor derives. Historical tapes are never rewritten (replayability; evidence roots stay valid); the Python `Tape` is retained as a labeled test fixture. Reject PyO3 (Option 3) this increment.

**R-M1-3. Close the R9 authorization gap on THIS host with the gnome-keyring headless session pattern (§2.5), running one real worker run with `--authorization-mode required --authority-provider os-keyring` and the strict audit with `--require-authorization-head`.** Rationale: both environment probes passed here during this research; this exercises the exact production `OsKeyringSigningBackend → secret-tool` path, so the resulting PASS is the real claim (not a file-backend simulacrum). Observability: the run's evidence root records keyring provider, session mode, and the auditor verdict. Status ceiling: the implementing agent marks this ADDRESSED; only an independent verifier can certify further.

**R-M1-4. Land `CostEvent.v2` + worker-identity fields (§2.6) at the `WorkerAdapter` seam, with `cost_source_kind` mandatory, integer micro-USD only, pinned price-table digest, and provider request IDs; extend the strict auditor with `--require-cost-provenance`; require native-API adapters for all G4-measured arms.** Rationale: this is the prerequisite for G4/G5 being *measurements* (F5+F7); Goodhart shielding (receipts live on the supervisor tape, never in worker-safe packets); honest reporting (bounded estimates are labeled, word-count pseudo-estimates are abolished).

**R-M1-5. Promote the runsc probe to the mutation-boundary gate of §2.7 (`runsc --rootless --network=none do` per mutation step; `SandboxBoundaryAssumed`/HOST_ASSUMED tape event as the recorded exception; auditor flag).** Rationale: constitution §5.6 compliance becomes tape-reconstructible instead of aspirational; the probe already passes on omega-vm so the common path is sandboxed, not HOST_ASSUMED; the upstream Docker scorer is explicitly out of scope (red line §5.7).

Execution order: R-M1-1 (gates first — they protect everything after) → R-M1-3 (independent of routing; unblocks G2's authorization KPI immediately) → R-M1-4 (schema work; prerequisite for M-experiment modules) → R-M1-5 (small, independent) → R-M1-2 (the larger routing refactor, protected by the already-green gates).

---

## 4. Pitfalls & mitigations

1. **`ensure_ascii` divergence class (proven live in `headless_common.py:37–38`).** Two helpers with identical names and near-identical code can differ on one default and silently fork bytes for non-ASCII values. Mitigation: xcheck corpus MUST include non-ASCII string values (it does — vector 6) and the corpus must be run against every allowlisted derived view, not only codec.py.
2. **Event-ID rigidity.** `tape.py:310` bytes are committed; commit OIDs are event IDs. Any serialization change alters all FUTURE event IDs and any test pinning them. Mitigation: designation is forward-only; never rewrite historical tapes; the 8/8 byte-equality proof means routing through the Rust owner preserves bytes for the payload domain — re-prove on the extended corpus BEFORE routing, exactly as `F1.1_ROUTING_MAP.md` sequences it (build adapter → prove bytes → route → gate flips GREEN).
3. **Gate false positives destroying legitimate independence.** The strict auditor's own `canonical_bytes` (`audit_micro_tape_decision_dag.py:91`) and any differential oracle are *deliberate* duplicates. Mitigation: allowlist them BY PATH with an in-gate comment explaining why (the F1.1 routing map's class-C category); `--wide` mode still reports them so the full picture is never hidden.
4. **Gate evasion by rename/aliasing.** Grep alone misses `from json import dumps as d`. Mitigation: the AST layer (§2.4-3) plus the `--self-test` discipline (a gate that cannot fail a tampered fixture is inert and must be rejected — gate_g10's G11 rule).
5. **Keyring session hangs.** A locked keyring makes `secret-tool` block on a prompt that never comes on a headless host. Mitigation: always the `dbus-run-session` + `gnome-keyring-daemon --unlock` wrapper; wrap all secret-tool calls in timeouts; treat timeout as NOT_RUN (blocks, never PASSes).
6. **Keyring passphrase handling.** The unlock passphrase must not land on tape, in evidence roots, or in shell history. Mitigation: read from a 0600 file outside the repo or an env var set by the operator; the evidence root records only `keyring_unlocked: true` and the provider name.
7. **Genesis-key conflation.** An agent could misread "set up signing keys on omega" as touching the genesis Ed25519 gate. Mitigation: the ADR text and every runbook states: approval keys are host-local, minted by the backend; the genesis key NEVER leaves the Mac (red line §5.1).
8. **Floats on tape via cost fields.** Naive `cost_usd: 0.0123` is rejected by the codec (correctly). Mitigation: integer `cost_microusd` + pinned price table; CI fixture that attempts a float cost and must be rejected (tamper self-test).
9. **Provider usage APIs are plan-gated.** Anthropic's Admin API requires Team/Enterprise; OpenAI requires an Admin key. Mitigation: Layer-1 inline usage is the load-bearing receipt; Layer-2 reconciliation is optional enrichment; the KPI wording already allows "explicit estimated-cost boundary" as the labeled fallback.
10. **DeepSeek cache split.** Recording only `prompt_tokens` for DeepSeek collapses cache-hit and cache-miss tokens whose prices differ enormously; cost would be wrong by up to ~50x on cached workloads. Mitigation: schema carries provider-specific usage verbatim plus normalized fields; the price table keys on (provider, model, token_class).
11. **Worker-visible cost leakage (Goodhart).** PPUT/price internals must not reach workers (constitution Art. III.4). Mitigation: receipts and price tables are appended by the SUPERVISOR side of the adapter seam; the worker-safe packet generator's leakage audit adds these fields to its blocklist.
12. **runsc overhead confounding G4 cost measurements.** gVisor slows syscall-heavy test suites. Mitigation: `sandbox.kind` is on every mutation event, so wall-clock comparisons across arms can condition on it; keep sandbox kind CONSTANT within an experiment.
13. **Scope creep into the omega track.** C18/E0 (OCI bundles, engine digests, ratification roots) belong to the turing_v5 foundation track. Mitigation: M1's runsc gate stays at the `runsc do` level; anything requiring rootfs image pinning is flagged to the owner, not built here (Project Intent §7).
14. **Self-closure.** None of the above may be declared CLOSED by its implementer. Mitigation: every M1 deliverable's ship gate emits an evidence bundle for a cross-family verifier; status ceiling ADDRESSED (Project Intent §5.2).

---

## 5. How to use this in an agentic loop (concrete)

**5.1 Byte-equality xcheck job (CI + local):**
```bash
# Python side (owner-view emitter; mirrors turingos_research/F1/xcheck/xcheck_emit.py)
python3 tools/gates/xcheck_emit.py /tmp/corpus_jcs.jsonl > /tmp/py.tsv
# Rust side (30-line harness over turing_contracts::jcs, add crates/turing-xcheck)
cargo run -q -p turing-xcheck < /tmp/corpus_jcs.jsonl > /tmp/rs.tsv
diff /tmp/py.tsv /tmp/rs.tsv && echo XCHECK_PASS || { echo XCHECK_FAIL; exit 1; }
```

**5.2 Singleton lint (grep layer) — port of gate_g10 to the turing repo:**
```bash
tools/gates/gate_singleton_codec.sh --self-test   # must print SELF-TEST PASS (clean rc=0, tamper rc=1)
tools/gates/gate_singleton_codec.sh               # 0 PASS | 1 FAIL | 3 NOT_RUN(blocks)
# Load-bearing patterns it bans outside the allowlist:
#   'json\.dumps\([^)]*sort_keys=True'         (canonical serialization)
#   'def +(canonical_bytes|canonical_dumps|canonical_json_bytes)'
#   'update-ref +refs/turingos/'                (head-set writer axis)
# Allowlist (by exact path, with reasons in-file):
#   src/turingos/codec.py                        # derived view until R-M1-2 routes it
#   tools/bench/audit_micro_tape_decision_dag.py # independent auditor BY DESIGN
```

**5.3 AST lint core (stdlib only, drop in `tools/gates/lint_no_second_codec.py`):**
```python
import ast, sys, pathlib
ALLOW = {"src/turingos/codec.py", "tools/bench/audit_micro_tape_decision_dag.py"}
def offenders(root: pathlib.Path):
    for p in root.rglob("*.py"):
        rel = str(p.relative_to(root))
        if rel in ALLOW or "__pycache__" in rel: continue
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=rel)
        aliases = {"dumps"}  # track `from json import dumps [as X]`
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module == "json":
                aliases |= {a.asname or a.name for a in n.names if a.name == "dumps"}
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                f = n.func
                named = isinstance(f, ast.Attribute) and f.attr == "dumps"
                bare = isinstance(f, ast.Name) and f.id in aliases
                if (named or bare) and any(
                    k.arg == "sort_keys" and getattr(k.value, "value", None) is True
                    for k in n.keywords):
                    yield f"{rel}:{n.lineno}"
if __name__ == "__main__":
    hits = list(offenders(pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
    print("\n".join(hits)); sys.exit(1 if hits else 0)
```

**5.4 R9 real-run authorization sequence (omega-vm; probe-verified pattern):**
```bash
# 1. Build daemons once:   . ~/.cargo/env && cargo build --release   (bin_dir = target/release)
# 2. Unlocked-keyring session wrapping the REAL run (passphrase from 0600 file OUTSIDE the repo):
dbus-run-session -- sh -c '
  cat /path/outside/repo/keyring_pass | gnome-keyring-daemon --unlock --components=secrets >/dev/null 2>&1
  sleep 1
  python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
    --authorization-mode required --authority-provider os-keyring \
    ... (real worker + task flags per the stage7 README recipe, lines 40-70) ...
'
# 3. Strict audit of the produced tape (must PASS, no LEGACY_MISSING):
python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput --strict-terminal-market --require-authorization-head \
  ... (bundle path flags per the stage7 README, lines 100-110) ...
# 4. Evidence root README: REAL label, keyring provider recorded, verdict JSON attached.
#    Claim ceiling: ADDRESSED. A prior-failure reference: stage7 README lines 47-53.
```

**5.5 CostEvent.v2 payload shape (codec-legal: ASCII keys, integers only, no floats, no secrets):**
```json
{
  "schema_id": "turingos.cost_event.v2",
  "run_id": "…", "capsule_id": "…", "receipt_id": "rcpt:…",
  "worker": {
    "adapter_kind": "native_api",
    "provider": "anthropic",
    "model_id_requested": "claude-…",
    "model_id_resolved": "claude-…-2025….",
    "endpoint": "/v1/messages",
    "request_id": "req_…",
    "response_sha256": "sha256:…"
  },
  "usage": {
    "input_tokens": 1234, "output_tokens": 567,
    "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
    "provider_usage_raw_sha256": "sha256:…"
  },
  "cost": {
    "cost_source_kind": "provider_receipt_inline",
    "cost_microusd": 12345,
    "price_table_digest": "sha256:…",
    "bound_kind": null
  },
  "wall_time_ms": 45210
}
```
Auditor extension: `--require-cost-provenance` FAILs any REAL-run CostEvent with `cost_source_kind` absent or `unspecified`, any `bounded_estimate` without `bound_kind`, and any float anywhere (the codec already rejects that at append time). Extend `cost_conservation_status` (`audit_micro_tape_decision_dag.py:738`) to also conserve `cost_microusd` per run.

**5.6 runsc mutation-boundary gate (wrap every patch-apply/test-run step):**
```bash
# self-test at run start (record which_digest(runsc) + version into the run manifest)
runsc --rootless --network=none do /bin/true \
  && SANDBOX='{"kind":"runsc_rootless_do","network":"none"}' \
  || SANDBOX='{"kind":"HOST_ASSUMED"}'   # then append SandboxBoundaryAssumed BEFORE any mutation
# sandboxed step:
runsc --rootless --network=none do git -C "$WORKTREE" apply /tmp/candidate.patch
runsc --rootless --network=none do python -m pytest "$WORKTREE" -x -q
```

**5.7 Drift-check hook for every M1 atom (Project Intent §8):** each atom's ship gate re-runs: seal check not applicable here, but (i) all four §2.4 gates, (ii) `--self-test` on each, (iii) grep for forbidden claims (`CLOSED`, `RATIFIED`) in the atom's own outputs, (iv) confirmation that no file outside `PROJECT_PLAN_…` (for plan atoms) or outside the agreed implementation surface (for repo atoms) was touched.

---

## 6. ADR-ready decision records (MADR-style)

**ADR-M1-001 — Single canonical-bytes owner: `turing-contracts::jcs` with gate-enforced derived views.**
Context: the active repo holds ≥6 canonical-bytes implementations, three load-bearing (`codec.py`, `tape.py:310` node bytes, the Rust JCS), and a live silent divergence exists (`headless_common.py` ensure_ascii default); the omega track proved Rust-vs-Python byte equality 8/8 and shipped a self-testing second-owner gate. Decision: designate `crates/turing-contracts/src/jcs.rs` (profile `turingos.jcs.v1`, restricted: integers only, ASCII keys, no floats) the singleton owner; demote `src/turingos/codec.py` to a cross-checked derived view; explicitly allowlist the strict auditor's independent implementation as a cross-check, not an owner; adopt no external RFC 8785 library. Consequences: byte stability of all existing digests/event IDs is preserved (proven equality); a CI xcheck + grep + AST + ref-lint gate quartet makes recurrence mechanical to catch; the codec becomes a frozen port whose changes require constitutional-grade review; Python-only contexts pay a subprocess dependency once routing (ADR-M1-002) lands.

**ADR-M1-002 — Routing architecture: CLI subprocess now, daemon-owned appends as end-state; PyO3 rejected.**
Context: Python must consume the Rust owner; candidates were formal designation only, CLI subprocess, PyO3/FFI, and the existing turingd daemon; the repo already shells out to git per tape operation and already runs six daemons from the Python harness; no PyO3/maturin exists anywhere. Decision: phase 1 — a batch-capable `turing jcs` CLI verb becomes the byte producer behind `codec.canonical_bytes`; phase 2 — NEW tapes are appended only via turingd `event.append_preserve`/turing-git-tape (three-ref model, `event` blob), demoting the Python `Tape` to a labeled test fixture; PyO3 is rejected this increment (build complexity, blurred failure boundary, weaker binary attestation, no latency need). Consequences: one owner in fact for bytes AND refs on all new tapes; process-boundary failure isolation (nonzero exit → fail-closed reject); the producing binary's sha256 is recordable on tape; historical two-ref/node.json tapes remain readable by the independent auditor and are never rewritten.

**ADR-M1-003 — Real-run authorization via headless gnome-keyring session on omega-vm; file-backend only as a labeled fallback.**
Context: `authorization_head` has never passed `--require-authorization-head` outside fixtures because the only real run's host lacked a working secret-tool (stage7 evidence); the production signer is `OsKeyringSigningBackend`→secret-tool; research probes on omega-vm (2026-07-02) proved `dbus-run-session` + `gnome-keyring-daemon --unlock` + secret-tool store/lookup/clear works headlessly. Decision: close R9 on omega-vm by wrapping one real worker run in an unlocked-keyring session with `--authorization-mode required --authority-provider os-keyring`, then strict-auditing with `--require-authorization-head`; `LocalFileSigningBackend` remains a distinctly-labeled fallback route, never a silent substitute; approval keys are host-minted and are categorically not the genesis key (which never leaves the Mac). Consequences: the strongest strict gate gains its first non-fixture PASS on the exact production code path; keyring passphrase handling discipline (0600 file outside repo, timeouts, no tape leakage) becomes part of the runbook; implementer status ceiling ADDRESSED.

**ADR-M1-004 — Tape-canonical cost and worker identity: CostEvent.v2 with mandatory `cost_source_kind`, integer micro-USD, pinned price table, provider request IDs.**
Context: current cost records are word-count pseudo-estimates (`len(prompt.split())`) with `cost_source_kind: unspecified`; worker identity (model ID/version/receipt) is absent from tape, making the central uplift question unanswerable (audit F5/F7); per-call provider `usage` fields exist for OpenAI/xAI/Anthropic/DeepSeek while org-level Usage/Cost APIs are admin-key- and plan-gated; the codec rejects floats. Decision: capture Layer-1 inline usage + resolved model ID + request-ID header + response digest at the `WorkerAdapter` seam into a `CostEvent.v2` (integer micro-USD, `price_table_digest`, provider-specific usage verbatim including DeepSeek cache-hit/miss split); `cost_source_kind ∈ {provider_receipt_inline, provider_usage_api_reconciled, bounded_estimate, fixture}`; bounded estimates must declare a defensible upper-bound derivation; native-API adapters are required for all G4-measured arms; the strict auditor gains `--require-cost-provenance`. Consequences: H-VPPUT becomes measurable (or explicitly bounded) per run; worker attribution becomes machine-verifiable from tape; receipts stay supervisor-side (Goodhart shielding); the word-count estimator is abolished.

**ADR-M1-005 — Mutation-boundary enforcement: runsc rootless `do` gate with HOST_ASSUMED recorded on tape.**
Context: sandboxing is currently only an environment probe (`platform_not_run()` reports `runsc_missing`); constitution/intent §5.6 requires mutation paths under gVisor where available with exceptions recorded; a research probe proved `runsc --rootless --network=none do` works on omega-vm (release-20260608.0). Decision: every substrate-driven mutation step (patch apply, test run) executes under `runsc --rootless --network=none do`, with runsc version + binary sha256 in the run manifest and a `sandbox` block on each mutation event; if the run-start self-test fails, a `SandboxBoundaryAssumed` (HOST_ASSUMED) PRESERVE event must precede any mutation; the auditor gains `--require-sandbox-provenance`; the upstream SWE-bench Docker scorer's runtime is explicitly untouched; OCI-bundle-level pinning is deferred to the omega track (C18/E0), not duplicated. Consequences: §5.6 compliance becomes tape-reconstructible; the common path on omega is genuinely sandboxed with network denied; gVisor wall-clock overhead is visible per-event so experiments can hold sandbox kind constant.

**ADR-M1-006 — Recurrence-proof singleton gating: self-testing grep + AST + byte-equality + ref-lint quartet in CI.**
Context: the diagnosed meta-bug (second canonical owner) recurred despite prose discipline; the omega track's `gate_g10_provenance.sh` demonstrates the working pattern (fail-closed, `--self-test` clean/tamper discrimination, `--wide` audit mode, NOT_RUN blocks); grep alone is evadable by aliasing and AST alone misses non-Python surfaces. Decision: wire four jobs into the turing repo CI — (1) cross-impl byte-equality xcheck over an extended corpus (control chars, surrogate boundaries, non-ASCII values, U+2028/U+2029, integer extremes), (2) grep gate banning `sort_keys=True` canonicalization and canonical-def names outside an explicit reasoned allowlist, (3) stdlib-AST lint catching aliased `json.dumps(sort_keys=True)` calls, (4) ref-lint banning `update-ref refs/turingos/` outside the designated writer; every gate must pass its own tamper self-test or the pipeline rejects it as inert. Consequences: a reintroduced second owner fails CI within one commit; the deliberately independent auditor is protected by an explicit allowlist entry rather than deleted for gate-greenness; gate maintenance cost is a small allowlist review whenever a legitimate new consumer appears.

---

*End of report. This document is a planning/research artifact; it confers no CLOSED/RATIFIED status. The two EXECUTED environment probes (keyring round-trip, rootless runsc echo) were performed in a session-scoped scratchpad and left no state in any repo.*
