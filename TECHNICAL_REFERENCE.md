# SmartPresence — Technical Reference Guide

> **Purpose**: A comprehensive guide to every import, variable, function, class, and design decision in the SmartPresence codebase. Written for a 3rd-year university AI & Software Development project defense.

---

# Part 1: Concept-Based Overview

## 1.1 Architecture & Design Decisions

### Why Flask (not Django)?

| Factor | Flask | Django |
|--------|-------|--------|
| **Size** | Micro-framework (~1 file to start) | Full-stack (ORM, admin panel, migrations built-in) |
| **Learning curve** | Minimal — add what you need | Must learn Django's way of doing everything |
| **Flexibility** | Choose your own DB, auth, etc. | Opinionated — uses its own ORM, template engine |
| **Our need** | REST API + HTML templates + video streaming | We don't need Django's admin, ORM, or forms |
| **Verdict** | ✅ **Chosen** — lightweight, perfect for single-purpose apps | Overkill for our scope |

Flask follows the **WSGI** (Web Server Gateway Interface) standard. Our app uses `app.run(threaded=True)` which means each HTTP request gets its own thread — important because our AI loop runs in a separate background thread.

### Why SQLite (not PostgreSQL/MySQL)?

| Factor | SQLite | PostgreSQL |
|--------|--------|------------|
| **Setup** | Zero — single `.db` file | Requires server installation + configuration |
| **Deployment** | Copy one file | Need a running database server |
| **Concurrency** | Single-writer (fine for us) | Multi-writer (needed for high-traffic apps) |
| **Scale** | Up to ~200 concurrent users | Thousands of concurrent users |
| **Our need** | One classroom, one camera, ~50 students | We don't need multi-server |
| **Verdict** | ✅ **Chosen** — zero-config, portable | Unnecessary complexity |

SQLite uses **file-level locking** — only one write operation at a time. This is fine because our system is single-process (one Flask server + one AI thread). If we needed to scale to university-level (1000+ students, multiple cameras), we would migrate to PostgreSQL.

### Why dlib (not OpenCV DNN / MTCNN)?

| Factor | dlib (HOG) | OpenCV DNN | MTCNN |
|--------|-----------|------------|-------|
| **Speed** | ~15ms/frame (CPU) | ~25ms/frame (CPU) | ~80ms/frame |
| **Accuracy** | Good for frontal faces | Better for angles | Best for difficult poses |
| **Dependencies** | Requires C++ build tools | Built into OpenCV | Requires TensorFlow |
| **Integration** | `face_recognition` library wraps it | Manual model loading | Heavy dependency |
| **Our need** | Classroom = frontal faces, controlled lighting | — | — |
| **Verdict** | ✅ **Chosen** — fast, accurate enough | Backup option | Too heavy |

The `face_recognition` library (by Adam Geitgey) is a Python wrapper around dlib's face recognition. It provides a simple API: `face_locations()` for detection, `face_encodings()` for 128-dim feature extraction, and `compare_faces()` for matching.

### Why Pickle (not JSON/DB) for Face Encodings?

Face encodings are **128-dimensional NumPy arrays** (128 float64 values per face). Pickle is used because:

- JSON cannot serialize NumPy arrays natively (would need conversion)
- Storing binary blobs in SQLite would complicate queries
- Pickle preserves the exact NumPy dtype — no precision loss
- Load/save is a single `pickle.load()`/`pickle.dump()` call

**Trade-off**: Pickle files are Python-specific and not human-readable. For a production system, we might store encodings as BLOBs in PostgreSQL. For our scope, pickle is simpler and faster.

### Why Brevo SMTP (not SendGrid / AWS SES)?

| Factor | Brevo | SendGrid | AWS SES |
|--------|-------|----------|---------|
| **Free tier** | 300 emails/day | 100 emails/day | 62,000/month (but requires AWS account) |
| **Setup** | Create account → get SMTP key | Similar | Complex IAM permissions |
| **Protocol** | Standard SMTP (port 587) | SMTP or REST API | SMTP or REST API |
| **Our need** | ~50 emails/class max | — | — |
| **Verdict** | ✅ **Chosen** — generous free tier, simple SMTP | Also good | Too complex |

We use standard Python `smtplib` with STARTTLS — no vendor-specific SDK needed. This means we could switch to any SMTP provider by changing `.env` variables.

---

## 1.2 Face Recognition Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Camera Feed │────▶│  Resize 0.5x │────▶│  BGR → RGB   │────▶│  Detect      │
│  (OpenCV)    │     │  (faster)    │     │  (cv2 color) │     │  (dlib HOG)  │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                      │
                     ┌──────────────┐     ┌──────────────┐            ▼
                     │  Log to DB   │◀────│  Match?      │◀────┌──────────────┐
                     │  (SQLite)    │     │  dist < 0.5  │     │  Encode      │
                     └──────────────┘     └──────────────┘     │  (128-dim)   │
                                                               └──────────────┘
```

### Key Terms

| Term | Meaning |
|------|---------|
| **HOG** | Histogram of Oriented Gradients — a feature descriptor that captures edge/gradient structure. Used by dlib for face detection. Faster than CNN on CPU. |
| **128-dim encoding** | A vector of 128 floating-point numbers that represents a face's identity. Two photos of the same person produce similar vectors (small Euclidean distance). |
| **Euclidean distance** | `sqrt(Σ(a_i - b_i)²)` — measures how "far apart" two face encodings are. Below 0.5 = same person. |
| **Tolerance** | The distance threshold (default 0.5). Lower = stricter matching (fewer false positives, more false negatives). Higher = more lenient. |
| **Detection scale** | Frame is resized to `scale × original` before detection. 0.5 = half size = 4× faster, but misses small/distant faces. |
| **BGR vs RGB** | OpenCV uses Blue-Green-Red channel order. dlib/face_recognition uses Red-Green-Blue. We convert with `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)`. |
| **dlib correlation tracking** | Instead of running recognition on every frame (expensive), we use `dlib.correlation_tracker()` between recognition cycles. It follows a face's position across frames using a correlation filter — much faster than re-encoding. |
| **Liveness detection** | *Planned but not yet implemented.* Would use MediaPipe Face Mesh to detect blinks via Eye Aspect Ratio (EAR). Currently, the system has no anti-spoofing — this is a known limitation. |

### Why 0.5 Tolerance?

The `face_recognition` library default is 0.6. We use 0.5 because:

- Classroom environment = controlled lighting, frontal faces
- Lower tolerance reduces false positives (marking wrong student present)
- False negatives (not recognizing a student) are less harmful — teacher can manually add them
- Trade-off: students with very similar faces might need tolerance adjustment in Settings

---

## 1.3 Authentication & Security Model

### Multi-Layer Security

```
Layer 1: Login (username + password)
    └─▶ Layer 2: Session (Flask cookie)
        └─▶ Layer 3: Role check (admin vs teacher)
            └─▶ Layer 4: PIN gate (for sensitive settings)
                └─▶ Layer 5: CSRF token (on all POST/PUT/DELETE)
