"""Small, dependency-free aggregation helpers for visual occupancy intervals."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass
class _Bucket:
    frames: int = 0
    evaluable_frames: int = 0
    object_sum: int = 0
    peak_objects: int = 0


class OccupancyAccumulator:
    """Aggregate per-frame detections into conservative time intervals."""

    def __init__(self, interval_seconds: float, reference_item_count: int) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")
        if reference_item_count <= 0:
            raise ValueError("reference_item_count must be greater than zero")
        self.interval_seconds = interval_seconds
        self.reference_item_count = reference_item_count
        self._buckets: dict[int, _Bucket] = {}

    def add(self, time_s: float, detected_objects: int, evaluable: bool) -> None:
        if time_s < 0:
            raise ValueError("time_s must be non-negative")
        if detected_objects < 0:
            raise ValueError("detected_objects must be non-negative")

        bucket_index = int(time_s / self.interval_seconds)
        bucket = self._buckets.setdefault(bucket_index, _Bucket())
        bucket.frames += 1
        if evaluable:
            bucket.evaluable_frames += 1
            bucket.object_sum += detected_objects
            bucket.peak_objects = max(bucket.peak_objects, detected_objects)

    def rows(self, video_duration_s: float) -> list[dict[str, float | int | str | None]]:
        if video_duration_s < 0:
            raise ValueError("video_duration_s must be non-negative")

        rows: list[dict[str, float | int | str | None]] = []
        bucket_count = ceil(video_duration_s / self.interval_seconds)
        for index in range(bucket_count):
            bucket = self._buckets.get(index, _Bucket())
            start_s = index * self.interval_seconds
            duration_s = min(self.interval_seconds, video_duration_s - start_s)
            fully_evaluable = bucket.frames > 0 and bucket.evaluable_frames == bucket.frames

            if not fully_evaluable:
                quality = "unevaluable"
                average: float | None = None
                peak: int | None = None
                score: float | None = None
            else:
                quality = "visually_empty" if bucket.peak_objects == 0 else "detections_present"
                average = bucket.object_sum / bucket.evaluable_frames
                peak = bucket.peak_objects
                score = min(average / self.reference_item_count, 1.0)

            rows.append(
                {
                    "time_start_s": round(start_s, 3),
                    "duration_s": round(max(duration_s, 0.0), 6),
                    "quality": quality,
                    "frame_count": bucket.frames,
                    "evaluable_frame_ratio": (
                        round(bucket.evaluable_frames / bucket.frames, 3) if bucket.frames else 0.0
                    ),
                    "average_detected_objects": (
                        round(average, 3) if average is not None else None
                    ),
                    "peak_detected_objects": peak,
                    "approx_occupancy_score": round(score, 3) if score is not None else None,
                }
            )
        return rows