import cv2
import face_recognition
import pickle
import os
import sys
import sqlite3
import time
import threading
import dlib
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_module import common

log = common.get_logger('recognition')


class FaceSystemThreaded:
    def __init__(self):
        self.encodings_data = self.load_encodings()
        self.known_names = self.encodings_data.get("names", [])
        self.known_encodings = self.encodings_data.get("encodings", [])

        # Shared Data
        self.latest_frame = None
        self.new_results_available = False
        self.detected_results = []

        # Settings & State
        self.is_running = False
        self.lock = threading.Lock()
        self.show_debug = True

        # Trackers
        self.trackers = []
        self.tracking_names = []

        # Session tracking: {student_name: schedule_id} — prevents duplicate logs per class
        self.session_logged = {}
        # Last seen tracking: {student_name: timestamp}
        self.last_seen = {}
        self.last_disappear_check = 0

        self.sync_students_to_db()

    def load_encodings(self):
        if os.path.exists(common.ENCODINGS_PATH):
            try:
                with open(common.ENCODINGS_PATH, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                log.error(f"Could not load encodings: {e}")
        return {"names": [], "encodings": []}

    def sync_students_to_db(self):
        try:
            with sqlite3.connect(common.DB_PATH) as conn:
                cursor = conn.cursor()
                for name in set(self.known_names):
                    cursor.execute("SELECT id FROM students WHERE name = ?", (name,))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO students (name) VALUES (?)", (name,))
                        log.info(f"Auto-synced new student to DB: {name}")
                conn.commit()
        except Exception as e:
            log.warning(f"Database sync failed: {e}")

    # ── Schedule Logic ──────────────────────────────────

    def get_active_schedule(self):
        """Check if current time falls inside any active class schedule."""
        mode = getattr(common, 'SYSTEM_MODE', 'auto')
        if mode == 'force_on':
            return {'id': -1, 'class_name': 'Manual', 'start_time': '00:00', 'end_time': '23:59'}
        if mode == 'force_off':
            return None

        now = datetime.now()
        day_name = now.strftime('%A')  # Monday, Tuesday, etc.
        current_time = now.strftime('%H:%M')

        try:
            with sqlite3.connect(common.DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("""
                    SELECT * FROM class_schedules
                    WHERE day_of_week = ? AND is_active = 1
                      AND ? BETWEEN start_time AND end_time
                    ORDER BY start_time LIMIT 1
                """, (day_name, current_time)).fetchone()
                return dict(row) if row else None
        except Exception as e:
            log.warning(f"Schedule check failed: {e}")
            return None

    def determine_status(self, schedule):
        """Determine if the student is On Time or Late based on class start + threshold."""
        if not schedule or schedule.get('id') == -1:
            return 'Present'

        now = datetime.now()
        try:
            start_parts = schedule['start_time'].split(':')
            class_start = now.replace(hour=int(start_parts[0]), minute=int(start_parts[1]), second=0)
            threshold = getattr(common, 'LATE_THRESHOLD', 10)
            late_cutoff = class_start + timedelta(minutes=threshold)

            if now <= late_cutoff:
                return 'On Time'
            else:
                return 'Late'
        except Exception:
            return 'Present'

    # ── Attendance Logging with Smart Dedup ──────────────

    def log_attendance(self, name):
        """Log attendance with schedule awareness and session dedup."""
        schedule = self.get_active_schedule()

        # If no active schedule (and mode is auto), don't log
        if schedule is None:
            return

        schedule_id = schedule.get('id')
        session_key = f"{name}:{schedule_id}"

        # Session dedup: only log once per student per class slot
        if session_key in self.session_logged:
            # Still update last_seen
            self.last_seen[name] = time.time()
            return

        try:
            with sqlite3.connect(common.DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM students WHERE name = ?", (name,))
                result = cursor.fetchone()

                if result:
                    student_id = result[0]
                    status = self.determine_status(schedule)
                    sid = schedule_id if schedule_id != -1 else None

                    cursor.execute(
                        "INSERT INTO attendance_logs (student_id, status, source, schedule_id, last_seen) VALUES (?, ?, 'ai', ?, ?)",
                        (student_id, status, sid, datetime.now().isoformat())
                    )
                    conn.commit()

                    self.session_logged[session_key] = True
                    self.last_seen[name] = time.time()
                    log.info(f"[ATTENDANCE] {name} → {status}" +
                             (f" ({schedule.get('class_name', '')})" if schedule.get('class_name') else ""))
        except Exception as e:
            log.error(f"Attendance log failed: {e}")

    # ── Disappearance Tracking ───────────────────────────

    def check_disappearances(self):
        """Check for students who were present but vanished."""
        now = time.time()

        # Only check every RECHECK_INTERVAL seconds
        interval = getattr(common, 'RECHECK_INTERVAL', 300)
        if now - self.last_disappear_check < interval:
            return
        self.last_disappear_check = now

        threshold_secs = getattr(common, 'DISAPPEAR_THRESHOLD', 15) * 60
        schedule = self.get_active_schedule()
        if schedule is None:
            return

        for name, last_time in list(self.last_seen.items()):
            elapsed = now - last_time
            if elapsed > threshold_secs:
                session_key = f"{name}:disappeared"
                if session_key in self.session_logged:
                    continue

                try:
                    with sqlite3.connect(common.DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT id FROM students WHERE name = ?", (name,))
                        result = cursor.fetchone()
                        if result:
                            cursor.execute(
                                "INSERT INTO attendance_logs (student_id, status, source, notes) VALUES (?, 'Disappeared', 'ai', ?)",
                                (result[0], f"Last seen {int(elapsed/60)} min ago")
                            )
                            conn.commit()
                            self.session_logged[session_key] = True
                            log.warning(f"[DISAPPEARED] {name} — last seen {int(elapsed/60)} min ago")
                except Exception as e:
                    log.error(f"Disappearance check failed: {e}")

    # ── Reset Session on Schedule Change ─────────────────

    def maybe_reset_session(self, schedule):
        """Reset session tracking when a new class slot starts."""
        if schedule is None:
            return

        new_key = f"_schedule_{schedule.get('id')}_{schedule.get('start_time')}"
        if not hasattr(self, '_current_schedule_key') or self._current_schedule_key != new_key:
            self._current_schedule_key = new_key
            self.session_logged.clear()
            self.last_seen.clear()
            log.info(f"New class session: {schedule.get('class_name', 'Unknown')} ({schedule.get('start_time')}–{schedule.get('end_time')})")

    # ── AI Loop ──────────────────────────────────────────

    def ai_loop(self):
        log.info("AI Thread Started.")
        while self.is_running:
            frame_to_process = None
            with self.lock:
                if self.latest_frame is not None:
                    frame_to_process = self.latest_frame.copy()

            if frame_to_process is not None:
                # Check schedule & reset sessions as needed
                schedule = self.get_active_schedule()
                self.maybe_reset_session(schedule)
                self.check_disappearances()

                scale = getattr(common, 'DETECTION_SCALE', 0.5)
                rgb_frame = cv2.cvtColor(frame_to_process, cv2.COLOR_BGR2RGB)

                if scale != 1.0:
                    small_frame = cv2.resize(rgb_frame, (0, 0), fx=scale, fy=scale)
                else:
                    small_frame = rgb_frame

                boxes = face_recognition.face_locations(small_frame, model="hog")

                results = []
                if boxes:
                    encodings = face_recognition.face_encodings(small_frame, boxes)

                    for box, encoding in zip(boxes, encodings):
                        matches = face_recognition.compare_faces(self.known_encodings, encoding, tolerance=common.TOLERANCE)
                        name = "Unknown"
                        if True in matches:
                            first_match_index = matches.index(True)
                            name = self.known_names[first_match_index]
                            self.log_attendance(name)

                        if scale != 1.0:
                            top, right, bottom, left = box
                            top = int(top / scale)
                            right = int(right / scale)
                            bottom = int(bottom / scale)
                            left = int(left / scale)
                            box = (top, right, bottom, left)

                        results.append((box, name))

                # Init Trackers
                new_trackers = []
                new_tracking_names = []

                if self.is_running:
                    for box, name in results:
                        top, right, bottom, left = box
                        rect = dlib.rectangle(left, top, right, bottom)
                        tracker = dlib.correlation_tracker()
                        tracker.start_track(frame_to_process, rect)
                        new_trackers.append(tracker)
                        new_tracking_names.append(name)

                with self.lock:
                    self.detected_results = results
                    self.trackers = new_trackers
                    self.tracking_names = new_tracking_names
                    self.new_results_available = True

            time.sleep(0.03)

    # ── Standalone Mode ──────────────────────────────────

    def start(self):
        log.info("Starting Threaded Recognition System...")
        log.info("  > Hotkeys: 's' = Toggle Scale | 'd' = Toggle Debug | 'q' = Quit")

        cap = cv2.VideoCapture(common.CAMERA_ID)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, common.FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, common.FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FPS, 60)

        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        log.info(f"Camera Hardware FPS: {actual_fps}")

        self.is_running = True
        ai_thread = threading.Thread(target=self.ai_loop)
        ai_thread.daemon = True
        ai_thread.start()

        try:
            while True:
                start_time = time.time()
                ret, frame = cap.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)

                with self.lock:
                    self.latest_frame = frame
                    current_trackers = list(self.trackers)
                    current_names = list(self.tracking_names)

                for i, tracker in enumerate(current_trackers):
                    tracker.update(frame)
                    pos = tracker.get_position()
                    left = int(pos.left())
                    top = int(pos.top())
                    right = int(pos.right())
                    bottom = int(pos.bottom())
                    name = current_names[i]
                    color = common.COLOR_GREEN if name != "Unknown" else common.COLOR_RED
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    cv2.putText(frame, name, (left, top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                if self.show_debug:
                    fps = 1.0 / (time.time() - start_time)
                    scale = getattr(common, 'DETECTION_SCALE', 0.5)
                    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    cv2.putText(frame, f"Scale: {scale}x", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

                cv2.imshow("SmartPresence - Threaded", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    if common.DETECTION_SCALE == 1.0:
                        common.DETECTION_SCALE = 0.5
                        log.info("Switched to Speed Mode (0.5x)")
                    else:
                        common.DETECTION_SCALE = 1.0
                        log.info("Switched to Distance Mode (1.0x)")
                elif key == ord('d'):
                    self.show_debug = not self.show_debug

        finally:
            self.is_running = False
            cap.release()
            cv2.destroyAllWindows()
            log.info("System Stopped.")


if __name__ == "__main__":
    system = FaceSystemThreaded()
    system.start()
