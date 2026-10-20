# CCTV Event Monitor - Improvement Roadmap

## Phase 1: UI/UX Polish & Quick Wins (Make it look good)
- [x] **Dashboard Metrics:** Add React metric cards at the top of the UI to show summary stats (e.g., Total Events, People Detected, Unattended Objects, Video Duration).
- [x] **Interactive Timeline Chart:** Show events over time with the React timeline chart.
- [x] **History Selector:** Add a sidebar selector to load previously analyzed videos from the SQLite database instead of re-uploading/re-analyzing.
- [x] **Configurable Thresholds:** Add controls for `unattended_after_seconds` and `proximity_ratio` so users can tune the heuristic detector.
- [x] **Export Feature:** Export the events table as a CSV from the UI.

## Phase 2: Core Functionality (Make it robust)
- [x] **Smart Caching:** Hash uploaded videos to detect if they've already been analyzed. If so, instantly load the results from the DB instead of re-running YOLO.
- [x] **Annotated Video Export:** Modify `VideoAnalyzer` to optionally write an `output.mp4` with bounding boxes, tracking IDs, and event labels drawn directly on the frames.
- [x] **Background Processing:** Run the VideoAnalyzer loop in a separate thread so analysis doesn't block the React interface, allowing smoother progress updates.
- [x] **Better Natural Language Search:** Upgrade `answer_question` to use NLP/Embeddings or an LLM API to handle complex questions instead of basic keyword matching.

## Phase 3: High Novelty Features (The "Wow" Factor)
- [x] **Region of Interest (ROI) Zone & Alerts:** Configurable polygon zones on footage, OpenCV point-in-polygon checks (`cv2.pointPolygonTest`), and automatic `zone_breach` / `zone_entry` event alerts.
- [x] **Spatial Activity Heatmap Overlay:** Track bounding box centers across all frames and generate a Gaussian-blurred, colormap-blended heatmap with category filtering and PNG export.
- [x] **AI Security Incident Reports:** Automated security risk scoring (0-100, LOW/MEDIUM/HIGH/CRITICAL) and incident audit report generator in `src/reporter.py` with offline Markdown synthesis and optional Claude LLM generation.
- [x] **Loitering & Dwell Time Detection:** Track dwell-time monitoring with configurable threshold (`loitering_threshold_seconds`), emitting `loitering` events when individuals linger.

## Phase 4: DevOps & Code Quality
- [x] **Linting & Formatting:** Add `ruff` and `mypy` configurations to `pyproject.toml`.
- [x] **Expanded Testing:** Write tests for `src/db.py`, `src/analyzer.py`, and the `answer_question` logic.
- [x] **Dockerization:** Add a `Dockerfile` and `docker-compose.yml` for easy deployment.
- [x] **CI/CD:** Add a `.github/workflows/test.yml` to run `pytest` automatically on push.
