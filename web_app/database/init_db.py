import sqlite3
import os
import pickle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "attendance.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
ENCODINGS_PATH = os.path.join(PROJECT_ROOT, "ai_module", "encodings.pickle")


def init_db():
    print(f"[INFO] Initializing database at {DB_PATH}...")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        # Apply schema (IF NOT EXISTS safe for re-runs)
        with open(SCHEMA_PATH, 'r') as f:
            conn.executescript(f.read())

        cursor = conn.cursor()

        # ── Migrate students table ──
        cursor.execute("PRAGMA table_info(students)")
        student_cols = [col[1] for col in cursor.fetchall()]

        for col, typedef in [('student_id', "TEXT DEFAULT ''"),
                             ('email', "TEXT DEFAULT ''"),
                             ('notes', "TEXT DEFAULT ''")]:
            if col not in student_cols:
                cursor.execute(f"ALTER TABLE students ADD COLUMN {col} {typedef}")
                print(f"[MIGRATE] Added '{col}' to students")

        # ── Migrate attendance_logs table ──
        cursor.execute("PRAGMA table_info(attendance_logs)")
        log_cols = [col[1] for col in cursor.fetchall()]

        for col, typedef in [('source', "TEXT NOT NULL DEFAULT 'ai'"),
                             ('notes', "TEXT DEFAULT ''"),
                             ('last_seen', "TIMESTAMP"),
                             ('schedule_id', "INTEGER")]:
            if col not in log_cols:
                cursor.execute(f"ALTER TABLE attendance_logs ADD COLUMN {col} {typedef}")
                print(f"[MIGRATE] Added '{col}' to attendance_logs")

        # ── Migrate class_schedules table ──
        cursor.execute("PRAGMA table_info(class_schedules)")
        sched_cols = [col[1] for col in cursor.fetchall()]

        if 'teacher_email' not in sched_cols:
            cursor.execute("ALTER TABLE class_schedules ADD COLUMN teacher_email TEXT DEFAULT ''")
            print("[MIGRATE] Added 'teacher_email' to class_schedules")

        # ── Indexes (safe to re-run) ──
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_student_name ON students(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_logs(student_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_timestamp ON attendance_logs(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedule_day ON class_schedules(day_of_week)")
        except sqlite3.OperationalError:
            pass

        # ── Cameras Table (Migration) ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'usb',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Seed default camera if none exists
        cursor.execute("SELECT count(*) FROM cameras")
        if cursor.fetchone()[0] == 0:
            print("[SEED] Adding default Integrated Camera (ID 0)")
            cursor.execute("INSERT INTO cameras (name, source, type, is_active) VALUES (?, ?, ?, ?)",
                           ("Integrated Camera", "0", "usb", 1))

        # ── Settings Table (Migration) ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Seed default settings
        defaults = {
            'DETECTOR_MODEL': 'dlib',     # 'dlib' | 'mediapipe'
            'TOLERANCE': '0.5',
            'DETECTION_SCALE': '0.5',
            'LATE_THRESHOLD': '10',
            'DISAPPEAR_THRESHOLD': '15',
            'RECHECK_INTERVAL': '300',
            'SYSTEM_MODE': 'auto',
            'FRAME_SKIP': '3'             # For MediaPipe/performance tuning
        }
        for k, v in defaults.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # ── Seed admin user ──
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if cursor.fetchone() is None:
            from werkzeug.security import generate_password_hash
            # Load from .env or use defaults
            admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
            cursor.execute(
                "INSERT INTO users (username, display_name, password_hash, role) VALUES (?, ?, ?, ?)",
                ('admin', 'Administrator', generate_password_hash(admin_pass), 'admin')
            )
            print("[SEED] Created default admin user (admin / admin123)")

        conn.commit()
        print("[SUCCESS] Schema applied + migrations complete.")


def migrate_students():
    print("[INFO] Checking for existing students in pickle file...")

    if not os.path.exists(ENCODINGS_PATH):
        print("[INFO] No encodings.pickle found. Skipping migration.")
        return

    try:
        with open(ENCODINGS_PATH, "rb") as f:
            data = pickle.load(f)
            names = data.get("names", [])
    except Exception as e:
        print(f"[ERROR] Could not load encodings: {e}")
        return

    if not names:
        print("[INFO] No students found in encodings.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        count = 0
        for name in set(names):
            cursor.execute("SELECT id FROM students WHERE name = ?", (name,))
            if cursor.fetchone() is None:
                cursor.execute("INSERT INTO students (name) VALUES (?)", (name,))
                count += 1
        conn.commit()
        print(f"[SUCCESS] Migrated {count} new students to database.")


if __name__ == "__main__":
    init_db()
    migrate_students()
