"""
R1 - Text-to-Speech using Pocket-TTS
"""
import io
import base64
import asyncio
from typing import Optional


class TTSEngine:
    def __init__(self):
        self.model = None
        self.ready = False
    
    async def initialize(self):
        try:
            from pocket_tts import TTSModel
            self.model = TTSModel.load_model()
            self.ready = True
            return True
        except Exception as e:
            print(f"TTS init error: {e}")
            return False
    
    async def speak(self, text: str) -> Optional[str]:
        if not self.ready:
            await self.initialize()
        
        try:
            audio = self.model.generate(text)
            
            import scipy.io.wavfile as wavfile
            buffer = io.BytesIO()
            wavfile.write(buffer, rate=24000, data=audio)
            buffer.seek(0)
            
            audio_b64 = base64.b64encode(buffer.read()).decode()
            return audio_b64
        except Exception as e:
            print(f"TTS error: {e}")
            return None
    
    async def speak_to_file(self, text: str, filepath: str) -> bool:
        if not self.ready:
            await self.initialize()
        
        try:
            audio = self.model.generate(text)
            import scipy.io.wavfile as wavfile
            wavfile.write(filepath, rate=24000, data=audio)
            return True
        except Exception as e:
            print(f"TTS error: {e}")
            return False


tts_engine = TTSEngine()
