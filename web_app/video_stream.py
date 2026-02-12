import cv2
import threading
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_module import common
from ai_module.recognition_system import FaceSystemThreaded

log = common.get_logger('stream')


class VideoStream:
    """
    Wraps FaceSystemThreaded to provide an MJPEG stream for Flask.
    Supports start/stop/restart from the web UI.
    """
    def __init__(self):
        self.face_system = FaceSystemThreaded()
        self.output_frame = None
        self.lock = threading.Lock()
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

        ai_thread = threading.Thread(target=self.face_system.ai_loop, daemon=True)
        ai_thread.start()

        capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        capture_thread.start()

        self._threads = [ai_thread, capture_thread]
        log.info("Video stream started.")

    def stop(self):
        """Stop camera and AI threads gracefully."""
        if not self.is_running:
            return
        self.is_running = False
        self.face_system.is_running = False

        if self._cap and self._cap.isOpened():
            self._cap.release()
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
        schedule = self.face_system.get_active_schedule() if self.is_running else None
        return {
            'ai_running': self.is_running,
            'system_mode': getattr(common, 'SYSTEM_MODE', 'auto'),
            'active_schedule': schedule,
            'students_loaded': len(self.face_system.known_names),
            'session_logged': len(self.face_system.session_logged),
            'detection_scale': getattr(common, 'DETECTION_SCALE', 0.5),
            'tolerance': getattr(common, 'TOLERANCE', 0.5),
        }

    def _capture_loop(self):
        """Captures frames, runs tracking, and stores annotated frames."""
        self._cap = cv2.VideoCapture(common.CAMERA_ID)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, common.FRAME_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, common.FRAME_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self._cap.set(cv2.CAP_PROP_FPS, 60)

        import dlib

        while self.is_running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)

            with self.face_system.lock:
                self.face_system.latest_frame = frame
                current_trackers = list(self.face_system.trackers)
                current_names = list(self.face_system.tracking_names)

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

            # Status overlay
            scale = getattr(common, 'DETECTION_SCALE', 0.5)
            mode = getattr(common, 'SYSTEM_MODE', 'auto')
            mode_label = {'auto': 'AUTO', 'force_on': 'ON', 'force_off': 'OFF'}.get(mode, mode.upper())
            cv2.putText(frame, f"Scale: {scale}x | Mode: {mode_label}", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            with self.lock:
                self.output_frame = frame.copy()

            time.sleep(0.03)

        if self._cap:
            self._cap.release()
            self._cap = None

    def generate_frames(self):
        """Generator that yields MJPEG frames for Flask streaming."""
        while self.is_running:
            with self.lock:
                if self.output_frame is None:
                    time.sleep(0.01)
                    continue
                frame = self.output_frame.copy()

            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            time.sleep(0.033)


# Singleton instance
video_stream = VideoStream()
