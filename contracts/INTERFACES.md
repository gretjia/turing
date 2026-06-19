# Contract: Frozen Build Interfaces (the build-wide glossary / CONTEXT)

**Status:** frozen Stage-0 baseline. This is the single source of truth for module API signatures so
parallel atom-builders implement against a stable seam (eval evidence: "glossary beats swarm merge").
Package root: `src/turingos/`. Python ≥ 3.9. **No third-party runtime deps** for the kernel (stdlib only:
`hashlib`, `json`, `subprocess`, `pathlib`, `dataclasses`). Textual TUI (panorama) is the one optional dep.

> Where a later module needs a richer signature, it is an **additive** change to this file via a project ADR,
> never a silent divergence. Implementers MUST NOT change a frozen signature unilaterally.

## Package layout
```
src/turingos/
  __init__.py        # version
  errors.py          # TuringOSError, RejectedAppend, PredicateFail, GuardReject, SchemaInvalid
  codec.py           # turingos.jcs.v1
  registry.py        # 18-event registry loader + class/head_effect lookup
  envelope.py        # AppendEnvelope dataclass + local guard checks
  tape.py            # Tape: sha256 Micro repo, 2 refs, append, single-writer guard, handoff
  schemas.py         # JSON-schema validation for capsule/receipt/event payloads
  predicate.py       # deterministic predicate kernel (9 checks)
  evidence.py        # receipt import + macro-anchor binding
  replay.py          # deterministic replay + q_t reconstruction + handoff bundle
  reduce.py          # tape -> q_t ; derive WorkGraph projection
  boot.py            # boot/adopt -> SystemBootstrapped/ProjectAdopted/GoalStateAccepted/ModulePlanAccepted
  planner.py         # progressive Module->Atom expansion -> AtomProposed
  capsule.py         # build Shielded Work Capsule + FailureMemory shield
  signing.py         # SigningBackend ABC + InProcSigningBackend + ApprovalCard
  worker/
    __init__.py
    adapter.py       # WorkerAdapter ABC + dispatch/timeout/kill/retry (PG reap)
    fake.py          # FakeWorker deterministic stub (Stage 1)
  panorama.py        # Textual TUI over the derived WorkGraph (Authorized-vs-Accepted labels)
  loop.py            # Stage-1 E2E loop driver
  cli.py             # `turingos` CLI entrypoint
```

## codec.py  (turingos.jcs.v1)
```python
def canonical_bytes(payload: dict) -> bytes
    # RFC 8785 JCS of payload; raises AsciiKeyViolation on non-ASCII load-bearing key; FloatViolation on any float.
def content_digest(payload: dict) -> str        # "sha256:" + hex(sha256(canonical_bytes(payload)))
def assert_ascii_keys(payload: dict) -> None     # recursive; raises on non-ASCII key
def assert_no_floats(payload: dict) -> None      # recursive; raises on any float value
def event_id_from_oid(oid: str) -> str           # "mu:" + oid ; validates ^mu:[0-9a-f]{64}$
EVENT_ID_RE = r"^mu:[0-9a-f]{64}$"
```

## registry.py
```python
REGISTRY_PATH = "contracts/event_registry.json"
def load_registry(path: str = REGISTRY_PATH) -> dict
def event_names() -> frozenset[str]
def event_class(event_type: str) -> str          # SOVEREIGN_ACCEPT | PROPOSAL | OBSERVATION ; KeyError->RejectedAppend
def head_effect(event_type: str) -> str          # "ADVANCE" | "PRESERVE"  (registry-derived, never writer-trusted)
def is_predicate_gated(event_type: str) -> bool
def is_known(event_type: str) -> bool            # closed-world: unknown => False
```

## envelope.py
```python
@dataclass(frozen=True)
class AppendEnvelope:
    prev_tape_tip: str          # load-bearing (FF parent)
    event_schema_id: str        # load-bearing (event type / payload schema id)
    payload_hash: str           # load-bearing (= content_digest(payload))
    head_effect: str            # load-bearing, registry-derived
    accepted_head_before: str   # load-bearing
    writer_id: str              # RESERVED-fixed (single writer)
    authority_epoch: int = 0    # RESERVED-deferred (not enforced in 1.0)
    def to_payload(self) -> dict
def derive_head_effect(event_type: str) -> str   # delegates to registry.head_effect
```

