from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.analyzer import AnalysisResult, VideoAnalyzer


def test_analyzer_init():
    analyzer = VideoAnalyzer(
        model_name="yolo11n.pt",
        tracker="bytetrack.yaml",
        unattended_after_seconds=5.0,
        proximity_ratio=0.8,
        loitering_threshold_seconds=10.0,
        roi_polygon=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
    )
    assert analyzer.unattended_after_seconds == 5.0
    assert analyzer.proximity_ratio == 0.8
    assert analyzer.loitering_threshold_seconds == 10.0
    assert analyzer.raw_roi_polygon is not None
    assert len(analyzer.raw_roi_polygon) == 4


def test_analyzer_observations_empty():
    assert VideoAnalyzer._observations([], {}, 0.0) == []

    mock_result = MagicMock()
    mock_result.boxes = None
    assert VideoAnalyzer._observations([mock_result], {}, 0.0) == []


def test_analyzer_observations_parsing():
    mock_result = MagicMock()
    mock_boxes = MagicMock()

    mock_boxes.id.int().cpu().tolist.return_value = [101, 102, 103]
    mock_boxes.cls.int().cpu().tolist.return_value = [0, 24, 67]
    mock_boxes.conf.cpu().tolist.return_value = [0.95, 0.88, 0.72]
    mock_boxes.xyxy.cpu().tolist.return_value = [
        [10.0, 20.0, 50.0, 100.0],
        [60.0, 70.0, 90.0, 110.0],
        [200.0, 200.0, 250.0, 260.0],
    ]
    mock_result.boxes = mock_boxes

    names = {0: "person", 24: "backpack", 67: "cell phone", 999: "car"}

    obs = VideoAnalyzer._observations([mock_result], names, 2.5)
    assert len(obs) == 3

    assert obs[0].tracking_id == 101
    assert obs[0].label == "person"
    assert obs[0].confidence == 0.95
    assert obs[0].timestamp_seconds == 2.5

    assert obs[1].tracking_id == 102
    assert obs[1].label == "backpack"

    # "cell phone" should be aliased to "phone"
    assert obs[2].tracking_id == 103
    assert obs[2].label == "phone"


def test_analyzer_observations_without_tracking_ids_fallback():
    mock_result = MagicMock()
    mock_boxes = MagicMock()
    mock_boxes.id = None
    mock_boxes.cls.int().cpu().tolist.return_value = [0, 24]
    mock_boxes.conf.cpu().tolist.return_value = [0.91, 0.76]
    mock_boxes.xyxy.cpu().tolist.return_value = [
        [10.0, 20.0, 50.0, 100.0],
        [60.0, 70.0, 90.0, 110.0],
    ]
    mock_result.boxes = mock_boxes

    names = {0: "person", 24: "backpack"}

    obs = VideoAnalyzer._observations([mock_result], names, 1.5)
    assert len(obs) == 2
    assert obs[0].tracking_id == 0
    assert obs[0].label == "person"
    assert obs[1].tracking_id == 1
    assert obs[1].label == "backpack"


def test_analyzer_invalid_video_path():
    analyzer = VideoAnalyzer()
    with pytest.raises(ValueError, match="Could not open video"):
        analyzer.analyze("non_existent_video_path_xyz123.mp4")


@patch("src.analyzer.cv2.VideoCapture")
@patch("src.analyzer.YOLO")
def test_analyzer_mock_run(mock_yolo_cls, mock_capture_cls):
    # Mock VideoCapture
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.side_effect = lambda prop: {
        5: 30.0,   # CAP_PROP_FPS
        7: 2.0,    # CAP_PROP_FRAME_COUNT
        3: 640,    # CAP_PROP_FRAME_WIDTH
        4: 480,    # CAP_PROP_FRAME_HEIGHT
    }.get(prop, 0.0)

    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # 2 frames then EOF
    mock_cap.read.side_effect = [(True, dummy_frame), (True, dummy_frame), (False, None)]
    mock_capture_cls.return_value = mock_cap

    # Mock YOLO
    mock_model = MagicMock()
    mock_model.names = {0: "person"}

    mock_yolo_result = MagicMock()
    mock_boxes = MagicMock()
    mock_boxes.id.int().cpu().tolist.return_value = [1]
    mock_boxes.cls.int().cpu().tolist.return_value = [0]
    mock_boxes.conf.cpu().tolist.return_value = [0.9]
    mock_boxes.xyxy.cpu().tolist.return_value = [[100.0, 100.0, 200.0, 300.0]]
    mock_yolo_result.boxes = mock_boxes
    mock_yolo_result.plot.return_value = dummy_frame

    mock_model.track.return_value = [mock_yolo_result]
    mock_yolo_cls.return_value = mock_model

    progress_calls = []
    def on_progress(p, metrics):
        progress_calls.append((p, metrics))

    analyzer = VideoAnalyzer(
        roi_polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    )
    result = analyzer.analyze("mock_video.mp4", progress=on_progress)

    assert isinstance(result, AnalysisResult)
    assert result.fps == 30.0
    assert result.frame_count == 2
    assert result.first_frame is not None
    assert len(result.heatmap_points) == 2
    assert len(progress_calls) == 2
    assert mock_cap.release.called
