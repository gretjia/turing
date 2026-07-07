"""Red-first pytest mirror for HW-SW-001 (Art. 0.2 traceability audit).

Independently parses the docs/roadmap/secure_os_18_month/02_software_sufficiency_proof.md
Section 1.3 markdown table (no shelling out to audit-art-0-2-traceability.sh for the row
checks — no self-reference / no Goodhart loop), asserts the frozen 10-row / V-code
contract straight from the constitution's Art. 0.2 repair list, and separately asserts
that the shipped shell audit (./scripts/audit-art-0-2-traceability.sh) exits 0.

Negative vectors tamper a copy of the real table (row deleted / V-code mutated) in
tmp_path and assert the independent parser/validator rejects it.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORK_ROOT = Path(os.environ.get("TURINGOS_WORK_ROOT", "/home/zephryj/turingos_backup/work"))
MATRIX_DOC = WORK_ROOT / "docs" / "roadmap" / "secure_os_18_month" / "02_software_sufficiency_proof.md"
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit-art-0-2-traceability.sh"

# Frozen contract: constitution's Art. 0.2 repair list, Commit -> V-code set (order matters,
# the table cell is a literal comma-joined list, not a set).
EXPECTED_VCODES: dict[int, list[str]] = {
    1: ["V-01", "V-06", "V-18"],
    2: ["V-02", "V-03", "V-22"],
    3: ["V-04", "V-05", "V-15", "V-16"],
    4: ["V-03", "V-09", "V-13"],
    5: ["V-08a", "V-17"],
    6: ["V-07"],
    7: ["V-08b", "V-22"],
    8: ["V-10", "V-11", "V-14"],
    9: ["V-19", "V-21"],
    10: ["V-18", "V-24"],
}


def parse_table(text: str) -> list[tuple[int, list[str]]]:
    """Independently parse the §1.3 markdown table into (commit, [v-codes]) rows.

    Locates the header row (contains both "Commit" and "Constitutional violation
    closed"), skips the markdown separator row directly below it, then reads data
    rows until the first line that is not a table row. This is a from-scratch
    parser: it does not call the shell script and does not assume the table is
    well-formed — malformed input simply yields whatever rows it can extract, and
    validate_table() below is what rejects bad content.
    """
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "Commit" in line and "Constitutional violation closed" in line:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("§1.3 table header not found (missing 'Commit' / "
                          "'Constitutional violation closed' columns)")

    rows: list[tuple[int, list[str]]] = []
    i = header_idx + 2  # header_idx+1 is the "|---|---|...|" separator row
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            i += 1
            continue
        commit_match = re.match(r"^(\d+)$", cells[0])
        if not commit_match:
            i += 1
            continue
        commit_num = int(commit_match.group(1))
        vcodes = [v.strip() for v in cells[1].split(",") if v.strip()]
        rows.append((commit_num, vcodes))
        i += 1
    return rows


def validate_table(rows: list[tuple[int, list[str]]]) -> dict[int, list[str]]:
    """Enforce the A1(a)/(b) contract: exactly 10 rows, commits 1..10 each present
    exactly once, and each row's V-code list matches EXPECTED_VCODES exactly.
    Raises ValueError on any violation (used by the negative vectors below).
    """
    commits = [c for c, _ in rows]
    if sorted(commits) != list(range(1, 11)):
        raise ValueError(
            f"expected commits 1..10 present exactly once each, got {sorted(commits)}"
        )
    for commit, vcodes in rows:
        expected = EXPECTED_VCODES[commit]
        if vcodes != expected:
            raise ValueError(
                f"commit {commit}: expected V-codes {expected}, got {vcodes}"
            )
    return dict(rows)


@pytest.fixture(scope="module")
def matrix_text() -> str:
    assert MATRIX_DOC.exists(), f"matrix doc not found at {MATRIX_DOC}"
    return MATRIX_DOC.read_text()


def test_matrix_doc_exists():
    assert MATRIX_DOC.exists(), f"matrix doc not found at {MATRIX_DOC}"


def test_table_has_exactly_10_rows_commit_1_to_10(matrix_text):
    rows = parse_table(matrix_text)
    commits = sorted(c for c, _ in rows)
    assert commits == list(range(1, 11)), f"expected commit 1..10 exactly once, got {commits}"


def test_real_table_passes_validation(matrix_text):
    rows = parse_table(matrix_text)
    validated = validate_table(rows)
    assert validated == EXPECTED_VCODES


@pytest.mark.parametrize("commit,expected_vcodes", sorted(EXPECTED_VCODES.items()))
def test_row_vcodes_match_constitutional_contract(matrix_text, commit, expected_vcodes):
    rows = dict(parse_table(matrix_text))
    assert commit in rows, f"commit {commit} missing from §1.3 table"
    assert rows[commit] == expected_vcodes


def test_tampered_copy_row_deleted_is_rejected(tmp_path, matrix_text):
    """Delete the data row for commit 5 and confirm the independent parser/validator
    rejects the tampered copy (row count / commit-set violation)."""
    lines = matrix_text.splitlines()
    filtered = [line for line in lines if not re.match(r"^\|\s*5\s*\|", line.strip())]
    assert len(filtered) < len(lines), "sanity check: row deletion did not remove a line"
    tampered_path = tmp_path / "tampered_row_deleted.md"
    tampered_path.write_text("\n".join(filtered))

    rows = parse_table(tampered_path.read_text())
    with pytest.raises(ValueError):
        validate_table(rows)


def test_tampered_copy_vcode_mutated_is_rejected(tmp_path, matrix_text):
    """Mutate commit 1's V-code cell (V-01 -> V-99) and confirm the independent
    parser/validator rejects the tampered copy (V-code contract violation)."""
    tampered_text = matrix_text.replace("V-01, V-06, V-18", "V-99, V-06, V-18")
    assert tampered_text != matrix_text, "sanity check: V-code mutation did not apply"
    tampered_path = tmp_path / "tampered_vcode.md"
    tampered_path.write_text(tampered_text)

    rows = parse_table(tampered_path.read_text())
    with pytest.raises(ValueError):
        validate_table(rows)


def test_audit_script_exits_zero():
    assert AUDIT_SCRIPT.exists(), f"audit script not found at {AUDIT_SCRIPT}"
    result = subprocess.run(
        [str(AUDIT_SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"audit-art-0-2-traceability.sh exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
