"""turingos.planner — progressive Module -> Atom expansion (M-loop layer).

Frozen seam (contracts/INTERFACES.md planner.py section):

    def expand_atoms(tape: "Tape", module_id: str) -> list[dict]
        # progressive; emits AtomProposed (active module only)

PROGRESSIVE elaboration [Art. III progressive disclosure / CLAUDE.md "never all atoms up
front"]: this expands ONLY the ONE active/named module into a small handful of atoms — it
does NOT enumerate the whole project. Each atom is recorded on the Micro Tape as an
`AtomProposed` event, which the 18-event registry classes as a PROPOSAL (head_effect
PRESERVE): so `tape_tip` advances once per atom and `accepted_head` NEVER moves. Acceptance
is a later, predicate-gated SOVEREIGN_ACCEPT — proposing an atom is not accepting it.

Each atom dict carries exactly the loop contract fields:

    {atom_id, module_id, intent, allowed_files: [...], acceptance_commands: [...]}

  * atom_id            — deterministic, content-addressed from (module_id, ordinal, intent)
                         so the same module yields the same plan on any fresh tape (replay
                         equality precondition; no host/time leakage).
  * module_id          — every atom is scoped to the REQUESTED module; expanding M1 never
                         emits an atom for any other module.
  * intent             — a short human-readable description of the unit of work.
  * allowed_files      — the scope fence the predicate's SCOPE check (P3) binds the worker to.
  * acceptance_commands — the frozen, declared tests the predicate's TESTS_DECLARED/PASS
                         checks run; frozen at proposal time (predicate-first discipline).

Determinism: the expansion is a pure function of `module_id` (no clock, no RNG, no host
state), so two replays of the same module produce byte-identical atom payloads. The Tape's
own append path enforces the single-writer FF guard, the registry-derived head_effect, and
the JCS/ASCII/no-float codec guard on each payload.

Stdlib only.
"""
from __future__ import annotations

from . import codec

# Registry event name this module emits — PROPOSAL / PRESERVE (registry #5).
_ATOM_PROPOSED = "AtomProposed"

# Progressive disclosure: a SMALL bounded fan-out per module, never the whole project.
# Three atoms per module is the 1.0 loop's canonical "implement -> verify -> ship-gate"
# triad — enough to drive both predicate branches without an unbounded up-front dump.
_ATOMS_PER_MODULE = 3

# The canonical per-module atom triad. Kept as a pure data template (no host/time leakage)
# so the plan is deterministic and content-addressable. {module} is filled per module_id.
_ATOM_TEMPLATES = (
    {
        "slug": "implement",
        "intent": "Implement {module} per its frozen contract (predicate-first, allowed_files only).",
        "allowed_files": ["src/turingos/{module_lower}.py"],
        "acceptance_commands": [
            "python3 -m unittest tests.test_{module_lower} -v",
        ],
    },
    {
        "slug": "test",
        "intent": "Write the stdlib unittest contract tests for {module} capturing its acceptance commands.",
        "allowed_files": ["tests/test_{module_lower}.py"],
        "acceptance_commands": [
            "python3 -m unittest tests.test_{module_lower} -v",
        ],
    },
    {
        "slug": "shipgate",
        "intent": "Ship-gate audit {module}: run acceptance commands + IPQC + constitution-slice checks.",
        "allowed_files": ["src/turingos/{module_lower}.py", "tests/test_{module_lower}.py"],
        "acceptance_commands": [
            "python3 -m unittest tests.test_{module_lower} -v",
        ],
    },
)


def _module_lower(module_id: str) -> str:
    """A filesystem-safe lowercase slug for a module id (e.g. 'M1' -> 'm1')."""
    return module_id.strip().lower()


def _build_atom(module_id: str, ordinal: int, template: dict) -> dict:
    """Build one deterministic atom dict for `module_id` from a template (no side effects)."""
    fields = {"module": module_id, "module_lower": _module_lower(module_id)}
    intent = template["intent"].format(**fields)
    allowed_files = [p.format(**fields) for p in template["allowed_files"]]
    acceptance_commands = [c.format(**fields) for c in template["acceptance_commands"]]

    # Content-addressed, deterministic atom_id: scoped under the module + the atom's stable
    # identity (ordinal + slug + intent). No clock / RNG / host state, so replays are equal.
    identity = {
        "module_id": module_id,
        "ordinal": ordinal,
        "slug": template["slug"],
        "intent": intent,
    }
    digest = codec.content_digest(identity)  # "sha256:" + 64 hex
    atom_id = "atom:" + module_id + ":" + digest.split(":", 1)[1][:16]

    return {
        "atom_id": atom_id,
        "module_id": module_id,
        "intent": intent,
        "allowed_files": allowed_files,
        "acceptance_commands": acceptance_commands,
    }


def expand_atoms(tape: "Tape", module_id: str) -> list[dict]:
    """Progressively expand ONE module into a small list of atoms; emit each as AtomProposed.

    Expands ONLY `module_id` (active-module-only, Art. III progressive disclosure) into a
    bounded handful of atoms. Each atom is appended to the Tape as an `AtomProposed` event
    (PROPOSAL / PRESERVE): `tape_tip` advances once per atom, `accepted_head` is never
    touched. The atom dicts are returned in proposal order.

    Deterministic: a pure function of `module_id` (no clock/RNG), so the same module yields
    the same atom_ids and payloads on any fresh tape (replay-equality precondition). The
    Tape's append path enforces the single-writer FF guard, the registry-derived head_effect,
    and the JCS/ASCII/no-float codec guard on each payload.
    """
    if not isinstance(module_id, str) or not module_id:
        raise ValueError("expand_atoms requires a non-empty string module_id")

    atoms: list[dict] = []
    for ordinal, template in enumerate(_ATOM_TEMPLATES[:_ATOMS_PER_MODULE]):
        atom = _build_atom(module_id, ordinal, template)
        # PROPOSAL append: registry-derived head_effect is PRESERVE, so tape_tip advances and
        # accepted_head does NOT. No predicate_pass is required for a PRESERVE event.
        tape.append(_ATOM_PROPOSED, atom)
        atoms.append(atom)
    return atoms
