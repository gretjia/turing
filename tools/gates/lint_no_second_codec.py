#!/usr/bin/env python3
"""AST lint for M1a: no second canonical JSON codec in production paths."""
from __future__ import annotations

import argparse
import ast
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]

ALLOWLIST = {
    "src/turingos/codec.py": "Rust owner client plus labeled Python xcheck fixture",
    "src/turingos/tape.py": "legacy Python Tape path, demoted in M1e",
    "src/turingos/replay.py": "replay manifest digest helper, not substrate owner",
    "tools/bench/audit_micro_tape_decision_dag.py": "independent auditor by design",
    "tools/bench/audit_mini_swe_bench_plan.py": "legacy plan digest helper",
    "tools/bench/mini_swe_bench_grok_headless.py": "legacy seed digest helper",
    "tools/bench/prepare_stage12_run_plan.py": "JSONL fixture materializer",
    "tools/bench/run_mini_swe_bench_substrate_smoke.py": "legacy smoke harness shim",
    "tools/headless/fixture_probe.py": "headless fixture digest helper",
    "tools/headless/grok_verify.py": "verifier packet digest helper",
    "tools/headless/headless_common.py": "shared verifier packet digest helper",
}

SCAN_ROOTS = ("src", "tools/bench", "tools/headless")
CANONICAL_DEF_NAMES = {"canonical_bytes", "canonical_dumps", "canonical_json_bytes"}


class CodecVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self.json_aliases = {"json"}
        self.dumps_aliases: set[str] = set()
        self.findings: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "json":
                self.json_aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "json":
            for alias in node.names:
                if alias.name == "dumps":
                    self.dumps_aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name in CANONICAL_DEF_NAMES:
            self.findings.append(f"{self.rel_path}:{node.lineno}: canonical function definition {node.name!r}")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name in CANONICAL_DEF_NAMES:
            self.findings.append(f"{self.rel_path}:{node.lineno}: canonical function definition {node.name!r}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_json_dumps(node) and self._has_sort_keys_true(node) and self._has_minimal_separators(node):
            self.findings.append(
                f"{self.rel_path}:{node.lineno}: json.dumps(sort_keys=True, separators=(\",\", \":\"))"
            )
        self.generic_visit(node)

    def _is_json_dumps(self, node: ast.Call) -> bool:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "dumps":
            return isinstance(func.value, ast.Name) and func.value.id in self.json_aliases
        return isinstance(func, ast.Name) and func.id in self.dumps_aliases

    @staticmethod
    def _has_sort_keys_true(node: ast.Call) -> bool:
        for keyword in node.keywords:
            if keyword.arg == "sort_keys" and isinstance(keyword.value, ast.Constant):
                return keyword.value.value is True
        return False

    @staticmethod
    def _has_minimal_separators(node: ast.Call) -> bool:
        for keyword in node.keywords:
            if keyword.arg != "separators":
                continue
            value = keyword.value
            if not isinstance(value, (ast.Tuple, ast.List)) or len(value.elts) != 2:
                return False
            first, second = value.elts
            return (
                isinstance(first, ast.Constant)
                and first.value == ","
                and isinstance(second, ast.Constant)
                and second.value == ":"
            )
        return False


def iter_python_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for scan_root in SCAN_ROOTS:
        base = root / scan_root
        if base.exists():
            out.extend(sorted(base.rglob("*.py")))
    return out


def lint(root: Path) -> list[str]:
    findings: list[str] = []
    for path in iter_python_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except SyntaxError as exc:
            findings.append(f"{rel}:{exc.lineno or 0}: syntax error: {exc.msg}")
            continue
        visitor = CodecVisitor(rel)
        visitor.visit(tree)
        if rel in ALLOWLIST:
            continue
        findings.extend(visitor.findings)
    return findings


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src/turingos").mkdir(parents=True)
        (root / "tools/bench").mkdir(parents=True)
        (root / "src/turingos/codec.py").write_text(
            "\n".join(
                [
                    "import json as js",
                    "def canonical_bytes(value):",
                    "    return js.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        if lint(root):
            raise SystemExit("AST_CODEC_SELF_TEST_FAIL allowlisted clean fixture failed")

        (root / "tools/bench/bad_alias.py").write_text(
            "\n".join(
                [
                    "import json as js",
                    "def encode(value):",
                    "    return js.dumps(value, sort_keys=True, separators=(',', ':'))",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        findings = lint(root)
        if not findings:
            raise SystemExit("AST_CODEC_SELF_TEST_FAIL tamper fixture was not detected")
    print("AST_CODEC_SELF_TEST_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--root", default=str(REPO))
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    findings = lint(Path(args.root).resolve())
    if findings:
        for finding in findings:
            print(f"AST_CODEC_FAIL {finding}")
        return 1
    print("AST_CODEC_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
