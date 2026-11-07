import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.workflow import RouteOptimizationCoordinator


class WorkflowTests(unittest.TestCase):
    def test_route_returns_to_depot_and_review_alerts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "stops.csv").write_text(
                "stop_id,latitude,longitude,priority,service_minutes\nDEPOT,41.525,-88.081,1,0\nA,41.55,-88.02,2,10\nB,41.49,-88.12,3,10\n",
                encoding="utf-8",
            )
            (root / "config.json").write_text(json.dumps({
                "last_optimization_review": "2026-01-01",
                "review_interval_days": 182,
                "long_leg_miles": 100,
            }))
            result = RouteOptimizationCoordinator().run(root / "stops.csv", root / "config.json", date(2026, 8, 1))
            self.assertEqual(result["route"][0], "DEPOT")
            self.assertEqual(result["route"][-1], "DEPOT")
            self.assertIn("optimization_review_due", [a["type"] for a in result["alerts"]])
            self.assertEqual(len(result["trace"]), 3)


if __name__ == "__main__":
    unittest.main()
