
## Phase 5: Complete Architecture Migration (React + FastAPI)
The goal is to transition the frontend from Streamlit to a full React (Vite, TypeScript, Tailwind) application and expose the Python computer vision logic via a headless FastAPI backend.

### 5.1: Backend API Architecture (FastAPI)
- [ ] **Dependencies:** Add `fastapi`, `uvicorn`, `python-multipart`, and `websockets` to `pyproject.toml`.
- [ ] **API Scaffolding (`src/api.py`):** Set up the FastAPI app with CORS middleware and static file serving for raw videos and heatmap overlays.
- [ ] **Data Endpoints:**
  - `GET /api/videos` & `GET /api/videos/{video_id}`: List history and fetch specific video metadata.
  - `GET /api/events/{video_id}`: Streamlined endpoint for fetching and filtering event logs.
  - `GET /api/stats/{video_id}`: Generate numerical metrics (counts, duration).
- [ ] **Uploads & Processing:**
  - `POST /api/upload`: Handle `multipart/form-data` MP4 uploads and hash generation.
  - `POST /api/analyze/{video_id}`: Trigger the YOLO analysis in a background asyncio task.
- [ ] **Live Telemetry & Communication:**
  - `WS /ws/progress/{video_id}`: WebSocket or SSE endpoint for streaming live bounding boxes, frame counts, and FPS updates to the frontend during analysis.
- [ ] **Advanced Features API:**
  - `POST /api/query`: Expose the Natural Language Query Q&A endpoint.
  - `GET /api/reports/{video_id}`: Generate and serve the AI Security Incident Report (Markdown).
- [ ] **Testing:** Add `tests/test_api.py` to ensure all endpoints function correctly.

### 5.2: React Frontend Scaffolding & Setup (`frontend/`)
- [ ] **Initialization:** Run `npm create vite@latest frontend -- --template react-ts`.
- [ ] **Styling Setup:** Hook up Tailwind CSS, PostCSS, and install a component library (e.g., Shadcn UI or Headless UI).
- [ ] **Proxy Configuration:** Configure `vite.config.ts` to proxy `/api` requests to the FastAPI backend running on port 8000.
- [ ] **API Client:** Setup an HTTP client (Axios or Fetch wrappers) and generic WebSocket hooks for real-time state management.

### 5.3: React UI Components & Layouts
- [ ] **Shell & Navigation:** Build the top navigation bar, system status indicator, and dark/light theme toggle.
- [ ] **Upload & Analysis Config View:**
  - Drag-and-drop file uploader component.
  - Configuration controls (sliders for loitering threshold, parameter inputs).
  - ROI (Region of Interest) Polygon drawing tool over an HTML5 `<canvas>`.
- [ ] **Dashboard Metrics & HUD:** Build metric cards (Total Events, People, Unattended) and live progress bars.
- [ ] **Playback & Synchronization:**
  - Custom HTML5 Video Player with synced Timeline marking event occurrences.
- [ ] **Telemetry Tables & Charts:**
  - Implement a Gantt-style timeline chart (using Recharts).
  - Implement a paginated, filterable generic data table for the Event Log with a CSV export button.
- [ ] **Advanced Views (Heatmaps & AI):**
  - **Heatmap Viewer:** Toggleable spatial heatmap overlay mapped directly over the background video frame.
  - **AI Security Audit:** Chat-like interface for NL queries and a Markdown rendering component for the incident report.

### 5.4: DevOps & CI/CD Updates
- [ ] **Containerization:** Update `docker-compose.yml` to spin up two containers (`cctv_backend` and `cctv_frontend`), and refine `Dockerfile` (or create isolated `frontend.Dockerfile` / `backend.Dockerfile`).
- [ ] **GitHub Actions:** Update `.github/workflows/test.yml` to run React TS/Linting/Tests alongside the Python tests.