```

### Key Security Terms

| Term | What It Is | Where Used |
|------|-----------|------------|
| **Password hashing** | `werkzeug.security.generate_password_hash()` — uses PBKDF2-SHA256 with salt. One-way: can verify but never reverse. | `init_db.py` (seed), `api.py` (login, user CRUD) |
| **Session cookie** | Flask stores `user_id` and `role` in a signed cookie. `HttpOnly` = JS can't read it. `SameSite=Lax` = prevents CSRF from external sites. | `app.py` config |
| **CSRF token** | Cross-Site Request Forgery protection. Every form/API call must include `X-CSRFToken` header. Generated by Flask-WTF. | `base.html` → `safeFetch()` |
| **Rate limiting** | Flask-Limiter restricts login attempts (e.g., 5/minute) to prevent brute-force attacks. | `app.py` → `api.py` login |
| **PIN gate** | Sensitive settings (changing passwords, environment variables) require a separate 4-digit PIN. | `api.py` → `verify_settings_pin()` |
| **Parameterized queries** | `cursor.execute("SELECT * FROM users WHERE id = ?", (id,))` — prevents SQL injection by separating code from data. | All database queries |
| **`escapeHtml()`** | Frontend function that converts `<script>` to `&lt;script&gt;` — prevents XSS (Cross-Site Scripting). | `base.html` |

### Why CSRF Exemptions?

Two endpoints are exempt from CSRF: `/api/auth/login` and `/api/lookup`. Because:

- **Login**: The user doesn't have a session yet, so they can't have a CSRF token
- **Lookup**: Public endpoint (no authentication), designed for students

---

## 1.4 Database Design

### Entity-Relationship Diagram

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│   users      │       │   students       │       │ class_schedules  │
├──────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)      │       │ id (PK)          │──┐    │ id (PK)          │──┐
│ username     │       │ name (UNIQUE)    │  │    │ day_of_week      │  │
│ display_name │       │ student_id       │  │    │ start_time       │  │
│ password_hash│       │ email            │  │    │ end_time          │  │
│ role         │       │ notes            │  │    │ class_name       │  │
│ created_at   │       │ created_at       │  │    │ teacher_email    │  │
└──────────────┘       └──────────────────┘  │    │ is_active        │  │
                                             │    │ created_at       │  │
                       ┌──────────────────┐  │    └──────────────────┘  │
                       │ attendance_logs  │  │                          │
                       ├──────────────────┤  │                          │
                       │ id (PK)          │  │                          │
                       │ student_id (FK) ─┼──┘                          │
                       │ timestamp        │                             │
                       │ status           │                             │
                       │ source           │                             │
                       │ notes            │                             │
                       │ last_seen        │                             │
                       │ schedule_id (FK)─┼─────────────────────────────┘
                       └──────────────────┘

┌──────────────┐       ┌──────────────────┐
│   cameras    │       │    settings      │
├──────────────┤       ├──────────────────┤
│ id (PK)      │       │ key (PK)         │
│ name         │       │ value            │
│ source       │       │ updated_at       │
│ type         │       └──────────────────┘
│ is_active    │
│ created_at   │
└──────────────┘
```

### Why These Indexes?

```sql
CREATE INDEX idx_attendance_student ON attendance_logs (student_id);
-- Speeds up: "Show me all attendance for student X" (student_detail page)

CREATE INDEX idx_attendance_timestamp ON attendance_logs (timestamp);
-- Speeds up: "Show me today's attendance" (dashboard, date filter)

CREATE INDEX idx_schedule_day ON class_schedules (day_of_week);
-- Speeds up: "What classes are on Monday?" (auto-schedule check every minute)
```

Without indexes, SQLite would do a **full table scan** (check every row). With indexes, it uses a **B-tree** lookup — O(log n) instead of O(n).

### Migration Strategy

We use `ALTER TABLE ADD COLUMN` for schema evolution (not a migration framework like Alembic). Why:

- SQLite doesn't support `ALTER TABLE DROP COLUMN` (before 3.35.0)
- Our migrations are simple (only adding columns)
- `init_db.py` checks `PRAGMA table_info(table_name)` to see which columns exist, then adds missing ones
- `IF NOT EXISTS` on CREATE TABLE makes the schema idempotent (safe to re-run)

---

## 1.5 Email Integration

### SMTP Flow

```
Python (smtplib)
    │
    ├─▶ Connect to smtp-relay.brevo.com:587
    ├─▶ STARTTLS (upgrade to encrypted connection)
    ├─▶ Login with SMTP_LOGIN + SMTP_KEY
    ├─▶ Send MIME message (HTML body)
    └─▶ Close connection
```

### Key Terms

| Term | Meaning |
|------|---------|
| **SMTP** | Simple Mail Transfer Protocol — the standard for sending emails |
| **STARTTLS** | Upgrades a plain text connection to TLS/SSL encrypted |
| **MIME** | Multipurpose Internet Mail Extensions — format for emails with HTML, attachments, etc. |
| **MIMEMultipart('alternative')** | Email with both plain text and HTML versions; client picks the best one |
| **Brevo** | Email service provider (formerly Sendinblue). Free tier: 300 emails/day |

### Three Email Types

1. **Student Report** — individual status email after class (Present ✅ / Late ⚠️ / Absent ❌)
2. **Teacher Summary** — class-level overview with present count, absent count, student lists
3. **Error Report** — system crashes/bugs sent to admin email for monitoring

---

## 1.6 Frontend Architecture

### Template Inheritance (Jinja2)

```
base.html (layout + sidebar + global JS/CSS)
    ├── login.html (standalone — no sidebar)
    ├── lookup.html (standalone — public page)
    ├── dashboard.html
    ├── students.html
    ├── student_detail.html
    ├── enroll.html
    ├── live.html
    ├── timetable.html
    ├── settings.html
    ├── report.html
    ├── user_management.html
    ├── debug.html
    └── 403.html
```

> **Note**: 14 templates total. There is no standalone `attendance.html` — attendance is displayed within `dashboard.html` and `student_detail.html`.

### Key Frontend Concepts

| Concept | What It Does | Where |
|---------|-------------|-------|
| **`safeFetch()`** | Wrapper around `fetch()` that auto-injects CSRF token and handles 401 redirects | `base.html` |
| **`escapeHtml()`** | Converts `<>&"'` to HTML entities — prevents XSS | `base.html` |
| **`showToast()`** | Displays Bootstrap toast notifications (success/error) | `base.html` |
| **Chart.js** | Renders attendance bar charts on dashboard | `dashboard.html` |
| **Bootstrap 5** | CSS framework for responsive layout, cards, modals, tables | All templates |
| **MJPEG stream** | `<img src="/video_feed">` — browser displays live camera as streaming JPEG frames | `live.html` |
| **`setInterval(5000)`** | Dashboard auto-refreshes stats and attendance table every 5 seconds | `dashboard.js` |

---

# Part 2: File-by-File Reference

## 2.1 `ai_module/common.py` — Shared Configuration

**Purpose**: Central configuration file. Every other module imports constants from here.

### Imports

| Import | Why |
|--------|-----|
| `os` | File paths (`os.path.join`), environment variables (`os.environ.get`) |
| `logging` | Python's built-in logging framework — structured log messages with timestamps and severity levels |

### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `PROJECT_ROOT` | Auto-detected | Absolute path to project root. Computed dynamically so the code works regardless of where it's installed |
| `ENCODINGS_PATH` | `ai_module/encodings.pickle` | Path to the serialized face encoding file |
| `DB_PATH` | `web_app/database/attendance.db` | Path to SQLite database |
| `CRASH_REPORTS_DIR` | `crash_reports/` | Directory for saved crash/bug reports |
| `ENV_PATH` | `.env` | Path to environment variables file |
| `CAMERA_ID` | `0` | Default USB camera index (0 = first camera) |
| `FRAME_WIDTH` / `FRAME_HEIGHT` | `1920` / `1080` | Camera resolution (Full HD) |
| `COLOR_GREEN`, `COLOR_RED`, etc. | BGR tuples | OpenCV uses BGR (not RGB). `(0, 255, 0)` = green in BGR |
| `TOLERANCE` | `0.5` | Face matching threshold. Distance below this = same person |
| `DETECTION_SCALE` | `0.5` | Resize factor before detection. 0.5 = half size = 4× faster |
| `FRAME_SKIP` | `30` | Legacy — originally skipped N frames between recognition runs |
| `LATE_THRESHOLD` | `10` | Minutes after class start before marking "Late" |
| `DISAPPEAR_THRESHOLD` | `15` | Minutes unseen before marking "Disappeared" |
| `RECHECK_INTERVAL` | `300` | Seconds between disappearance scans (5 minutes) |
| `SYSTEM_MODE` | `'auto'` | `'auto'` = follow schedule, `'force_on'` = always on, `'force_off'` = always off |
| `SETTINGS_PIN` | From `.env` | 4-digit PIN for sensitive settings access |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | From `.env` | For sending crash reports to Telegram |
| `VALID_STATUSES` | List of 8 strings | All allowed attendance status values |

