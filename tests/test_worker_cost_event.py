"""Tests for CostEvent.v2 construction at the WorkerAdapter seam."""
from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from turingos import codec, schemas
from turingos.worker import WorkerAdapter, dispatch
from turingos.worker import cost

REPO = Path(__file__).resolve().parents[1]


def _receipt() -> dict:
    return {
        "schema_id": "turingos.receipt.v1",
        "receipt_id": "rcpt:" + "a" * 64,
        "capsule_id": "cap:" + "b" * 64,
        "worker_id": "fake",
        "worktree_path": "/tmp/turingos-cost",
        "candidate": {"tree_oid": "c" * 64, "files_touched": ["x.py"]},
        "declared_test_results": [],
        "status": "ok",
        "no_orphan": True,
    }


class TestWorkerCostEvent(unittest.TestCase):
    def test_active_bench_producers_do_not_emit_cost_event_v1(self):
        active_producers = [
            REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py",
            REPO / "tools" / "bench" / "build_stage16r_unsolved_repair.py",
        ]
        for path in active_producers:
            self.assertNotIn('"schema_id": "cost_event.v1"', path.read_text(encoding="utf-8"), str(path))

    def test_dispatch_records_cost_event_at_worker_adapter_seam(self):
        class InProcAdapter(WorkerAdapter):
            worker_id = "unit-inproc"

            def run(self, capsule, worktree):  # noqa: D401
                rid = codec.content_digest({"capsule_id": capsule["capsule_id"], "worker": self.worker_id})
                return {
                    "schema_id": "turingos.receipt.v1",
                    "receipt_id": "rcpt:" + rid.removeprefix("sha256:"),
                    "capsule_id": capsule["capsule_id"],
                    "worker_id": self.worker_id,
                    "worktree_path": worktree,
                    "candidate": {"tree_oid": "0" * 64, "files_touched": []},
                    "declared_test_results": [],
                    "status": "ok",
                    "no_orphan": True,
                }

        capsule = {
            "schema_id": "turingos.capsule.v1",
            "capsule_id": "cap:" + "1" * 16,
            "atom_id": "atom-cost",
            "allowed_files": [],
            "budget": {"wall_seconds": 1, "max_retries": 0},
            "acceptance_commands": ["true"],
            "context": {"tape_tip": "x", "accepted_head": "y"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            adapter = InProcAdapter()
            receipt = dispatch(adapter, capsule, tmp, timeout_s=1)

        self.assertEqual(receipt["status"], "ok")
        schemas.validate_cost_event_v2(adapter.last_cost_event)
        self.assertEqual(adapter.last_cost_event["receipt_id"], receipt["receipt_id"])

    def test_price_table_is_pinned_and_has_deepseek_cache_split(self):
        table = cost.load_price_table()
        digest = cost.price_table_digest(table)
        self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")
        keys = {
            (row["provider"], row["model"], row["token_class"])
            for row in table["prices"]
        }
        self.assertIn(("deepseek", "deepseek-chat", "prompt_cache_hit_tokens"), keys)
        self.assertIn(("deepseek", "deepseek-chat", "prompt_cache_miss_tokens"), keys)

    def test_cost_event_from_receipt_has_worker_identity_and_no_secret_headers(self):
        payload = cost.cost_event_from_receipt(
            _receipt(),
            run_id="run:worker-cost",
            problem_id="prob:worker-cost",
            split="dogfood",
            agent_id="unit-worker",
            branch_id="branch:unit",
            adapter_kind="fake",
            provider="fixture",
            model_id_requested="fixture-model",
            model_id_resolved="fixture-model-20260702",
            endpoint="fixture://worker",
            request_id="req_fixture",
            response_sha256="sha256:" + "1" * 64,
            usage={"input_tokens": 4, "output_tokens": 2},
            cost_source_kind="fixture",
            cost_microusd=0,
            wall_time_ms=9,
            provider_usage_raw={"input_tokens": 4, "output_tokens": 2},
        )

        schemas.validate_cost_event_v2(payload)
        self.assertEqual(payload["schema_id"], "turingos.cost_event.v2")
        self.assertEqual(payload["receipt_id"], _receipt()["receipt_id"])
        self.assertEqual(payload["worker"]["adapter_kind"], "fake")
        self.assertEqual(payload["cost"]["price_table_digest"], cost.PRICE_TABLE_DIGEST)
        self.assertNotIn("authorization", str(payload).lower())
        self.assertNotIn("api_key", str(payload).lower())

    def test_bounded_token_upper_bound_uses_bytes_not_words(self):
        text = "one two three"
        by_words = len(text.split())
        bounded = cost.upper_bound_tokens_from_utf8_bytes(text, bytes_per_token_floor=2)
        self.assertGreater(bounded, by_words)

    def test_cost_event_registry_points_to_v2_payload_schema(self):
        registry_path = REPO / "pack" / "04_registries" / "event_registry_v5_3_1.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        rows = [
            row
            for row in registry["events"]
            if row["canonical_name"] == "CostEvent"
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["payload_schema_id"], "turingos.cost_event.v2")


if __name__ == "__main__":
    unittest.main()
