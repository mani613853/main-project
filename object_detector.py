"""
Object Detection Module - YOLOv8 COCO (80 classes)
Detects all COCO classes: person, car, chair, bottle, bicycle, etc. (not only person).
Distance: Calibration (FocalLength = PixelWidth×KnownDistance/RealWidth) + real-time
  Distance = RealObjectWidth×FocalLength/PixelWidth with frame averaging and spike rejection.
Direction: Left / Right / Ahead (object center vs frame center).
Safety: <0.5m critical, 0.5–1m warning, >1m informational.
"""
import cv2
import json
import threading
import time
from collections import deque
from pathlib import Path
from ultralytics import YOLO

from config import Config

CALIBRATION_FILE = Path(__file__).parent / "calibration.json"


# Reference object size database (meters) - for Distance = (RealObjectWidth × FocalLength) / PixelWidth
# Spec: Person 0.45m, Chair 0.50m, Car 1.8m, Bicycle 0.6m, Bottle 0.07m
REAL_OBJECT_WIDTHS = {
    'person': 0.45, 'bicycle': 0.6, 'car': 1.8, 'motorcycle': 0.8, 'bus': 2.5,
    'truck': 2.2, 'chair': 0.50, 'couch': 1.2, 'bottle': 0.07, 'laptop': 0.35,
    'tv': 0.8, 'cell phone': 0.15, 'book': 0.2, 'cup': 0.08, 'dining table': 1.0,
    'umbrella': 0.5, 'handbag': 0.3, 'backpack': 0.4, 'sports ball': 0.22,
    'keyboard': 0.45, 'mouse': 0.1, 'remote': 0.15, 'microwave': 0.5,
    'oven': 0.6, 'refrigerator': 0.9, 'clock': 0.2, 'vase': 0.2,
    'teddy bear': 0.3, 'potted plant': 0.3, 'bed': 1.5, 'toilet': 0.4,
}
DEFAULT_REAL_WIDTH = 0.5

_OBJ_TRANSLATIONS = {
    'person': {'te': 'వ్యక్తి', 'hi': 'व्यक्ति', 'ta': 'நபர்', 'en': 'person'},
    'car': {'te': 'కారు', 'hi': 'गाड़ी', 'ta': 'கார்', 'en': 'car'},
    'bicycle': {'te': 'సైకిల్', 'hi': 'साइकिल', 'ta': 'சைக்கிள்', 'en': 'bicycle'},
    'motorcycle': {'te': 'బైక్', 'hi': 'मोटरसाइकिल', 'ta': 'பைக்', 'en': 'motorcycle'},
    'bus': {'te': 'బస్సు', 'hi': 'बस', 'ta': 'பேருந்து', 'en': 'bus'},
    'truck': {'te': 'లారీ', 'hi': 'ट्रक', 'ta': 'லாரி', 'en': 'truck'},
    'cell phone': {'te': 'మొబైల్ ఫొన్', 'hi': 'मोबाइल फोन', 'ta': 'மொபைல்', 'en': 'cell phone'},
    'chair': {'te': 'కుర్చీ', 'hi': 'कुर्सी', 'ta': 'நாற்காலி', 'en': 'chair'},
    'bottle': {'te': 'బాటిల్', 'hi': 'बोतल', 'ta': 'பாட்டில்', 'en': 'bottle'},
    'laptop': {'te': 'ల్యాప్‌టాప్', 'hi': 'लैपटॉप', 'ta': 'மடிக்கணினி', 'en': 'laptop'},
}

_DIR_TRANSLATIONS = {
    'ahead': {'te': 'ముందుకు', 'hi': 'आगे', 'ta': 'நேராக', 'en': 'ahead'},
    'left': {'te': 'ఎడమ వైపు', 'hi': 'बाएँ', 'ta': 'இடதுபுறம்', 'en': 'left'},
    'right': {'te': 'కుడి వైపు', 'hi': 'दाएँ', 'ta': 'வலதுபுறம்', 'en': 'right'}
}

