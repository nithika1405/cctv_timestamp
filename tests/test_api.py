import uuid
from io import BytesIO

from fastapi.testclient import TestClient

from src.api import AnalysisRequest, app, database


client = TestClient(app)


def test_health_endpoint_reports_service_status():
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "cctv-event-monitor"
    assert "database" in payload
    assert "uploads" in payload


def test_upload_rejects_invalid_file_type_and_empty_payload():
    response = client.post(
        "/api/upload",
        files={"file": ("notes.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400
    assert "supported" in response.json()["detail"].lower()

    empty_response = client.post(
        "/api/upload",
        files={"file": ("video.mp4", BytesIO(b""), "video/mp4")},
    )
    assert empty_response.status_code == 400
    assert "empty" in empty_response.json()["detail"].lower()


def test_delete_video_removes_video_and_events():
    video_hash = f"delete_test_hash_{uuid.uuid4().hex}"
    video_id = database.create_video(
        "delete_test.mp4",
        "data/uploads/delete_test.mp4",
        30.0,
        60,
        video_hash,
    )
    database.add_events(video_id, [{
        "timestamp_seconds": 1.0,
        "object_label": "person",
        "tracking_id": 1,
        "event_type": "person_entering",
        "confidence": 0.9,
        "details": "",
    }])

    response = client.delete(f"/api/videos/{video_id}")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert database.get_video(video_id) is None


def test_analysis_defaults_prefer_stronger_model_settings():
    assert AnalysisRequest.model_fields['model_name'].default == 'yolo11s.pt'
    assert AnalysisRequest.model_fields['tracker'].default == 'botsort.yaml'
    assert AnalysisRequest.model_fields['confidence_threshold'].default == 0.45
    assert AnalysisRequest.model_fields['scene_profile'].default == 'balanced'


def test_analysis_request_accepts_supported_scene_profiles():
    request = AnalysisRequest(
        video_path='video.mp4',
        video_hash='hash',
        filename='video.mp4',
        scene_profile='low_light',
    )
    assert request.scene_profile == 'low_light'


# ── Expanded test coverage ──────────────────────────────────────────────

def test_upload_valid_video_returns_hash_and_path():
    content = b"\x00" * 1024  # Minimal dummy video bytes
    response = client.post(
        "/api/upload",
        files={"file": ("test_clip.mp4", BytesIO(content), "video/mp4")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "video_hash" in payload
    assert payload["filename"] == "test_clip.mp4"
    assert payload["path"].endswith(".mp4")


def test_upload_deduplicates_identical_files():
    content = b"\xDE\xAD\xBE\xEF" * 256
    resp1 = client.post(
        "/api/upload",
        files={"file": ("dup1.mp4", BytesIO(content), "video/mp4")},
    )
    resp2 = client.post(
        "/api/upload",
        files={"file": ("dup2.mp4", BytesIO(content), "video/mp4")},
    )
    assert resp1.json()["video_hash"] == resp2.json()["video_hash"]
    assert resp1.json()["path"] == resp2.json()["path"]


def test_list_videos_returns_array():
    response = client.get("/api/videos")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_nonexistent_video_returns_404():
    response = client.get("/api/videos/999999")
    assert response.status_code == 404


def test_delete_nonexistent_video_returns_404():
    response = client.delete("/api/videos/999999")
    assert response.status_code == 404


def test_list_events_returns_array():
    video_hash = f"events_test_{uuid.uuid4().hex}"
    video_id = database.create_video(
        "events_test.mp4", "data/uploads/events_test.mp4", 30.0, 90, video_hash,
    )
    database.add_events(video_id, [
        {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1,
         "event_type": "person_entering", "confidence": 0.9, "details": ""},
    ])
    response = client.get(f"/api/events/{video_id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_list_events_search_filter():
    video_hash = f"search_test_{uuid.uuid4().hex}"
    video_id = database.create_video(
        "search_test.mp4", "data/uploads/search_test.mp4", 30.0, 90, video_hash,
    )
    database.add_events(video_id, [
        {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1,
         "event_type": "person_entering", "confidence": 0.9, "details": ""},
        {"timestamp_seconds": 2.0, "object_label": "backpack", "tracking_id": 2,
         "event_type": "unattended", "confidence": 0.85, "details": "left alone"},
    ])
    response = client.get(f"/api/events/{video_id}", params={"search": "backpack"})
    data = response.json()
    assert all(e["object_label"] == "backpack" for e in data)


def test_stats_endpoint_returns_counts():
    video_hash = f"stats_test_{uuid.uuid4().hex}"
    video_id = database.create_video(
        "stats_test.mp4", "data/uploads/stats_test.mp4", 30.0, 90, video_hash,
    )
    database.add_events(video_id, [
        {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1,
         "event_type": "person_entering", "confidence": 0.9, "details": ""},
        {"timestamp_seconds": 5.0, "object_label": "backpack", "tracking_id": 2,
         "event_type": "unattended", "confidence": 0.85, "details": ""},
    ])
    response = client.get(f"/api/stats/{video_id}")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total"] == 2
    assert stats["people"] == 1
    assert stats["unattended"] == 1


def test_stats_nonexistent_video_returns_404():
    response = client.get("/api/stats/999999")
    assert response.status_code == 404


def test_query_endpoint_returns_answer():
    video_hash = f"query_test_{uuid.uuid4().hex}"
    video_id = database.create_video(
        "query_test.mp4", "data/uploads/query_test.mp4", 30.0, 90, video_hash,
    )
    database.add_events(video_id, [
        {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1,
         "event_type": "person_entering", "confidence": 0.9, "details": ""},
    ])
    response = client.post("/api/query", json={"video_id": video_id, "question": "any people?"})
    assert response.status_code == 200
    assert "answer" in response.json()


def test_report_endpoint_returns_report():
    video_hash = f"report_test_{uuid.uuid4().hex}"
    video_id = database.create_video(
        "report_test.mp4", "data/uploads/report_test.mp4", 30.0, 90, video_hash,
    )
    database.add_events(video_id, [
        {"timestamp_seconds": 1.0, "object_label": "person", "tracking_id": 1,
         "event_type": "person_entering", "confidence": 0.9, "details": ""},
    ])
    response = client.post("/api/report", json={"video_id": video_id})
    assert response.status_code == 200
    assert "report" in response.json()
    assert len(response.json()["report"]) > 0


def test_report_nonexistent_video_returns_404():
    response = client.post("/api/report", json={"video_id": 999999})
    assert response.status_code == 404


def test_analyze_rejects_path_traversal():
    response = client.post("/api/analyze", json={
        "video_path": "../../etc/passwd",
        "video_hash": "fakehash",
        "filename": "malicious.mp4",
    })
    assert response.status_code in {400, 404}


def test_jobs_endpoint_returns_dict():
    response = client.get("/api/jobs")
    assert response.status_code == 200
    assert "jobs" in response.json()
