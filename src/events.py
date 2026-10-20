from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from math import hypot

import cv2
import numpy as np


@dataclass(frozen=True)
class Observation:
    timestamp_seconds: float
    label: str
    tracking_id: int
    confidence: float
    bbox: tuple[float, float, float, float]

    @property
    def center(self) -> tuple[float, float]:
        left, top, right, bottom = self.bbox
        return ((left + right) / 2, (top + bottom) / 2)


@dataclass
class Event:
    timestamp_seconds: float
    object_label: str
    tracking_id: int | None
    event_type: str
    confidence: float
    details: str = ""

    def as_dict(self) -> dict:
        return {
            "timestamp_seconds": self.timestamp_seconds,
            "object_label": self.object_label,
            "tracking_id": self.tracking_id,
            "event_type": self.event_type,
            "confidence": self.confidence,
            "details": self.details,
        }


@dataclass
class TrackState:
    first_seen: float
    last_seen: float
    label: str
    confidence: float
    near_person: bool = False
    had_person_contact: bool = False
    last_near_change: float = 0.0
    unattended_emitted: bool = False
    last_bbox: tuple[float, float, float, float] = field(default=(0, 0, 0, 0))
    loitering_emitted: bool = False
    in_roi: bool = False
    roi_first_seen: float | None = None


class EventDetector:
    """Turns tracked observations into explainable, timestamped events."""

    def __init__(
        self,
        unattended_after_seconds: float = 8.0,
        proximity_ratio: float = 0.75,
        loitering_threshold_seconds: float = 15.0,
        roi_polygon: list[tuple[float, float]] | np.ndarray | None = None,
    ) -> None:
        self.unattended_after_seconds = unattended_after_seconds
        self.proximity_ratio = proximity_ratio
        self.loitering_threshold_seconds = loitering_threshold_seconds

        self.roi_polygon: np.ndarray | None
        if roi_polygon is not None and len(roi_polygon) >= 3:
            self.roi_polygon = np.array(roi_polygon, dtype=np.int32).reshape((-1, 1, 2))
        else:
            self.roi_polygon = None

        self.states: dict[tuple[str, int], TrackState] = {}
        self.last_timestamp = 0.0
        self.events: list[Event] = []

    def _in_roi(self, point: tuple[float, float]) -> bool:
        """Return True if point (x, y) is inside the configured ROI polygon."""
        if self.roi_polygon is None:
            return False
        return cv2.pointPolygonTest(self.roi_polygon, (float(point[0]), float(point[1])), False) >= 0

    @staticmethod
    def _near_person(
        object_observation: Observation,
        people: Iterable[Observation],
        proximity_ratio: float = 0.75,
    ) -> bool:
        object_x, object_y = object_observation.center
        object_width = max(object_observation.bbox[2] - object_observation.bbox[0], 1.0)
        object_height = max(object_observation.bbox[3] - object_observation.bbox[1], 1.0)
        object_radius = max(object_width, object_height) * 2.0
        for person in people:
            person_x, person_y = person.center
            person_width = max(person.bbox[2] - person.bbox[0], 1.0)
            person_height = max(person.bbox[3] - person.bbox[1], 1.0)
            distance = hypot(object_x - person_x, object_y - person_y)
            if distance <= max(object_radius, max(person_width, person_height) * 0.75) * proximity_ratio:
                return True
        return False

    def process(self, observations: list[Observation]) -> list[Event]:
        if not observations:
            self.last_timestamp += 0.04
            return []
        timestamp = max(item.timestamp_seconds for item in observations)
        self.last_timestamp = timestamp
        people = [item for item in observations if item.label == "person"]
        seen_keys: set[tuple[str, int]] = set()
        new_events: list[Event] = []

        for item in observations:
            key = (item.label, item.tracking_id)
            seen_keys.add(key)
            near_person = item.label != "person" and self._near_person(
                item, people, self.proximity_ratio
            )
            point_in_roi = self._in_roi(item.center)
            state = self.states.get(key)

            if state is None:
                state = TrackState(
                    first_seen=timestamp,
                    last_seen=timestamp,
                    label=item.label,
                    confidence=item.confidence,
                    near_person=near_person,
                    had_person_contact=near_person,
                    last_near_change=timestamp,
                    unattended_emitted=False,
                    last_bbox=item.bbox,
                    loitering_emitted=False,
                    in_roi=point_in_roi,
                    roi_first_seen=timestamp if point_in_roi else None,
                )
                self.states[key] = state

                # Standard entering / appearing event
                event_type = "person_entering" if item.label == "person" else "object_appeared"
                new_events.append(Event(timestamp, item.label, item.tracking_id, event_type, item.confidence))

                # Zone breach on first appearance inside ROI
                if point_in_roi:
                    etype = "zone_breach" if item.label == "person" else "zone_entry"
                    new_events.append(Event(
                        timestamp, item.label, item.tracking_id, etype, item.confidence,
                        "Detected inside restricted zone",
                    ))
                continue

            state.last_seen = timestamp
            state.confidence = item.confidence
            state.last_bbox = item.bbox

            # ── ROI zone transitions ──────────────────────────────────────────
            if self.roi_polygon is not None:
                was_in_roi = state.in_roi
                state.in_roi = point_in_roi
                if point_in_roi and not was_in_roi:
                    state.roi_first_seen = timestamp
                    etype = "zone_breach" if item.label == "person" else "zone_entry"
                    new_events.append(Event(
                        timestamp, item.label, item.tracking_id, etype, item.confidence,
                        "Entered restricted zone",
                    ))

            # ── Placed / picked-up / unattended logic ─────────────────────────
            if item.label != "person" and near_person != state.near_person:
                previous = state.near_person
                state.near_person = near_person
                state.last_near_change = timestamp
                if near_person:
                    state.had_person_contact = True
                    state.unattended_emitted = False
                    if not previous:
                        new_events.append(Event(timestamp, item.label, item.tracking_id, "picked_up", item.confidence, "Object is near a person"))
                elif state.had_person_contact:
                    new_events.append(Event(timestamp, item.label, item.tracking_id, "placed", item.confidence, "Object separated from person"))

            if item.label != "person" and state.had_person_contact and not state.near_person and not state.unattended_emitted:
                if timestamp - state.last_near_change >= self.unattended_after_seconds:
                    state.unattended_emitted = True
                    new_events.append(Event(timestamp, item.label, item.tracking_id, "unattended", item.confidence, f"No nearby person for {self.unattended_after_seconds:.0f}s"))

            # ── Loitering detection (person dwell time) ───────────────────────
            if item.label == "person" and not state.loitering_emitted:
                dwell_time = timestamp - state.first_seen
                if dwell_time >= self.loitering_threshold_seconds:
                    state.loitering_emitted = True
                    new_events.append(Event(
                        timestamp, item.label, item.tracking_id, "loitering", item.confidence,
                        f"Person lingering for {dwell_time:.1f}s",
                    ))

        self.events.extend(new_events)
        return new_events

    def finalize(self, timestamp_seconds: float | None = None) -> list[Event]:
        timestamp = self.last_timestamp if timestamp_seconds is None else timestamp_seconds
        final_events: list[Event] = []
        for (label, tracking_id), state in list(self.states.items()):
            event_type = "person_leaving" if label == "person" else "object_disappeared"
            final_events.append(Event(timestamp, label, tracking_id, event_type, state.confidence))
        self.events.extend(final_events)
        return final_events
