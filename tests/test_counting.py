import unittest

from src.counting import LineCounter
from src.metrics import OccupancyAccumulator


class LineCounterTests(unittest.TestCase):
    def setUp(self):
        self.counter = LineCounter((0, 50), (100, 50), direction="positive", hysteresis_px=3)

    def test_counts_only_the_configured_direction_once_per_track(self):
        self.assertIsNone(self.counter.update(1, (50, 20)))
        crossing = self.counter.update(1, (50, 80))
        self.assertEqual(crossing.direction, "positive")
        self.assertEqual(self.counter.total, 1)
        self.assertIsNone(self.counter.update(1, (50, 20)))
        self.assertEqual(self.counter.total, 1)

    def test_ignores_jitter_inside_hysteresis_band(self):
        self.counter.update(2, (50, 40))
        self.assertIsNone(self.counter.update(2, (50, 49)))
        self.assertIsNone(self.counter.update(2, (50, 51)))
        self.assertIsNone(self.counter.update(2, (50, 40)))
        self.assertEqual(self.counter.total, 0)

    def test_reverse_crossing_does_not_count_but_can_be_followed_by_valid_crossing(self):
        self.counter.update(3, (50, 80))
        self.assertIsNone(self.counter.update(3, (50, 20)))
        crossing = self.counter.update(3, (50, 80))
        self.assertEqual(crossing.direction, "positive")
        self.assertEqual(self.counter.total, 1)

    def test_crossing_outside_finite_line_is_not_counted(self):
        self.counter.update(4, (-20, 20))
        self.assertIsNone(self.counter.update(4, (-20, 80)))
        self.assertEqual(self.counter.total, 0)

    def test_reset_forgets_positions_without_erasing_counts(self):
        self.counter.update(5, (50, 20))
        self.counter.reset()
        self.assertIsNone(self.counter.update(5, (50, 80)))
        self.assertEqual(self.counter.total, 0)


class OccupancyAccumulatorTests(unittest.TestCase):
    def test_emits_empty_and_occupied_intervals_with_visual_proxy(self):
        accumulator = OccupancyAccumulator(interval_seconds=1, reference_item_count=4)
        accumulator.add(0.0, 0, True)
        accumulator.add(0.5, 0, True)
        accumulator.add(1.0, 2, True)
        accumulator.add(1.5, 4, True)

        rows = accumulator.rows(video_duration_s=2)
        self.assertEqual(
            [row["quality"] for row in rows], ["visually_empty", "detections_present"]
        )
        self.assertEqual(rows[1]["approx_occupancy_score"], 0.75)

    def test_any_unavailable_frame_makes_the_whole_interval_unevaluable(self):
        accumulator = OccupancyAccumulator(interval_seconds=1, reference_item_count=4)
        accumulator.add(0.0, 0, True)
        accumulator.add(0.5, 0, False)

        row = accumulator.rows(video_duration_s=0.75)[0]
        self.assertEqual(row["quality"], "unevaluable")
        self.assertIsNone(row["approx_occupancy_score"])
        self.assertEqual(row["duration_s"], 0.75)

    def test_rejects_invalid_interval_or_reference_count(self):
        with self.assertRaises(ValueError):
            OccupancyAccumulator(interval_seconds=0, reference_item_count=1)
        with self.assertRaises(ValueError):
            OccupancyAccumulator(interval_seconds=1, reference_item_count=0)


if __name__ == "__main__":
    unittest.main()