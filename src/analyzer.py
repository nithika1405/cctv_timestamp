from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from .events import Event, EventDetector, Observation

TARGET_LABELS = {"person", "backpack", "bottle", "cell phone", "suitcase", "box", "phone"}
LABEL_ALIASES = {"cell phone": "phone", "suitcase": "box"}
SCENE_PROFILES = {
    "balanced": {"imgsz": 640, "max_det": 300, "low_light": False},
    "crowded": {"imgsz": 960, "max_det": 500, "low_light": False},
    "low_light": {"imgsz": 960, "max_det": 300, "low_light": True},
    "outdoor": {"imgsz": 768, "max_det": 300, "low_light": False},
}

# Module-level model cache to avoid reloading YOLO weights on every analyze() call
_MODEL_CACHE: dict[str, YOLO] = {}


def _get_model(model_name: str) -> YOLO:
    """Return a cached YOLO model, loading it only on first use."""
    if model_name not in _MODEL_CACHE:
        _MODEL_CACHE[model_name] = YOLO(model_name)
    return _MODEL_CACHE[model_name]


@dataclass
class HeatmapPoint:
    x: float
    y: float
    label: str
    timestamp_seconds: float


@dataclass
class AnalysisResult:
    fps: float
    frame_count: int
    events: list[Event]
    first_frame: np.ndarray | None = None
    heatmap_points: list[HeatmapPoint] = field(default_factory=list)
    video_dimensions: tuple[int, int] = (0, 0)


def normalize_roi_polygon(
    polygon: list[tuple[float, float]],
    width: int,
    height: int,
) -> np.ndarray:
    """Converts normalized (0.0 to 1.0) coordinates into integer pixel contours."""
    pts = []
    for x, y in polygon:
        pts.append([int(x * width), int(y * height)])
    return np.array(pts, dtype=np.int32).reshape((-1, 1, 2))


