import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from src.build_report import build_report
from src.pricing import calculate_quote
from src.reporting import analyze_telemetry, n2_per_counted_unit, summarize_clip


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            {
                "clip_id": "demo_1",
                "track_id": "1",
                "recipe_id": "burger_200g",
                "clip_origin": "simulated",
                "measurement_status": "estimated",
                "event_type": "counted",
                "quality": "evaluable",
            },
            {
                "clip_id": "demo_1",
                "track_id": "1",
                "recipe_id": "burger_200g",
                "clip_origin": "simulated",
                "event_type": "counted",
                "quality": "evaluable",
            },
            {
                "clip_id": "demo_1",
                "track_id": "2",
                "recipe_id": "burger_200g",
                "clip_origin": "simulated",
                "event_type": "counted",
                "quality": "unevaluable",
            },
        ]
        self.intervals = [
            {
                "time_start_s": "0",
                "duration_s": "1",
                "clip_origin": "simulated",
                "quality": "visually_empty",
                "approx_occupancy_score": "0",
            },
            {
                "time_start_s": "1",
                "duration_s": "1",
                "clip_origin": "simulated",
                "quality": "detections_present",
                "approx_occupancy_score": "0.5",
            },
            {
                "time_start_s": "2",
                "duration_s": "1",
                "clip_origin": "simulated",
                "quality": "unevaluable",
                "approx_occupancy_score": "",
            },
        ]

    def test_summary_deduplicates_tracks_and_excludes_unevaluable_time(self):
        summary = summarize_clip(self.events, self.intervals, empty_run_alert_seconds=2)
        self.assertEqual(summary["counted_units"], 1)
        self.assertEqual(summary["evaluable_seconds"], 2)
        self.assertEqual(summary["pieces_per_minute"], 30)
        self.assertEqual(summary["visually_empty_seconds"], 1)
        self.assertFalse(summary["fully_evaluable"])

    def test_rejects_mixed_clip_origins(self):
        intervals = [dict(row) for row in self.intervals]
        intervals[0]["clip_origin"] = "real"
        with self.assertRaises(ValueError):
            summarize_clip(self.events, intervals)

    def test_full_simulated_telemetry_and_zero_denominator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            telemetry_path = Path(temp_dir) / "telemetry.csv"
            with telemetry_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["time_s", "n2_kg_interval", "interval_s", "tunnel_id", "origin"],
                )
                writer.writeheader()
                writer.writerow(
                    {"time_s": "0", "n2_kg_interval": "2", "interval_s": "1", "tunnel_id": "T1", "origin": "simulat"}
                )
                writer.writerow(
                    {"time_s": "1", "n2_kg_interval": "3", "interval_s": "1", "tunnel_id": "T1", "origin": "simulat"}
                )

            telemetry = analyze_telemetry(telemetry_path, video_duration_s=2)
            self.assertEqual(telemetry["status"], "available")
            self.assertEqual(telemetry["origin"], "simulated")
            n2_ratio = n2_per_counted_unit(
                telemetry,
                {"fully_evaluable": True, "counted_units": 2},
            )
            self.assertEqual(n2_ratio["value"], 2.5)
            no_units = n2_per_counted_unit(
                telemetry,
                {"fully_evaluable": True, "counted_units": 0},
            )
            self.assertEqual(no_units["status"], "not_applicable_zero_units")

    def test_telemetry_gap_is_not_used(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            telemetry_path = Path(temp_dir) / "telemetry.csv"
            with telemetry_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["time_s", "n2_kg_interval", "interval_s", "tunnel_id", "origin"],
                )
                writer.writeheader()
                writer.writerow(
                    {"time_s": "0.5", "n2_kg_interval": "2", "interval_s": "1", "tunnel_id": "T1", "origin": "real"}
                )

            telemetry = analyze_telemetry(telemetry_path, video_duration_s=2)
            self.assertEqual(telemetry["status"], "unavailable")

    def test_build_report_writes_offline_html_and_provenance_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            events_path = temp_path / "events.csv"
            occupancy_path = temp_path / "occupancy.csv"
            output_path = temp_path / "report.html"
            with events_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "clip_id",
                        "time_s",
                        "track_id",
                        "recipe_id",
                        "clip_origin",
                        "measurement_status",
                        "event_type",
                        "quality",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "clip_id": "demo_1",
                        "time_s": "0.5",
                        "track_id": "7",
                        "recipe_id": "burger_200g",
                        "clip_origin": "simulated",
                        "measurement_status": "estimated",
                        "event_type": "counted",
                        "quality": "evaluable",
                    }
                )
            with occupancy_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "time_start_s",
                        "duration_s",
                        "clip_origin",
                        "measurement_status",
                        "quality",
                        "frame_count",
                        "evaluable_frame_ratio",
                        "average_detected_objects",
                        "peak_detected_objects",
                        "approx_occupancy_score",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "time_start_s": "0",
                        "duration_s": "1",
                        "clip_origin": "simulated",
                        "measurement_status": "estimated",
                        "quality": "detections_present",
                        "frame_count": "10",
                        "evaluable_frame_ratio": "1",
                        "average_detected_objects": "1",
                        "peak_detected_objects": "1",
                        "approx_occupancy_score": "0.167",
                    }
                )

            build_report(events_path, occupancy_path, output_path)
            html_report = output_path.read_text(encoding="utf-8")
            summary = json.loads(output_path.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertIn("SIMULACIÓ", html_report)
            self.assertIn("no és un comptador homologat", html_report.lower())
            self.assertNotIn("https://", html_report)
            self.assertEqual(summary["clip_id"], "demo_1")
            self.assertEqual(summary["telemetry"]["status"], "unavailable")


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.recipes = {
            "burger_200g": {
                "description": "200 g declared",
                "nominal_mass_g": "200",
                "illustrative_rate_eur_per_unit": "",
            },
            "burger_500g": {
                "description": "500 g declared",
                "nominal_mass_g": "500",
                "illustrative_rate_eur_per_unit": "",
            },
        }

    def test_mixed_recipe_scenario_uses_explicit_rates_and_rounds_total(self):
        result = calculate_quote(
            self.recipes,
            {"burger_200g": 100, "burger_500g": 20},
            fixed_fee=Decimal("10"),
            approved_extras={"approved support": Decimal("5")},
            rate_overrides={
                "burger_200g": Decimal("0.12"),
                "burger_500g": Decimal("0.21"),
            },
        )
        self.assertEqual(result["total_eur"], "31.20")
        self.assertFalse(result["invoice_eligible"])
        self.assertEqual(len(result["products"]), 2)
        self.assertEqual(
            {item["rate_source"] for item in result["products"]}, {"manual_run_override"}
        )

    def test_missing_rate_is_not_inferred_from_declared_mass(self):
        with self.assertRaisesRegex(ValueError, "do not infer it from nominal mass"):
            calculate_quote(self.recipes, {"burger_200g": 1})

    def test_rejects_negative_amounts_and_unknown_recipes(self):
        with self.assertRaises(ValueError):
            calculate_quote(self.recipes, {"burger_200g": -1})
        with self.assertRaises(ValueError):
            calculate_quote(self.recipes, {"unknown_recipe": 1})


if __name__ == "__main__":
    unittest.main()