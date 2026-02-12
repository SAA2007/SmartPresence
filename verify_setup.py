import sys
import importlib

def check_package(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    
    try:
        module = importlib.import_module(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"✅ {package_name}: Installed ({version})")
        return True
    except ImportError as e:
        print(f"❌ {package_name}: NOT INSTALLED ({e})")
        return False
    except Exception as e:
        print(f"⚠️ {package_name}: Error during import ({e})")
        return False

print("--- SmartPresence Framework Verification ---")
print(f"Python Version: {sys.version.split()[0]}")

required_packages = [
    ("opencv-python", "cv2"),
    ("mediapipe", "mediapipe"),
    ("face_recognition", "face_recognition"),
    ("dlib", "dlib"),
    ("flask", "flask"),
    ("pandas", "pandas"),
    ("numpy", "numpy")
]

success_count = 0
for pkg, import_name in required_packages:
    if check_package(pkg, import_name):
        success_count += 1
        
        # Specific check for dlib CUDA (GPU support)
        if pkg == "dlib":
            try:
                import dlib
                if dlib.DLIB_USE_CUDA:
                    print("   [INFO] dlib is using CUDA (GPU Acceleration Enabled! 🚀)")
                else:
                    print("   [INFO] dlib is using CPU (Standard Mode)")
            except:
                pass

print("-" * 40)
if success_count == len(required_packages):
    print("🎉 All systems go! The framework is ready.")
else:
    print(f"⚠️ Found {len(required_packages) - success_count} missing packages.")
    print("   Run: pip install -r requirements.txt")
    print("   Note: If dlib fails, install Visual Studio C++ Build Tools first.")