def generate_heatmap_overlay(
    background_frame: np.ndarray,
    points: list[HeatmapPoint],
    filter_label: str | None = None,
    colormap: int = cv2.COLORMAP_JET,
    alpha: float = 0.6,
    blur_radius: int = 45,
    roi_polygon: np.ndarray | None = None,
) -> np.ndarray:
    """Generates a Gaussian smoothed heatmap blended over the background frame."""
    if background_frame is None:
        raise ValueError("Background frame is required.")

    height, width = background_frame.shape[:2]
    accum = np.zeros((height, width), dtype=np.float32)

    for pt in points:
        if filter_label and pt.label != filter_label:
            continue
        cx, cy = int(pt.x), int(pt.y)
        if 0 <= cx < width and 0 <= cy < height:
            accum[cy, cx] += 1.0

    # Ensure blur radius is odd
    blur_radius = blur_radius if blur_radius % 2 != 0 else blur_radius + 1

    blurred = cv2.GaussianBlur(accum, (blur_radius, blur_radius), sigmaX=blur_radius//3, sigmaY=blur_radius//3)

    if blurred.max() > 0:
        blurred = cv2.normalize(blurred, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U) # type: ignore
    else:
        blurred = blurred.astype(np.uint8)

    colored_map = cv2.applyColorMap(blurred, colormap)

    # Mask out areas with minimal density so background shows cleanly
    mask = blurred > 10

    blended = cv2.addWeighted(background_frame, 1.0 - alpha, colored_map, alpha, 0)
    output = background_frame.copy()
    output[mask] = blended[mask]

    if roi_polygon is not None:
        cv2.polylines(output, [roi_polygon], isClosed=True, color=(0, 255, 255), thickness=3)

    return output


class VideoAnalyzer:
    def __init__(
        self,
        model_name: str = "yolo11s.pt",
        tracker: str = "botsort.yaml",
        unattended_after_seconds: float = 8.0,
        proximity_ratio: float = 0.75,
        loitering_threshold_seconds: float = 15.0,
        roi_polygon: list[tuple[float, float]] | None = None,
        confidence_threshold: float = 0.45,
        scene_profile: str = "balanced",
    ) -> None:
        if scene_profile not in SCENE_PROFILES:
            raise ValueError(f"Unsupported scene profile: {scene_profile}")
        self.model_name = model_name
        self.tracker = tracker
        self.unattended_after_seconds = unattended_after_seconds
        self.proximity_ratio = proximity_ratio
        self.loitering_threshold_seconds = loitering_threshold_seconds
        self.raw_roi_polygon = roi_polygon
        self.confidence_threshold = confidence_threshold
        self.scene_profile = scene_profile

    def analyze(
        self,
        video_path: str | Path,
        progress: Callable[[float, dict], None] | None = None,
        sample_every_n_frames: int = 1,
        export_path: str | Path | None = None,
    ) -> AnalysisResult:
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        first_frame = None
        heatmap_points: list[HeatmapPoint] = []

        pixel_roi = None
        if self.raw_roi_polygon:
            pixel_roi = normalize_roi_polygon(self.raw_roi_polygon, width, height)

        writer = None
        if export_path:
            fourcc = cv2.VideoWriter.fourcc(*"mp4v") if hasattr(cv2.VideoWriter, "fourcc") else cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore
            writer = cv2.VideoWriter(str(export_path), fourcc, fps, (width, height))

        model = _get_model(self.model_name)
        names = model.names if hasattr(model, "names") else {}
        class_ids = [class_id for class_id, name in names.items() if name in TARGET_LABELS]

        detector = EventDetector(
            unattended_after_seconds=self.unattended_after_seconds,
            proximity_ratio=self.proximity_ratio,
            loitering_threshold_seconds=self.loitering_threshold_seconds,
            roi_polygon=pixel_roi,
        )
        profile = SCENE_PROFILES[self.scene_profile]
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)) if profile["low_light"] else None
        frame_index = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                if first_frame is None:
                    first_frame = frame.copy()

                annotated_frame = frame
                if frame_index % sample_every_n_frames == 0:
                    timestamp = frame_index / fps
                    detection_frame = frame
                    if clahe is not None:
                        lab_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
                        lightness, channel_a, channel_b = cv2.split(lab_frame)
                        enhanced_lightness = clahe.apply(lightness)
                        detection_frame = cv2.cvtColor(
                            cv2.merge((enhanced_lightness, channel_a, channel_b)),
                            cv2.COLOR_LAB2BGR,
                        )
                    results = model.track(
                        detection_frame,
                        persist=True,
                        tracker=self.tracker,
                        classes=class_ids or None,
                        conf=self.confidence_threshold,
                        iou=0.45,
                        imgsz=profile["imgsz"],
                        max_det=profile["max_det"],
                        verbose=False,
                    )
                    observations = self._observations(results, names, timestamp)
                    observations = [obs for obs in observations if obs.confidence >= self.confidence_threshold]
                    new_events = detector.process(observations)

                    for obs in observations:
                        cx, cy = obs.center
                        heatmap_points.append(HeatmapPoint(cx, cy, obs.label, timestamp))

                    if export_path and results:
                        annotated_frame = results[0].plot()

                        if pixel_roi is not None:
                            cv2.polylines(annotated_frame, [pixel_roi], True, (0, 255, 255), 2)

                        if new_events:
                            y_offset = 30
                            for ev in new_events:
                                text = f"NEW EVENT: {ev.event_type.upper()} ({ev.object_label})"
                                cv2.putText(annotated_frame, text, (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                                y_offset += 30

                if writer:
                    writer.write(annotated_frame)

                frame_index += 1
                if progress and frame_count:
                    metrics = {
                        "fps": fps,
                        "frame_index": frame_index,
                        "timestamp_seconds": frame_index / fps,
                    }
                    progress(min(frame_index / frame_count, 1.0), metrics)
        finally:
            capture.release()
            if writer:
                writer.release()

        detector.finalize(frame_index / fps if fps else 0.0)

        return AnalysisResult(
            fps=fps,
            frame_count=frame_count,
            events=detector.events,
            first_frame=first_frame,
            heatmap_points=heatmap_points,
            video_dimensions=(width, height)
        )

    @staticmethod
    def _observations(results, names: dict, timestamp: float) -> list[Observation]:
        if not results:
            return []
        boxes = results[0].boxes
        if boxes is None:
            return []

        observations: list[Observation] = []
        classes = boxes.cls.int().cpu().tolist() if boxes.cls is not None else []
        confidences = boxes.conf.cpu().tolist() if boxes.conf is not None else []
        coordinates = boxes.xyxy.cpu().tolist() if boxes.xyxy is not None else []

        tracked_ids = boxes.id.int().cpu().tolist() if boxes.id is not None else None

        for index, (class_id, confidence, bbox) in enumerate(zip(classes, confidences, coordinates, strict=False)):
            raw_label = names.get(class_id, str(class_id))
            if raw_label not in TARGET_LABELS:
                continue

            tracking_id = tracked_ids[index] if tracked_ids is not None and index < len(tracked_ids) else index
            observations.append(
                Observation(
                    timestamp,
                    LABEL_ALIASES.get(raw_label, raw_label),
                    int(tracking_id),
                    float(confidence),
                    (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                )
            )

        return observations