class ObjectDetector:
    def __init__(self, voice_engine):
        self.voice_engine = voice_engine
        
        # Enhanced YOLO model with COCO dataset
        model_path = Path(__file__).parent / Config.YOLO_MODEL
        print(f"🔍 Loading YOLO model: {Config.YOLO_MODEL}")
        
        try:
            if model_path.exists():
                self.model = YOLO(str(model_path))
                print(f"✅ YOLO model loaded from: {model_path}")
            else:
                # Use YOLOv8n pretrained on COCO dataset (best for real-time)
                self.model = YOLO('yolov8n.pt')  # Nano version - fastest
                print("🌐 Downloaded YOLOv8n pretrained model (COCO dataset)")
        except Exception as e:
            print(f"❌ Failed to load YOLO model: {e}")
            # Fallback to yolov8n
            self.model = YOLO('yolov8n.pt')
        
        # COCO class names (80 classes)
        self.coco_classes = self.model.names
        print(f"🏷️ COCO classes loaded: {len(self.coco_classes)} classes")
        
        # Important classes for assistive vision
        self.important_classes = {
            'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck',
            'traffic light', 'stop sign', 'parking meter', 'bench',
            'chair', 'couch', 'potted plant', 'bed', 'dining table',
            'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard',
            'cell phone', 'microwave', 'oven', 'sink', 'refrigerator',
            'book', 'clock', 'vase', 'scissors', 'teddy bear',
            'hair drier', 'toothbrush'
        }
        
        self.camera = None
        self.is_detecting = False
        self.detection_thread = None

        # Calibration: load from calibration.json if exists, else use default
        self.focal_length = Config.DEFAULT_FOCAL_LENGTH
        self.calibrated = False
        if CALIBRATION_FILE.exists():
            try:
                with open(CALIBRATION_FILE) as f:
                    data = json.load(f)
                    self.focal_length = float(data.get("focal_length", self.focal_length))
                    self.calibrated = True
            except Exception:
                pass

        # Distance smoothing: frame averaging + ignore abnormal spikes
        self._distance_history = {}
        self._smoothing_frames = max(5, getattr(Config, 'DISTANCE_SMOOTHING_FRAMES', 5))
        self._max_spike_ratio = 2.0  # reject if new value > 2x or < 0.5x of recent avg
        self._last_detected = []
        self._session_token = 0  # increments on start/stop to cancel late announcements
        self._last_spoken_at = 0.0
        self._last_spoken_key = None
        self._last_spoken_zone = None
        self._last_spoken_distance = None
        self._last_spoken_direction = None

    def get_last_detection_summary(self):
        """Return (name, distance_m, direction) for closest last detection, or None."""
        objs = getattr(self, "_last_detected", []) or []
        if not objs:
            return None
        closest = min(objs, key=lambda x: x.get("distance", 1e9))
        name = closest.get("name")
        dist = float(closest.get("distance", 0.0))
        direction = closest.get("direction", "ahead")
        if not name:
            return None
        return (name, dist, direction)
    
    def calibrate(self, pixel_width, known_distance, real_width):
        """
        Calibration: FocalLength = (PixelWidth * KnownDistance) / RealWidth
        """
        if pixel_width > 0 and real_width > 0:
            self.focal_length = (pixel_width * known_distance) / real_width
            self.calibrated = True
            return self.focal_length
        return self.focal_length
    
    def start_detection(self):
        if self.is_detecting:
            return
        try:
            self._session_token += 1
            # On Windows, MSMF backend can fail with "can't grab frame" for some cameras.
            # Prefer DirectShow when available, then fall back.
            try:
                self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            except Exception:
                self.camera = cv2.VideoCapture(0)
            if self.camera and not self.camera.isOpened():
                self.camera.release()
                self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                self.voice_engine.speak("Camera not available")
                return
            self.is_detecting = True
            self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
            self.detection_thread.start()
        except Exception as e:
            print(f"Detection error: {e}")
            self.voice_engine.speak("Failed to start detection")
    
    def stop_detection(self):
        self._session_token += 1
        self.is_detecting = False
        if self.camera:
            self.camera.release()
            self.camera = None
        self._distance_history.clear()
        self._last_detected = []
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
    
    def run_detection_frame(self, frame):
        """Run detection on a frame - used for parallel safety during navigation"""
        return self._process_frame_internal(frame, announce=False)

    def announce_detections_safe(self, detected_list):
        """Same as Start Detection: use safety thresholds and voice for a list of detections.
        Used during navigation so parallel object detection works identically."""
        if not detected_list or getattr(self.voice_engine, '_shutting_down', False):
            return
        detected_list = sorted(detected_list, key=lambda x: x['distance'])
        self._announce_with_safety(detected_list)
    
    def _detection_loop(self):
        last_time = 0
        fail_count = 0
        session = self._session_token
        window_name = "Object Detection - Say 'stop' to exit"
        while self.is_detecting and not getattr(self.voice_engine, '_shutting_down', False):
            if self.camera and self.camera.isOpened():
                ret, frame = self.camera.read()
                if not ret:
                    fail_count += 1
                    if fail_count >= 60:
                        self.voice_engine.speak("Camera frame not available. Stopping detection.")
                        break
                    time.sleep(0.05)
                    continue
                fail_count = 0
                now = time.time()
                if (now - last_time) >= Config.DETECTION_INTERVAL:
                    detected = self._process_frame_internal(frame, announce=True, session=session)
                    last_time = now
                    frame = self._draw_boxes(frame, detected)
                else:
                    frame = self._draw_boxes(frame, [])
                try:
                    cv2.imshow(window_name, frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                except Exception:
                    pass
            time.sleep(0.03)
        # Ensure camera/resources are released even on capture failure.
        if self.is_detecting:
            self.stop_detection()
    
    def _process_frame_internal(self, frame, announce=True, session=None):
        """Enhanced frame processing with COCO dataset and smart filtering"""
        if getattr(self.voice_engine, '_shutting_down', False):
            return []
        try:
            # Enhanced YOLO inference with optimized settings
            results = self.model(
                frame,
                conf=Config.CONFIDENCE_THRESHOLD,
                iou=Config.NMS_THRESHOLD,
                verbose=False,
                max_det=20  # Limit detections for performance
            )
            height, width = frame.shape[:2]
            detected = []
            
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0].cpu().numpy())
                    cls_id = int(box.cls[0].cpu().numpy())
                    name = self.model.names[cls_id]
                    
                    # Prioritize important classes for assistive vision
                    if name not in self.important_classes:
                        continue  # Skip less important objects
                    
                    pixel_width = x2 - x1
                    center_x = x1 + pixel_width / 2
                    center_y = y1 + (y2 - y1) / 2

                    # Enhanced tracking with location buckets
                    bucket_x = int(center_x // 80)
                    bucket_y = int(center_y // 80)
                    track_key = f"{name}:{bucket_x}:{bucket_y}"
                    
                    # Distance calculation
                    raw_dist = self._compute_distance(pixel_width, name)
                    dist = self._smooth_distance(track_key, raw_dist)
                    direction = self._direction(center_x, width)
                    
                    # Only include objects within reasonable detection range
                    if dist <= 10.0:  # Max 10 meters for practical use
                        detected.append({
                            'name': name,
                            'distance': dist,
                            'direction': direction,
                            'confidence': conf,
                            'track_key': track_key,
                            'box': (x1, y1, x2, y2),
                            'importance': 'high' if name in ['person', 'car', 'bicycle', 'motorcycle', 'bus', 'truck'] else 'medium'
                        })
            
            # Sort by distance and importance
            detected.sort(key=lambda x: (x['distance'], 0 if x['importance'] == 'high' else 1))
            
            if announce and detected and not getattr(self.voice_engine, '_shutting_down', False):
                # Avoid late announcements after user says STOP
                if session is None or session == self._session_token:
                    self._announce_with_safety(detected)
            self._last_detected = detected
            return detected
        except Exception as e:
            print(f"Frame error: {e}")
            return []
    
    def _draw_boxes(self, frame, detected):
        """Draw bounding boxes and labels (object, distance, direction) on frame."""
        if getattr(self.voice_engine, '_shutting_down', False):
            return frame
        to_draw = detected if detected else getattr(self, '_last_detected', [])
        for obj in to_draw:
            name = obj.get('name', '')
            dist = obj.get('distance', 0)
            direction = obj.get('direction', '')
            conf = obj.get('confidence', None)
            box = obj.get('box')
            if box is None:
                continue
            x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            # 0.1–0.9 m: warning (red). >= 1.0 m: safe (green).
            color = (0, 0, 255) if 0.1 <= dist < Config.WARNING_DISTANCE else (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            if conf is not None:
                label = f"{name} | {dist:.1f} m | {conf:.2f}"
            else:
                label = f"{name} | {dist:.1f} m"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            # Keep label inside frame
            y_label_top = y1 - th - 10
            y_label_bottom = y1
            if y_label_top < 0:
                y_label_top = y1
                y_label_bottom = y1 + th + 10
            cv2.rectangle(frame, (x1, y_label_top), (x1 + tw, y_label_bottom), color, -1)
            cv2.putText(frame, label, (x1, y_label_bottom - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        return frame
    
    def _compute_distance(self, pixel_width, object_name):
        """Distance = (RealWidth * FocalLength) / PixelWidth"""
        real_w = REAL_OBJECT_WIDTHS.get(object_name, DEFAULT_REAL_WIDTH)
        if pixel_width <= 0:
            return 50.0
        dist = (real_w * self.focal_length) / pixel_width
        # Clamp to avoid 0.0 being spoken; minimum 0.1 m, max 50 m.
        return max(0.1, min(dist, 50.0))
    
    def _smooth_distance(self, name, distance):
        """Frame averaging + ignore sudden abnormal distance spikes."""
        if name not in self._distance_history:
            self._distance_history[name] = deque(maxlen=self._smoothing_frames)
        hist = self._distance_history[name]
        if len(hist) > 0:
            avg = sum(hist) / len(hist)
            if avg > 0:
                ratio = distance / avg
                if ratio > self._max_spike_ratio or ratio < (1.0 / self._max_spike_ratio):
                    distance = avg
        hist.append(distance)
        return sum(hist) / len(hist)
    
    def _direction(self, center_x, frame_width):
        """Left / Right / Ahead"""
        center = frame_width / 2
        thresh = frame_width / 6
        if abs(center_x - center) < thresh:
            return "ahead"
        return "left" if center_x < center else "right"
    
    def _announce_with_safety(self, objects):
        """Enhanced safety announcements with priority for assistive vision:
        - Emergency: <0.5m (Critical)
        - Warning: 0.5-1.0m (Caution)
        - Safe: >1.0m (Informational)
        - Priority: People > Vehicles > Other objects
        """
        if getattr(self.voice_engine, '_shutting_down', False):
            return
        
        # Find most important object (closest + highest priority)
        closest = objects[0]
        d = closest['distance']
        name = closest['name']
        direction = closest['direction']
        importance = closest.get('importance', 'medium')
        
        # Enhanced zone determination
        if d < Config.EMERGENCY_DISTANCE:
            zone = "emergency"
        elif d < Config.WARNING_DISTANCE:
            zone = "warning"
        else:
            zone = "safe"

        # Throttle speech to reduce lag and allow STOP/CLOSE to be recognized.
        now = time.time()
        min_interval = getattr(Config, "DETECTION_SPEECH_MIN_INTERVAL", 1.2)
        dist_delta = getattr(Config, "DETECTION_SPEECH_DISTANCE_DELTA", 0.2)

        key = closest.get("track_key") or name
        should_speak = False
        if self._last_spoken_key is None:
            should_speak = True
        elif key != self._last_spoken_key:
            should_speak = True
        elif zone != self._last_spoken_zone:
            should_speak = True
        elif self._last_spoken_direction != direction:
            should_speak = True
        elif self._last_spoken_distance is not None and abs(d - self._last_spoken_distance) >= dist_delta:
            should_speak = True
        elif now - self._last_spoken_at >= (min_interval * 2.5):
            should_speak = True

        if not should_speak:
            return
        if now - self._last_spoken_at < min_interval:
            return

        self._last_spoken_at = now
        self._last_spoken_key = key
        self._last_spoken_zone = zone
        self._last_spoken_distance = d
        self._last_spoken_direction = direction

        lang = self.voice_engine.current_language
        
        # Translate object
        t_obj = _OBJ_TRANSLATIONS.get(name, {}).get(lang)
        if not t_obj:
            t_obj = name if lang == 'en' else {'te': 'అడ్డంకి', 'hi': 'रुकावट', 'ta': 'பொருள்'}.get(lang, name)
        if not t_obj:
            t_obj = "obstacle" if lang == 'en' else "అడ్డంకి"
            
        # Translate direction
        t_dir = _DIR_TRANSLATIONS.get(direction, {}).get(lang, direction)
        
        # Build phrase
        if lang == 'te':
            if zone == "emergency":
                phrase = f"అత్యవసరం! {t_obj} {d:.1f} మీటర్ల {t_dir} ఉంది. ఆగు!"
            elif zone == "warning":
                phrase = f"జాగ్రత్త. {t_obj} {d:.1f} మీటర్ల {t_dir} ఉంది."
            else:
                phrase = f"{t_obj} {d:.1f} మీటర్ల {t_dir} ఉంది."
        elif lang == 'hi':
            if zone == "emergency":
                phrase = f"आपातकाल! {t_obj} {d:.1f} मीटर {t_dir} है। रुकें!"
            elif zone == "warning":
                phrase = f"सावधान। {t_obj} {d:.1f} मीटर {t_dir} है।"
            else:
                phrase = f"{t_obj} {d:.1f} मीटर {t_dir} है।"
        elif lang == 'ta':
            if zone == "emergency":
                phrase = f"அவசரம்! {t_obj} {d:.1f} மீட்டர் {t_dir}. நில்லுங்கள்!"
            elif zone == "warning":
                phrase = f"எச்சரிக்கை. {t_obj} {d:.1f} மீட்டர் {t_dir}."
            else:
                phrase = f"{t_obj} {d:.1f} மீட்டர் {t_dir}."
        else:
            # English
            if zone == "emergency":
                phrase = f"Emergency! {t_obj.title()} {d:.1f} meters {t_dir}. Stop!"
            elif zone == "warning":
                phrase = f"Caution. {t_obj.title()} {d:.1f} meters {t_dir}."
            else:
                phrase = f"{t_obj.title()} {d:.1f} meters {t_dir}."

        self.voice_engine.speak(phrase)
