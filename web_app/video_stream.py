import cv2
import threading
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_module import common
from ai_module.recognition_system import FaceSystemThreaded
from ai_module.settings import SettingsManager

log = common.get_logger('stream')


class VideoStream:
    """
    Wraps FaceSystemThreaded to provide an MJPEG stream for Flask.
    Supports start/stop/restart from the web UI.
    Includes camera reconnect and crash protection.
    """
    def __init__(self):
        self.face_system = FaceSystemThreaded()
        self.output_frame = None
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self.is_running = False
        self._cap = None
        self._threads = []

    def start(self):
        """Start the camera and AI in background threads."""
        if self.is_running:
            log.info("Stream already running.")
            return

        self.is_running = True
        self.face_system.is_running = True
        self._stop_event.clear()

        ai_thread = threading.Thread(target=self._safe_ai_loop, daemon=True, name="ai-loop")
        ai_thread.start()

        capture_thread = threading.Thread(target=self._capture_loop, daemon=True, name="capture-loop")
        capture_thread.start()

        self._threads = [ai_thread, capture_thread]
        log.info("Video stream started.")

    def stop(self):
        """Stop camera and AI threads gracefully."""
        if not self.is_running:
            return
        self.is_running = False
        self.face_system.is_running = False
        self._stop_event.set()

        if self._cap and self._cap.isOpened():
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        self._threads.clear()
        log.info("Video stream stopped.")

    def restart(self):
        """Stop then start."""
        self.stop()
        time.sleep(0.5)
        # Reload encodings in case new students were added
        self.face_system = FaceSystemThreaded()
        self.start()
        log.info("Video stream restarted.")

    def get_status(self):
        """Return current system state dict."""
        try:
            schedule = self.face_system.get_active_schedule() if self.is_running else None
        except Exception:
            schedule = None

        return {
            'ai_running': self.is_running,
            'system_mode': SettingsManager.get('SYSTEM_MODE', default='auto'),
            'active_schedule': schedule,
            'students_loaded': len(self.face_system.known_names),
            'session_logged': len(self.face_system.session_logged),
            'detection_scale': SettingsManager.get('DETECTION_SCALE', type_cast=float),
            'tolerance': SettingsManager.get('TOLERANCE', type_cast=float),
            'detector': SettingsManager.get('DETECTOR_MODEL', default='dlib')
        }

    def _safe_ai_loop(self):
        """Wrapper around AI loop that catches and logs crashes."""
        try:
            self.face_system.ai_loop()
        except Exception as e:
            log.error(f"AI loop crashed: {type(e).__name__}: {e}")
            # Don't crash the system — AI can be restarted

    def _open_camera(self):
        """Open camera with retries and exponential backoff, using DB config."""
        from ai_module.camera_manager import CameraManager
        
        backoff = 1.0
        max_backoff = 10.0
        attempt = 0

        while not self._stop_event.is_set():
            attempt += 1
            cam_config = CameraManager.get_active_camera()
            source = cam_config.get('source', '0')
            name = cam_config.get('name', 'Unknown Camera')

            # Handle numeric source (USB) vs string (RTSP)
            if source.isdigit():
                source = int(source)

            try:
                log.info(f"Opening camera: {name} (Source: {source})...")
                cap = cv2.VideoCapture(source)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, common.FRAME_WIDTH)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, common.FRAME_HEIGHT)
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                    # RTSP streams often ignore fps setting, but harmless to try
                    cap.set(cv2.CAP_PROP_FPS, 60)
                    
                    log.info(f"Camera opened successfully (attempt {attempt}).")
                    return cap
                else:
                    cap.release()
            except Exception as e:
                log.warning(f"Camera open failed (attempt {attempt}): {e}")

            log.warning(f"Camera not available, retrying in {backoff:.0f}s...")
            self._stop_event.wait(backoff)
            backoff = min(backoff * 2, max_backoff)

        return None

    def _capture_loop(self):
        """Captures frames, runs tracking, and stores annotated frames."""
        try:
            import dlib
        except ImportError:
            log.error("dlib not installed — capture loop cannot run. Install with: pip install dlib")
            self.is_running = False
            return

        self._cap = self._open_camera()
        if not self._cap:
            log.error("Camera could not be opened. Capture loop exiting.")
            self.is_running = False
            return

        consecutive_failures = 0
        max_failures = 30  # ~1 second of failures at 30fps

        while not self._stop_event.is_set():
            try:
                ret, frame = self._cap.read()
            except Exception as e:
                log.error(f"Camera read exception: {e}")
                ret = False

            if not ret:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    log.warning(f"Camera failed {consecutive_failures} times. Attempting reconnect...")
                    try:
                        self._cap.release()
                    except Exception:
                        pass
                    self._cap = self._open_camera()
                    if not self._cap:
                        log.error("Camera reconnect failed. Capture loop exiting.")
                        self.is_running = False
                        return
                    consecutive_failures = 0
                time.sleep(0.01)
                continue

            consecutive_failures = 0
            frame = cv2.flip(frame, 1)

            # Update shared frame for AI
            with self.face_system.lock:
                self.face_system.latest_frame = frame
                current_trackers = list(self.face_system.trackers)
                current_names = list(self.face_system.tracking_names)

            # Draw tracker annotations (with crash protection)
            for i, tracker in enumerate(current_trackers):
                try:
                    tracker.update(frame)
                    pos = tracker.get_position()
                    left = int(pos.left())
                    top = int(pos.top())
                    right = int(pos.right())
                    bottom = int(pos.bottom())
                    name = current_names[i] if i < len(current_names) else "?"
                    color = common.COLOR_GREEN if name != "Unknown" else common.COLOR_RED
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    cv2.putText(frame, name, (left, top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                except Exception:
                    # Tracker can fail on edge-of-frame or corrupted data — skip silently
                    pass

            # Status overlay
            from ai_module.settings import SettingsManager
            scale = SettingsManager.get('DETECTION_SCALE', type_cast=float)
            mode = SettingsManager.get('SYSTEM_MODE', default='auto')
            mode_label = {'auto': 'AUTO', 'force_on': 'ON', 'force_off': 'OFF'}.get(mode, mode.upper())
            cv2.putText(frame, f"Scale: {scale}x | Mode: {mode_label}", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            with self.lock:
                self.output_frame = frame.copy()

            time.sleep(0.03)

        # Cleanup on exit
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def generate_frames(self):
        """Generator that yields MJPEG frames for Flask streaming."""
        while self.is_running:
            with self.lock:
                if self.output_frame is None:
                    time.sleep(0.01)
                    continue
                frame = self.output_frame.copy()

            try:
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not ret:
                    continue
            except Exception:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            time.sleep(0.033)


# Singleton instance
video_stream = VideoStream()
