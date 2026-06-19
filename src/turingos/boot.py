"""turingos.boot — Boot/Adopt + Goal/Module sovereign accepts (LOOP layer).

Frozen Stage-0 interface (contracts/INTERFACES.md boot.py section):

    def boot(tape, project_spec) -> dict          # SystemBootstrapped, ProjectAdopted
    def accept_goalstate(tape, goalstate) -> str   # GoalStateAccepted (predicate-gated)
    def accept_module_plan(tape, module_plan) -> str # ModulePlanAccepted (predicate-gated)

These four event types are all SOVEREIGN_ACCEPT in the 18-event registry
(contracts/event_registry.md): SystemBootstrapped, ProjectAdopted, GoalStateAccepted,
ModulePlanAccepted. By the registry, a SOVEREIGN_ACCEPT is an ADVANCE event and the Tape
guard requires predicate_pass=True for any ADVANCE (else RejectedAppend) — a FAILED accept
is emitted as a FailureNode (OBSERVATION), never as a non-advancing SOVEREIGN_ACCEPT
[Art. 0.4 / tape.py append invariant]. So every append here carries predicate_pass=True and,
on success, advances accepted_head (and tape_tip) together.

The Project Spec is the Boot INPUT [Art. IV]: boot() ingests it, emits SystemBootstrapped
(which establishes the single active sovereign writer) followed by ProjectAdopted (which
records the adopted Project Spec). The SystemBootstrapped payload MUST carry writer_id so the
Tape's single-writer guard is established from the genesis commit onward.

Tape-canonical [Art. 0.2]: no state is persisted here beyond the Tape commits — everything
boot writes is replayable/foldable from the Micro Tape alone (reduce_qt picks up the accepted
goal and module from these events).

Stdlib only. This is a thin sovereign-accept driver over the FROZEN Tape.append seam; it adds
no third-party deps and changes no frozen signature.
"""
from __future__ import annotations

from .errors import SchemaInvalid

# Event-type axis (registry names; see contracts/event_registry.md / event_registry.json).
_SYSTEM_BOOTSTRAPPED = "SystemBootstrapped"
_PROJECT_ADOPTED = "ProjectAdopted"
_GOAL_STATE_ACCEPTED = "GoalStateAccepted"
_MODULE_PLAN_ACCEPTED = "ModulePlanAccepted"


def _require_dict(value: object, where: str) -> dict:
    """Structural floor: the input must be a JSON object (dict). Raises SchemaInvalid."""
    if not isinstance(value, dict):
        raise SchemaInvalid(f"{where}: expected object, got {type(value).__name__}")
    return value


def boot(tape, project_spec: dict) -> dict:
    """Bootstrap the system and adopt the Project Spec.

    Emits two SOVEREIGN_ACCEPT events as exactly two Micro commits:

      1. SystemBootstrapped — establishes the single active sovereign writer. Its payload
         carries writer_id (the tape's sovereign writer), which the Tape single-writer guard
         reads from the envelope; carrying it in the payload too keeps it on the Tape for any
         later fold/audit. This is the genesis commit (parent is None), so it is the special
         genesis-boot that the guard admits without a prior current_writer.
      2. ProjectAdopted — records the adopted Project Spec [Art. IV: Spec is the Boot INPUT].

    Both are ADVANCE events with predicate_pass=True, so accepted_head advances to ProjectAdopted
    and ends equal to tape_tip after a clean boot.

    Returns {"bootstrapped": <event_id>, "adopted": <event_id>}.
    """
    _require_dict(project_spec, "project_spec")

    # The sovereign writer for this tape. boot establishes it; the SystemBootstrapped envelope
    # writer_id (what the guard reads) is the tape's writer_id, so the payload mirrors that to
    # keep the single value on the Tape.
    writer_id = tape.writer_id

    bootstrap_payload = {
        "writer_id": writer_id,
        "project_spec": project_spec,
    }
    bootstrapped = tape.append(
        _SYSTEM_BOOTSTRAPPED,
        bootstrap_payload,
        predicate_pass=True,
    )

    adopted = tape.append(
        _PROJECT_ADOPTED,
        {"project_spec": project_spec},
        predicate_pass=True,
    )

    return {"bootstrapped": bootstrapped, "adopted": adopted}


def accept_goalstate(tape, goalstate: dict) -> str:
    """Accept a GoalState as a SOVEREIGN_ACCEPT (predicate-gated ADVANCE).

    Structurally validates the goalstate (must be an object with a 'goal'), then appends a
    GoalStateAccepted event with predicate_pass=True so accepted_head advances. A goalstate
    that fails structural validation raises SchemaInvalid BEFORE any append, so no ref moves
    (a failed accept would be a FailureNode in the full loop, never a non-advancing accept).

    reduce_qt(tape)['active_goal'] folds to this payload afterward.

    Returns the GoalStateAccepted event_id ("mu:"+oid).
    """
    _require_dict(goalstate, "goalstate")
    if "goal" not in goalstate:
        raise SchemaInvalid("goalstate: missing required field 'goal'")

    return tape.append(
        _GOAL_STATE_ACCEPTED,
        goalstate,
        predicate_pass=True,
    )


def accept_module_plan(tape, module_plan: dict) -> str:
    """Accept a ModulePlan as a SOVEREIGN_ACCEPT (predicate-gated ADVANCE).

    Structurally validates the module_plan (must be an object), then appends a
    ModulePlanAccepted event with predicate_pass=True so accepted_head advances.
    reduce_qt(tape)['active_module'] folds to this payload afterward.

    Returns the ModulePlanAccepted event_id ("mu:"+oid).
    """
    _require_dict(module_plan, "module_plan")

    return tape.append(
        _MODULE_PLAN_ACCEPTED,
        module_plan,
        predicate_pass=True,
    )
