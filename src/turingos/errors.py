"""TuringOS error hierarchy (frozen Stage-0 interface).

Every kernel module imports its exceptions from here so error handling is uniform across the loop.
"""
from __future__ import annotations


class TuringOSError(Exception):
    """Base for all TuringOS kernel errors."""


class RejectedAppend(TuringOSError):
    """An append was rejected before any commit landed (closed-world / registry / consistency)."""


class GuardReject(RejectedAppend):
    """The single-writer authority guard rejected an append (wrong writer or non-FF parent)."""


class SchemaInvalid(TuringOSError):
    """A payload failed structural schema validation."""


class AsciiKeyViolation(TuringOSError):
    """A load-bearing key was not ASCII (turingos.jcs.v1 codec policy)."""


class FloatViolation(TuringOSError):
    """A load-bearing value was a float (forbidden: non-deterministic across platforms)."""


class PredicateFail(TuringOSError):
    """Raised when a deterministic Predicate gate fails in a context that must hard-stop."""
