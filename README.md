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
| **AI Engine** | `ai_module/` | Face detection, recognition, liveness check, centroid tracking |
| **Web Backend** | `web_app/routes/` | REST API (45 endpoints), authentication, data management |
| **Frontend** | `web_app/templates/` | Dashboard, Live View, Student Management, Settings, Reports |
| **Database** | `web_app/database/` | SQLite schema + initialization script |

---

## ✨ Key Features

### Core AI

- **Real-time face recognition** using dlib's 128-dim face encoding
- **Liveness detection** via MediaPipe Face Mesh (blink detection to prevent photo spoofing)
- **Centroid tracking** to maintain identity across frames without re-running recognition every frame
- **Configurable thresholds** (detection scale, recognition tolerance, late/disappear timers)

### Attendance Management

- Automatic status tagging: `Present`, `Late`, `Absent`, `Disappeared`
- Per-student profile with attendance statistics and history
- Class schedule integration (auto start/stop AI per timetable)
- Excel export (.xlsx) and database backup

### Security & Authentication

- Multi-user login system (Admin + Teacher roles)
- Password hashing with Werkzeug (bcrypt-based)
- Settings PIN gate for sensitive configuration
- Session-based auth with role-based access control

### Admin Dashboard

- Real-time system status monitoring
- In-app configuration editor (Telegram tokens, security keys)
- Crash reporting system (local save + Telegram forwarding)
- System controls (Start/Stop/Restart AI, mode switching)

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Face Detection** | dlib (HOG/CNN) | Industry-standard, accurate face detection |
| **Face Recognition** | face_recognition lib | Simplified dlib wrapper, 128-dim encodings |
| **Liveness** | MediaPipe Face Mesh | Lightweight, real-time blink detection |
| **Image Processing** | OpenCV | Camera capture, frame manipulation |
| **Web Framework** | Flask | Lightweight Python web server |
| **Database** | SQLite | Zero-config, file-based relational DB |
| **Frontend** | Bootstrap 5 + Chart.js | Responsive UI with live charts |
| **Auth** | Werkzeug + Flask Sessions | Secure password hashing + session management |
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
git clone https://github.com/YOUR_USERNAME/SmartPresence.git
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
# Edit .env with your values

# 5. Initialize the database
python -c "from web_app.database.init_db import init_db; init_db()"

# 6. Run the application
python -m web_app.app
```

Open **<http://localhost:5000>** in your browser.

### Default Login

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `admin123` |
| Settings PIN | `1234` |

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
│   ├── database/
│   │   ├── schema.sql          # Database schema (6 tables)
│   │   └── init_db.py          # DB init + migration + admin seed
│   ├── routes/
│   │   ├── api.py              # REST API (45 endpoints)
│   │   └── views.py            # Page routes + auth decorators
│   ├── templates/              # HTML pages (11 templates)
│   │   ├── base.html           # Layout + sidebar + global JS
│   │   ├── login.html          # Login page
│   │   ├── dashboard.html      # Main dashboard
│   │   ├── students.html       # Student management
│   │   ├── student_detail.html # Per-student profile
│   │   ├── settings.html       # System settings + admin config
│   │   ├── report.html         # Crash/issue reporting
│   │   └── ...                 # enrollment, live view, users, 403
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
attendance_logs   → id, student_id, timestamp, status, source, notes
class_schedules   → id, day_of_week, start_time, end_time, class_name, is_active
users             → id, username, display_name, password_hash, role
crash_reports     → stored as JSON files
```

---

## 🔌 API Endpoints (45 total)

| Category | Endpoints | Auth |
|----------|-----------|------|
| **Auth** | `/api/auth/login`, `/logout`, `/me`, `/verify-pin` | Public / Login |
| **Students** | `/api/students` (CRUD), `/api/students/<id>` | Login |
| **Attendance** | `/api/attendance`, `/api/stats`, `/api/export` | Login |
| **Schedule** | `/api/schedule` (CRUD) | Login |
| **System** | `/api/system` (start/stop/restart/shutdown) | Login/Admin |
| **Users** | `/api/users` (CRUD) | Admin |
| **Config** | `/api/config` (GET/PUT), `/api/config/export-db` | Admin + PIN |
| **Settings** | `/api/settings` (GET/POST) | Login |
| **Reports** | `/api/report` (POST) | Login |

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

