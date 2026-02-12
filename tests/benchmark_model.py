import cv2
import face_recognition
import time
import os
import urllib.request
import pickle
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_module import common

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# URLs for test images (Using GitHub raw content which is more reliable)
TEST_IMAGES = {
    "obama_1.jpg": "https://raw.githubusercontent.com/ageitgey/face_recognition/master/examples/obama.jpg",
    "obama_2.jpg": "https://raw.githubusercontent.com/ageitgey/face_recognition/master/examples/obama2.jpg",
    "biden.jpg": "https://raw.githubusercontent.com/ageitgey/face_recognition/master/examples/biden.jpg"
}

def download_data():
    print("[INFO] Downloading test dataset...")
    if not os.path.exists(TEST_DATA_DIR):
        os.makedirs(TEST_DATA_DIR)
        
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    for filename, url in TEST_IMAGES.items():
        path = os.path.join(TEST_DATA_DIR, filename)
        if not os.path.exists(path):
            print(f"  - Downloading {filename}...")
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
                    out_file.write(response.read())
            except Exception as e:
                print(f"    [ERROR] Failed to download {filename}: {e}")
        else:
            print(f"  - {filename} already exists.")

def run_benchmark():
    print("\n[INFO] Starting Benchmark...")
    
    # 1. Train (Enroll Obama)
    print("[STEP 1] Encoding reference face (Obama)...")
    obama_img = face_recognition.load_image_file(os.path.join(TEST_DATA_DIR, "obama_1.jpg"))
    obama_enc = face_recognition.face_encodings(obama_img)[0]
    
    known_encodings = [obama_enc]
    known_names = ["Barack Obama"]
    
    # 2. Test (Recognize Obama in different photo)
    print("[STEP 2] Testing recognition (Obama 2)...")
    start_time = time.time()
    
    test_img = face_recognition.load_image_file(os.path.join(TEST_DATA_DIR, "obama_2.jpg"))
    # Resize to emulate webcam 1080p -> processing size? 
    # Current logic uses 1.0 scale (so full size).
    
    locations = face_recognition.face_locations(test_img, model="hog")
    encodings = face_recognition.face_encodings(test_img, locations)
    
    end_time = time.time()
    process_time = end_time - start_time
    
    print(f"  - Processed in {process_time:.4f} seconds.")
    print(f"  - FPS Equivalent (Single Thread): {1.0/process_time:.2f}")
    
    found = False
    for encoding in encodings:
        matches = face_recognition.compare_faces(known_encodings, encoding, tolerance=common.TOLERANCE)
        if True in matches:
            print("  - [SUCCESS] Recognized Barack Obama!")
            found = True
            
    if not found:
        print("  - [FAILURE] Could not recognize Obama.")

    # 3. Test Unknown (Biden)
    print("\n[STEP 3] Testing Unknown (Biden)...")
    test_img_b = face_recognition.load_image_file(os.path.join(TEST_DATA_DIR, "biden.jpg"))
    locations_b = face_recognition.face_locations(test_img_b, model="hog")
    encodings_b = face_recognition.face_encodings(test_img_b, locations_b)
    
    for encoding in encodings_b:
        matches = face_recognition.compare_faces(known_encodings, encoding, tolerance=common.TOLERANCE)
        if True in matches:
             print("  - [FAILURE] False Positive! Recognized Biden as Obama.")
        else:
             print("  - [SUCCESS] Correctly identified as Unknown.")

if __name__ == "__main__":
    download_data()
    
    # Check if files exist before running
    if not os.path.exists(os.path.join(TEST_DATA_DIR, "obama_1.jpg")):
        print("[ERROR] Test data missing. Cannot run benchmark.")
    else:
        run_benchmark()
