#!/usr/bin/env python3
"""TC0 event-registry self-consistency lint.

This deliberately checks only registry-internal invariants. It does not bless
or modify event rows; TC0 uses the report to prove drift is detected rather
than silently corrected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HEAD_COUNT_KEYS = {
    "ADVANCE": "advance",
    "PRESERVE": "preserve",
}

CLASS_COUNT_KEYS = {
    "SOVEREIGN_ACCEPT": "sovereign_accept",
    "AUTHORIZATION": "authorization",
    "PROPOSAL": "proposal",
    "OBSERVATION": "observation",
    "RECEIPT": "receipt",
    "FAILURE": "failure",
    "ECONOMY": "economy",
}

NAME_DIGEST_PROFILE = "sorted_canonical_names_lf_trailing_lf"


def _sha256_names(names: list[str]) -> str:
    payload = "\n".join(sorted(names)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _check(name: str, ok: bool, message: str) -> dict[str, str]:
    return {"name": name, "status": "PASS" if ok else "FAIL", "message": message}


def lint_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    events = data.get("events", [])
    counts = data.get("counts", {})
    names = [event.get("canonical_name") for event in events]
    name_counter = Counter(names)
    duplicate_names = sorted(name for name, count in name_counter.items() if count > 1)
    head_counts = Counter(event.get("head_effect") for event in events)
    class_counts = Counter(event.get("event_class") for event in events)
    actual_name_digest = _sha256_names([name for name in names if isinstance(name, str)])
    expected_name_digest = data.get("registry_name_set_sha256")
    profile = data.get("registry_name_set_sha256_profile")

    checks: list[dict[str, str]] = []
    checks.append(
        _check(
            "canonical_name.unique",
            not duplicate_names and all(isinstance(name, str) and name for name in names),
            f"duplicates={duplicate_names!r}; blank_or_nonstring={len(names) - len([n for n in names if isinstance(n, str) and n])}",
        )
    )
    checks.append(
        _check(
            "counts.total",
            counts.get("total") == len(events),
            f"declared={counts.get('total')}; observed={len(events)}",
        )
    )
    for head_effect, key in HEAD_COUNT_KEYS.items():
        checks.append(
            _check(
                f"counts.{key}",
                counts.get(key) == head_counts.get(head_effect, 0),
                f"declared={counts.get(key)}; observed={head_counts.get(head_effect, 0)}",
            )
        )
    for event_class, key in CLASS_COUNT_KEYS.items():
        checks.append(
            _check(
                f"counts.{key}",
                counts.get(key) == class_counts.get(event_class, 0),
                f"declared={counts.get(key)}; observed={class_counts.get(event_class, 0)}",
            )
        )
    checks.append(
        _check(
            "unknown_event_policy",
            data.get("unknown_event_policy") == "REJECT",
            f"declared={data.get('unknown_event_policy')!r}",
        )
    )
    checks.append(
        _check(
            "append_only_by_name",
            data.get("append_only_by_name") is True,
            f"declared={data.get('append_only_by_name')!r}",
        )
    )
    checks.append(
        _check(
            "never_renumber",
            data.get("never_renumber") is True,
            f"declared={data.get('never_renumber')!r}",
        )
    )
    checks.append(
        _check(
            "registry_name_set_sha256_profile",
            profile == NAME_DIGEST_PROFILE,
            f"declared={profile!r}; expected={NAME_DIGEST_PROFILE!r}",
        )
    )
    checks.append(
        _check(
            "registry_name_set_sha256",
            expected_name_digest == actual_name_digest,
            f"declared={expected_name_digest}; observed={actual_name_digest}",
        )
    )

    verdict = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": "turingos.tc0.event_registry_self_consistency_report.v1",
        "timestamp_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "registry_path": str(path.resolve()),
        "verdict": verdict,
        "observed": {
            "counts": counts,
            "event_count": len(events),
            "unique_canonical_name_count": len(set(names)),
            "head_effect_counts": dict(sorted(head_counts.items())),
            "event_class_counts": dict(sorted(class_counts.items())),
            "registry_name_set_sha256_profile": profile,
            "registry_name_set_sha256": actual_name_digest,
        },
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    report = lint_registry(args.registry)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
