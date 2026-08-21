import json
import unittest
from pathlib import Path

from build_faction_diagnostics import SCHEMA_VERSION, serialize_payload


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "faction_diagnostics.json"


class FactionDiagnosticsArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = ARTIFACT.read_text(encoding="utf-8")
        cls.payload = json.loads(cls.raw)

    def test_artifact_is_deterministic_and_dates_match_metadata(self):
        self.assertEqual(self.raw, serialize_payload(self.payload))
        self.assertEqual(self.payload["meta"]["schema_version"], SCHEMA_VERSION)
        dates = list(self.payload["daily"])
        self.assertEqual(dates, sorted(dates))
        self.assertTrue(dates)
        self.assertEqual(self.payload["meta"]["min_date"], dates[0])
        self.assertEqual(self.payload["meta"]["max_date"], dates[-1])

    def test_daily_and_snapshot_invariants(self):
        passed = 0
        for date, day in self.payload["daily"].items():
            self.assertRegex(date, r"^\d{4}-\d{2}-\d{2}$")
            for faction_id, metrics in day["factions"].items():
                self.assertTrue(faction_id.isdigit())
                self.assertTrue(all(isinstance(value, int) and value >= 0 for value in metrics.values()))
                self.assertLessEqual(metrics["active"], metrics["present"])
                self.assertLessEqual(metrics["present"], metrics["total"])
                self.assertLessEqual(metrics["discipline_agree"], metrics["discipline_total"])

            coalition = day["coalition"]
            self.assertEqual(coalition["sn_alone"] + coalition["sn_dependent"], coalition["passed"])
            passed += coalition["passed"]
            for faction_id, metrics in coalition["partners"].items():
                self.assertNotEqual(faction_id, "1")
                self.assertTrue(all(isinstance(value, int) and value >= 0 for value in metrics.values()))
                self.assertLessEqual(metrics["for_votes"], metrics["opportunities"])
                self.assertLessEqual(metrics["strictly_necessary_votes"], coalition["sn_dependent"])

        counts = self.payload["meta"]["counts"]
        self.assertEqual(passed, counts["passed_law_stage_votes"])
        self.assertLessEqual(counts["passed_law_stage_votes"], counts["law_stage_votes"])
        self.assertLessEqual(counts["relevant_votes"], counts["source_rows"])


if __name__ == "__main__":
    unittest.main()