## tape.py
```python
class Tape:
    def __init__(self, repo_dir: str, writer_id: str): ...
    @classmethod
    def init(cls, repo_dir: str, writer_id: str) -> "Tape"     # git init --object-format=sha256 + refs + FF config
    def object_format(self) -> str                              # expect "sha256"
    def tape_tip(self) -> str | None
    def accepted_head(self) -> str | None
    def current_writer(self) -> str                             # from latest boot/HandoffGenerated event
    def append(self, event_type: str, payload: dict, *, writer_id: str | None = None,
               predicate_pass: bool | None = None) -> str
        # builds envelope (registry-derived head_effect), runs local guard (FF, schema-known,
        # head_effect, payload_hash, single-writer identity, accepted_head ancestor),
        # writes ONE commit, advances tape_tip; advances accepted_head iff head_effect==ADVANCE AND predicate_pass.
        # INVARIANT (tape-canonical replay): for an ADVANCE (SOVEREIGN_ACCEPT) event, predicate_pass MUST be
        #   True, else raise RejectedAppend — a FAILED accept is emitted as a FailureNode (OBSERVATION), never
        #   as a non-advancing SOVEREIGN_ACCEPT. Thus "SOVEREIGN_ACCEPT on the tape <=> accepted_head advanced",
        #   so replay rebuilds accepted_head = last SOVEREIGN_ACCEPT commit, Tape-only, with no predicate_pass flag stored.
        # returns event_id ("mu:"+oid). Raises GuardReject on any guard failure (no commit).
    def read_event(self, event_id: str) -> dict                 # {event_type, payload, envelope, parents, oid}
    def walk(self) -> list[dict]                                # genesis..tape_tip in order
    def handoff(self, to_writer: str) -> str                    # emits HandoffGenerated; changes current_writer
```
**Guard contract (S-2):** only `current_writer`'s FF append admits; wrong-writer / non-FF rejected by the
guard (raises GuardReject), not by convention. `handoff` is a Tape event that changes who the guard admits.

## schemas.py
```python
def validate_capsule(capsule: dict) -> None      # raises SchemaInvalid
def validate_receipt(receipt: dict) -> None
def validate_event_payload(event_type: str, payload: dict) -> None
```

## predicate.py
```python
@dataclass(frozen=True)
class PredicateResult:
    passed: bool
    reasons: tuple[dict, ...]     # each {check, ok, reason_code|None, detail}
    reason_digest: str            # sha256:hex(JCS(sorted reason records)) — deterministic
def evaluate(*, capsule: dict, receipt: dict, worktree: str, tape: "Tape",
             event_type: str) -> PredicateResult
    # runs P1..P9 + codec guard; deterministic; same inputs => same (passed, reason_digest).
CHECK_CODES = ("schema_invalid","parent_mismatch","scope_violation","isolation_violation",
               "receipt_hash_mismatch","test_fail","anchor_mismatch","replay_mismatch",
               "advance_rule_violation","ascii_key_violation","float_violation")
```

## evidence.py
```python
def import_receipt(tape: "Tape", receipt: dict) -> str        # emits WorkerReceiptImported, returns event_id
def import_macro_observation(tape: "Tape", obs: dict) -> str  # emits MacroObservationImported (tree OID anchor)
```

## replay.py
```python
@dataclass(frozen=True)
class ReplayState:
    accepted_head: str | None
    q_t: dict
    workgraph: dict
def replay(tape: "Tape") -> ReplayState
    # walks Tape ONLY (no sqlite/projection); recompute every content_digest; re-derive head_effect;
    # rebuild accepted_head; assert == on-disk accepted_head. Byte-deterministic.
def make_handoff_bundle(tape: "Tape", out_dir: str) -> str    # emits HandoffGenerated; writes bundle
def replay_from_handoff(bundle_dir: str) -> ReplayState
def verify_replay_equal(tape: "Tape") -> bool                  # two replays byte-identical; emits ReplayVerified
```

## reduce.py
```python
def reduce_qt(tape: "Tape") -> dict
    # q_t = {active_goal, active_module, active_atom, current_policy, pending_decision, retry_state}
def derive_workgraph(q_t: dict, tape: "Tape", macro_obs: list[dict]) -> dict
    # WorkGraph = derive(q_t, tape_t, declared Macro observations). DERIVED PROJECTION ONLY — never written back.
```

