from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from theta_core import edge_rpc

DAY = int(datetime(2026, 11, 9, 12, tzinfo=timezone.utc).timestamp() * 1000)


def job(amount: str, status: str, end_time: int = DAY) -> dict:
    return {"id": "job", "reward_amount": amount, "status": status, "end_time": end_time}


class EdgeRpcTests(unittest.TestCase):
    def setUp(self):
        edge_rpc._CACHE.update(at=0.0, data=None)

    def test_rewards_split_completed_and_rewarded(self):
        pages = {
            "lavita": [[job("200000000000000000", "completed")]],
            "fedml": [[job("100000000000000000", "rewarded")]],
        }

        def fake_rpc(url, method, params=None, timeout=2.5):
            kind = params[0]["type"]
            page = params[0]["page"]
            return {"body": pages[kind][page] if page < len(pages[kind]) else []}

        with patch.object(edge_rpc, "rpc", side_effect=fake_rpc):
            summary = edge_rpc.rewards_summary(max_pages=1)
        self.assertAlmostEqual(summary["pending_tfuel"], 0.2)
        self.assertAlmostEqual(summary["paid_tfuel"], 0.1)
        self.assertEqual(summary["jobs"], 2)
        self.assertEqual(len(summary["daily"]), 7)
        self.assertAlmostEqual(sum(row["tfuel"] for row in summary["daily"]), 0.3)

    def test_bad_reward_amount_does_not_crash(self):
        def fake_rpc(url, method, params=None, timeout=2.5):
            return {"body": [job("not-a-number", "completed")]}

        with patch.object(edge_rpc, "rpc", side_effect=fake_rpc):
            summary = edge_rpc.rewards_summary(max_pages=1)
        self.assertEqual(summary["pending_tfuel"], 0.0)

    def test_node_status_online(self):
        def fake_rpc(url, method, params=None, timeout=2.5):
            if method == "edgecore.GetVersion":
                return {"version": "5.2.26"}
            if method == "edgecore.GetEdgeNodeSummary":
                return {"Summary": "0xABCDEF"}
            if method == "edgecore.GetStatus":
                return {"synced": True, "peers": 12}
            if method == "edgecore.GetPeers":
                return [1, 2, 3]
            if method == "edgelauncher.GetPastJobs":
                return {"body": []}
            raise AssertionError(method)

        with patch.object(edge_rpc, "rpc", side_effect=fake_rpc):
            status = edge_rpc.node_status()
        self.assertTrue(status["running"])
        self.assertEqual(status["version"], "5.2.26")
        self.assertEqual(status["holder_address"], "0xABCDEF")
        self.assertTrue(status["synced"])
        self.assertEqual(status["peers"], 3)
        self.assertEqual(status["rewards"]["jobs"], 0)

    def test_offline_node_reports_not_running(self):
        with patch.object(edge_rpc, "rpc", side_effect=edge_rpc.EdgeRpcError("connection refused")):
            status = edge_rpc.node_status()
        self.assertFalse(status["running"])
        self.assertIn("connection refused", status["error"])


if __name__ == "__main__":
    unittest.main()
