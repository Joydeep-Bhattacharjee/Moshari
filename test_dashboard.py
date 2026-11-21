"""Run after installing requirements: python -m unittest test_dashboard -v."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
from sklearn.dummy import DummyRegressor
from streamlit.testing.v1 import AppTest

import app


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = app.build_mock_data()
        cls.week = cls.bundle["features"].week.max()

    def test_forecasts_and_scenarios(self):
        for horizon in (2, 3, 4):
            result = app.get_ward_forecast(self.bundle, "Ward-07", self.week, horizon, 1)
            self.assertEqual(len(result["series"]), 26)
            self.assertEqual(len(result["scenarios"]), 16)
            self.assertIsNone(result["actual_cases"])
            self.assertLessEqual(result["lo"], result["pred_cases"])
            self.assertGreaterEqual(result["hi"], result["pred_cases"])
            self.assertTrue(result["scenarios"].pred_cases.is_monotonic_increasing)
        historical = app.get_ward_forecast(self.bundle, "Ward-07", self.week - app.pd.Timedelta(weeks=6), 3, 1)
        self.assertIsNotNone(historical["actual_cases"])

    def test_priority_and_validation(self):
        table, matrix = app.get_priority_table(self.bundle, self.week, 3)
        self.assertEqual(len(table), 12)
        self.assertEqual(matrix.shape, (12, 3))
        ranks = table.tier.map({tier: i for i, tier in enumerate(app.TIERS[::-1])})
        self.assertTrue(ranks.is_monotonic_increasing)
        validation = app.get_validation_data(self.bundle, "Ward-07")
        self.assertEqual(len(validation["lag_correlation"]), 9)
        self.assertEqual(validation["split"]["purge_weeks"], 4)
        self.assertTrue(0 <= validation["coverage"] <= 1)

    def test_missing_corrupt_and_live_artifacts(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(app, "ROOT", Path(directory)):
            self.assertTrue(app.load_dashboard_bundle()["is_mock_mode"])
            root = Path(directory)
            (root / "models").mkdir()
            (root / "data/processed").mkdir(parents=True)
            (root / "models/model.joblib").write_bytes(b"invalid")
            (root / "models/meta.json").write_text("{}")
            (root / "data/processed/features.csv").write_text("invalid")
            self.assertTrue(app.load_dashboard_bundle()["is_mock_mode"])
            frame = self.bundle["features"].copy()
            cols = ["rainfall_mm", "avg_temp_C", "horizon"]
            train = frame.assign(horizon=3)[cols]
            model = DummyRegressor(strategy="constant", constant=62).fit(train, np.ones(len(train)))
            joblib.dump(model, root / "models/model.joblib")
            (root / "models/meta.json").write_text(json.dumps({
                "feature_columns": cols, "rainfall_scale_features": ["rainfall_mm"],
                "interval_absolute_width": 12,
            }))
            frame.to_csv(root / "data/processed/features.csv", index=False)
            live = app.load_dashboard_bundle()
            self.assertFalse(live["is_mock_mode"])
            result = app.get_ward_forecast(live, "Ward-07", self.week, 3, 1.5)
            self.assertEqual(result["pred_cases"], 62)
            self.assertFalse(app.get_validation_data(live, "Ward-07")["available"])


class StreamlitTests(unittest.TestCase):
    def test_startup_and_language_switch(self):
        dashboard = AppTest.from_file("app.py", default_timeout=30).run()
        self.assertFalse(dashboard.exception)
        self.assertEqual(len(dashboard.tabs), 4)
        self.assertFalse(any(w.value == app.TEXTS["en"]["error"] for w in dashboard.warning))
        dashboard.selectbox[0].set_value("বাংলা").run()
        self.assertFalse(dashboard.exception)
        self.assertEqual(dashboard.tabs[0].label, "পূর্বাভাস")
        dashboard.selectbox[0].set_value("EN + বাংলা").run()
        self.assertFalse(dashboard.exception)
        self.assertIn("Forecast /", dashboard.tabs[0].label)
        dashboard.slider[0].set_value(1.5).run()
        self.assertFalse(dashboard.exception)


if __name__ == "__main__":
    unittest.main()