### Functions

| Function | Signature | Purpose |
|----------|-----------|---------|
| `_load_env()` | `_load_env()` | Reads `.env` file line by line, parses `KEY=VALUE` pairs, loads into `os.environ`. Uses `setdefault` so existing env vars aren't overwritten. The underscore prefix means "private — not for external use" |
| `get_logger()` | `get_logger(name='smartpresence')` | Creates a configured Python logger with timestamp format `YYYY-MM-DD HH:MM:SS [LEVEL] name: message`. Uses `StreamHandler` (prints to console). Checks `if not logger.handlers` to prevent duplicate handlers on re-import |

---

## 2.2 `ai_module/recognition_system.py` — Core AI Engine

**Purpose**: The main face recognition loop. Detects faces, computes encodings, matches identities, logs attendance.

### Imports

| Import | Why | Alternative Considered |
|--------|-----|----------------------|
| `numpy as np` | NumPy — numerical computing library. Face encodings are `np.ndarray` (128-dim float64 vectors). Used for `np.argmin()` (find best match index) | None — NumPy is the standard for numerical Python |
| `cv2` | OpenCV — camera capture, image manipulation, color conversion, drawing rectangles/text on frames | Could use Pillow, but OpenCV has video capture built-in |
| `face_recognition` | High-level face detection + encoding API. Wraps dlib internally | Could use dlib directly, but this is simpler |
| `pickle` | Serialization — loading/saving face encodings to disk | Could use `json` but NumPy arrays aren't JSON-serializable |
| `os`, `sys` | File path manipulation, adding project root to `sys.path` | — |
| `sqlite3` | Database access — logging attendance records | Could use SQLAlchemy ORM, but raw SQL is simpler for our queries |
| `time` | `time.time()` for timestamps, `time.sleep()` for rate limiting | — |
| `threading` | Background thread for AI loop so it doesn't block the web server | Could use `multiprocessing` but threads share memory (simpler) |
| `dlib` | Direct dlib access for `correlation_tracker()` (inter-frame face tracking) and `dlib.DLIB_USE_CUDA` check | — |
| `datetime, timedelta` | Date/time arithmetic — "is this student late?" (compare current time vs class start + threshold) | — |

### Class: `FaceSystemThreaded`

This is the **main AI engine class**. One instance runs per server process.

#### Instance Variables (set in `__init__`)

| Variable | Type | Purpose |
|----------|------|---------|
| `self.encodings_data` | `dict` | `{"names": [...], "encodings": [...]}` loaded from pickle |
| `self.known_names` | `list[str]` | List of enrolled student names |
| `self.known_encodings` | `list[np.ndarray]` | List of 128-dim face encoding vectors |
| `self.latest_frame` | `np.ndarray` | Latest frame shared between capture thread and AI thread |
| `self.new_results_available` | `bool` | Flag indicating unprocessed detection results are ready |
| `self.detected_results` | `list[tuple]` | List of `(box, name)` pairs — results from last recognition run |
| `self.is_running` | `bool` | Flag to control the main loop. `False` = stop |
| `self.lock` | `threading.Lock` | Thread safety — prevents race conditions when two threads access shared data |
| `self.show_debug` | `bool` | Whether to overlay FPS/scale debug info on the video frame |
| `self.detector_name` | `str` | Currently active detector model name (`'dlib'` or `'mediapipe'`) — used for hot-swap detection |
| `self.detector` | `BaseDetector` | Face detector instance (DlibDetector or MediaPipeDetector) |
| `self.trackers` | `list[dlib.correlation_tracker]` | Active dlib correlation trackers — one per detected face, used to follow faces between recognition frames |
| `self.tracking_names` | `list[str]` | Names corresponding to each tracker (parallel array) |
| `self.session_logged` | `dict` | `{name: True}` — students already logged in current session. Prevents duplicate entries |
| `self.last_seen` | `dict` | `{name: timestamp}` — when each student was last seen. Used for disappearance checks |
| `self.last_disappear_check` | `float` | Timestamp of last disappearance scan |
| `self.settings_mgr` | `SettingsManager` | Reference via import — accessed as `SettingsManager.get()` (classmethod) |

#### Methods

| Method | Purpose |
|--------|---------|
| `__init__()` | Initializes all state, loads encodings, syncs students to DB |
| `_init_detector()` | Creates the appropriate detector based on settings (`'dlib'` or `'mediapipe'`) |
| `_check_settings_change()` | Compares current detector setting with active one — hot-swaps if changed |
| `load_encodings()` | Reads `encodings.pickle` file. Returns `{"names": [], "encodings": []}` if file missing |
| `sync_students_to_db()` | Ensures every name in pickle also exists in the `students` DB table |
| `get_active_schedule()` | Queries DB for class schedules matching current day/time. Returns schedule dict or None |
| `determine_status(schedule)` | Compares current time vs schedule start time. Returns `'On Time'`, `'Late'`, or `'Present'` |
| `log_attendance(name)` | Inserts attendance record into DB. Skips if already logged today. Links to active schedule |
| `check_disappearances()` | Every `RECHECK_INTERVAL` seconds, checks `last_seen` dict. If a student unseen for > `DISAPPEAR_THRESHOLD` minutes, logs "Disappeared" |
| `maybe_reset_session(schedule)` | Detects when schedule changes (new class starts). Resets `session_logged` and tracking state |
| `ai_loop()` | **Main loop**: capture frame → detect → encode → match → track → log. Runs until `self.is_running = False` |
| `start()` | Starts the AI loop in a background thread |

---

## 2.3 `ai_module/detectors.py` — Face Detection Strategy Pattern

**Purpose**: Implements the **Strategy design pattern** for swappable face detectors.

### Design Pattern: Strategy

```
BaseDetector (ABC)          ← Abstract base class
    ├── DlibDetector        ← HOG-based detection (default)
    └── MediaPipeDetector   ← Google MediaPipe detection (alternative)
```

**Why Strategy Pattern?** We wanted to support multiple detection backends without changing the recognition system code. The recognition system calls `self.detector.detect_faces(frame)` — it doesn't know or care which detector is behind it.

### Imports

| Import | Why |
|--------|-----|
| `from abc import ABC, abstractmethod` | `ABC` = Abstract Base Class. `@abstractmethod` forces subclasses to implement `detect_faces()`. If a subclass doesn't implement it, Python raises `TypeError` at instantiation |
| `mediapipe as mp` | Google's MediaPipe library — provides Face Detection, Face Mesh, Pose Estimation, etc. We use Face Detection |

### Classes

| Class | Detection Method | Speed | Accuracy |
|-------|-----------------|-------|----------|
| `DlibDetector` | HOG (Histogram of Oriented Gradients) via `face_recognition.face_locations(model="hog")` | ~15ms/frame | Good for frontal |
| `MediaPipeDetector` | SSD MobileNet (deep learning) via `mp.solutions.face_detection` | ~10ms/frame | Better at angles |

### Key Variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `HAS_MEDIAPIPE` | Module level | Boolean flag — `True` if MediaPipe is installed. Uses try/except for graceful degradation |
| `model_selection=0` | MediaPipeDetector.**init** | 0 = short-range model (< 2m), 1 = long-range (< 5m). We use 0 for classroom close-up |
| `min_detection_confidence=0.5` | MediaPipeDetector.**init** | Minimum probability to consider a detection valid. Lower = more detections but more false positives |
| `bboxC.relative_bounding_box` | detect_faces() | MediaPipe returns boxes as percentages (0-1). We convert to pixel coordinates by multiplying by frame width/height |

