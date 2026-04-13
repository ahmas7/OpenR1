"""
R1 Voice System - TTS and STT
Uses Windows SAPI or pyttsx3
"""
import threading
import queue
import time

# Try different TTS backends
TTS_ENGINE = None
TTS_AVAILABLE = False

# Try pyttsx3 first
try:
    import pyttsx3
    TTS_ENGINE = pyttsx3.init()
    TTS_AVAILABLE = True
    print("TTS: pyttsx3 loaded")
except Exception as e:
    import logging
    logging.getLogger("R1").debug(f"TTS backend unavailable: {e}")

# Try Windows SAPI as fallback
if not TTS_AVAILABLE:
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        TTS_AVAILABLE = True
        TTS_ENGINE = "sapi"
        print("TTS: Windows SAPI loaded")
    except:
        pass

# Try gtts as web fallback
try:
    from gtts import gTTS
    TTS_AVAILABLE_WEB = True
except Exception:
    TTS_AVAILABLE_WEB = False

is_speaking = False

def speak(text, async_mode=True):
    """R1 speaks the given text"""
    global is_speaking
    
    if not TTS_AVAILABLE:
        # Try web TTS
        if TTS_AVAILABLE_WEB:
            import tempfile
            import os
            try:
                tts = gTTS(text=text, lang='en')
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                    tts.save(f.name)
                    os.system(f'start /b "{f.name}"')
                return True
            except:
                pass
        return False
    
    def _speak():
        global is_speaking
        try:
            is_speaking = True
            if TTS_ENGINE == "sapi":
                speaker.Speak(text)
            else:
                TTS_ENGINE.say(text)
                TTS_ENGINE.runAndWait()
        except Exception as e:
            print(f"TTS Error: {e}")
        finally:
            is_speaking = False
    
    if async_mode:
        threading.Thread(target=_speak, daemon=True).start()
    else:
        _speak()
    
    return True


def set_wake_word(word: str):
    global WAKE_WORD
    if word:
        WAKE_WORD = word.lower()


def set_voice_preference(gender: str = "male"):
    global TTS_ENGINE
    if not TTS_AVAILABLE or TTS_ENGINE in ("sapi", None):
        return False
    try:
        voices = TTS_ENGINE.getProperty("voices")
        if not voices:
            return False
        preferred = None
        gender = (gender or "").lower()
        for v in voices:
            name = (v.name or "").lower()
            if gender == "male" and ("male" in name or "david" in name):
                preferred = v
                break
            if gender == "female" and ("female" in name or "zira" in name):
                preferred = v
                break
        if not preferred:
            preferred = voices[0]
        TTS_ENGINE.setProperty("voice", preferred.id)
        return True
    except Exception:
        return False

def stop_speaking():
    """Stop R1 from speaking"""
    global is_speaking
    try:
        if TTS_ENGINE == "sapi":
            speaker.Speak("")  # Interrupts
        elif TTS_ENGINE:
            TTS_ENGINE.stop()
        is_speaking = False
        return True
    except:
        return False

def speak_sync(text):
    """Speak synchronously"""
    speak(text, async_mode=False)

# Speech Recognition
STT_AVAILABLE = False
try:
    import speech_recognition as sr
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    STT_AVAILABLE = True
    print("STT: speech_recognition loaded")
except Exception as e:
    print(f"STT not available: {e}")

def listen(timeout=5):
    """Listen for speech and convert to text"""
    if not STT_AVAILABLE:
        return None
    
    try:
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=timeout)
        
        text = recognizer.recognize_google(audio)
        return text
    except Exception as e:
        print(f"STT Error: {e}")
        return None

# Wake word
try:
    from R1.config.settings import settings
    WAKE_WORD = settings.wake_word.lower()
except Exception:
    WAKE_WORD = "ar1"
wake_listening = False

def start_wake_listener(callback):
    """Start listening for wake word"""
    if not STT_AVAILABLE:
        return False
    
    global wake_listening
    wake_listening = True
    
    def _listen():
        while wake_listening:
            try:
                with microphone as source:
                    audio = recognizer.listen(source, timeout=1)
                text = recognizer.recognize_google(audio).lower()
                if WAKE_WORD in text:
                    callback()
            except:
                continue
    
    threading.Thread(target=_listen, daemon=True).start()
    return True

def stop_wake_listener():
    global wake_listening
    wake_listening = False
    return True

def get_status():
    return {
        "tts_available": TTS_AVAILABLE,
        "stt_available": STT_AVAILABLE,
        "is_speaking": is_speaking,
        "wake_listening": wake_listening,
        "wake_word": WAKE_WORD
    }
