# 🎓 SmartPresence — AI-Powered Attendance System

> An automated, contactless attendance system using real-time face recognition.  
> Built with Python, OpenCV, Flask, and SQLite.

---

## 📖 What It Does

SmartPresence replaces manual roll calls with a camera-based system that:

1. **Detects** faces in a live video feed using OpenCV + dlib
2. **Recognizes** enrolled students by comparing face encodings
3. **Logs** attendance automatically (Present / Late / Absent / Disappeared)
4. **Provides** a web dashboard for teachers to monitor, manage, and export data
5. **Emails** per-class reports to students and teachers via Brevo SMTP

---

## 🏗️ System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   USB Camera    │────▶│   AI Module     │────▶│   Flask Web     │
│   (Live Feed)   │     │   (OpenCV +     │     │   Application   │
│                 │     │   face_recog)   │     │   (Dashboard)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │                        │
                              ▼                        ▼
                        ┌───────────┐           ┌───────────┐
                        │ Encodings │           │  SQLite   │
                        │  (pickle) │           │  Database │
                        └───────────┘           └───────────┘
```

### Module Breakdown

| Module | Path | Purpose |
|--------|------|---------|
| **AI Engine** | `ai_module/` | Face detection, recognition, dlib correlation tracking |
| **Web Backend** | `web_app/routes/` | REST API (47+ endpoints), authentication, data management |
| **Email Service** | `web_app/email_service.py` | SMTP email reports (student + teacher + admin) |
| **Frontend** | `web_app/templates/` | 14 HTML pages — Dashboard, Timetable, Enrollment, Settings, etc. |
| **Database** | `web_app/database/` | SQLite schema + initialization + migrations |

---

## ✨ Key Features

### Core AI

- **Real-time face recognition** using dlib's 128-dim face encoding
- **dlib correlation tracking** to maintain identity across frames without re-running recognition every frame
- **Configurable thresholds** (detection scale, recognition tolerance, late/disappear timers)

> **Note**: Liveness detection (anti-spoofing via EAR blink detection) is a planned feature, not yet implemented.

### Attendance Management

- Automatic status tagging: `Present`, `Late`, `Absent`, `Disappeared`
- Per-student profile with attendance statistics and history
- Class schedule integration (auto start/stop AI per timetable)
- Student self-lookup page (public, no login required)
- Teacher 7-day edit limit on attendance overrides
- Excel export (.xlsx) and database backup

### Email Reports (Brevo SMTP)

- **Student emails** — individual attendance status after each class
- **Teacher summary** — per-class overview with present/absent counts and student lists
- **Admin error reports** — automatic bug/crash notifications
- One-click "Send Report" button on the Timetable page
- SMTP test button in Settings for easy verification

### Security & Authentication

- Multi-user login system (Admin + Teacher roles)
- CSRF protection on all endpoints
- Password hashing with Werkzeug (bcrypt-based)
- Settings PIN gate for sensitive configuration
- Session-based auth with role-based access control
- All credentials stored in `.env` (gitignored — never pushed to GitHub)
- XSS mitigation via `escapeHtml()` on all user-facing outputs
- Parameterized SQL queries (no raw string concatenation)

### Admin Dashboard

- Real-time system status monitoring
- In-app configuration editor (Telegram tokens, security keys, email test)
- Crash reporting system (local save + Telegram forwarding)
- System controls (Start/Stop/Restart AI, mode switching)
- Secret debug page for diagnostics (admin only)

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Face Detection** | dlib (HOG/CNN) | Industry-standard, accurate face detection |
| **Face Recognition** | face_recognition lib | Simplified dlib wrapper, 128-dim encodings |
| **Tracking** | dlib correlation_tracker | Inter-frame face position tracking (DCF) |
| **Image Processing** | OpenCV | Camera capture, frame manipulation |
| **Web Framework** | Flask | Lightweight Python web server |
| **Database** | SQLite | Zero-config, file-based relational DB |
| **Frontend** | Bootstrap 5 + Chart.js | Responsive UI with live charts |
| **Auth** | Werkzeug + Flask Sessions | Secure password hashing + session management |
| **Email** | Brevo SMTP (smtp-relay.brevo.com) | Transactional email delivery |
| **Config** | python-dotenv | Environment variable management |
| **Reporting** | openpyxl | Excel file generation |

---

## 📦 Installation

### Prerequisites

- **Python 3.9+**
- **Visual Studio Build Tools** with C++ workload (required for dlib compilation)
- **USB Webcam** or IP Camera

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/SAA2007/SmartPresence.git
cd SmartPresence

# 2. Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env   # Windows
# cp .env.example .env   # Linux/Mac
# Edit .env with your values (SMTP keys, admin password, etc.)

# 5. Initialize the database
python -c "from web_app.database.init_db import init_db; init_db()"

# 6. Run the application
python -m web_app.app
```