---

## 2.4 `ai_module/enroll_student.py` — Face Enrollment (CLI)

**Purpose**: Command-line tool for enrolling students via webcam. Opens camera, captures face on 's' keypress, computes encoding, saves to pickle.

### Key Functions

| Function | Purpose |
|----------|---------|
| `load_encodings()` | Reads pickle file. Returns empty dict if file doesn't exist. Uses try/except for corruption handling |
| `save_encodings(data)` | Writes pickle file. Overwrites existing file |
| `enroll_student()` | Main flow: open camera → display mirror view → wait for 's' key → detect single face → encode → ask name → save |

### Key Logic

| Code | Why |
|------|-----|
| `cv2.flip(frame, 1)` | Mirrors the frame horizontally — makes it feel like a mirror instead of a security camera. Only for display; the original unflipped frame is used for detection |
| `len(boxes) > 1` → reject | Ensures only ONE person is in frame during enrollment. Multiple faces would create ambiguous encodings |
| `cv2.waitKey(1) & 0xFF` | `waitKey(1)` waits 1ms for keypress. `& 0xFF` masks to 8 bits — required on some systems where `waitKey` returns a 32-bit value |

---

## 2.5 `ai_module/camera_manager.py` — Database-Driven Camera Config

**Purpose**: Replaces hardcoded `CAMERA_ID = 0` with database-configured cameras. Allows switching cameras from the web UI.

### Class: `CameraManager` (all `@staticmethod`)

| Method | Purpose |
|--------|---------|
| `get_active_camera()` | Queries `cameras` table for first active camera (`is_active = 1`, ordered by `id`). Falls back to `{"source": "0", "type": "usb"}` if DB fails |
| `get_all_cameras()` | Returns all cameras for the API/settings page |

### Why `@staticmethod`?

No instance state needed. Camera config comes from the database, not from object attributes. Using `@staticmethod` avoids creating unnecessary instances and makes the API cleaner: `CameraManager.get_active_camera()` instead of `CameraManager().get_active_camera()`.

---

## 2.6 `ai_module/settings.py` — Persistent Settings Manager

**Purpose**: Key-value settings stored in SQLite. Supports live changes from the web UI without restarting the server.

### Class: `SettingsManager` (all `@classmethod`)

| Attribute/Method | Purpose |
|-----------------|---------|
| `_cache` | Class-level dict — caches settings to avoid DB reads on every access. Invalidated on `set()` |
| `DEFAULTS` | Fallback values if DB is empty or inaccessible |
| `get(key, default, type_cast)` | Priority: cache → DB → provided default → class default. Supports type casting (`int`, `float`, `bool`, `str`) |
| `set(key, value)` | `INSERT OR REPLACE` — upserts the setting. Updates cache immediately |
| `get_all()` | Returns all settings merged with defaults (ensures every key exists) |
| `_fetch_from_db(key)` | Private helper — raw DB query for a single key |

### Why `@classmethod` (not `@staticmethod`)?

`@classmethod` receives `cls` as first argument — allows access to class-level attributes (`cls._cache`, `cls.DEFAULTS`). `@staticmethod` would require referencing `SettingsManager._cache` directly, which is less flexible for inheritance.

### Why Cache?

The AI loop reads settings every frame (e.g., tolerance, detection scale). Without cache, that's ~30 DB queries per second. The cache is a dict in memory — O(1) lookup. Cache invalidation happens on `set()` — when the user changes a setting via the web UI, the next AI frame picks up the new value.

---

## 2.7 `web_app/app.py` — Application Factory

**Purpose**: Creates and configures the Flask application. Entry point when running `python -m web_app.app`.

### Key Imports

| Import | Why |
|--------|-----|
| `Flask` | The web framework class |
| `Blueprint` | Used to organize routes into modules (`api_bp`, `views_bp`) — keeps code modular |
| `Config` | Configuration class from `config.py` — holds `SECRET_KEY`, `DB_PATH`, etc. |
| `CSRFProtect` | Flask-WTF extension — adds CSRF protection to all POST/PUT/DELETE requests |
| `Limiter` | Flask-Limiter — rate limiting (e.g., max 5 login attempts per minute) |

### Design Pattern: Application Factory

`create_app()` is a **factory function** — it creates and returns a configured Flask app. Why:

- Testability: can create multiple app instances with different configs
- Flask best practice: avoids circular imports
- Separation: configuration happens in one place

### Key Configuration

| Config | Value | Why |
|--------|-------|-----|
| `SESSION_COOKIE_HTTPONLY` | `True` | JavaScript cannot access the session cookie (prevents XSS from stealing sessions) |
| `SESSION_COOKIE_SAMESITE` | `'Lax'` | Browser only sends cookie for same-site requests or top-level navigation (prevents CSRF) |
| `PERMANENT_SESSION_LIFETIME` | `28800` | Session expires after 8 hours (a school day) |
| `MAX_CONTENT_LENGTH` | `10MB` | Prevents denial-of-service via large file uploads |

### Startup Flow

```
create_app() → configure → register blueprints
    ↓
__main__ block:
    1. Check for insecure defaults → warn
    2. Start video stream (background thread)
    3. Start Flask server (threaded=True)
    4. On shutdown → stop video stream
```

---

## 2.8 `web_app/config.py` — Configuration Class

**Purpose**: Simple config class. Flask loads it via `app.config.from_object(Config)`.

| Attribute | Source | Purpose |
|-----------|--------|---------|
| `SECRET_KEY` | `.env` or default | Signs session cookies. MUST be changed in production |
| `DB_PATH` | Computed | Absolute path to SQLite database |
| `CAMERA_ID` | `0` | Default camera (overridden by CameraManager) |
| `FRAME_WIDTH/HEIGHT` | `1920/1080` | Camera resolution |

---

## 2.9 `web_app/video_stream.py` — Video Stream Manager

**Purpose**: Bridges the AI engine and Flask web server. Manages camera lifecycle and MJPEG streaming.

### Design Pattern: Singleton

```python
video_stream = VideoStream()  # Module-level singleton
```

Only one instance exists. Imported by `app.py` and `views.py`. Why: there's only one camera and one AI engine — multiple instances would cause conflicts.

### Class: `VideoStream`

| Variable | Purpose |
|----------|---------|
| `self.face_system` | Instance of `FaceSystemThreaded` (AI engine) |
| `self.output_frame` | Most recent annotated frame (shown in browser via MJPEG) |
| `self.lock` | `threading.Lock` for thread-safe access to `output_frame` |
| `self._stop_event` | `threading.Event` — signals threads to stop gracefully |
| `self.is_running` | Boolean flag for capture loop |
| `self._cap` | OpenCV `VideoCapture` object |
| `self._threads` | List of background threads (capture + AI) |

| Method | Purpose |
|--------|---------|
| `start()` | Opens camera, starts capture thread + AI thread |
| `stop()` | Sets `running=False`, waits for threads to finish, releases camera |
| `restart()` | `stop()` then `start()` |
| `get_status()` | Returns dict: `{running, ai_running, camera_open, fps, students_detected, mode}` |
| `_open_camera()` | Opens camera with retry logic and exponential backoff (1s, 2s, 4s...) |
| `_capture_loop()` | Reads frames, passes to AI for processing, stores annotated frame |
| `_safe_ai_loop()` | Wrapper that catches AI crashes and logs them (prevents entire system crash) |
| `generate_frames()` | **Generator** — yields MJPEG frames. Flask calls this for `/video_feed` |

### MJPEG Streaming

```python
def generate_frames(self):
    while not self._stop_event.is_set():
        with self.lock:
            frame = self.output_frame
        if frame is None:
            time.sleep(0.03)
            continue
        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
```

This is a **multipart HTTP response** — each frame is a separate JPEG image sent as a continuous stream. The browser's `<img>` tag handles this natively.

