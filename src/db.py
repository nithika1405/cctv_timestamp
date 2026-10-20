from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    video_hash TEXT UNIQUE,
    path TEXT NOT NULL,
    fps REAL NOT NULL,
    frame_count INTEGER NOT NULL,
    duration_seconds REAL NOT NULL,
    heatmap_path TEXT,
    roi_coords TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    timestamp_seconds REAL NOT NULL,
    object_label TEXT NOT NULL,
    tracking_id INTEGER,
    event_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    details TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_events_video_time ON events(video_id, timestamp_seconds);
CREATE INDEX IF NOT EXISTS idx_events_search ON events(object_label, event_type, tracking_id);
"""


class EventDatabase:
    def __init__(self, path: str | Path = "data/events.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        """Return a thread-local reusable connection."""
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._local.connection = conn
        return conn

    def close(self) -> None:
        """Close the thread-local connection if it exists."""
        conn = getattr(self._local, "connection", None)
        if conn is not None:
            conn.close()
            self._local.connection = None

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

            # Backward compatibility migration for older DBs
            existing_cols = {
                row["name"] for row in connection.execute("PRAGMA table_info(videos)").fetchall()
            }
            columns_to_add = {
                "video_hash": "TEXT",
                "heatmap_path": "TEXT",
                "roi_coords": "TEXT",
            }
            for col_name, col_type in columns_to_add.items():
                if col_name not in existing_cols:
                    connection.execute(f"ALTER TABLE videos ADD COLUMN {col_name} {col_type}")

            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_videos_hash ON videos(video_hash)")

    def create_video(self, filename: str, path: str, fps: float, frame_count: int, video_hash: str | None = None) -> int:
        duration = frame_count / fps if fps > 0 else 0.0
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO videos(filename, path, fps, frame_count, duration_seconds, video_hash) VALUES (?, ?, ?, ?, ?, ?)",
                (filename, path, fps, frame_count, duration, video_hash),
            )
            return int(cursor.lastrowid or 0)

    def update_video_meta(self, video_id: int, heatmap_path: str | None = None, roi_coords: str | None = None) -> None:
        """Update video record with persisted heatmap path and ROI coordinates."""
        if not heatmap_path and not roi_coords:
            return
        query = "UPDATE videos SET "
        sets: list[str] = []
        params: list[object] = []
        if heatmap_path:
            sets.append("heatmap_path = ?")
            params.append(heatmap_path)
        if roi_coords:
            sets.append("roi_coords = ?")
            params.append(roi_coords)

        query += ", ".join(sets) + " WHERE id = ?"
        params.append(video_id)

        with self.connect() as connection:
            connection.execute(query, params)

    def get_video_by_hash(self, video_hash: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM videos WHERE video_hash = ?", (video_hash,)).fetchone()
            return dict(row) if row else None

    def get_video(self, video_id: int) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
            return dict(row) if row else None

    def add_events(self, video_id: int, events: Iterable[dict]) -> None:
        rows = [
            (
                video_id,
                event["timestamp_seconds"],
                event["object_label"],
                event.get("tracking_id"),
                event["event_type"],
                event["confidence"],
                event.get("details", ""),
            )
            for event in events
        ]
        if not rows:
            return
        with self.connect() as connection:
            connection.executemany(
                """INSERT INTO events(
                    video_id, timestamp_seconds, object_label, tracking_id,
                    event_type, confidence, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )

    def list_events(self, video_id: int, search: str = "") -> list[dict]:
        query = "SELECT * FROM events WHERE video_id = ?"
        params: list[object] = [video_id]
        if search.strip():
            query += " AND (object_label LIKE ? OR event_type LIKE ? OR details LIKE ?)"
            pattern = f"%{search.strip()}%"
            params.extend([pattern, pattern, pattern])
        query += " ORDER BY timestamp_seconds, id"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    def delete_video(self, video_id: int) -> bool:
        video = self.get_video(video_id)
        if not video:
            return False

        video_path = Path(video["path"])
        if video_path.exists():
            video_path.unlink(missing_ok=True)

        heatmap_path = Path(video["heatmap_path"]) if video.get("heatmap_path") else None
        if heatmap_path and heatmap_path.exists():
            heatmap_path.unlink(missing_ok=True)

        with self.connect() as connection:
            result = connection.execute("DELETE FROM videos WHERE id = ?", (video_id,)).rowcount
        return result > 0

    def latest_video(self) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM videos ORDER BY id DESC LIMIT 1").fetchone()
            return dict(row) if row else None

    def list_videos(self) -> list[dict]:
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM videos ORDER BY id DESC"
            ).fetchall()]

    def event_summary(self, video_id: int) -> dict:
        """Return aggregate counts used for the metrics panel (single query)."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN object_label = 'person' THEN 1 ELSE 0 END) AS people,
                    SUM(CASE WHEN event_type = 'unattended' THEN 1 ELSE 0 END) AS unattended,
                    COUNT(DISTINCT CASE WHEN object_label != 'person' THEN tracking_id END) AS objects_detected
                FROM events WHERE video_id = ?""",
                (video_id,),
            ).fetchone()
        return {
            "total": row["total"] or 0,
            "people": row["people"] or 0,
            "unattended": row["unattended"] or 0,
            "objects_detected": row["objects_detected"] or 0,
        }

    def total_event_count(self) -> int:
        """Return the total number of events across all videos (single query)."""
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM events").fetchone()
            return row[0] or 0