### Liveness Detection (Anti-Spoofing)

```
Face Detected → MediaPipe Face Mesh (468 landmarks)
    → Calculate Eye Aspect Ratio (EAR)
    → If EAR drops below threshold → Blink detected
    → No blinks for extended period → Flag as possible photo
```

---

## ❓ Common Questions (Q&A)

### "What algorithm do you use for face recognition?"
>
> We use **dlib's ResNet-based face encoder** which produces a 128-dimensional face embedding. Faces are matched by computing the Euclidean distance between encodings — if the distance is below a configurable tolerance (default 0.5), it's a match. This is the same approach used by FaceNet (Google) but implemented via the `face_recognition` library which wraps dlib.

### "How do you prevent cheating with photos?"
>
> **Liveness detection** using MediaPipe Face Mesh. It tracks 468 facial landmarks in real-time and monitors the Eye Aspect Ratio (EAR). A real person blinks naturally; a printed photo does not. If no blinks are detected over a period, the system flags it as a potential spoof attempt.

### "What's Centroid Tracking?"
>
> Instead of running the expensive face recognition algorithm on every single frame (which would lag at 30 FPS), we run recognition periodically (every N frames) and use **centroid tracking** in between. This tracks faces by their center position across consecutive frames, maintaining identity without re-computing encodings. This gives us real-time performance on standard hardware.

### "Why SQLite instead of MySQL/PostgreSQL?"
>
> SQLite is **zero-configuration** — no server setup needed. It stores the entire database in a single `.db` file, making it portable and easy to deploy. For a classroom-scale system (50–200 students), SQLite handles the load perfectly. If scaling to a university level, we could migrate to PostgreSQL.

### "How does the scheduling system work?"
>
> Teachers define class timetables (day, start time, end time) through the Settings page. When the system is in **Auto mode**, it checks the schedule every minute. If the current time falls within a class slot, the AI engine starts automatically. When the class ends, it stops. Teachers can also use **Force ON/OFF** to override the schedule.

### "How is security handled?"
>
> Three layers: (1) **Login authentication** with hashed passwords (Werkzeug/bcrypt), (2) **Role-based access control** (Admin vs Teacher — admins can manage users and config, teachers can only view), (3) **Settings PIN** — sensitive configuration like API keys requires an additional PIN verification beyond being logged in as admin.

### "What happens if the camera disconnects?"
>
> The video stream manager detects the disconnection and updates the system status to "Stopped". The dashboard shows a real-time status indicator. Teachers can restart the stream from the Settings page. If Telegram is configured, crash reports can be sent to the teacher's phone.

### "Can this work with multiple cameras?"
>
> The current implementation supports one camera (configurable index in `config.py`). The architecture is designed so that multiple `video_stream` instances could be created for multi-camera support in a future version.

### "What are the hardware requirements?"
>
> Minimum: Core i5 8th Gen, 8GB RAM, any USB webcam. Recommended: dedicated GPU for faster dlib CNN detection (the system auto-detects CUDA). On CPU, we use HOG detection which runs at ~5–10 FPS recognition with centroid tracking smoothing the experience.

---

## 👥 Team Roles

| Role | Responsibilities |
|------|------------------|
| **AI & Vision Lead** | OpenCV integration, face recognition pipeline, liveness detection |
| **Optimization & Tracking** | Performance tuning, centroid tracking, frame skipping strategy |
| **Backend & Database** | Flask API design, SQLite schema, authentication system |
| **Frontend & UI** | Dashboard design, real-time charts, responsive dark theme |

---

## 📄 License

This project was built for academic purposes.

---

## 🔮 Future Improvements

- [ ] Multi-camera support
- [ ] Database encryption (SQLCipher / Fernet)
- [ ] Notification system (email/SMS when student is absent)
- [ ] Mobile app for students to view their own attendance
- [ ] GPU-accelerated CNN face detection