---

## 2.10 `web_app/email_service.py` — SMTP Email Module

**Purpose**: All email functionality. Three email types, one shared `_send_email()` core.

### Functions

| Function | Parameters | Purpose |
|----------|-----------|---------|
| `_get_smtp_config()` | — | Loads SMTP settings from `os.environ`. Returns dict |
| `_send_email(to, subject, html)` | to_email, subject, html_body | Core sender. STARTTLS → login → send → close. Returns `(success, error)` tuple |
| `send_test_email()` | — | Sends test to `ADMIN_EMAIL` to verify SMTP works |
| `send_student_report(...)` | email, name, class, status, date | Individual attendance notification to student |
| `send_teacher_summary(...)` | email, class, date, present_list, absent_list | Class overview with counts and student names |
| `send_error_report(title, details)` | title, details | System error/bug notification to admin |

### Why HTML Emails?

We use `MIMEMultipart('alternative')` with HTML bodies (inline CSS). Why not plain text:

- Styled emails look professional (color-coded statuses, branded header)
- Inline CSS works across all email clients (no external stylesheet)
- `f-strings` for template interpolation (simple, no template engine needed)

---

## 2.11 `web_app/routes/views.py` — Page Routes

**Purpose**: Serves HTML pages. Handles authentication redirects.

### Auth Decorators

| Decorator | Logic |
|-----------|-------|
| `@login_required` | Checks `session['user_id']`. Redirects to `/login` if missing |
| `@admin_required` | Checks `session['user_id']` AND `session['role'] == 'admin'`. Returns 403 if not admin |

