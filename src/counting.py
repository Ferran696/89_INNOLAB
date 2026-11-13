"""Directional line crossing with a per-track once-only count guard."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Literal

Point = tuple[float, float]
Direction = Literal["positive", "negative", "both"]


@dataclass(frozen=True)
class Crossing:
    track_id: int
    direction: Literal["positive", "negative"]


class LineCounter:
    """Count tracks that cross a finite line in the configured direction."""

    def __init__(
        self,
        line_start: Point,
        line_end: Point,
        direction: Direction = "positive",
        hysteresis_px: float = 4.0,
    ) -> None:
        if direction not in ("positive", "negative", "both"):
            raise ValueError("direction must be 'positive', 'negative', or 'both'")
        if hysteresis_px < 0:
            raise ValueError("hysteresis_px must be non-negative")
        if line_start == line_end:
            raise ValueError("count line endpoints must be different")

        self.line_start = line_start
        self.line_end = line_end
        self.direction = direction
        self.hysteresis_px = hysteresis_px
        self._line_length = hypot(line_end[0] - line_start[0], line_end[1] - line_start[1])
        self._last_stable: dict[int, tuple[Point, float]] = {}
        self._counted: set[int] = set()

    @property
    def total(self) -> int:
        return len(self._counted)

    def update(self, track_id: int, point: Point) -> Crossing | None:
        """Observe a center point and return its first valid count crossing, if any."""
        distance = self._signed_distance(point)
        if distance == 0 or abs(distance) < self.hysteresis_px:
            return None

        previous = self._last_stable.get(track_id)
        self._last_stable[track_id] = (point, distance)
        if previous is None or track_id in self._counted:
            return None

        previous_point, previous_distance = previous
        if previous_distance * distance >= 0:
            return None

        crossing_point = self._interpolate_crossing(previous_point, point, previous_distance, distance)
        if not self._lies_on_finite_line(crossing_point):
            return None

        crossing_direction: Literal["positive", "negative"] = (
            "positive" if previous_distance < 0 < distance else "negative"
        )
        if self.direction not in ("both", crossing_direction):
            return None

        self._counted.add(track_id)
        return Crossing(track_id=track_id, direction=crossing_direction)

    def reset(self) -> None:
        """Forget track positions after an unevaluable image interval."""
        self._last_stable.clear()

    def _signed_distance(self, point: Point) -> float:
        dx = self.line_end[0] - self.line_start[0]
        dy = self.line_end[1] - self.line_start[1]
        px = point[0] - self.line_start[0]
        py = point[1] - self.line_start[1]
        return (dx * py - dy * px) / self._line_length

    @staticmethod
    def _interpolate_crossing(
        start: Point,
        end: Point,
        start_distance: float,
        end_distance: float,
    ) -> Point:
        fraction = start_distance / (start_distance - end_distance)
        return (
            start[0] + fraction * (end[0] - start[0]),
            start[1] + fraction * (end[1] - start[1]),
        )

    def _lies_on_finite_line(self, point: Point) -> bool:
        dx = self.line_end[0] - self.line_start[0]
        dy = self.line_end[1] - self.line_start[1]
        length_squared = dx * dx + dy * dy
        projection = (
            (point[0] - self.line_start[0]) * dx + (point[1] - self.line_start[1]) * dy
        ) / length_squared
        tolerance = self.hysteresis_px / self._line_length
        return -tolerance <= projection <= 1 + tolerance