## boot.py / planner.py / capsule.py
```python
# boot.py
def boot(tape: "Tape", project_spec: dict) -> dict            # SystemBootstrapped, ProjectAdopted
def accept_goalstate(tape: "Tape", goalstate: dict) -> str    # GoalStateAccepted (predicate-gated)
def accept_module_plan(tape: "Tape", module_plan: dict) -> str# ModulePlanAccepted (predicate-gated)
# planner.py
def expand_atoms(tape: "Tape", module_id: str) -> list[dict]  # progressive; emits AtomProposed (active module only)
# capsule.py
def build_capsule(tape: "Tape", atom: dict, *, failure_memory: "FailureMemory") -> dict  # emits WorkCapsuleBuilt
class FailureMemory:
    def classify(self, failure_node: dict) -> dict            # raw FailureNode -> {failure_class, rule}
    def relevant_rules(self, atom: dict) -> list[dict]        # ONLY rules whose class is relevant to atom
```

## explore.py  (Exploration + Human Steer)
```python
def register_exploration(tape: "Tape", exploration: dict) -> str   # PRESERVE record of an explored branch
def archive_exploration(tape: "Tape", exploration_id: str, *, predicate_pass: bool) -> str  # ExplorationArchived (SOVEREIGN_ACCEPT)
def promote_exploration(tape: "Tape", exploration_id: str, *, predicate_pass: bool) -> str   # ExplorationPromoted (SOVEREIGN_ACCEPT)
def inject_human_steer(tape: "Tape", message: dict) -> str          # HumanSteerInjected (PROPOSAL, typed Tape event)
```

## loop.py  (Stage-1 E2E driver)
```python
def run_loop(spec: dict, tape_dir: str, *, worker=None, max_atoms: int = 3) -> dict
    # Drives the full loop with a (fake) Worker: boot -> goalstate -> module plan -> for each atom:
    #   expand -> build shielded capsule (inject only relevant FailureClass rule) -> dispatch worker to an
    #   isolated worktree -> import receipt -> predicate.evaluate -> {FAIL: FailureNode + classify ; PASS:
    #   CandidateAccepted (advance)} -> reduce/panorama. Then HandoffGenerated. MUST traverse BOTH predicate
    #   branches (>=1 FailureNode AND >=1 CandidateAccepted). Returns a summary dict:
    #   {accepted: int, failed: int, accepted_head, tape_tip, branches_covered: bool, handoff_bundle}.
    # Worker defaults to FakeWorker; pass a scenario list so the run produces both a fail and an accept.
```
```python
class SigningBackend(abc.ABC):
    @abc.abstractmethod
    def sign(self, canonical_bytes: bytes) -> str: ...
    @abc.abstractmethod
    def verify(self, canonical_bytes: bytes, signature: str) -> bool: ...
    @abc.abstractmethod
    def key_id(self) -> str: ...
class InProcSigningBackend(SigningBackend): ...               # deterministic HMAC-style signer for 1.0 local E2E
def build_approval_card(fields: dict, backend: SigningBackend) -> dict
    # -> {canonical_bytes(hex), visible_card_hash, signature, key_id, display(excluded from bytes)}
def verify_approval_card(card: dict, backend: SigningBackend) -> bool   # re-derive hash + verify signature
```

## worker/adapter.py + worker/fake.py
```python
class WorkerAdapter(abc.ABC):
    worker_id: str
    @abc.abstractmethod
    def run(self, capsule: dict, worktree: str) -> dict: ...  # returns a receipt dict (turingos.receipt.v1)
def dispatch(adapter: WorkerAdapter, capsule: dict, worktree: str, *, timeout_s: int) -> dict
    # timeout/kill/retry; on timeout TERM->KILL reaps whole process group (no orphan); normalizes failure.
class FakeWorker(WorkerAdapter):                              # deterministic stub for Stage 1
    def __init__(self, scenario: str = "pass"): ...           # scenario in {"pass","fail_scope","fail_test",...}
```

## cli.py  (entrypoints — used by E2E + spikes)
```
turingos tape-init <dir>
turingos append <dir> <event_type> <payload.json>
turingos predicate evaluate --capsule <c> --receipt <r> --worktree <w> --tape <dir>
turingos replay --tape <dir> --out <dir>
turingos handoff generate --tape <dir> --out <dir>
turingos panorama --tape <dir>
turingos loop --spec <spec.json> --tape <dir>     # Stage-1 E2E driver
```