**Why decorators?** Avoids repeating `if 'user_id' not in session: return redirect(...)` in every route function. The `@wraps(f)` preserves the original function name (important for Flask's `url_for()`).

### Routes Summary

| Route | Decorator | Template |
|-------|-----------|----------|
| `/login` | Public | `login.html` |
| `/logout` | Public | Redirect to `/login` |
| `/lookup` | Public | `lookup.html` |
| `/` | `@login_required` | `dashboard.html` |
| `/live` | `@login_required` | `live.html` |
| `/students` | `@login_required` | `students.html` |
| `/enroll` | `@login_required` | `enroll.html` |
| `/settings` | `@login_required` | `settings.html` |
| `/report` | `@login_required` | `report.html` |
| `/timetable` | `@login_required` | `timetable.html` |
| `/student/<id>` | `@login_required` | `student_detail.html` |
| `/users` | `@admin_required` | `user_management.html` |
| `/debug` | `@admin_required` | `debug.html` |
| `/video_feed` | `@login_required` | MJPEG stream (not HTML) |

---

## 2.12 `web_app/routes/api.py` — REST API (1583 lines, 47+ endpoints)

**Purpose**: All backend logic. CRUD operations, system control, authentication, export, email triggers.

### Key Imports

| Import | Why |
|--------|-----|
| `base64` | Decoding base64-encoded profile photos sent from the enrollment page |
| `hmac` | HMAC comparison for PIN verification (timing-safe comparison) |
| `requests as http_requests` | Renamed to avoid collision with `flask.request`. Used for Telegram API calls |
| `werkzeug.security` | `generate_password_hash()` and `check_password_hash()` for password hashing |
| `openpyxl` | Excel file generation for attendance export |
| `BytesIO` | In-memory file buffer — we generate XLS in memory, never write to disk |

### Helper Functions

| Function | Purpose |
|----------|---------|
| `handle_api_error(e)` | Global error handler — catches any unhandled exception and returns JSON instead of HTML traceback |
| `_require_json()` | Parses `request.get_json()`. Returns `(data, None)` on success or `(None, error_response)` on failure |
| `_get_limiter()` | Gets rate limiter from `current_app` (may be None if Flask-Limiter not installed) |
| `get_db()` | Opens SQLite connection with `row_factory = sqlite3.Row` (enables dict-like access to rows) |
| `api_login_required(f)` | API version of login check — returns 401 JSON instead of redirect |
| `api_admin_required(f)` | API version of admin check — returns 401/403 JSON |

### Endpoint Groups (47+ endpoints)

| Group | Endpoints | Key Logic |
|-------|-----------|-----------|
| **Auth** | `login`, `logout`, `me`, `verify-pin` | Password hash comparison, session creation, rate limiting |
| **Users** | `get`, `add`, `update`, `delete` | Admin-only CRUD. Prevents deleting the last admin |
| **Students** | `get_all`, `add`, `get_one`, `update`, `delete` | CRUD + attendance history in `get_one` |
| **Enrollment** | `enroll` | Base64 image → face detection → duplicate check → encoding → pickle + DB |
| **Lookup** | `student_lookup` | Public. Query by student_id, return attendance history |
| **Attendance** | `get`, `manual`, `override`, `delete` | Date filtering, source tracking, 7-day edit limit for teachers |
| **Schedule** | `get`, `add`, `update`, `delete` | Timetable CRUD with teacher_email support |
| **System** | `status`, `control` | Start/stop/restart AI, mode switching, shutdown |
| **Reports** | `submit_report` | Crash reports: save to file + send to Telegram |
| **Stats** | `get_stats`, `chart_data` | Dashboard numbers + 7-day chart data |
| **Export** | `export_data` | XLSX/CSV generation with date filtering |
| **Config** | `get`, `update`, `export_db` | .env editing (PIN-gated), database backup download |
| **Cameras** | `get`, `add`, `update`, `delete`, `test` | Camera CRUD + connection testing |
| **Settings** | `get`, `update` | AI settings CRUD (tolerance, scale, mode, etc.) |
| **Health** | `health_check` | System status + DB connectivity check |
| **Debug** | `debug_info` | Admin-only diagnostics (Python version, packages, memory, uptime) |
| **Email** | `test`, `class_report` | SMTP verification + per-class attendance email distribution |

### Security Constants

| Constant | Purpose |
|----------|---------|
| `EDITABLE_ENV_KEYS` | Whitelist of `.env` variables that can be edited via the web UI. Prevents arbitrary env manipulation |
| `MASKED_KEYS` | Keys whose values are replaced with `***` in GET responses (e.g., `SECRET_KEY`) |

---

## 2.13 `web_app/database/schema.sql` — Database Schema

6 tables defined with `CREATE TABLE IF NOT EXISTS` (idempotent).

### Table Details

| Table | PK | Key Columns | Notes |
|-------|-----|-------------|-------|
| `users` | `id` | `username` (UNIQUE), `password_hash`, `role` | Roles: `'admin'` or `'teacher'` |
| `students` | `id` | `name` (UNIQUE), `student_id`, `email` | Face encodings stored in pickle, not DB |
| `class_schedules` | `id` | `day_of_week`, `start_time`, `end_time`, `teacher_email` | `is_active` flag for enable/disable |
| `attendance_logs` | `id` | `student_id` (FK), `schedule_id` (FK), `status`, `source` | `source`: `'ai'`, `'manual'`, `'override'` |
| `cameras` | `id` | `source`, `type` | `type`: `'usb'`, `'ip'`, `'file'` |
| `settings` | `key` | `value` | Key-value store for AI config |

### Foreign Keys

```sql
FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
-- When a student is deleted, all their attendance logs are automatically deleted

FOREIGN KEY (schedule_id) REFERENCES class_schedules (id)
-- Links attendance to specific class (no cascade — keep logs if schedule deleted)
```

---

## 2.14 `web_app/database/init_db.py` — Database Initialization

**Purpose**: Creates tables, runs migrations, seeds default data.

### Key Concepts

| Concept | Code | Why |
|---------|------|-----|
| **Idempotent schema** | `CREATE TABLE IF NOT EXISTS` | Safe to run multiple times — won't error if table exists |
| **Column migration** | `PRAGMA table_info(table) → ALTER TABLE ADD COLUMN` | Checks existing columns, adds missing ones |
| **Default seeding** | `INSERT OR IGNORE INTO settings` | Populates default settings without overwriting existing values |
| **Admin seeding** | Checks if admin exists → creates if not | Uses `ADMIN_PASSWORD` from `.env` or fallback `admin123` |
| **Student migration** | `migrate_students()` | Reads names from `encodings.pickle` and inserts into `students` table |

---

## 2.15 `web_app/static/js/dashboard.js` — Dashboard Logic

### Key Functions

| Function | Purpose |
|----------|---------|
| `loadStats()` | Fetches `/api/stats` → updates stat cards (total students, present/absent today) |
| `loadAttendance(date)` | Fetches `/api/attendance` → renders HTML table rows with status badges |
| `updateExportLinks(date)` | Updates XLSX/CSV download links when date filter changes |
| `setTextSafe(id, value)` | Safe DOM update — `document.getElementById(id).textContent = value` with null check |

### Auto-Refresh

```javascript
setInterval(() => {
    loadStats();
    loadAttendance();
}, 5000);  // Every 5 seconds
```

Why 5 seconds? Balances freshness (new students detected) with server load (not hammering the API). Could be configurable in future.

---

## 2.16 `web_app/static/css/style.css` — Dark Theme

### Design Choices

| Choice | Why |
|--------|-----|
| **Dark theme** (`#0f0f23` background) | Reduces eye strain for teachers monitoring all day. Modern look |
| **Glassmorphism** (`backdrop-filter: blur`) | Frosted glass effect on cards — premium feel |
| **`#6C63FF` primary color** | Purple/indigo — unique, doesn't conflict with status colors (green/red/yellow) |
| **CSS custom properties** (`--color-primary`) | Single source of truth for colors — change one variable, update entire theme |
| **Status badges** (`.bg-present`, `.bg-late`, `.bg-absent`) | Color-coded attendance statuses for quick visual scanning |

---

# Part 3: Anticipated Q&A for University Defense

## Q1: "What algorithm does your face recognition use?"

**Answer**: We use **dlib's HOG (Histogram of Oriented Gradients)** for face detection and a **ResNet-based deep metric learning model** for face encoding. HOG detects face bounding boxes by analyzing gradient patterns in the image. The ResNet model converts each detected face into a 128-dimensional embedding vector — a numeric representation of the face's identity. Two faces are matched by computing the **Euclidean distance** between their vectors. Distance below 0.5 = same person.

**Complexity**: Detection is O(w×h) where w,h are frame dimensions. Encoding is O(n) per face (forward pass through a fixed-size neural network). Matching is O(k) where k is the number of enrolled students (linear scan of known encodings).

---

## Q2: "Why not use a CNN for detection instead of HOG?"

**Answer**: HOG is faster on CPU (~15ms vs ~25ms per frame). Our deployment target is a classroom PC without a GPU. CNN would be better for varied angles and lighting but our classroom setting has controlled conditions (frontal faces, consistent lighting). We can switch to CNN by changing `model="hog"` to `model="cnn"` in one line of code, but it would halve our frame rate.

---

## Q3: "How do you handle the case where a student's face is not recognized?"

**Answer**: If no match is found (all distances > tolerance), the face is drawn with a red box and labeled "Unknown". No attendance record is created. The teacher can then manually add an attendance record via the dashboard (Manual Add feature). This is a deliberate design choice: **false negatives (missing a real student) are safer than false positives (marking the wrong student present)**.

---

## Q4: "What happens if two students look very similar?"

**Answer**: The system would match to the **closest** encoding (smallest Euclidean distance). If both are below the tolerance threshold, it picks the best match. In extreme cases (twins), you could lower the tolerance in Settings (0.4 instead of 0.5) to make matching stricter, trading recall for precision. The system logs which student was matched, so any errors are auditable.

---

## Q5: "How do you prevent spoofing (showing a photo to the camera)?"

**Answer**: Liveness detection (anti-spoofing) is **planned but not yet implemented** in the current version. The intended approach would use **MediaPipe Face Mesh** to calculate the **Eye Aspect Ratio (EAR)** — the ratio of eye height to eye width. When a person blinks, EAR drops below ~0.25. Real people blink naturally; photos don't. The system would require detecting at least one blink within a time window before confirming identity. Currently, spoofing (e.g., holding a photo to the camera) is a **known limitation**. For our classroom context, the risk is low (a teacher is present and would notice), but for production, liveness detection is a priority enhancement.

---

## Q6: "Is your system GDPR compliant?"

**Answer**: For a production system, there are several GDPR considerations:

- **Consent**: Students must consent to face data collection (we would add a consent form)
- **Right to deletion**: Our "Delete Student" endpoint removes both the DB record and the pickle encoding
- **Data minimization**: We store only the 128-dim encoding, not the original photo
- **Storage**: Face encodings are stored locally (not cloud) — data doesn't leave the school network
- For a full production deployment, we'd add a privacy policy, data retention limits, and consent logging.

---

## Q7: "Why did you choose SQLite over a proper database?"

**Answer**: SQLite is a "proper" database — it's the most widely deployed database in the world (every smartphone uses it). For our scope (single classroom, ~50 students, one concurrent writer), SQLite is optimal:

- Zero setup, zero maintenance
- ACID compliant (Atomicity, Consistency, Isolation, Durability)
- Single-file backup (just copy `attendance.db`)
- Performance is excellent for our data volume (< 10,000 rows)

If we scaled to a university (1000+ students, multiple cameras), we'd migrate to PostgreSQL for concurrent writes and connection pooling.

---

## Q8: "How do you handle concurrent access to the database?"

**Answer**: SQLite uses file-level locking — one writer at a time. Our system has two actors that write: the AI thread (logging attendance) and the Flask web server (manual attendance, settings changes). Since both are in the same process, SQLite's default `journal_mode=WAL` (Write-Ahead Logging) allows concurrent reads while one write is happening. In practice, writes are very fast (< 1ms for an INSERT) and contention is minimal.

---

## Q9: "What design patterns did you use?"

**Answer**:

1. **Strategy Pattern** — `detectors.py`: Swappable face detection backends (dlib vs MediaPipe) via a common `BaseDetector` ABC
2. **Factory Pattern** — `app.py`: `create_app()` factory function for Flask app creation
3. **Singleton Pattern** — `video_stream.py`: Module-level `video_stream = VideoStream()` instance
4. **Observer Pattern (implicit)** — Settings changes propagate to the AI loop via the cache mechanism
5. **Decorator Pattern** — `@login_required`, `@admin_required` wrapping route functions
6. **Template Method** — `base.html` defines the layout skeleton, child templates fill in blocks

---

## Q10: "How scalable is your system?"

**Answer**: Current scale: **1 camera, ~50 students, 1 classroom**. Bottlenecks:

- CPU-bound face recognition (~30 FPS with HOG)
- SQLite single-writer (fine for our load)
- Single-process Flask (adequate for < 100 concurrent users)

To scale:

| Target | Changes Needed |
|--------|---------------|
| 100 students | Lower `DETECTION_SCALE` to 0.3, increase tolerance slightly |
| Multiple cameras | Run one AI thread per camera, shared database |
| 1000+ students | Switch to PostgreSQL, add Redis for caching, use face_recognition with GPU (CUDA) |
| Multiple classrooms | Deploy as microservices, one instance per room, central database |

---

## Q11: "How do you secure the API against SQL injection?"

**Answer**: Every database query uses **parameterized queries** (placeholder `?`):

```python
# SAFE — parameters are separated from SQL
cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))

# UNSAFE — never do this (string concatenation)
cursor.execute(f"SELECT * FROM students WHERE id = {student_id}")
```

The `?` placeholder tells SQLite to treat the value as data, not as SQL code. Even if `student_id` contains `'; DROP TABLE students; --`, it would be treated as a literal string, not executed as SQL.

---

## Q12: "How does your CSRF protection work?"

**Answer**: We use **Flask-WTF's CSRFProtect**. On every page load, the server generates a unique token and embeds it in the HTML (as a meta tag). Our `safeFetch()` JavaScript function reads this token and includes it as `X-CSRFToken` header on every API request. The server validates this token — if missing or invalid, the request is rejected with 400. This prevents an attacker from tricking a logged-in user into making requests from a malicious website, because the attacker can't read the CSRF token from our domain.

---

## Q13: "What's the time complexity of your face matching?"

**Answer**: For each detected face, we compute the Euclidean distance against all known encodings: **O(k)** where k = number of enrolled students. Each distance computation is O(128) = O(1) (fixed-dimension vector). So matching one face is O(k), and matching m faces in one frame is O(m × k). For 50 students and 5 faces in frame: 250 distance computations — negligible time (~0.5ms).

For 10,000+ students, we'd switch to **approximate nearest neighbor** (ANN) structures like FAISS or Annoy, which give O(log k) matching using KD-trees or locality-sensitive hashing.

---

## Q14: "Why do you use threading instead of async/await?"

**Answer**: The AI loop is **CPU-bound** (face detection/encoding uses CPU intensively). Python's `asyncio` is designed for **I/O-bound** tasks (network requests, database queries). Using `asyncio` for CPU-bound work would block the event loop entirely. Threading works because:

- The AI thread and Flask thread run concurrently (Python GIL releases during C-extension calls in OpenCV/dlib)
- OpenCV's `VideoCapture.read()` releases the GIL while waiting for the camera
- `face_recognition` (C++ under the hood via dlib) releases the GIL during computation

For true CPU parallelism, we'd use `multiprocessing`, but threads are simpler for our single-camera case.

---

## Q15: "What happens if the camera disconnects?"

**Answer**: `VideoStream._capture_loop()` checks `cap.isOpened()` and `ret` (return value of `cap.read()`). If the camera fails:

1. Logs an error
2. Attempts to reconnect with **exponential backoff** (1s, 2s, 4s, 8s...)
3. The web dashboard shows "Camera Disconnected" in the status
4. The AI loop pauses (no frames to process)
5. Existing attendance data is preserved (already in SQLite)

The system recovers automatically when the camera is reconnected.

---

## Q16: "Why did you build your own auth system instead of using Flask-Login?"

**Answer**: Flask-Login adds a user loader, login manager, and mixin class overhead. Our auth needs are simple:

- Two roles: admin and teacher
- Session-based (Flask's built-in session)
- PIN gate for sensitive operations
- We have 6 lines of decorator logic vs. a whole Flask-Login dependency

For a larger system with OAuth, social login, or JWT tokens, Flask-Login (or Flask-JWT-Extended) would be the right choice.

---

## Q17: "How do you export attendance data?"

**Answer**: The `/api/export` endpoint supports both **XLSX** (Excel) and **CSV** formats:

- **XLSX**: Uses `openpyxl` to create an in-memory workbook (`BytesIO`), write headers and rows, then send as a downloadable file
- **CSV**: Uses Python's `csv` module with an `io.StringIO` buffer
- Both support **date range filtering** (start_date, end_date query params)
- The file is generated in memory — never written to disk — and streamed directly to the browser as a download

---

## Q18: "What data structures are most important in your system?"

**Answer**:

| Data Structure | Where | Why |
|---------------|-------|-----|
| **List** (Python) | `known_encodings` | Ordered collection of face vectors. Index corresponds to `known_names[i]` |
| **NumPy ndarray** (128-dim) | Face encodings | Fixed-size float64 vector. Efficient for vectorized distance computation |
| **Set-like Dict** (Python) | `session_logged` | O(1) lookup for "has this student been logged this session?" |
| **Dict** (Python) | `last_seen` | O(1) lookup by student name for disappearance tracking |
| **B-tree** (SQLite index) | Database indexes | O(log n) lookup for attendance queries |
| **Key-value store** | `settings` table | O(1) lookup for configuration values |

---

## Q19: "How do you handle time zones?"

**Answer**: We use the server's local time (`datetime.now()`). This works because:

- The system runs in one physical location (one classroom, one school)
- Class schedules are defined in local time
- All timestamps in the database are local time

For a multi-campus deployment, we'd switch to UTC timestamps in the database and convert to local time in the frontend using JavaScript's `Intl.DateTimeFormat`.

---

## Q20: "What would you improve if you had more time?"

**Answer**:

1. **GPU acceleration** — Use dlib's CUDA support for CNN detection (10× faster)
2. **Multi-camera support** — One AI thread per camera, load balancing
3. **Real-time WebSocket** — Replace polling (`setInterval`) with WebSocket push for instant updates
4. **PostgreSQL migration** — For concurrent writes and better scalability
5. **JWT authentication** — Stateless auth for potential mobile app
6. **Docker deployment** — Containerized setup for easy installation
7. **Unit tests** — pytest suite for API endpoints and face matching logic
8. **Attendance analytics** — Weekly/monthly trends, per-student patterns, early warning for habitual absentees

---

## Q21: "How does your enrollment process prevent duplicate faces?"

**Answer**: During enrollment (`/api/enroll`), after detecting a face and computing its encoding, we compare it against ALL existing encodings using `face_recognition.compare_faces()`. If ANY existing encoding matches (distance < tolerance), the enrollment is **rejected** with an error message identifying who the duplicate matches. This prevents enrolling the same student twice (which would create two entries) and also prevents enrolling different people who look nearly identical (which would cause matching ambiguity).

---

## Q22: "How does the schedule system work?"

**Answer**: The system operates in three modes:

- **`auto`** (default): Every AI loop iteration calls `get_active_schedule()`, which queries: `SELECT * FROM class_schedules WHERE day_of_week = ? AND start_time <= ? AND end_time >= ? AND is_active = 1`. If a matching schedule exists, attendance is linked to that class. If no schedule matches, AI still detects but doesn't log.
- **`force_on`**: Always logs attendance regardless of schedule
- **`force_off`**: AI loop runs but doesn't process frames

When a **new schedule starts** (different `schedule_id`), `maybe_reset_session()` clears `session_logged` so students can be re-logged for the new class.

---

## Q23: "Explain the video streaming architecture."

**Answer**: We use **MJPEG (Motion JPEG)** streaming:

1. Camera → `VideoCapture.read()` → raw frame (NumPy array)
2. AI processes frame → draws bounding boxes → annotated frame
3. `cv2.imencode('.jpg', frame)` → JPEG bytes
4. Flask generator yields: `--frame\r\nContent-Type: image/jpeg\r\n\r\n[bytes]\r\n`
5. Browser `<img src="/video_feed">` renders the stream

This is **HTTP multipart streaming** — one long-lived connection with continuous JPEG frames. It works in all browsers without WebSocket or special plugins. Downside: ~500KB/s bandwidth per viewer (each frame is a full JPEG, no delta compression like H.264).

---

## Q24: "Why do you use Pickle instead of a database for face encodings?"

**Answer**: Face encodings are **128-dimensional NumPy float64 arrays**. Pickle natively serializes NumPy arrays with zero conversion overhead. The alternatives:

- **SQLite BLOB**: Would work, but complicates query logic and requires serialization/deserialization on every access
- **JSON**: Cannot serialize NumPy arrays natively (requires `.tolist()` conversion, losing dtype precision)
- **HDF5**: Good for large-scale ML data, but overkill for ~50 students

Pickle loads the entire file into memory once at startup — O(1) access thereafter. New enrollments append to the pickle and reload.

---

## Q25: "What is the difference between `source` values in attendance_logs?"

**Answer**:

| Source | Meaning | Set By |
|--------|---------|--------|
| `'ai'` | Face detected by the AI engine automatically | `recognition_system.py` → `log_attendance()` |
| `'manual'` | Teacher manually added attendance via dashboard | `api.py` → `manual_attendance()` |
| `'override'` | Teacher corrected/changed an existing record | `api.py` → `override_attendance()` |

This enables **audit trails** — you can always trace how each record was created. Teachers can only override within 7 days (hardcoded business rule to prevent historical tampering).

---

## Q26: "How does error reporting work?"

**Answer**: Three-tier error handling:

1. **Try/except in AI loop** — Catches crashes, logs them, continues processing
2. **File-based crash reports** — Saved to `crash_reports/` directory with timestamp, error details, and system state at time of crash
3. **Telegram notification** — If configured, sends crash details to a Telegram chat via the Bot API (`requests.post()` to `api.telegram.org`)
4. **Email error reports** — `send_error_report()` sends HTML-formatted error details to `ADMIN_EMAIL` via SMTP

This ensures the admin is notified immediately of any system issues, even if they're not watching the dashboard.

---

## Q27: "What is the `safeFetch()` function and why is it important?"

**Answer**: `safeFetch()` is a frontend JavaScript wrapper around the native `fetch()` API:

```javascript
async function safeFetch(url, options = {}) {
    options.headers = options.headers || {};
    options.headers['X-CSRFToken'] = document.querySelector('meta[name=csrf-token]').content;
    const response = await fetch(url, options);
    if (response.status === 401) window.location.href = '/login';
    return response;
}
```

It does three things:

1. **Auto-injects CSRF token** — Every request includes the anti-forgery token
2. **Handles 401 redirects** — If the session expires, automatically redirects to login
3. **Centralizes HTTP logic** — All API calls go through one function (easy to add logging, retries, etc.)

---

## Q28: "How would you deploy this to production?"

**Answer**: Current deployment is direct `python -m web_app.app` on a local machine. For production:

1. **WSGI Server**: Replace Flask dev server with Gunicorn or uWSGI (better performance, process management)
2. **Reverse Proxy**: Nginx in front for SSL termination, static file serving, and load balancing
3. **Process Manager**: systemd service file for auto-restart on crash
4. **SSL/TLS**: Let's Encrypt certificate for HTTPS
5. **Environment**: Proper `.env` with strong `SECRET_KEY`, unique `SETTINGS_PIN`, production `ADMIN_PASSWORD`
6. **Database**: PostgreSQL for concurrent access (if multi-server)
7. **Monitoring**: Add health check monitoring (e.g., UptimeRobot hitting `/api/health`)

**Important constraint**: Since the AI engine uses threads (not multiprocessing), we must use a **single worker** WSGI configuration (one process) to ensure the shared `video_stream` singleton works correctly.

---

## Q29: "What are the ethical implications of face recognition in education?"

**Answer**: Key considerations:

- **Consent**: Students should explicitly consent (opt-in, not opt-out)
- **Privacy**: Face data is biometric (sensitive personal data under GDPR/local laws)
- **Bias**: Face recognition models can have higher error rates for certain demographics — we should test across our student population
- **Surveillance perception**: Students may feel monitored — transparency about what data is collected and how it's used is essential
- **Alternative**: Always provide manual attendance as a fallback for students who opt out
- **Data retention**: Define clear policies (e.g., delete face data after semester ends)

Our system mitigates some concerns: we store only 128-dim vectors (not photos), data stays local, and the teacher has full control.

---

## Q30: "How does the face tracking between recognition frames work?"

**Answer**: Instead of running full face recognition on every frame (expensive), we use **dlib's `correlation_tracker()`** between recognition cycles:

1. On a **recognition frame**: detect faces → compute 128-dim encodings → match identities → create a `dlib.correlation_tracker()` for each matched face, initialized with their bounding box
2. On **subsequent frames**: call `tracker.update(frame)` → get updated positions via `tracker.get_position()`. This is extremely fast (~0.5ms per tracker) because it uses a correlation filter (DCF), not neural-network-based re-detection
3. The tracked positions are used to **draw bounding boxes and names** on the display frame in real-time
4. The AI thread periodically runs full recognition again (every ~30ms) and replaces the trackers with fresh ones — correcting any drift

This gives us **real-time UI responsiveness** (names and boxes drawn every frame at full camera FPS) while the computationally expensive recognition runs in a background thread at a lower rate (~30 FPS recognition vs 60 FPS display).

---

## Q31: "Why dlib's correlation tracker instead of OpenCV's KCF/MOSSE trackers?"

**Answer**: dlib's `correlation_tracker()` uses a **Discriminative Correlation Filter (DCF)** approach that excels at:

- **Scale adaptation**: Automatically adjusts the tracked region as the face moves closer or farther from the camera
- **Robustness**: Handles partial occlusion better than MOSSE (which is faster but less accurate)
- **Native integration**: Since we already use dlib for face recognition, adding correlation tracking adds zero new dependencies

OpenCV's KCF would be a viable alternative (~same speed), but MOSSE, while faster (~2×), drifts more on face rotations. For our use case (faces moving slowly in a classroom), DCF offers the best accuracy-to-speed tradeoff.

---

## Q32: "How does Flask handle concurrent requests with `threaded=True`?"

**Answer**: We run Flask with `threaded=True`, meaning each incoming HTTP request is handled in a **separate thread**. This is important because:

- The `/video_feed` endpoint is a **long-lived connection** (MJPEG stream). Without threading, it would block all other requests
- The Python **GIL (Global Interpreter Lock)** still applies, but it releases during I/O operations (network writes, database queries), so concurrent requests are handled efficiently
- Our AI thread runs C-extension code (OpenCV, dlib, numpy) that releases the GIL during computation, so it doesn't block Flask threads

For production, we'd replace Flask's dev server with **Gunicorn** (single worker, multiple threads) for better connection management and stability.

---

## Q33: "Is using Pickle for face encodings a security risk?"

**Answer**: Yes, Pickle is inherently insecure — `pickle.load()` can execute arbitrary code if the file is tampered with. Our mitigations:

- The pickle file (`encodings.pickle`) is **server-side only** — it's never uploaded by users or received from external sources
- Only the enrollment endpoint and the CLI tool write to it
- File system permissions should restrict write access to the application user
- In a production environment, we'd consider **signing the pickle** (HMAC hash stored separately) or migrating to a safer format like **MessagePack** or SQLite BLOB storage

The risk is low in our deployment context (local school network), but it's a valid concern for untrusted environments.

---

## Q34: "Why a Multi-Page Application (MPA) instead of a Single-Page Application (SPA)?"

**Answer**: We use **Jinja2 server-side rendering** (MPA) instead of a React/Vue SPA for practical reasons:

- **No build toolchain**: No Node.js, webpack, npm required — the entire app runs with just Python
- **SEO irrelevant**: This is an internal school tool, not a public website
- **Simpler deployment**: One Flask process serves both API and pages
- **Template inheritance**: `base.html` → child templates gives us code reuse without a JavaScript framework
- **Progressive enhancement**: JavaScript (`safeFetch()`, `loadStats()`) enhances the already-rendered pages with dynamic data

The trade-off is slightly slower page transitions (full page reload), but for a dashboard used by 1–3 teachers, this is negligible.

---

## Q35: "What is your database backup strategy?"

**Answer**: SQLite's single-file architecture makes backups trivial:

- **Live download**: The `/api/config/export-db` endpoint lets admins download `attendance.db` directly from the browser (PIN-gated for security)
- **File copy**: Since SQLite uses WAL mode, a simple file copy during low-activity periods is safe
- **Automated**: Could add a cron job / scheduled task to copy the DB file daily to a backup location

The pickle file (`encodings.pickle`) should also be backed up, since it contains all face encodings that can’t be regenerated without the original enrollment photos.

For a production system, we'd add **automated daily backups** with rotation (keep last 30 days) and **off-site replication** (e.g., to a network share or cloud storage).

---

*End of Technical Reference — SmartPresence v1.0*
