"""Run local YOLO tracking, directional counting, and visual occupancy summaries."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

try:
    import cv2
    import numpy as np
    import yaml
    from ultralytics import YOLO
except ImportError as exc:
    raise SystemExit(
        "Missing runtime dependency. From freezeproof, install requirements with "
        "'python -m pip install -r requirements.txt'."
    ) from exc

try:
    from .counting import LineCounter
    from .metrics import OccupancyAccumulator
except ImportError:
    from counting import LineCounter
    from metrics import OccupancyAccumulator


def _point(raw: list[float], width: int, height: int) -> tuple[float, float]:
    if len(raw) != 2:
        raise ValueError("each normalized point must contain x and y")
    x, y = float(raw[0]), float(raw[1])
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ValueError("zone and line coordinates must be normalized to [0, 1]")
    return x * (width - 1), y * (height - 1)


def _load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a YAML mapping: {path}")
    return config


def _frame_is_evaluable(
    frame: np.ndarray,
    time_s: float,
    quality_config: dict[str, Any],
) -> bool:
    for interval in quality_config.get("unavailable_intervals", []):
        if len(interval) != 2:
            raise ValueError("each unavailable interval must be [start_seconds, end_seconds]")
        start_s, end_s = float(interval[0]), float(interval[1])
        if start_s < 0 or end_s <= start_s:
            raise ValueError("unavailable intervals must have 0 <= start < end")
        if start_s <= time_s < end_s:
            return False

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    min_sharpness = quality_config.get("min_laplacian_variance")
    if min_sharpness is not None:
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if sharpness < float(min_sharpness):
            return False

    mean_luma = float(gray.mean())
    min_luma = quality_config.get("min_mean_luma")
    max_luma = quality_config.get("max_mean_luma")
    if min_luma is not None and mean_luma < float(min_luma):
        return False
    if max_luma is not None and mean_luma > float(max_luma):
        return False
    return True


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def process_video(video_path: Path, model_path: Path, config_path: Path, output_dir: Path) -> None:
    config = _load_config(config_path)
    detector_config = config.get("detector", {})
    tracking_config = config.get("tracking", {})
    quality_config = config.get("quality", {})
    occupancy_config = config.get("occupancy", {})
    recipe_id = str(config.get("recipe_id", "unknown"))
    clip_origin = str(config.get("clip_origin", "unknown")).strip().lower()
    if clip_origin not in ("real", "simulated"):
        raise ValueError("clip_origin must be explicitly set to 'real' or 'simulated'")

    if not video_path.is_file():
        raise FileNotFoundError(f"Input video not found: {video_path}")
    if not model_path.is_file():
        raise FileNotFoundError(f"Model weights not found: {model_path}")

    model = YOLO(str(model_path))
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or width <= 0 or height <= 0:
        capture.release()
        raise RuntimeError("Video metadata is missing a valid FPS or frame size")

    output_dir.mkdir(parents=True, exist_ok=True)
    annotated_path = output_dir / f"{video_path.stem}_annotated.mp4"
    writer = cv2.VideoWriter(
        str(annotated_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"Could not create annotated video: {annotated_path}")

    zone = np.array(
        [_point(point, width, height) for point in config["zone_polygon"]], dtype=np.float32
    )
    if len(zone) < 3:
        capture.release()
        writer.release()
        raise ValueError("zone_polygon must contain at least three points")
    zone_contour = zone.astype(np.int32).reshape((-1, 1, 2))

    line_points = config["count_line"]["points"]
    line_start = _point(line_points[0], width, height)
    line_end = _point(line_points[1], width, height)
    counter = LineCounter(
        line_start,
        line_end,
        direction=config["count_line"].get("direction", "positive"),
        hysteresis_px=float(config["count_line"].get("hysteresis_px", 4)),
    )
    occupancy = OccupancyAccumulator(
        interval_seconds=float(occupancy_config.get("interval_seconds", 1.0)),
        reference_item_count=int(occupancy_config.get("reference_item_count", 6)),
    )

    tracker_yaml = tracking_config.get("tracker", "bytetrack.yaml")
    class_ids = detector_config.get("class_ids", [])
    clip_id = video_path.stem
    event_rows: list[dict[str, Any]] = []
    seen_tracks: set[int] = set()
    frame_index = 0

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            time_s = frame_index / fps
            evaluable = _frame_is_evaluable(frame, time_s, quality_config)
            result = model.track(
                frame,
                persist=True,
                tracker=tracker_yaml,
                conf=float(detector_config.get("confidence", 0.25)),
                iou=float(detector_config.get("iou", 0.45)),
                imgsz=int(detector_config.get("image_size", 640)),
                classes=class_ids or None,
                verbose=False,
            )[0]

            visible_in_zone = 0
            boxes = result.boxes
            if boxes is not None and len(boxes) > 0:
                xyxy = boxes.xyxy.cpu().numpy()
                track_ids = (
                    boxes.id.int().cpu().tolist()
                    if boxes.id is not None
                    else [None] * len(xyxy)
                )
                confidences = boxes.conf.cpu().tolist()
                class_indices = boxes.cls.int().cpu().tolist()
                for box, track_id, confidence, class_index in zip(
                    xyxy, track_ids, confidences, class_indices
                ):
                    x1, y1, x2, y2 = (int(value) for value in box)
                    center = ((x1 + x2) / 2, (y1 + y2) / 2)
                    inside_zone = cv2.pointPolygonTest(
                        zone_contour, (float(center[0]), float(center[1])), False
                    ) >= 0
                    if inside_zone:
                        visible_in_zone += 1

                    if track_id is not None:
                        track_id = int(track_id)
                        if evaluable and track_id not in seen_tracks:
                            seen_tracks.add(track_id)
                            event_rows.append(
                                {
                                    "clip_id": clip_id,
                                    "time_s": round(time_s, 3),
                                    "track_id": track_id,
                                    "recipe_id": recipe_id,
                                    "clip_origin": clip_origin,
                                    "measurement_status": "estimated",
                                    "event_type": "track_started",
                                    "quality": "evaluable" if inside_zone else "outside_zone",
                                }
                            )
                        if evaluable and inside_zone:
                            crossing = counter.update(track_id, center)
                            if crossing is not None:
                                event_rows.append(
                                    {
                                        "clip_id": clip_id,
                                        "time_s": round(time_s, 3),
                                        "track_id": track_id,
                                        "recipe_id": recipe_id,
                                        "clip_origin": clip_origin,
                                        "measurement_status": "estimated",
                                        "event_type": "counted",
                                        "quality": "evaluable",
                                    }
                                )

                    color = (0, 200, 0) if track_id is not None else (0, 180, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    label = f"id={track_id}" if track_id is not None else "untracked"
                    cv2.putText(
                        frame,
                        f"{label} cls={class_index} {confidence:.2f}",
                        (x1, max(y1 - 7, 18)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        1,
                        cv2.LINE_AA,
                    )

            if not evaluable:
                counter.reset()
            occupancy.add(time_s, visible_in_zone, evaluable)

            cv2.polylines(frame, [zone_contour], True, (255, 180, 0), 2)
            cv2.line(
                frame,
                tuple(int(value) for value in line_start),
                tuple(int(value) for value in line_end),
                (255, 0, 255),
                2,
            )
            status = "EVALUABLE" if evaluable else "UNEVALUABLE"
            status_color = (0, 220, 0) if evaluable else (0, 165, 255)
            cv2.putText(
                frame,
                f"{status} | CV ESTIMATED | {clip_origin.upper()} | count={counter.total} | "
                f"zone detections={visible_in_zone}",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                status_color,
                2,
                cv2.LINE_AA,
            )
            writer.write(frame)
            frame_index += 1
    finally:
        capture.release()
        writer.release()

    if frame_index == 0:
        raise RuntimeError("Video contains no decodable frames")

    duration_s = frame_index / fps
    interval_rows = occupancy.rows(duration_s)
    for row in interval_rows:
        row["clip_origin"] = clip_origin
        row["measurement_status"] = "estimated"
    _write_csv(
        output_dir / "events.csv",
        [
            "clip_id",
            "time_s",
            "track_id",
            "recipe_id",
            "clip_origin",
            "measurement_status",
            "event_type",
            "quality",
        ],
        event_rows,
    )
    _write_csv(
        output_dir / "occupancy.csv",
        [
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
        interval_rows,
    )
    counted = sum(row["event_type"] == "counted" for row in event_rows)
    print(f"Annotated video: {annotated_path}")
    print(f"Events CSV: {output_dir / 'events.csv'}")
    print(f"Occupancy CSV: {output_dir / 'occupancy.csv'}")
    print(f"Directional counts: {counted} (visual demo only; not for billing)")


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    default_config = Path(__file__).resolve().parents[1] / "config" / "demo.yaml"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="input video file; keep originals outside Git")
    parser.add_argument("--model", type=Path, help="local YOLO weights file; not copied to outputs")
    parser.add_argument("--config", type=Path, default=default_config)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args(argv)

    config = _load_config(args.config)
    if args.model is None and config.get("model"):
        args.model = Path(config["model"])
    if args.model is None:
        parser.error("provide --model or set a local model path in the config")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        process_video(args.video, args.model, args.config, args.output_dir)
    except (FileNotFoundError, RuntimeError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())