Open **<http://localhost:5000>** in your browser.

> ⚠️ **Deployment Note**: This application must run as a **single process** (`threaded=True`, not multi-worker). The AI state (face encodings, video stream) is stored in-memory and will not sync across multiple WSGI workers. Use the built-in server or a single-worker Gunicorn deployment.

### Default Login

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `admin123` |
| Settings PIN | `1234` |

> 🔒 **Important**: Change these defaults immediately after first login. On a deployed school system, all credentials live in the `.env` file which is **never** pushed to GitHub.

---

## 📁 Project Structure

```
SmartPresence/
├── ai_module/                  # 🧠 Computer Vision
│   ├── common.py               # Shared config, .env loader, constants
│   ├── enroll_student.py       # Face enrollment (capture + encode)
│   └── recognition_system.py   # Main recognition loop + tracking
│
├── web_app/                    # 🌐 Flask Application
│   ├── app.py                  # Entry point, app factory
│   ├── config.py               # Camera resolution settings
│   ├── video_stream.py         # Video stream manager (start/stop)
│   ├── email_service.py        # SMTP email sender (Brevo)
│   ├── database/
│   │   ├── schema.sql          # Database schema (6 tables)
│   │   └── init_db.py          # DB init + migration + admin seed
│   ├── routes/
│   │   ├── api.py              # REST API (47+ endpoints)
│   │   └── views.py            # Page routes + auth decorators
│   ├── templates/              # HTML pages (14 templates)
│   │   ├── base.html           # Layout + sidebar + global JS
│   │   ├── login.html          # Login page
│   │   ├── dashboard.html      # Main dashboard
│   │   ├── students.html       # Student management
│   │   ├── student_detail.html # Per-student profile
│   │   ├── enroll.html         # Face enrollment wizard
│   │   ├── live.html           # Real-time camera view
│   │   ├── timetable.html      # Class timetable + email reports
│   │   ├── settings.html       # System settings + admin config
│   │   ├── report.html         # Crash/issue reporting
│   │   ├── lookup.html         # Student self-lookup (public)
│   │   ├── user_management.html # User management (admin)
│   │   ├── debug.html          # System diagnostics (admin)
│   │   └── 403.html            # Forbidden error page
│   └── static/
│       ├── css/style.css       # Dark theme + glassmorphism
│       └── js/dashboard.js     # Chart.js dashboard logic
│
├── tests/                      # Benchmark & stress tests
├── verify_setup.py             # Dependency verification script
├── requirements.txt            # Python dependencies
├── .env.example                # Environment config template
└── .gitignore
```

---

## 🗄️ Database Schema

```
students          → id, name, student_id, email, encoding
attendance_logs   → id, student_id, timestamp, status, source, notes, schedule_id
class_schedules   → id, day_of_week, start_time, end_time, class_name, teacher_email, is_active
users             → id, username, display_name, password_hash, role
settings          → key, value (app configuration)
cameras           → id, name, source, is_active
```

---

## 🔌 API Endpoints (47+)

| Category | Endpoints | Auth |
|----------|-----------|------|
| **Auth** | `/api/auth/login`, `/logout`, `/me`, `/verify-pin` | Public / Login |
| **Students** | `/api/students` (CRUD), `/api/students/<id>` | Login |
| **Enrollment** | `/api/enroll` (POST with face capture) | Login |
| **Attendance** | `/api/attendance`, `/api/stats`, `/api/export` | Login |
| **Schedule** | `/api/schedule` (CRUD) | Login |
| **System** | `/api/system` (start/stop/restart/shutdown) | Login/Admin |
| **Users** | `/api/users` (CRUD) | Admin |
| **Config** | `/api/config` (GET/PUT), `/api/config/export-db` | Admin + PIN |
| **Settings** | `/api/settings` (GET/POST) | Login |
| **Email** | `/api/email/test`, `/api/email/class-report/<id>` | Admin / Login |
| **Reports** | `/api/report` (POST) | Login |
| **Lookup** | `/api/lookup` (POST) | Public |
| **Debug** | `/api/debug` (GET) | Admin |

---

## 🎯 How It Works (Technical Flow)

### Face Recognition Pipeline

```
Camera Frame → Resize (0.5x) → Detect Faces (dlib HOG)
    → Compute 128-dim Encoding → Compare with Known Encodings
    → If Distance < Tolerance (0.5): MATCH → Log Attendance
    → If No Match: Unknown Visitor
```

### Attendance Logic

