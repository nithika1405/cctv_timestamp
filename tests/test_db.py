import tempfile
from pathlib import Path

from src.db import EventDatabase


def _make_db():
    """Create a fresh temporary database for testing."""
    tmpdir = tempfile.mkdtemp()
    return EventDatabase(Path(tmpdir) / "test_events.db")


def test_db_crud_and_phase3_meta():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_events.db"
        db = EventDatabase(db_path)

        # Create video
        vid = db.create_video("cctv_test.mp4", "/path/to/cctv_test.mp4", 30.0, 300, "hash123")
        assert vid == 1

        # Fetch video by hash and id
        by_hash = db.get_video_by_hash("hash123")
        assert by_hash is not None
        assert by_hash["filename"] == "cctv_test.mp4"

        by_id = db.get_video(vid)
        assert by_id is not None
        assert by_id["duration_seconds"] == 10.0

        # Update metadata (heatmap and ROI)
        db.update_video_meta(vid, heatmap_path="/path/to/heatmap.png", roi_coords="[[0,0],[1,1]]")
        updated = db.get_video(vid)
        assert updated["heatmap_path"] == "/path/to/heatmap.png"
        assert updated["roi_coords"] == "[[0,0],[1,1]]"

        # Add events and check summary
        events = [
            {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1, "event_type": "person_entering", "confidence": 0.9, "details": ""},
            {"timestamp_seconds": 3.0, "object_label": "backpack", "tracking_id": 2, "event_type": "unattended", "confidence": 0.85, "details": ""},
        ]
        db.add_events(vid, events)
        summary = db.event_summary(vid)
        assert summary["total"] == 2
        assert summary["people"] == 1
        assert summary["unattended"] == 1

        # Close connection before cleanup to avoid Windows file lock
        db.close()


# ── Expanded test coverage ──────────────────────────────────────────────

def test_list_videos_ordered_by_id_desc():
    db = _make_db()
    id1 = db.create_video("first.mp4", "/path/first.mp4", 30.0, 100, "hash_a")
    id2 = db.create_video("second.mp4", "/path/second.mp4", 25.0, 200, "hash_b")
    videos = db.list_videos()
    assert len(videos) == 2
    assert videos[0]["id"] == id2  # Most recent first
    assert videos[1]["id"] == id1


def test_latest_video_returns_most_recent():
    db = _make_db()
    db.create_video("old.mp4", "/path/old.mp4", 30.0, 100, "hash_old")
    db.create_video("new.mp4", "/path/new.mp4", 25.0, 200, "hash_new")
    latest = db.latest_video()
    assert latest is not None
    assert latest["filename"] == "new.mp4"


def test_latest_video_returns_none_when_empty():
    db = _make_db()
    assert db.latest_video() is None


def test_get_video_returns_none_for_missing_id():
    db = _make_db()
    assert db.get_video(999) is None


def test_get_video_by_hash_returns_none_for_missing():
    db = _make_db()
    assert db.get_video_by_hash("nonexistent_hash") is None


def test_list_events_returns_ordered_by_timestamp():
    db = _make_db()
    vid = db.create_video("order.mp4", "/path/order.mp4", 30.0, 100, "hash_order")
    db.add_events(vid, [
        {"timestamp_seconds": 5.0, "object_label": "person", "tracking_id": 1,
         "event_type": "loitering", "confidence": 0.8, "details": ""},
        {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1,
         "event_type": "person_entering", "confidence": 0.9, "details": ""},
        {"timestamp_seconds": 3.0, "object_label": "backpack", "tracking_id": 2,
         "event_type": "placed", "confidence": 0.85, "details": "near person"},
    ])
    events = db.list_events(vid)
    times = [e["timestamp_seconds"] for e in events]
    assert times == sorted(times)


def test_list_events_search_filters_by_label():
    db = _make_db()
    vid = db.create_video("search.mp4", "/path/search.mp4", 30.0, 100, "hash_search")
    db.add_events(vid, [
        {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1,
         "event_type": "person_entering", "confidence": 0.9, "details": ""},
        {"timestamp_seconds": 2.0, "object_label": "backpack", "tracking_id": 2,
         "event_type": "unattended", "confidence": 0.85, "details": "left alone"},
    ])
    filtered = db.list_events(vid, search="backpack")
    assert len(filtered) == 1
    assert filtered[0]["object_label"] == "backpack"


def test_list_events_search_filters_by_details():
    db = _make_db()
    vid = db.create_video("detail.mp4", "/path/detail.mp4", 30.0, 100, "hash_detail")
    db.add_events(vid, [
        {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1,
         "event_type": "person_entering", "confidence": 0.9, "details": "came from north"},
        {"timestamp_seconds": 2.0, "object_label": "person", "tracking_id": 2,
         "event_type": "loitering", "confidence": 0.8, "details": "near entrance"},
    ])
    filtered = db.list_events(vid, search="entrance")
    assert len(filtered) == 1
    assert "entrance" in filtered[0]["details"]


