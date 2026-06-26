from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class EnvironmentContractTests(unittest.TestCase):
    def test_rust_authority_workspace_exists(self):
        self.assertTrue((REPO / "Cargo.toml").exists(), "Cargo.toml is required")
        self.assertTrue((REPO / "Cargo.lock").exists(), "Cargo.lock is required")
        self.assertTrue((REPO / "rust-toolchain.toml").exists(), "rust-toolchain.toml is required")
        self.assertTrue(
            (REPO / "pack/04_registries/event_registry_v5_3_1.json").exists(),
            "event registry is required by the Rust authority crates",
        )
        self.assertTrue(
            (REPO / "pack/04_registries/failure_disposition_map_v5_3_1.json").exists(),
            "failure disposition map is required by the Rust authority crates",
        )
        self.assertTrue(
            (REPO / "pack/03_contracts/semantic_digest_v5_3_1.json").exists(),
            "semantic digest contract vectors are required by the Rust authority tests",
        )
        for crate in [
            "turing-contracts",
            "turing-git-tape",
            "turing-kernel",
            "turing-replay",
        ]:
            self.assertTrue((REPO / "crates" / crate / "Cargo.toml").exists(), crate)

    def test_cargo_metadata_sees_authority_crates(self):
        result = subprocess.run(
            ["cargo", "metadata", "--format-version", "1", "--no-deps"],
            cwd=REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads(result.stdout)
        packages = {package["name"] for package in metadata["packages"]}
        self.assertIn("turing-contracts", packages)
        self.assertIn("turing-git-tape", packages)
        self.assertIn("turing-kernel", packages)
        self.assertIn("turing-replay", packages)

    def test_github_actions_runs_python_and_rust_gates(self):
        workflow = REPO / ".github/workflows/ci.yml"
        self.assertTrue(workflow.exists(), "GitHub Actions workflow is required")
        text = workflow.read_text(encoding="utf-8")
        for needle in [
            "python3 -m pytest",
            "cargo fmt --all -- --check",
            "cargo clippy --workspace --all-targets -- -D warnings",
            "cargo test --workspace",
            "tools/headless/run_local_gates.py",
            "tools/headless/build_evidence_bundle.py",
        ]:
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
