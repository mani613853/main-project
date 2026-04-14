"""
Configuration for Assistive Vision System
All Google API credentials loaded from .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root
PROJECT_ROOT = Path(__file__).parent.resolve()


class Config:
    # Google API - Loaded from .env
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
    
    # YOLOv8 COCO Model - place .pt file in Go folder and set filename here
    YOLO_MODEL = 'yolov8n.pt'
    YOLO_MODEL_PATH = PROJECT_ROOT / YOLO_MODEL
    
    # Detection
    CONFIDENCE_THRESHOLD = 0.5
    DETECTION_INTERVAL = 0.5  # seconds (real-time feel)
    NMS_THRESHOLD = 0.4
    
    # Distance calibration
    DEFAULT_FOCAL_LENGTH = 615
    CALIBRATION_KNOWN_DISTANCE = 1.0  # meters
    CALIBRATION_KNOWN_WIDTH = 0.5     # meters (reference object)
    
    # Safety thresholds (meters)
    EMERGENCY_DISTANCE = 0.5   # < 0.5m: Emergency alert
    WARNING_DISTANCE = 1.0     # 0.5-1m: Warning, >1m: Informational
    
    # Distance smoothing (frames)
    # Lower = faster updates (less lag when object moves).
    DISTANCE_SMOOTHING_FRAMES = 3

    # Speech update rate during detection (seconds)
    # Prevents repeating old distance many times and improves command recognition.
    DETECTION_SPEECH_MIN_INTERVAL = 0.8
    DETECTION_SPEECH_DISTANCE_DELTA = 0.1  # meters change required to speak again
    
    # Voice commands
    VOICE_COMMANDS = {
        'en': {
            'START_DETECTION': ['start detection', 'detect', 'begin detection', 'what is this', 'what is around me'],
            'NAVIGATE': ['navigate', 'navigation', 'start navigation', 'navigate to', 'directions'],
            'STOP': ['stop', 'exit', 'quit', 'stop detection', 'stop navigation'],
            'CLOSE': ['close', 'shutdown', 'exit app', 'quit app', 'terminate'],
            'CHANGE_LANGUAGE': ['change language', 'switch language', 'language change']
        },
        'te': {
            'START_DETECTION': ['start detection', 'start object detection', 'detection prarambhinchu', 'object detection prarambhinchu', 'detection start cheyi', 'డిటెక్షన్ ప్రారంభించు', 'ఆబ్జెక్ట్ డిటెక్షన్ ప్రారంభించు', 'ఆబ్జెక్ట్ ని', 'డిటెక్షన్'],
            'NAVIGATE': ['navigate', 'start navigation', 'navigation prarambhinchu', 'navigate cheyi', 'daari chupinchu', 'నావిగేషన్ ప్రారంభించు', 'దారి చూపించు', 'నావిగేట్ చేయి'],
            'STOP': ['stop', 'aapu', 'apeyi', 'ఆపు', 'ఆపేయి'],
            'CLOSE': ['close', 'exit', 'moosiveyi', 'app moosiveyi', 'మూసివేయి', 'యాప్ మూసివేయి', 'క్లోజ్'],
            'CHANGE_LANGUAGE': ['change language', 'language marchu', 'bhasha marchu', 'భాష మార్చు', 'లాంగ్వేజ్ మార్చు']
        },
        'hi': {
            'START_DETECTION': ['start detection', 'start object detection', 'detection shuru karo', 'object detection shuru karo', 'डिटेक्शन शुरू करो', 'ऑब्जेक्ट डिटेक्शन शुरू करो'],
            'NAVIGATE': ['navigate', 'start navigation', 'navigation shuru karo', 'rasta dikhao', 'नेविगेशन शुरू करो', 'रास्ता दिखाओ', 'नेविगेशन'],
            'STOP': ['stop', 'ruko', 'रुको', 'बंद करो'],
            'CLOSE': ['close', 'exit', 'app band karo', 'ऐप बंद करो', 'बाहर निकलो'],
            'CHANGE_LANGUAGE': ['change language', 'language badlo', 'bhasha badlo', 'भाषा बदलो']
        },
        'ta': {
            'START_DETECTION': ['start detection', 'start object detection', 'detection thodangu', 'object detection thodangu', 'டிடெக்ஷன் தொடங்கு', 'ஆப்ஜெக்ட் டிடெக்ஷன் தொடங்கு', 'கண்டறிதல் தொடங்கு'],
            'NAVIGATE': ['navigate', 'start navigation', 'navigation thodangu', 'vazhi kaattu', 'நெவிகேஷன் தொடங்கு', 'வழி காட்டு'],
            'STOP': ['stop', 'niruthu', 'நிறுத்து'],
            'CLOSE': ['close', 'exit', 'app moodu', 'ஆப்பை மூடு', 'வெளியேறு'],
            'CHANGE_LANGUAGE': ['change language', 'language maattru', 'mozhi maattru', 'மொழியை மாற்று', 'மொழி மாற்று']
        }
    }
    
    LANGUAGE_ALIASES = {
        'en': ['english', 'en', 'speak english', 'ఇంగ్లీష్', 'अंग्रेजी', 'ஆங்கிலம்'],
        'te': ['telugu', 'te', 'telugu language', 'తెలుగు', 'తెలుగు భాష', 'tell you', 'tell you go', 'tail-go', 'tailgo', 'taylor go'],
        'hi': ['hindi', 'hi', 'hindi language', 'हिंदी', 'हिन्दी', 'indy', 'in the', 'hen d', 'hin d'],
        'ta': ['tamil', 'ta', 'tamil language', 'தமிழ்', 'தமிழ் மொழி', 'tommel', 'tumble', 'camel']
    }
    
    # Duplicate speech suppression (seconds)
    DUPLICATE_SPEECH_INTERVAL = 3.0
    
    # Speech input: True = try Sphinx (offline) first, False = Google first
    USE_OFFLINE_SPEECH_FIRST = True
    
    # Navigation: route deviation and Roads API
    DEVIATION_THRESHOLD_METERS = 50
    POSITION_UPDATE_INTERVAL = 5  # seconds between position checks during nav

    # Places search: radius for "near me" / user preference (meters). 5000 = 5 km
    PLACES_SEARCH_RADIUS_METERS = 5000

    # Category keywords for daily life: say "hospital", "restaurant", "bank", "shopping mall" for nearest in radius
    PLACES_CATEGORY_KEYWORDS = [
        'hospital', 'restaurant', 'bank', 'shopping mall', 'mall', 'atm', 'pharmacy',
        'grocery', 'supermarket', 'cafe', 'coffee', 'petrol', 'gas station', 'police',
        'bus stand', 'railway station', 'train station', 'post office', 'library', 'park'
    ]
