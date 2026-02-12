import cv2
import face_recognition
import pickle
import os
import sys

# Add project root to path to import common
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_module import common

def load_encodings():
    if os.path.exists(common.ENCODINGS_PATH):
        try:
            with open(common.ENCODINGS_PATH, "rb") as f:
                data = pickle.load(f)
            return data
        except Exception as e:
            print(f"[ERROR] Could not load encodings: {e}")
            return {"names": [], "encodings": []}
    return {"names": [], "encodings": []}

def save_encodings(data):
    try:
        with open(common.ENCODINGS_PATH, "wb") as f:
            pickle.dump(data, f)
        print(f"[INFO] Encodings saved to {common.ENCODINGS_PATH}")
    except Exception as e:
        print(f"[ERROR] Could not save encodings: {e}")

def enroll_student():
    print("[INFO] Starting Webcam...")
    cap = cv2.VideoCapture(common.CAMERA_ID)
    
    if not cap.isOpened():
        print("[ERROR] Could not open webcam.")
        return

    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, common.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, common.FRAME_HEIGHT)

    print("="*50)
    print("  SMART PRESENCE - ENROLLMENT MODE")
    print("  Press 's' to Save a Face")
    print("  Press 'q' to Quit")
    print("="*50)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Failed to grab frame.")
            break

        # Display instructions on frame
        display_frame = cv2.flip(frame, 1)  # Mirror for natural view
        cv2.putText(display_frame, "Press 's' to Save | 'q' to Quit", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, common.COLOR_GREEN, 2)

        # Show the frame
        cv2.imshow("Enrollment", display_frame)

        key = cv2.waitKey(1) & 0xFF

        # --- Capture Logic ---
        if key == ord('s'):
            print("\n[INFO] Processing frame for face detection...")
            
            # Convert to RGB (face_recognition uses RGB, OpenCV uses BGR)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 1. Detect Face Locations
            boxes = face_recognition.face_locations(rgb_frame, model="hog")
            
            if len(boxes) == 0:
                print("[WARNING] No face detected! Try getting closer/better lighting.")
                continue
            elif len(boxes) > 1:
                print("[WARNING] Multiple faces detected! Please ensure only ONE person is in frame.")
                continue
            
            # 2. Compute Encoding (for the one face)
            print("[INFO] Face detected. Encoding...")
            encodings = face_recognition.face_encodings(rgb_frame, boxes)
            
            if len(encodings) > 0:
                new_encoding = encodings[0]
                
                # 3. Ask for Name
                # We temporarily release the camera/window focus by input()
                name = input("Enter Student Name: ").strip()
                
                if name:
                    # 4. Save to Pickle
                    data = load_encodings()
                    data["names"].append(name)
                    data["encodings"].append(new_encoding)
                    save_encodings(data)
                    print(f"[SUCCESS] Enrolled {name}!")
                else:
                    print("[INFO] Enrollment cancelled (empty name).")
            else:
                 print("[ERROR] Could not encode face.")

        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    enroll_student()