```
Student Detected → Check Schedule → Is class active?
    → YES: Mark PRESENT (or LATE if > threshold minutes)
    → Student disappears for > threshold: Mark DISAPPEARED
    → End of class + not seen: Mark ABSENT
```

### Email Report Flow

```
Teacher clicks "Report" on Timetable page
    → System queries today's attendance for that class
    → Each student gets an individual status email
    → Teacher gets a summary (present count, absent count, names)
    → Any send failures are reported to admin email
```

### Liveness Detection (Planned — Not Yet Implemented)

```
Face Detected → MediaPipe Face Mesh (468 landmarks)
    → Calculate Eye Aspect Ratio (EAR)
    → If EAR drops below threshold → Blink detected
    → No blinks for extended period → Flag as possible photo
    (This feature is planned for a future release)
```

---

## ❓ Common Questions (Q&A)

### "What algorithm do you use for face recognition?"
>
> We use **dlib's ResNet-based face encoder** which produces a 128-dimensional face embedding. Faces are matched by computing the Euclidean distance between encodings — if the distance is below a configurable tolerance (default 0.5), it's a match. This is the same approach used by FaceNet (Google) but implemented via the `face_recognition` library which wraps dlib.

### "How do you prevent cheating with photos?"
>
> Liveness detection (anti-spoofing) is **planned but not yet implemented**. The intended approach uses MediaPipe Face Mesh to monitor the Eye Aspect Ratio (EAR) — a real person blinks naturally; a printed photo does not. Currently, a teacher's physical presence in the classroom serves as the primary anti-spoofing measure.

### "What's dlib correlation tracking?"
>
> Instead of running the expensive face recognition algorithm on every single frame (which would lag at 30 FPS), we run recognition periodically in a background thread and use **dlib's `correlation_tracker()`** in between. Each recognized face is assigned a DCF (Discriminative Correlation Filter) tracker that follows its position across consecutive frames — much faster than re-computing 128-dim encodings. This gives us real-time performance on standard hardware.

### "Why SQLite instead of MySQL/PostgreSQL?"
>
> SQLite is **zero-configuration** — no server setup needed. It stores the entire database in a single `.db` file, making it portable and easy to deploy. For a classroom-scale system (50–200 students), SQLite handles the load perfectly. If scaling to a university level, we could migrate to PostgreSQL.

### "How does the scheduling system work?"
>
> Teachers define class timetables (day, start time, end time) through the Timetable page. Each class can have a teacher email assigned for report delivery. When the system is in **Auto mode**, it checks the schedule every minute. If the current time falls within a class slot, the AI engine starts automatically. When the class ends, it stops. Teachers can also use **Force ON/OFF** to override the schedule.

### "How is security handled?"
>
> Multiple layers: (1) **Login authentication** with hashed passwords (Werkzeug/bcrypt), (2) **Role-based access control** (Admin vs Teacher — admins can manage users and config, teachers can only view/operate), (3) **Settings PIN** — sensitive configuration requires additional PIN verification, (4) **CSRF protection** on all form submissions, (5) **All credentials** stored in `.env` which is gitignored — deployed systems have unique passwords that never appear in the source code.

### "What happens if the camera disconnects?"
>
> The video stream manager detects the disconnection and updates the system status to "Stopped". The dashboard shows a real-time status indicator. Teachers can restart the stream from the Settings page. If Telegram is configured, crash reports can be sent to the teacher's phone.

### "Can this work with multiple cameras?"
>
> The current implementation supports one camera (configurable index in `config.py`). The architecture is designed so that multiple `video_stream` instances could be created for multi-camera support in a future version.

### "What are the hardware requirements?"
>
> Minimum: Core i5 8th Gen, 8GB RAM, any USB webcam. Recommended: dedicated GPU for faster dlib CNN detection (the system auto-detects CUDA). On CPU, we use HOG detection which runs at ~5–10 FPS recognition with dlib correlation tracking smoothing the display experience.

---

## 👥 Team Roles

| Role | Responsibilities |
|------|------------------|
| **AI & Vision Lead** | OpenCV integration, face recognition pipeline, detection models |
| **Optimization & Tracking** | Performance tuning, dlib correlation tracking, frame skipping strategy |
| **Backend & Database** | Flask API design, SQLite schema, authentication system |
| **Frontend & UI** | Dashboard design, real-time charts, responsive dark theme |

---

## 📄 License

This project was built for academic purposes.

---

## 🔮 Future Improvements

- [ ] Liveness detection (anti-spoofing via EAR blink analysis)
- [ ] Multi-camera support
- [ ] Database encryption (SQLCipher)
- [ ] WhatsApp/SMS absence notifications (Telegram already integrated)
- [ ] Mobile-native app (web lookup already available at `/lookup`)
- [ ] Automated daily database backups
