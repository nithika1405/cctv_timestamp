import numpy as np

from src.analyzer import HeatmapPoint, generate_heatmap_overlay, normalize_roi_polygon


def test_normalize_roi_polygon():
    normalized = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
    pts = normalize_roi_polygon(normalized, 640, 480)
    assert pts.shape == (3, 1, 2)
    assert pts.dtype == np.int32
    assert (pts[0, 0] == [0, 0]).all()
    assert (pts[1, 0] == [320, 240]).all()
    assert (pts[2, 0] == [640, 480]).all()


def test_generate_heatmap_overlay():
    background = np.zeros((480, 640, 3), dtype=np.uint8)
    points = [
        HeatmapPoint(100.0, 100.0, "person", 1.0),
        HeatmapPoint(100.0, 100.0, "person", 1.5),
        HeatmapPoint(200.0, 200.0, "backpack", 2.0),
    ]

    overlay = generate_heatmap_overlay(background, points, alpha=0.5, blur_radius=31)
    assert overlay.shape == (480, 640, 3)
    assert overlay.dtype == np.uint8
    # Ensure there is non-zero content in the overlay near point (100, 100)
    assert np.any(overlay[90:110, 90:110] > 0)


def test_generate_heatmap_overlay_filter():
    background = np.zeros((200, 200, 3), dtype=np.uint8)
    points = [
        HeatmapPoint(50.0, 50.0, "bottle", 1.0),
    ]

    # Filter for 'person' when only 'bottle' exists -> should be empty heatmap
    overlay = generate_heatmap_overlay(background, points, filter_label="person", alpha=0.5)
    assert overlay.shape == (200, 200, 3)
    # Background should remain unmodified (all 0s)
    assert np.all(overlay == 0)


def test_generate_heatmap_overlay_with_roi():
    background = np.zeros((200, 200, 3), dtype=np.uint8)
    points = [HeatmapPoint(50.0, 50.0, "person", 1.0)]
    roi = np.array([[20, 20], [80, 20], [80, 80], [20, 80]], dtype=np.int32).reshape((-1, 1, 2))

    overlay = generate_heatmap_overlay(background, points, roi_polygon=roi)
    assert overlay.shape == (200, 200, 3)
    # ROI contour lines should be drawn in yellow (BGR: (0, 255, 255))
    assert np.any(overlay[:, :, 1] == 255)