def test_list_events_empty_search_returns_all():
    db = _make_db()
    vid = db.create_video("all.mp4", "/path/all.mp4", 30.0, 100, "hash_all")
    db.add_events(vid, [
        {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1,
         "event_type": "person_entering", "confidence": 0.9, "details": ""},
        {"timestamp_seconds": 2.0, "object_label": "backpack", "tracking_id": 2,
         "event_type": "unattended", "confidence": 0.85, "details": ""},
    ])
    assert len(db.list_events(vid, search="")) == 2
    assert len(db.list_events(vid, search="   ")) == 2


def test_add_events_empty_list_is_noop():
    db = _make_db()
    vid = db.create_video("noop.mp4", "/path/noop.mp4", 30.0, 100, "hash_noop")
    db.add_events(vid, [])
    assert len(db.list_events(vid)) == 0


def test_event_summary_with_no_events():
    db = _make_db()
    vid = db.create_video("empty.mp4", "/path/empty.mp4", 30.0, 100, "hash_empty")
    summary = db.event_summary(vid)
    assert summary["total"] == 0
    assert summary["people"] == 0
    assert summary["unattended"] == 0
    assert summary["objects_detected"] == 0


def test_event_summary_counts_objects_detected():
    db = _make_db()
    vid = db.create_video("obj.mp4", "/path/obj.mp4", 30.0, 100, "hash_obj")
    db.add_events(vid, [
        {"timestamp_seconds": 1.0, "object_label": "backpack", "tracking_id": 10,
         "event_type": "placed", "confidence": 0.8, "details": ""},
        {"timestamp_seconds": 2.0, "object_label": "backpack", "tracking_id": 10,
         "event_type": "unattended", "confidence": 0.8, "details": ""},
        {"timestamp_seconds": 3.0, "object_label": "bottle", "tracking_id": 11,
         "event_type": "placed", "confidence": 0.7, "details": ""},
    ])
    summary = db.event_summary(vid)
    assert summary["objects_detected"] == 2  # tracking_id 10 and 11


def test_total_event_count():
    db = _make_db()
    vid1 = db.create_video("v1.mp4", "/path/v1.mp4", 30.0, 100, "hash_v1")
    vid2 = db.create_video("v2.mp4", "/path/v2.mp4", 30.0, 100, "hash_v2")
    db.add_events(vid1, [
        {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1,
         "event_type": "person_entering", "confidence": 0.9, "details": ""},
    ])
    db.add_events(vid2, [
        {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1,
         "event_type": "person_entering", "confidence": 0.9, "details": ""},
        {"timestamp_seconds": 2.0, "object_label": "person", "tracking_id": 1,
         "event_type": "loitering", "confidence": 0.8, "details": ""},
    ])
    assert db.total_event_count() == 3


def test_total_event_count_empty():
    db = _make_db()
    assert db.total_event_count() == 0


def test_delete_video_returns_false_for_missing():
    db = _make_db()
    assert db.delete_video(999) is False


def test_update_video_meta_partial_update():
    db = _make_db()
    vid = db.create_video("partial.mp4", "/path/partial.mp4", 30.0, 100, "hash_partial")

    # Only update heatmap_path
    db.update_video_meta(vid, heatmap_path="/path/heatmap.png")
    v = db.get_video(vid)
    assert v["heatmap_path"] == "/path/heatmap.png"
    assert v["roi_coords"] is None

    # Only update roi_coords
    db.update_video_meta(vid, roi_coords="[[0.1,0.2]]")
    v = db.get_video(vid)
    assert v["roi_coords"] == "[[0.1,0.2]]"


def test_update_video_meta_noop_when_nothing_provided():
    db = _make_db()
    vid = db.create_video("noop.mp4", "/path/noop2.mp4", 30.0, 100, "hash_noop2")
    db.update_video_meta(vid)  # Should not raise
    v = db.get_video(vid)
    assert v["heatmap_path"] is None


def test_duration_calculation():
    db = _make_db()
    vid = db.create_video("dur.mp4", "/path/dur.mp4", 24.0, 240, "hash_dur")
    v = db.get_video(vid)
    assert v["duration_seconds"] == 10.0  # 240 / 24.0


def test_duration_zero_fps():
    db = _make_db()
    vid = db.create_video("zero.mp4", "/path/zero.mp4", 0.0, 100, "hash_zero")
    v = db.get_video(vid)
    assert v["duration_seconds"] == 0.0
