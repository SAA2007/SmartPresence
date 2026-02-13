import numpy as np
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
from ai_module.settings import SettingsManager
from ai_module import detectors

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
        
        # Detector
        self.detector_name = SettingsManager.get('DETECTOR_MODEL', default='dlib')
        self._init_detector()

        # Trackers
        self.trackers = []
        self.tracking_names = []

        # Session tracking
        self.session_logged = {}
        self.last_seen = {}
        self.last_disappear_check = 0

        self.sync_students_to_db()

    def _init_detector(self):
        """Initialize the face detector based on settings."""
        try:
            if self.detector_name == 'mediapipe' and detectors.HAS_MEDIAPIPE:
                self.detector = detectors.MediaPipeDetector()
                log.info("Initialized MediaPipe Face Detector (Fast)")
            else:
                self.detector = detectors.DlibDetector()
                log.info("Initialized Dlib Face Detector (Accurate)")
        except Exception as e:
            log.error(f"Detector init failed: {e}. Fallback to Dlib.")
            self.detector = detectors.DlibDetector()
        
    def _check_settings_change(self):
        """Check if detector settings changed and reload if needed."""
        new_model = SettingsManager.get('DETECTOR_MODEL', default='dlib')
        if new_model != self.detector_name:
            log.info(f"Detector change detected: {self.detector_name} -> {new_model}")
            self.detector_name = new_model
            self._init_detector()

    def load_encodings(self):
        if os.path.exists(common.ENCODINGS_PATH):
            try:
                with open(common.ENCODINGS_PATH, "rb") as f:
                    data = pickle.load(f)
                if not isinstance(data, dict):
                    return {"names": [], "encodings": []}
                names = data.get("names", [])
                encodings = data.get("encodings", [])
                # Ensure lists
                if not isinstance(names, list) or not isinstance(encodings, list):
                    return {"names": [], "encodings": []}
                # Truncate mismatch
                min_len = min(len(names), len(encodings))
                return {"names": names[:min_len], "encodings": encodings[:min_len]}
            except Exception as e:
                log.error(f"Could not load encodings: {e}")
        return {"names": [], "encodings": []}

    def sync_students_to_db(self):
        try:
            with sqlite3.connect(common.DB_PATH) as conn:
                cursor = conn.cursor()
                existing = {row[0] for row in cursor.execute("SELECT name FROM students").fetchall()}
                for name in set(self.known_names):
                    if name not in existing:
                        cursor.execute("INSERT INTO students (name) VALUES (?)", (name,))
                        log.info(f"Auto-synced new student to DB: {name}")
                conn.commit()
        except Exception as e:
            log.warning(f"Database sync failed: {e}")

    # ── Schedule Logic ──────────────────────────────────

    def get_active_schedule(self):
        """Check if current time falls inside any active class schedule."""
        mode = SettingsManager.get('SYSTEM_MODE', default='auto')
        if mode == 'force_on':
            return {'id': -1, 'class_name': 'Manual', 'start_time': '00:00', 'end_time': '23:59'}
        if mode == 'force_off':
            return None

        now = datetime.now()
        day_name = now.strftime('%A')
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
        except Exception:
            return None

    def determine_status(self, schedule):
        if not schedule or schedule.get('id') == -1:
            return 'Present'
        now = datetime.now()
        try:
            s_time = schedule['start_time'].split(':')
            c_start = now.replace(hour=int(s_time[0]), minute=int(s_time[1]), second=0)
            thresh = SettingsManager.get('LATE_THRESHOLD', type_cast=int)
            if now <= c_start + timedelta(minutes=thresh):
                return 'On Time'
            return 'Late'
        except Exception:
            return 'Present'

    def log_attendance(self, name):
        schedule = self.get_active_schedule()
        if schedule is None:
            return

        schedule_id = schedule.get('id')
        session_key = f"{name}:{schedule_id}"

        if session_key in self.session_logged:
            self.last_seen[name] = time.time()
            return

        try:
            with sqlite3.connect(common.DB_PATH) as conn:
                cursor = conn.cursor()
                res = cursor.execute("SELECT id FROM students WHERE name = ?", (name,)).fetchone()
                if res:
                    student_id = res[0]
                    status = self.determine_status(schedule)
                    sid = schedule_id if schedule_id != -1 else None
                    cursor.execute(
                        "INSERT INTO attendance_logs (student_id, status, source, schedule_id, last_seen) VALUES (?, ?, 'ai', ?, ?)",
                        (student_id, status, sid, datetime.now().isoformat())
                    )
                    conn.commit()
                    self.session_logged[session_key] = True
                    self.last_seen[name] = time.time()
                    log.info(f"[ATTENDANCE] {name} → {status}")
        except Exception as e:
            log.error(f"Attendance log failed: {e}")

    def check_disappearances(self):
        now = time.time()
        interval = SettingsManager.get('RECHECK_INTERVAL', type_cast=int)
        if now - self.last_disappear_check < interval:
            return
        self.last_disappear_check = now

        threshold = SettingsManager.get('DISAPPEAR_THRESHOLD', type_cast=int) * 60
        schedule = self.get_active_schedule()
        if schedule is None:
            return

        for name, last_time in list(self.last_seen.items()):
            elapsed = now - last_time
            if elapsed > threshold:
                session_key = f"{name}:disappeared"
                if session_key in self.session_logged:
                    continue
                try:
                    with sqlite3.connect(common.DB_PATH) as conn:
                        res = conn.execute("SELECT id FROM students WHERE name = ?", (name,)).fetchone()
                        if res:
                            conn.execute(
                                "INSERT INTO attendance_logs (student_id, status, source, notes) VALUES (?, 'Disappeared', 'ai', ?)",
                                (res[0], f"Last seen {int(elapsed/60)} min ago")
                            )
                            conn.commit()
                            self.session_logged[session_key] = True
                            log.warning(f"[DISAPPEARED] {name}")
                except Exception:
                    pass

    def maybe_reset_session(self, schedule):
        if schedule is None:
            return
        new_key = f"_schedule_{schedule.get('id')}_{schedule.get('start_time')}"
        if not hasattr(self, '_current_schedule_key') or self._current_schedule_key != new_key:
            self._current_schedule_key = new_key
            self.session_logged.clear()
            self.last_seen.clear()
            log.info(f"New class session: {schedule.get('class_name')}")

    # ── AI Loop ──────────────────────────────────────────

    def ai_loop(self):
        log.info("AI Thread Started.")
        while self.is_running:
            frame_to_process = None
            with self.lock:
                if self.latest_frame is not None:
                    frame_to_process = self.latest_frame.copy()
            
            if frame_to_process is not None:
                # 1. Update Settings / Detector
                self._check_settings_change()
                
                # 2. Schedule & Cleanup
                schedule = self.get_active_schedule()
                self.maybe_reset_session(schedule)
                self.check_disappearances()

                # 3. Process Frame
                scale = SettingsManager.get('DETECTION_SCALE', type_cast=float)
                rgb_frame = cv2.cvtColor(frame_to_process, cv2.COLOR_BGR2RGB)

                if scale != 1.0:
                    small_frame = cv2.resize(rgb_frame, (0, 0), fx=scale, fy=scale)
                    small_frame_bgr = cv2.resize(frame_to_process, (0, 0), fx=scale, fy=scale)
                else:
                    small_frame = rgb_frame
                    small_frame_bgr = frame_to_process

                # DETECT (Uses selected model)
                # Pass BGR because detectors convert if needed, or use BGR direct (Dlib HOG)
                boxes = self.detector.detect_faces(small_frame_bgr)

                results = []
                if boxes:
                    # RECOGNIZE (Always uses dlib/face_recognition for encodings)
                    # face_encodings expects RGB, but helper converts. Passing small_frame (RGB) is safe.
                    encodings = face_recognition.face_encodings(small_frame, boxes)

                    for box, encoding in zip(boxes, encodings):
                        tolerance = SettingsManager.get('TOLERANCE', type_cast=float)
                        matches = face_recognition.compare_faces(self.known_encodings, encoding, tolerance=tolerance)
                        name = "Unknown"
                        
                        if True in matches:
                            face_distances = face_recognition.face_distance(self.known_encodings, encoding)
                            best_match_index = int(np.argmin(face_distances))
                            name = self.known_names[best_match_index]
                            self.log_attendance(name)

                        # Upscale coords for display
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
            else:
                time.sleep(0.1)

    # ── Standalone Mode ──────────────────────────────────

    def start(self):
        log.info("Starting Threaded Recognition System...")
        log.info("  > Hotkeys: 's' = Toggle Scale | 'd' = Toggle Debug | 'q' = Quit")

        from ai_module.camera_manager import CameraManager
        
        # Retry loop for camera
        cap = None
        while cap is None:
            cam_config = CameraManager.get_active_camera()
            source = cam_config.get('source', '0')
            name = cam_config.get('name', 'Unknown')
            
            if source.isdigit():
                source = int(source)
                
            log.info(f"Opening camera: {name} (Source: {source})...")
            try:
                cap = cv2.VideoCapture(source)
                if not cap.isOpened():
                    log.warning("Camera failed to open. Retrying in 2s...")
                    cap = None
                    time.sleep(2)
            except Exception as e:
                log.error(f"Camera error: {e}")
                time.sleep(2)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, common.FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, common.FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        # RTSP might ignore FPS, but harmless
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
