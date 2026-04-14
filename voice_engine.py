"""
Speech Engine - Windows Platform
Input: Windows Speech Recognition
Output: Microsoft SAPI (Speech API)
No cloud API required for speech on Windows
Language-aware: switches STT locale when language changes.
"""
import threading
import time
import io
import pygame
from gtts import gTTS
import speech_recognition as sr

try:
    import win32com.client
    SAPI_AVAILABLE = True
except ImportError:
    SAPI_AVAILABLE = False
    import pyttsx3

from config import Config

# Google STT language codes per language
_STT_LOCALE = {
    'en': 'en-US',
    'te': 'te-IN',
    'hi': 'hi-IN',
    'ta': 'ta-IN',
}

# Hardcoded native system phrases (no Translation API needed)
_SYSTEM_PHRASES = {
    'en': {
        'appStarted': 'Application started. Please say a command in English.',
        'waitingCommand': 'Waiting for your command.',
        'commandNotRecognised': 'Command not recognised. Please say start detection, navigation, or change language.',
        'nothingToStop': 'Nothing to stop.',
        'appClosing': 'Application is closing. Goodbye.',
        'languageChanged': 'Language changed to English.',
        'languageNotRecognised': 'Language not recognised. Please say Telugu, Hindi, Tamil, or English.',
        'detectionStarted': 'Object detection started.',
        'detectionStopped': 'Object detection stopped. Ready for next command.',
        'navigationStarted': 'Navigation started.',
        'navigationStopped': 'Navigation stopped. Ready for next command.',
        'sayDestination': 'Please say your destination now.',
        'alreadyInMode': 'Already in this mode. Say stop to exit first.',
    },
    'te': {
        'appStarted': 'యాప్ ప్రారంభమైంది. దయచేసి తెలుగులో ఆదేశం చెప్పండి.',
        'waitingCommand': 'మీ ఆదేశం కోసం వేచి ఉన్నాను.',
        'commandNotRecognised': 'ఆదేశం గుర్తించబడలేదు. డిటెక్షన్ ప్రారంభించు, నావిగేషన్, లేదా భాష మార్చు అని చెప్పండి.',
        'nothingToStop': 'ఆపడానికి ఏమీ లేదు.',
        'appClosing': 'యాప్ మూతపడుతోంది. వెళ్ళొస్తాను.',
        'languageChanged': 'భాష తెలుగుకు మార్చబడింది.',
        'languageNotRecognised': 'భాష గుర్తించబడలేదు. తెలుగు, హిందీ, తమిళం లేదా ఇంగ్లీష్ అని చెప్పండి.',
        'detectionStarted': 'ఆబ్జెక్ట్ డిటెక్షన్ ప్రారంభమైంది.',
        'detectionStopped': 'ఆబ్జెక్ట్ డిటెక్షన్ ఆపివేయబడింది. తదుపరి ఆదేశం కోసం సిద్ధంగా ఉన్నాను.',
        'navigationStarted': 'నావిగేషన్ ప్రారంభమైంది.',
        'navigationStopped': 'నావిగేషన్ ఆపివేయబడింది. తదుపరి ఆదేశం కోసం సిద్ధంగా ఉన్నాను.',
        'sayDestination': 'దయచేసి మీ గమ్యస్థానం చెప్పండి.',
        'alreadyInMode': 'ఇప్పటికే ఈ మోడ్‌లో ఉన్నాను. ముందు ఆపు అని చెప్పండి.',
    },
    'hi': {
        'appStarted': 'एप्लीकेशन शुरू हो गया। कृपया हिंदी में आदेश बोलें।',
        'waitingCommand': 'आपके आदेश का इंतज़ार है।',
        'commandNotRecognised': 'आदेश पहचाना नहीं गया। डिटेक्शन शुरू करो, नेविगेशन, या भाषा बदलो बोलें।',
        'nothingToStop': 'रोकने के लिए कुछ नहीं है।',
        'appClosing': 'एप्लीकेशन बंद हो रहा है। नमस्ते।',
        'languageChanged': 'भाषा हिंदी में बदल दी गई है।',
        'languageNotRecognised': 'भाषा पहचानी नहीं गई। तेलुगू, हिंदी, तमिल या अंग्रेजी बोलें।',
        'detectionStarted': 'ऑब्जेक्ट डिटेक्शन शुरू हो गया।',
        'detectionStopped': 'ऑब्जेक्ट डिटेक्शन रुक गया। अगले आदेश के लिए तैयार हूं।',
        'navigationStarted': 'नेविगेशन शुरू हो गया।',
        'navigationStopped': 'नेविगेशन रुक गया। अगले आदेश के लिए तैयार हूं।',
        'sayDestination': 'कृपया अभी अपना गंतव्य बोलें।',
        'alreadyInMode': 'पहले से इस मोड में हूं। पहले रुको बोलें।',
    },
    'ta': {
        'appStarted': 'பயன்பாடு தொடங்கியது. தயவுசெய்து தமிழில் கட்டளை சொல்லுங்கள்.',
        'waitingCommand': 'உங்கள் கட்டளைக்காக காத்திருக்கிறேன்.',
        'commandNotRecognised': 'கட்டளை அடையாளம் காணப்படவில்லை. கண்டறிதல் தொடங்கு, வழிசெலுத்தல், அல்லது மொழி மாற்று என சொல்லுங்கள்.',
        'nothingToStop': 'நிறுத்த எதுவும் இல்லை.',
        'appClosing': 'பயன்பாடு மூடப்படுகிறது. வணக்கம்.',
        'languageChanged': 'மொழி தமிழாக மாற்றப்பட்டது.',
        'languageNotRecognised': 'மொழி அடையாளம் காணப்படவில்லை. தெலுங்கு, இந்தி, தமிழ் அல்லது ஆங்கிலம் என சொல்லுங்கள்.',
        'detectionStarted': 'பொருள் கண்டறிதல் தொடங்கியது.',
        'detectionStopped': 'பொருள் கண்டறிதல் நிறுத்தப்பட்டது. அடுத்த கட்டளைக்கு தயாராக இருக்கிறேன்.',
        'navigationStarted': 'வழிசெலுத்தல் தொடங்கியது.',
        'navigationStopped': 'வழிசெலுத்தல் நிறுத்தப்பட்டது. அடுத்த கட்டளைக்கு தயாராக இருக்கிறேன்.',
        'sayDestination': 'தயவுசெய்து இப்போது உங்கள் இலக்கை சொல்லுங்கள்.',
        'alreadyInMode': 'ஏற்கனவே இந்த பயன்முறையில் இருக்கிறேன். முதலில் நிறுத்து என்று சொல்லுங்கள்.',
    },
}


