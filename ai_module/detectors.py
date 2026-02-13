import cv2
import face_recognition
import numpy as np
from abc import ABC, abstractmethod
from ai_module import common

try:
    import mediapipe as mp
    if hasattr(mp, 'solutions'):
        HAS_MEDIAPIPE = True
    else:
        HAS_MEDIAPIPE = False
except ImportError:
    HAS_MEDIAPIPE = False


class BaseDetector(ABC):
    @abstractmethod
    def detect_faces(self, frame):
        """
        Detect faces in the frame.
        Args:
            frame: BGR numpy array
        Returns:
            List of (top, right, bottom, left) tuples in FRAME coordinates.
        """
        pass

class DlibDetector(BaseDetector):
    def detect_faces(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return face_recognition.face_locations(rgb_frame, model="hog")

class MediaPipeDetector(BaseDetector):
    def __init__(self):
        if not HAS_MEDIAPIPE:
            raise ImportError("MediaPipe not installed.")
        
        self.mp_face_detection = mp.solutions.face_detection
        self.detector = self.mp_face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=0.5
        )
    
    def detect_faces(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.detector.process(rgb_frame)
        
        if not results.detections:
            return []
            
        h, w, _ = frame.shape
        boxes = []
        for detection in results.detections:
            bboxC = detection.location_data.relative_bounding_box
            x = int(bboxC.xmin * w)
            y = int(bboxC.ymin * h)
            bw = int(bboxC.width * w)
            bh = int(bboxC.height * h)
            
            top = max(0, y)
            left = max(0, x)
            bottom = min(h, y + bh)
            right = min(w, x + bw)
            
            boxes.append((top, right, bottom, left))
            
        return boxes
