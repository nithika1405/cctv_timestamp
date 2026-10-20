from src.reporter import IncidentReporter


def test_calculate_risk_assessment_low():
    events = [
        {"event_type": "person_entering", "object_label": "person", "tracking_id": 1, "timestamp_seconds": 1.0},
        {"event_type": "person_leaving", "object_label": "person", "tracking_id": 1, "timestamp_seconds": 5.0},
    ]
    risk = IncidentReporter.calculate_risk_assessment(events)
    assert risk["level"] == "LOW"
    assert risk["score"] == 0
    assert len(risk["factors"]) > 0


def test_calculate_risk_assessment_critical():
    events = [
        {"event_type": "unattended", "object_label": "backpack", "tracking_id": 2, "timestamp_seconds": 10.0},
        {"event_type": "unattended", "object_label": "box", "tracking_id": 3, "timestamp_seconds": 12.0},
        {"event_type": "zone_breach", "object_label": "person", "tracking_id": 1, "timestamp_seconds": 15.0},
    ]
    # score = 30 + 30 + 25 = 85 -> CRITICAL
    risk = IncidentReporter.calculate_risk_assessment(events)
    assert risk["level"] == "CRITICAL"
    assert risk["score"] >= 80


def test_generate_offline_report():
    video_meta = {"filename": "test_cctv.mp4", "duration_seconds": 45.0, "created_at": "2026-09-23 12:00:00"}
    events = [
        {"event_type": "zone_breach", "object_label": "person", "tracking_id": 5, "timestamp_seconds": 14.2, "details": "Entered restricted zone"},
        {"event_type": "loitering", "object_label": "person", "tracking_id": 5, "timestamp_seconds": 30.0, "details": "Lingering 15s"},
    ]
    reporter = IncidentReporter()
    report = reporter.generate_offline_report(video_meta, events)
    assert "CCTV Security Incident Audit Report" in report
    assert "test_cctv.mp4" in report
    assert "ZONE_BREACH" in report
    assert "LOITERING" in report
    assert "Operational Recommendations" in report
