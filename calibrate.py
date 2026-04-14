#!/usr/bin/env python3
"""
One-time calibration for distance estimation.
Place an object of KNOWN SIZE at KNOWN DISTANCE from the camera, then run this script.
Formula: FocalLength = (PixelWidth × KnownDistance) / RealWidth
"""
import cv2
import json
from pathlib import Path
from ultralytics import YOLO

from config import Config

# Real-world widths (meters) - same as object_detector
REAL_WIDTHS = {
    'person': 0.5, 'bicycle': 0.6, 'car': 1.8, 'chair': 0.5, 'bottle': 0.08,
    'laptop': 0.35, 'cell phone': 0.15, 'cup': 0.08, 'book': 0.2,
}
CALIB_FILE = Path(__file__).parent / "calibration.json"


def run_calibration():
    print("=" * 60)
    print("CALIBRATION - Distance Estimation")
    print("=" * 60)
    print("\n1. Place an object of KNOWN size at a KNOWN distance from the camera.")
    print("   Example: A person (0.5m width) standing 2 meters away")
    print("   Example: A bottle (0.08m) at 1 meter")
    print("\n2. Enter when ready. The script will detect the object and compute focal length.")
    print("\nObject types:", ", ".join(REAL_WIDTHS.keys()))
    print("-" * 60)

    known_dist = float(input("Known distance in meters (e.g. 2.0): ") or "2.0")
    obj_name = input("Object type (e.g. person, chair, bottle) [person]: ").strip().lower() or "person"
    real_width = REAL_WIDTHS.get(obj_name, 0.5)
    if obj_name not in REAL_WIDTHS:
        custom = input(f"Real width in meters for '{obj_name}' [{real_width}]: ").strip()
        if custom:
            real_width = float(custom)

    model = YOLO(Config.YOLO_MODEL)
    # Prefer DirectShow on Windows to avoid MSMF grabFrame errors.
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    except Exception:
        cap = cv2.VideoCapture(0)
    if cap and not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Camera not available")
        return

    print("\nCapturing... Point camera at the object. Press SPACE when you see a good detection.")
    focal_length = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        results = model(frame, conf=0.5, verbose=False)
        vis = frame.copy()
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                cls_id = int(box.cls[0].cpu().numpy())
                name = model.names[cls_id]
                pw = x2 - x1
                fl = (pw * known_dist) / real_width if pw > 0 else 0
                cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                label = f"{name} pw={pw:.0f} -> FL={fl:.0f}"
                cv2.putText(vis, label, (int(x1), int(y1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                focal_length = fl
        cv2.imshow("Calibration - SPACE to save, Q to quit", vis)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(" "):
            break
        if key == ord("q"):
            cap.release()
            cv2.destroyAllWindows()
            return

    cap.release()
    cv2.destroyAllWindows()

    if focal_length and focal_length > 0:
        data = {"focal_length": focal_length, "known_distance": known_dist, "real_width": real_width}
        with open(CALIB_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nCalibration saved: focal_length = {focal_length:.1f}")
        print(f"Stored in {CALIB_FILE}")
        print("The object_detector will load this automatically on next run.")
    else:
        print("\nNo valid detection. Try again with the object clearly visible.")


if __name__ == "__main__":
    run_calibration()
