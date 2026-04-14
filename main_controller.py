"""
Main Assistant Controller - Assistive Vision System
Centralized control for all voice commands and modules.
- Start Detection, Navigate, Stop, Close
- Parallel safety detection during navigation (obstacle alerts override nav speech)
"""
import time
import signal
import sys
import threading
import cv2

from voice_engine import VoiceEngine
from object_detector import ObjectDetector
from navigation_module import NavigationModule
from intent_classifier import IntentClassifier
from config import Config


class MainController:
    def __init__(self):
        self.voice_engine = VoiceEngine()
        self.object_detector = ObjectDetector(self.voice_engine)
        self.navigation_module = NavigationModule(self.voice_engine)
        self.intent_classifier = IntentClassifier()
        
        self.current_mode = None
        self.is_running = True
        self.waiting_for_destination = False
        self.waiting_for_language = False   # NEW: waiting for user to say a language name
        
        self.safety_camera = None
        self.safety_thread = None
        
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)
    
    def start(self):
        self.voice_engine.speak_native('appStarted', async_speak=False)
        self.voice_engine.start_continuous_listening(self._handle_command)
        
        try:
            while self.is_running:
                time.sleep(0.02)
        except KeyboardInterrupt:
            self.shutdown()
    
    def _handle_command(self, command):
        if not command:
            return
        print(f"🔄 Processing command: {command}")
        
        lang = self.voice_engine.current_language

        # ── Language selection mode ─────────────────────────────────────────
        if self.waiting_for_language:
            intent = self.intent_classifier.classify_intent(command, lang)
            if intent == 'STOP':
                self.waiting_for_language = False
                self.voice_engine.speak_native('nothingToStop')
                return
            if intent == 'CLOSE':
                self.shutdown()
                return
            # Try to resolve a language name from what the user said
            resolved_lang = self.intent_classifier.resolve_language(command)
            if resolved_lang:
                old_lang = lang
                self.voice_engine.set_language(resolved_lang)
                self.waiting_for_language = False
                self.voice_engine.speak_native('languageChanged')
                print(f"🌐 Language changed: {old_lang} → {resolved_lang}")
            else:
                self.voice_engine.speak_native('languageNotRecognised')
            return

        # ── Waiting for navigation destination ──────────────────────────────
        if self.waiting_for_destination:
            intent = self.intent_classifier.classify_intent(command, lang)
            print(f"🎯 Navigation waiting - intent: {intent}")
            if intent == 'STOP':
                print("🛑 Calling STOP from navigation waiting")
                self._handle_stop()
                return
            if intent == 'CLOSE':
                self.shutdown()
                return
            # When waiting for destination, ANY non-command text is treated as destination
            if not intent and command and len(command.strip()) > 2:
                print(f"🎯 Treating as destination: {command}")
                self.navigation_module.set_destination(command)
                if self.navigation_module.is_navigating:
                    self.waiting_for_destination = False
                    self._start_safety_detection()
                return
            return

        # ── Normal command routing ──────────────────────────────────────────
        intent = self.intent_classifier.classify_intent(command, lang)
        print(f"🎯 Main intent: {intent}")
        
        if intent == 'STOP':
            print("🛑 Calling STOP from main handler")
            self._handle_stop()
            return
        if intent == 'CLOSE':
            self._handle_close()
            return

        if intent == 'CHANGE_LANGUAGE':
            self.waiting_for_language = True
            # Ask the user which language they want — in current language
            lang_prompt = {
                'en': 'Which language? Say Telugu, Hindi, Tamil, or English.',
                'te': 'ఏ భాష? తెలుగు, హిందీ, తమిళం లేదా ఇంగ్లీష్ అని చెప్పండి.',
                'hi': 'कौन सी भाषा? तेलुगू, हिंदी, तमिल या अंग्रेजी बोलें।',
                'ta': 'எந்த மொழி? தெலுங்கு, இந்தி, தமிழ் அல்லது ஆங்கிலம் என சொல்லுங்கள்.',
            }
            self.voice_engine.speak(lang_prompt.get(lang, lang_prompt['en']))
            return
        
        if self.current_mode is not None:
            self.voice_engine.speak_native('alreadyInMode')
            return
        
        if intent == 'START_DETECTION':
            print("🔍 Starting detection mode...")
            self.current_mode = 'DETECTION'
            self.voice_engine.speak_native('detectionStarted')
            self.object_detector.start_detection()
            print(f"🔍 Detection started - is_detecting: {self.object_detector.is_detecting}")
            # If camera failed, reset mode so user can try again.
            if not self.object_detector.is_detecting:
                print("❌ Camera failed - resetting mode")
                self.current_mode = None
        
        elif intent == 'NAVIGATE':
            self.current_mode = 'NAVIGATION'
            dest = self.intent_classifier.extract_destination(command)
            if dest:
                self.navigation_module.start_navigation(dest)
                if self.navigation_module.is_navigating:
                    self._start_safety_detection()
                elif self.current_mode == 'NAVIGATION':
                    self.current_mode = None
            else:
                self.voice_engine.speak_native('sayDestination')
                self.navigation_module.start_navigation()  # asks for destination
                self.waiting_for_destination = True
        
        elif not intent:
            self.voice_engine.speak_native('commandNotRecognised')
    
    def _handle_stop(self):
        print(f"🛑 STOP called - current_mode: {self.current_mode}, waiting_for_destination: {self.waiting_for_destination}, waiting_for_language: {self.waiting_for_language}")
        
        if self.waiting_for_language:
            self.waiting_for_language = False
            self.voice_engine.speak_native('nothingToStop')
            return
        
        if self.current_mode is None and not self.waiting_for_destination:
            self.voice_engine.speak_native('nothingToStop')
            return
        
        # Always clear waiting state and stop navigation
        self.waiting_for_destination = False
        # Stop any ongoing/pending speech immediately so "stop" actually stops.
        try:
            self.voice_engine.cancel_speech()
        except Exception:
            pass
        
        if self.current_mode == 'DETECTION':
            summary = self.object_detector.get_last_detection_summary()
            if summary:
                name, dist, direction = summary
                self.voice_engine.speak_sync(f"Last detected {name} {dist:.1f} meters {direction}.")
            self.object_detector.stop_detection()
            self.voice_engine.speak_native('detectionStopped')
        elif self.current_mode == 'NAVIGATION':
            summary = self.object_detector.get_last_detection_summary()
            if summary:
                name, dist, direction = summary
                self.voice_engine.speak_sync(f"Last detected {name} {dist:.1f} meters {direction}.")
            self._stop_safety_detection()
            self.navigation_module.stop_navigation()
            self.voice_engine.speak_native('navigationStopped')
        
        if self.current_mode == 'NAVIGATION' or self.waiting_for_destination:
            self.navigation_module.stop_navigation()
            if not self.voice_engine.is_speaking:
                self.voice_engine.speak_native('navigationStopped')
        
        self.current_mode = None
        print("🛑 STOP completed")
    
    def _handle_close(self):
        self.shutdown()
    
    def _start_safety_detection(self):
        """Parallel YOLO detection during navigation - obstacle alerts override nav"""
        if self.safety_thread and self.safety_thread.is_alive():
            return
        try:
            # Prefer DirectShow on Windows to avoid MSMF grabFrame errors.
            try:
                self.safety_camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            except Exception:
                self.safety_camera = cv2.VideoCapture(0)
            if self.safety_camera and not self.safety_camera.isOpened():
                self.safety_camera.release()
                self.safety_camera = cv2.VideoCapture(0)
            if not self.safety_camera.isOpened():
                return
            self.safety_thread = threading.Thread(target=self._safety_loop, daemon=True)
            self.safety_thread.start()
        except Exception as e:
            print(f"Safety detection start error: {e}")
    
    def _stop_safety_detection(self):
        if self.safety_camera:
            self.safety_camera.release()
            self.safety_camera = None
    
    def _safety_loop(self):
        """Parallel object detection during navigation - same as Start Detection (thresholds + voice)."""
        last_detection = 0
        fail_count = 0
        while (self.current_mode == 'NAVIGATION' and
               self.navigation_module.is_navigating and
               self.safety_camera and self.safety_camera.isOpened() and
               not self.voice_engine._shutting_down):
            now = time.time()
            if now - last_detection >= Config.DETECTION_INTERVAL:
                ret, frame = self.safety_camera.read()
                if not ret:
                    fail_count += 1
                    if fail_count >= 60:
                        # Stop safety camera to avoid OpenCV warning spam.
                        self._stop_safety_detection()
                        break
                    time.sleep(0.05)
                    continue
                fail_count = 0
                if not self.voice_engine._shutting_down:
                    objs = self.object_detector.run_detection_frame(frame)
                    if objs and not self.voice_engine._shutting_down:
                        self.object_detector.announce_detections_safe(objs)
                last_detection = now
            time.sleep(0.1)
    
    def _on_signal(self, signum, frame):
        self.voice_engine.set_shutting_down(True)
        self.shutdown()
    
    def shutdown(self):
        # Cancel any ongoing speech immediately, then mark shutting down.
        try:
            self.voice_engine.cancel_speech()
        except Exception:
            pass
        self.voice_engine.set_shutting_down(True)
        self.is_running = False
        self.waiting_for_destination = False
        
        # Stop all active modes and release microphone
        if self.current_mode == 'DETECTION':
            self.object_detector.stop_detection()
        elif self.current_mode == 'NAVIGATION':
            self._stop_safety_detection()
            self.navigation_module.stop_navigation()
        
        # Always stop voice engine to release microphone
        self.voice_engine.stop_listening()
        self.current_mode = None
        
        self.voice_engine.stop_listening()
        time.sleep(0.6)
        self.voice_engine.speak_native('appClosing', async_speak=False)
        time.sleep(0.8)
        print("🎤 Microphone released - Application shutdown complete")
        sys.exit(0)


if __name__ == "__main__":
    controller = MainController()
    controller.start()
