"""Dependency-free calculations for the local HTML report."""

from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as input_file:
        return list(csv.DictReader(input_file))


def _float(value: Any, label: str, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}: {value!r}") from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise ValueError(f"Invalid {label}: {value!r}")
    return result


def _clip_origin(rows: list[dict[str, Any]]) -> str:
    origins = {str(row.get("clip_origin", "")).strip().lower() for row in rows}
    origins.discard("")
    if len(origins) > 1:
        raise ValueError("Mixed clip origins found; build a report from one clip at a time")
    if not origins:
        return "unknown"
    origin = origins.pop()
    if origin not in ("real", "simulated"):
        raise ValueError(f"Unrecognized clip_origin: {origin}")
    return origin


def summarize_clip(
    event_rows: list[dict[str, Any]],
    occupancy_rows: list[dict[str, Any]],
    empty_run_alert_seconds: float = 2.0,
) -> dict[str, Any]:
    if not occupancy_rows:
        raise ValueError("Occupancy CSV has no intervals")
    if empty_run_alert_seconds < 0:
        raise ValueError("empty_run_alert_seconds must be non-negative")

    clip_origin = _clip_origin(event_rows + occupancy_rows)
    clip_ids = {str(row.get("clip_id", "")).strip() for row in event_rows}
    clip_ids.discard("")
    if len(clip_ids) > 1:
        raise ValueError("Events CSV contains more than one clip_id")
    intervals = sorted(
        occupancy_rows,
        key=lambda row: _float(row.get("time_start_s"), "interval start", 0.0) or 0.0,
    )
    duration_s = 0.0
    evaluable_seconds = 0.0
    visually_empty_seconds = 0.0
    weighted_occupancy = 0.0
    occupancy_weight_seconds = 0.0
    current_empty_run = 0.0
    max_empty_run = 0.0
    previous_end: float | None = None
    counts_by_recipe: dict[str, int] = defaultdict(int)
    counted_tracks: set[tuple[str, str]] = set()

    for row in event_rows:
        if row.get("event_type") != "counted" or row.get("quality", "evaluable") != "evaluable":
            continue
        recipe_id = str(row.get("recipe_id", "")).strip()
        track_id = str(row.get("track_id", "")).strip()
        if not recipe_id or not track_id:
            continue
        key = (recipe_id, track_id)
        if key not in counted_tracks:
            counted_tracks.add(key)
            counts_by_recipe[recipe_id] += 1

    for row in intervals:
        start_s = _float(row.get("time_start_s"), "interval start", 0.0) or 0.0
        interval_s = _float(row.get("duration_s"), "interval duration", 0.0) or 0.0
        if start_s < 0 or interval_s < 0:
            raise ValueError("Occupancy interval starts and durations must be non-negative")
        end_s = start_s + interval_s
        duration_s = max(duration_s, end_s)
        quality = str(row.get("quality", "unevaluable")).strip().lower()
        contiguous = previous_end is not None and abs(start_s - previous_end) <= 0.002

        if quality == "unevaluable":
            current_empty_run = 0.0
        else:
            evaluable_seconds += interval_s
            score = _float(row.get("approx_occupancy_score"), "occupancy score")
            if score is not None:
                weighted_occupancy += score * interval_s
                occupancy_weight_seconds += interval_s
            if quality == "visually_empty":
                visually_empty_seconds += interval_s
                current_empty_run = (current_empty_run if contiguous else 0.0) + interval_s
                max_empty_run = max(max_empty_run, current_empty_run)
            else:
                current_empty_run = 0.0
        previous_end = end_s

    total_units = sum(counts_by_recipe.values())
    pieces_per_minute = (
        total_units / evaluable_seconds * 60 if evaluable_seconds > 0 else None
    )
    approximate_occupancy = (
        weighted_occupancy / occupancy_weight_seconds if occupancy_weight_seconds > 0 else None
    )
    fully_evaluable = duration_s > 0 and evaluable_seconds >= duration_s - 0.002

    if max_empty_run >= empty_run_alert_seconds and max_empty_run > 0:
        observation = (
            "S'observa un interval visualment sense deteccions; revisar la regularitat "
            "d'alimentació amb l'especialista. Això no demostra una causa ni un estalvi."
        )
    elif not fully_evaluable:
        observation = (
            "La cobertura d'imatge és incompleta; no extreure conclusions sobre buits "
            "o regularitat d'alimentació."
        )
    else:
        observation = (
            "No s'ha superat el llindar d'interval visual sense deteccions; cal contrastar "
            "qualsevol interpretació amb l'equip de procés."
        )

    return {
        "clip_id": next(iter(clip_ids), "no identificat"),
        "clip_origin": clip_origin,
        "measurement_status": "estimated",
        "video_duration_s": round(duration_s, 6),
        "evaluable_seconds": round(evaluable_seconds, 6),
        "fully_evaluable": fully_evaluable,
        "counted_units": total_units,
        "counts_by_recipe": dict(sorted(counts_by_recipe.items())),
        "pieces_per_minute": round(pieces_per_minute, 3) if pieces_per_minute is not None else None,
        "visually_empty_seconds": round(visually_empty_seconds, 3),
        "max_visual_empty_run_seconds": round(max_empty_run, 3),
        "approx_occupancy_score": (
            round(approximate_occupancy, 3) if approximate_occupancy is not None else None
        ),
        "observation": observation,
    }