class VoiceEngine:
    """Platform-specific voice engine for Windows (SAPI + Windows Speech Recognition)"""
    
    def __init__(self):
        self.is_listening = False
        self.is_speaking = False
        self._speak_lock = threading.Lock()
        self._last_spoken = {}
        self._shutting_down = False
        self._speech_token = 0  # increment to cancel pending speech threads
        self._time_speech_ended = 0.0
        self.current_language = 'en'  # current language code: en, te, hi, ta
        
        # Initialize SAPI for output
        if SAPI_AVAILABLE:
            try:
                self._speaker = win32com.client.Dispatch("SAPI.SpVoice")
                self._speaker.Rate = 0
                self._speaker.Volume = 100
                self._use_sapi = True
            except Exception:
                self._use_sapi = False
                self._tts = pyttsx3.init()
        else:
            self._use_sapi = False
            self._tts = pyttsx3.init()
            
        try:
            pygame.mixer.init()
        except Exception:
            pass
        
        # Speech recognition
        self._recognizer = sr.Recognizer()
        # Faster barge-in / command capture tuning
        try:
            self._recognizer.pause_threshold = 0.2
            self._recognizer.non_speaking_duration = 0.1
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.energy_threshold = 200  # More sensitive to quiet speech
        except Exception:
            pass
        self._microphone = sr.Microphone()
        self._bg_stop = None
        self._mic_opened = False
        try:
            with self._microphone as source:
                self._mic_opened = True
                self._recognizer.adjust_for_ambient_noise(source, duration=3)
        except Exception:
            pass

    def set_language(self, lang_code: str):
        """Switch current language. lang_code: 'en', 'te', 'hi', 'ta'"""
        if lang_code in _STT_LOCALE:
            self.current_language = lang_code
            print(f"🌐 Language switched to: {lang_code} (STT: {_STT_LOCALE[lang_code]})")

    def get_system_phrase(self, key: str) -> str:
        """Return a hardcoded native-language phrase for the current language."""
        phrases = _SYSTEM_PHRASES.get(self.current_language, _SYSTEM_PHRASES['en'])
        return phrases.get(key, _SYSTEM_PHRASES['en'].get(key, key))

    def speak_native(self, key: str, async_speak=True):
        """Speak a hardcoded native-language system phrase."""
        text = self.get_system_phrase(key)
        self.speak(text, async_speak=async_speak)
    
    def set_shutting_down(self, value=True):
        """Block new speech during shutdown."""
        self._shutting_down = value

    def cancel_speech(self):
        """Immediately cancel/purge current and pending speech (best-effort)."""
        # Cancel any threads that haven't started speaking yet
        with self._speak_lock:
            self._speech_token += 1
        # Best-effort: purge current speech in the TTS engine
        try:
            if getattr(self, "_use_sapi", False):
                # SVSFPurgeBeforeSpeak = 2 (purge queue / stop current)
                self._speaker.Speak("", 2)
            else:
                self._tts.stop()
        except Exception:
            pass

    def speak(self, text, async_speak=True, suppress_duplicate=True, ignore_shutdown=False):
        """Speak text using SAPI"""
        if not text or not text.strip():
            return
        if self._shutting_down and not ignore_shutdown:
            return
        
        # Duplicate speech suppression
        if suppress_duplicate:
            key = text[:80]
            now = time.time()
            if key in self._last_spoken:
                if now - self._last_spoken[key] < Config.DUPLICATE_SPEECH_INTERVAL:
                    return
            self._last_spoken[key] = now
        
        token = self._speech_token
        
        def _do_speak():
            if self._shutting_down and not ignore_shutdown:
                return
            if token != self._speech_token:
                return
            with self._speak_lock:
                self.is_speaking = True
            try:
                if self._shutting_down and not ignore_shutdown:
                    return
                if token != self._speech_token:
                    return
                # Use Google TTS via Pygame for native languages (since Windows SAPI defaults to English)
                if self.current_language != 'en':
                    try:
                        tts = gTTS(text=text, lang=self.current_language)
                        fp = io.BytesIO()
                        tts.write_to_fp(fp)
                        fp.seek(0)
                        pygame.mixer.music.load(fp)
                        pygame.mixer.music.play()
                        while pygame.mixer.music.get_busy() and not self._shutting_down and token == self._speech_token:
                            time.sleep(0.1)
                        pygame.mixer.music.unload()
                    except Exception as gtts_error:
                        print(f"gTTS Error (falling back to SAPI): {gtts_error}")
                        if self._use_sapi:
                            self._speaker.Speak(text)
                        else:
                            self._tts.say(text)
                            self._tts.runAndWait()
                elif self._use_sapi:
                    self._speaker.Speak(text)
                else:
                    self._tts.say(text)
                    self._tts.runAndWait()
            except Exception as e:
                print(f"TTS Error: {e}")
            finally:
                with self._speak_lock:
                    self.is_speaking = False
                    self._time_speech_ended = time.time()
        
        if async_speak:
            threading.Thread(target=_do_speak, daemon=True).start()
        else:
            _do_speak()
    
    def speak_sync(self, text, ignore_shutdown=False):
        """Speak and wait for completion (for critical alerts)"""
        self.speak(text, async_speak=False, ignore_shutdown=ignore_shutdown)
    
    def listen_for_command(self, timeout=0.5):
        """Listen for voice command - Sphinx (offline) or Windows Speech Recognition via Google"""
        try:
            with self._microphone as source:
                # Keep phrases short so STOP/CLOSE reacts quickly.
                print("🎤 Listening... Speak clearly now!")
                audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=5.0)
            
            # Try Sphinx (offline) first if configured - no cloud, works like Windows Speech Recognition
            if getattr(Config, 'USE_OFFLINE_SPEECH_FIRST', False):
                try:
                    command = self._recognizer.recognize_sphinx(audio)
                    if command and command.strip():
                        print(f"Sphinx recognized: {command.strip().lower()}")
                        return command.strip().lower()
                except (sr.UnknownValueError, OSError, Exception):
                    pass
            
            # Fallback: Google Speech (more accurate, requires internet)
            try:
                command = self._recognizer.recognize_google(audio, language='en-US')
                if command:
                    print(f"Google recognized: {command.strip().lower()}")
                    return command.strip().lower()
            except sr.UnknownValueError:
                print("❌ Speech not understood - please speak clearly and loudly")
            except sr.RequestError:
                print("❌ Speech service unavailable - check internet")
        except sr.WaitTimeoutError:
            print("⏱️ Timeout - please speak when you see 🎤 Listening...")
        except Exception as e:
            print(f"Listen error: {e}")
        return None
    
    def start_continuous_listening(self, callback):
        """Start continuous command listening (non-blocking)"""
        self.is_listening = True

        # Stop any previous background listener if present
        try:
            if self._bg_stop:
                self._bg_stop(wait_for_stop=False)
        except Exception:
            pass
        self._bg_stop = None

        last_idle_lock = threading.Lock()
        last_idle = {"ts": time.time()}

        def _mark_activity():
            with last_idle_lock:
                last_idle["ts"] = time.time()

        def _is_control_phrase(text: str) -> bool:
            t = (text or "").lower()
            return any(k in t for k in ["stop", "close", "shutdown", "exit", "quit", "terminate"])

        def bg_callback(recognizer, audio):
            """Runs in speech_recognition background thread."""
            if self.is_speaking or (time.time() - getattr(self, '_time_speech_ended', 0) < 1.5):
                # Discard audio recorded while TTS was still actively playing 
                # to prevent the bot from incorrectly reacting to its own voice!
                return
            
            try:
                command = None
                # Determine the correct Google STT locale for the current language
                stt_locale = _STT_LOCALE.get(self.current_language, 'en-US')

                # Offline first (fast) — Sphinx only works for English
                if self.current_language == 'en' and getattr(Config, 'USE_OFFLINE_SPEECH_FIRST', False):
                    try:
                        sphinx_result = recognizer.recognize_sphinx(audio)
                        if sphinx_result and sphinx_result.strip():
                            command = sphinx_result.strip().lower()
                            print(f"Sphinx recognized: {command}")
                    except Exception:
                        command = None
                # Google Speech Recognition — uses the correct language locale
                if not command:
                    try:
                        google_result = recognizer.recognize_google(audio, language=stt_locale)
                        if google_result:
                            command = google_result.strip().lower()
                            print(f"Google [{stt_locale}] recognized: {command}")
                    except Exception:
                        command = None
                if not command:
                    # Silently ignore failed recognition of background noise
                    return

                _mark_activity()
                try:
                    print(f"Heard command: {command}")
                except Exception:
                    pass

                # Always allow control phrases through
                callback(command)
            except Exception:
                # Never crash the listener thread
                return

        try:
            # Continuous background listening
            self._bg_stop = self._recognizer.listen_in_background(
                self._microphone,
                bg_callback,
                phrase_time_limit=5.0
            )
        except Exception as e:
            print(f"Background listen error: {e}")

        def status_loop():
            last_listen_print = 0.0
            last_wait_print = 0.0
            while self.is_listening:
                now = time.time()
                if now - last_listen_print >= 2.0:
                    try:
                        print("Listening for command...")
                    except Exception:
                        pass
                    last_listen_print = now
                with last_idle_lock:
                    idle_for = now - last_idle["ts"]
                if idle_for >= 10.0 and now - last_wait_print >= 10.0:
                    try:
                        print("Waiting for your command...")
                    except Exception:
                        pass
                    last_wait_print = now
                time.sleep(0.1)

        threading.Thread(target=status_loop, daemon=True).start()
    
    def stop_listening(self):
        """Stop continuous listening and release microphone"""
        self.is_listening = False
        try:
            if self._bg_stop:
                self._bg_stop(wait_for_stop=False)
        except Exception:
            pass
        self._bg_stop = None
        
        # Release microphone resources
        try:
            if self._mic_opened:
                self._microphone = None
                self._mic_opened = False
                print("🎤 Microphone released")
        except Exception:
            pass
