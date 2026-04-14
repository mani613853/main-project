# Assistive Vision System

Cross-platform, voice-controlled application for visually impaired users: real-time object detection, distance estimation, and GPS-based outdoor navigation.

## Features

- **Object Detection** – YOLOv8 (COCO 80 classes)
- **Distance Estimation** – Calibration + focal-length formula with frame smoothing
- **Direction** – Left / Right / Ahead
- **Safety Thresholds** – Emergency (<0.5 m), Warning (0.5–1 m), Informational (>1 m)
- **Navigation** – Google Directions, Geocoding, Places, Roads APIs
- **Parallel Safety** – Obstacle alerts during navigation override route instructions
- **Map View** – Google Maps opens in browser during navigation (route + position)
- **Speech** – Windows: SAPI + Windows Speech Recognition

## Setup

### 1. Install Dependencies

```bash
cd c:\Users\majji\OneDrive\Desktop\Go
pip install -r requirements.txt
```

### 2. Configure Google API

1. Copy `.env.example` to `.env`
2. Add your Google Maps API key to `.env`:
   ```
   GOOGLE_MAPS_API_KEY=your_key_here
   ```
3. Enable APIs in [Google Cloud Console](https://console.cloud.google.com):
   - **Directions API** (required)
   - **Geocoding API** (required – specific addresses/place names)
   - **Places API** (required for: "hospital", "restaurant", "bank", "shopping mall" near you or "hospital in Hyderabad")
   - **Roads API** (optional – snaps GPS to road; enable if you use real GPS)
   - **Maps JavaScript API** (for map view during navigation)

   **If you see REQUEST_DENIED or PERMISSION_DENIED:**
   - Go to [APIs & Services → Library](https://console.cloud.google.com/apis/library).
   - Search for **Places API** and **Roads API**, open each and click **Enable**.
   - Go to **APIs & Services → Credentials** → your API key → **Edit**.
   - Under "API restrictions", either leave "Don't restrict key" or add the APIs you use (Directions, Geocoding, Places, Roads, Maps JavaScript).
   - Save. Wait a minute and run `python test_navigation_api.py` again.  

### 3. YOLOv8 Model

The `ultralytics` package downloads `yolov8n.pt` (COCO pretrained) on first use. Or place a `.pt` file in the Go folder.

### 4. Calibration (Optional, Improves Distance Accuracy)

Run once per camera to calibrate distance estimation:

```bash
python calibrate.py
```

1. Place an object of **known size** at **known distance** (e.g. a person at 2 m)
2. Enter distance and object type when prompted
3. Point the camera at the object, press **SPACE** when detection looks good
4. Focal length is saved to `calibration.json` and used automatically

## Voice Commands

| Command         | Action                  |
|----------------|-------------------------|
| **Start Detection** | Begin object detection        |
| **Navigate**       | Start navigation             |
| **Stop**           | Exit current mode            |
| **Close**          | Shut down application        |

## Usage

```bash
python run.py
```

On startup: *"Application started. Please say a command."*

When you say **"Navigate"**, you can say:
- **Specific place (anywhere):** *"Sri Chaitanya School Rajam"*, *"Apollo Hospital Hyderabad"*
- **Category near you (5 km):** *"hospital"*, *"restaurant"*, *"bank"*, *"shopping mall"*, *"ATM"*, *"pharmacy"*
- **Category in a city:** *"hospital in Hyderabad"*, *"restaurant in Mumbai"*

A map opens in your browser showing the route and your position (updates every 3 seconds).

## Project Structure

```
Go/
├── config.py          # Configuration
├── voice_engine.py    # SAPI + Windows Speech Recognition
├── object_detector.py # YOLOv8 + distance/direction
├── navigation_module.py # Google Maps APIs
├── intent_classifier.py
├── main_controller.py # Central controller
├── run.py
├── calibrate.py       # One-time calibration script
├── map_view.py        # Map server (opens in browser during navigation)
├── map_static/        # Map HTML template
├── location_service.py
├── calibration.json   # Saved focal length (created by calibrate.py)
├── .env               # API keys (create from .env.example)
└── requirements.txt
```

## Distance Algorithm

**Calibration:** `FocalLength = (PixelWidth × KnownDistance) / RealWidth`  
**Estimation:** `Distance = (RealWidth × FocalLength) / PixelWidth`

## Optional Notes

- **Maps JavaScript API** – Required for the map view; enables map display during navigation.
- **Route storage** – The current route is kept in memory during navigation to avoid extra API calls.
