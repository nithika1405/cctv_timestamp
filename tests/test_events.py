from src.events import EventDetector, Observation


def test_proximity_ratio_scales_person_object_distance():
    person = Observation(1.0, "person", 1, 0.9, (0, 0, 20, 100))
    item = Observation(1.0, "backpack", 2, 0.9, (100, 40, 120, 60))

    assert not EventDetector._near_person(item, [person], proximity_ratio=1.0)
    assert EventDetector._near_person(item, [person], proximity_ratio=1.5)


def test_person_enters_and_leaves():
    detector = EventDetector()
    detector.process([Observation(1.0, "person", 4, 0.95, (0, 0, 100, 200))])
    events = detector.finalize(2.0)
    assert [event.event_type for event in detector.events] == ["person_entering", "person_leaving"]
    assert events[0].tracking_id == 4


def test_object_is_placed_then_becomes_unattended():
    detector = EventDetector(unattended_after_seconds=2.0)
    detector.process([
        Observation(1.0, "person", 1, 0.9, (0, 0, 100, 200)),
        Observation(1.0, "backpack", 9, 0.9, (40, 120, 80, 160)),
    ])
    detector.process([Observation(2.0, "backpack", 9, 0.85, (300, 300, 340, 340))])
    detector.process([Observation(4.1, "backpack", 9, 0.85, (300, 300, 340, 340))])
    event_types = [event.event_type for event in detector.events]
    assert "placed" in event_types
    assert "unattended" in event_types


def test_loitering_detection():
    detector = EventDetector(loitering_threshold_seconds=5.0)
    # Person first seen at t=1.0s
    detector.process([Observation(1.0, "person", 1, 0.9, (10, 10, 50, 100))])
    # Still there at t=3.0s (dwell time 2.0s < 5.0s -> no loitering yet)
    detector.process([Observation(3.0, "person", 1, 0.9, (12, 10, 52, 100))])
    assert "loitering" not in [e.event_type for e in detector.events]

    # Still there at t=6.5s (dwell time 5.5s >= 5.0s -> loitering alert emitted)
    detector.process([Observation(6.5, "person", 1, 0.9, (15, 10, 55, 100))])
    event_types = [e.event_type for e in detector.events]
    assert "loitering" in event_types

    # Ensure loitering isn't duplicate emitted for same track
    initial_loitering_count = sum(1 for e in detector.events if e.event_type == "loitering")
    detector.process([Observation(8.0, "person", 1, 0.9, (15, 10, 55, 100))])
    assert sum(1 for e in detector.events if e.event_type == "loitering") == initial_loitering_count


def test_roi_zone_breach_and_entry():
    # ROI polygon covering x: 100..300, y: 100..300
    roi = [(100, 100), (300, 100), (300, 300), (100, 300)]
    detector = EventDetector(roi_polygon=roi)

    # Person 1 outside ROI at (20, 20) -> person_entering only
    detector.process([Observation(1.0, "person", 1, 0.9, (10, 10, 30, 30))])
    assert "zone_breach" not in [e.event_type for e in detector.events]

    # Person 1 steps inside ROI (center: 150, 150) -> zone_breach emitted
    detector.process([Observation(2.0, "person", 1, 0.9, (140, 140, 160, 160))])
    event_types = [e.event_type for e in detector.events]
    assert "zone_breach" in event_types

    # Box 2 appears directly inside ROI -> object_appeared and zone_entry emitted
    detector.process([Observation(3.0, "box", 2, 0.85, (200, 200, 250, 250))])
    event_types = [e.event_type for e in detector.events]
    assert "zone_entry" in event_types