def analyze_telemetry(
    path: Path | None,
    video_duration_s: float,
    offset_s: float = 0.0,
) -> dict[str, Any]:
    if path is None:
        return {"status": "unavailable", "reason": "No s'ha proporcionat telemetria."}
    if not path.is_file():
        return {"status": "unavailable", "reason": "No s'ha trobat el fitxer de telemetria."}

    try:
        rows = read_csv_rows(path)
        if not rows:
            raise ValueError("CSV buit")
        required = {"time_s", "n2_kg_interval", "interval_s", "tunnel_id", "origin"}
        if not required.issubset(rows[0]):
            raise ValueError("Falten columnes requerides al CSV de telemetria")

        parsed: list[tuple[Decimal, Decimal, Decimal, str, str]] = []
        for row in rows:
            start = Decimal(str(row["time_s"])) + Decimal(str(offset_s))
            n2_kg = Decimal(str(row["n2_kg_interval"]))
            interval = Decimal(str(row["interval_s"]))
            tunnel_id = row["tunnel_id"].strip()
            origin = row["origin"].strip().lower()
            if origin == "simulat":
                origin = "simulated"
            if origin not in ("real", "simulated"):
                raise ValueError("Origen de telemetria no reconegut")
            if not tunnel_id:
                raise ValueError("Falta l'identificador del túnel")
            if n2_kg < 0 or interval <= 0:
                raise ValueError("N₂ ha de ser no negatiu i interval_s positiu")
            parsed.append((start, start + interval, n2_kg, tunnel_id, origin))

        tunnels = {row[3] for row in parsed}
        origins = {row[4] for row in parsed}
        if len(tunnels) != 1 or len(origins) != 1:
            raise ValueError("La telemetria barreja túnels o orígens")

        parsed.sort(key=lambda row: row[0])
        tolerance = Decimal("0.002")
        cursor = Decimal("0")
        total_n2 = Decimal("0")
        for start, end, n2_kg, _, _ in parsed:
            if abs(start - cursor) > tolerance:
                raise ValueError("Intervals de telemetria no contigus o desfasament incorrecte")
            if end > Decimal(str(video_duration_s)) + tolerance:
                raise ValueError("Telemetria fora de la finestra del vídeo")
            total_n2 += n2_kg
            cursor = end
        if abs(cursor - Decimal(str(video_duration_s))) > tolerance:
            raise ValueError("La telemetria no cobreix tota la durada del vídeo")

        return {
            "status": "available",
            "origin": origins.pop(),
            "tunnel_id": tunnels.pop(),
            "interval_count": len(parsed),
            "n2_kg_total": float(total_n2),
            "offset_s": float(offset_s),
        }
    except (KeyError, InvalidOperation, OSError, ValueError) as exc:
        return {"status": "unavailable", "reason": f"Telemetria no avaluable: {exc}."}


def n2_per_counted_unit(
    telemetry: dict[str, Any], summary: dict[str, Any]
) -> dict[str, Any]:
    if telemetry.get("status") != "available":
        return {"status": "unavailable", "value": None, "origin": None}
    if not summary.get("fully_evaluable"):
        return {"status": "unavailable", "value": None, "origin": telemetry.get("origin")}
    units = int(summary.get("counted_units", 0))
    if units == 0:
        return {"status": "not_applicable_zero_units", "value": None, "origin": telemetry.get("origin")}
    value = float(telemetry["n2_kg_total"]) / units
    return {
        "status": "available",
        "value": round(value, 6),
        "origin": telemetry.get("origin"),
    }