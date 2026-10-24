import os
import uuid
import subprocess
import shutil
import hashlib
from pathlib import Path
from typing import Optional
from app.config import Config

import re

def _detect_tts_language(text: str, fallback_lang: str = "en") -> str:
    """Detects script of text to pick appropriate TTS voice/language."""
    if not text:
        return fallback_lang
    tamil_count = len(re.findall(r'[\u0B80-\u0BFF]', text))
    devanagari_count = len(re.findall(r'[\u0900-\u097F]', text))
    telugu_count = len(re.findall(r'[\u0C00-\u0C7F]', text))
    malayalam_count = len(re.findall(r'[\u0D00-\u0D7F]', text))
    kannada_count = len(re.findall(r'[\u0C80-\u0CFF]', text))
    bengali_count = len(re.findall(r'[\u0980-\u09FF]', text))
    gujarati_count = len(re.findall(r'[\u0A80-\u0AFF]', text))
    punjabi_count = len(re.findall(r'[\u0A00-\u0A7F]', text))
    arabic_urdu_count = len(re.findall(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]', text))
    latin_count = len(re.findall(r'[a-zA-Z]', text))
    
    # Marathi vs Hindi differentiation inside Devanagari
    is_marathi = False
    if devanagari_count > 0:
        marathi_markers = ["आहे", "नाही", "काय", "मला", "होतो", "झाला", "आहोत", "कसे", "त्रास", "दुखतंय"]
        if any(m in text for m in marathi_markers):
            is_marathi = True

    counts = {
        "ta": tamil_count,
        "mr": devanagari_count if is_marathi else 0,
        "hi": devanagari_count if not is_marathi else 0,
        "te": telugu_count,
        "ml": malayalam_count,
        "kn": kannada_count,
        "bn": bengali_count,
        "gu": gujarati_count,
        "pa": punjabi_count,
        "ur": arabic_urdu_count,
        "ar": arabic_urdu_count,
        "en": latin_count,
    }
    max_lang, max_count = max(counts.items(), key=lambda x: x[1])
    if max_count > 0:
        return max_lang
    return fallback_lang

def _clean_text_for_speech(text: str) -> str:
    """Removes code blocks, markdown syntax, and special formatting for smooth TTS."""
    t = re.sub(r'```[\s\S]*?```', 'Here is the code.', text)
    t = re.sub(r'`[^`]+`', '', t)
    t = re.sub(r'[*_~#>`]', '', t)
    t = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', t)
    t = re.sub(r'\n+', '. ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

class TTSService:
    def __init__(self):
        self.audio_cache_dir = Path(Config.AUDIO_CACHE_DIR)
        self.audio_cache_dir.mkdir(parents=True, exist_ok=True)
        self.piper_exe = Config.PIPER_EXE_PATH
        self.piper_voice = Config.PIPER_VOICE_MODEL
        self.engine = Config.TTS_ENGINE

    def _get_cache_filename(self, text: str, voice: str, language: str = "en") -> Path:
        content_hash = hashlib.md5(f"{text}_{voice}_{language}".encode("utf-8")).hexdigest()
        return self.audio_cache_dir / f"tts_{language}_{content_hash}.mp3"

    def synthesize_speech(self, text: str, language: str = "en", voice: Optional[str] = None) -> Optional[str]:
        """
        Synthesizes speech for the provided text in the target language.
        Returns the relative URL/filename for the audio file (e.g. 'tts_en_abc123.mp3').
        """
        if not text or not text.strip():
            return None

        clean_text = _clean_text_for_speech(text)
        if not clean_text:
            return None

        detected_lang = _detect_tts_language(clean_text, fallback_lang=(language or "en").lower().split("-")[0])
        voice_name = voice or self.piper_voice
        target_file = self._get_cache_filename(clean_text, voice_name, detected_lang)

        # Return cached if exists and not empty
        if target_file.exists() and target_file.stat().st_size > 500:
            return target_file.name

        # 1. Try high-quality Neural edge-tts for Indian and global languages
        VOICE_MAP = {
            "en": "en-IN-NeerjaNeural",
            "ta": "ta-IN-PallaviNeural",
            "hi": "hi-IN-SwaraNeural",
            "te": "te-IN-ShrutiNeural",
            "kn": "kn-IN-SapnaNeural",
            "ml": "ml-IN-SobhanaNeural",
            "bn": "bn-IN-TanishaaNeural",
            "mr": "mr-IN-AarohiNeural",
            "gu": "gu-IN-DhwaniNeural",
            "pa": "pa-IN-OjasNeural",
            "ur": "ur-IN-SalmanNeural",
            "ar": "ar-SA-ZariyahNeural",
        }
        edge_voice = voice or VOICE_MAP.get(detected_lang, "en-IN-NeerjaNeural")
        try:
            import asyncio
            import edge_tts
            
            async def _run_edge():
                communicate = edge_tts.Communicate(clean_text, edge_voice)
                await communicate.save(str(target_file))

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        pool.submit(lambda: asyncio.run(_run_edge())).result(timeout=10)
                else:
                    loop.run_until_complete(_run_edge())
            except RuntimeError:
                asyncio.run(_run_edge())

            if target_file.exists() and target_file.stat().st_size > 500:
                return target_file.name
        except Exception as e:
            print(f"[TTS Warning] edge-tts synthesis failed for lang '{detected_lang}' voice '{edge_voice}': {e}")

        # 2. Try Piper TTS if available (primarily English/Piper models)
        if detected_lang == "en" and self._is_piper_available():
            wav_file = target_file.with_suffix(".wav")
            piper_success = self._synthesize_piper(clean_text, wav_file, voice_name)
            if piper_success and wav_file.exists() and wav_file.stat().st_size > 500:
                return wav_file.name

        # 3. Fallback to gTTS (Supports English, Hindi, Tamil, Telugu, Malayalam, Kannada, etc.)
        try:
            from gtts import gTTS
            supported_langs = {'en', 'hi', 'ta', 'te', 'ml', 'kn', 'es', 'fr', 'de', 'ar', 'pt', 'it', 'ru', 'ja', 'ko', 'zh'}
            tts_lang = detected_lang if detected_lang in supported_langs else 'en'
            tts = gTTS(text=clean_text, lang=tts_lang, slow=False)
            tts.save(str(target_file))
            if target_file.exists() and target_file.stat().st_size > 500:
                return target_file.name
        except Exception as e:
            print(f"[TTS Warning] gTTS fallback failed for lang '{detected_lang}': {e}")

        # 4. Fallback to pyttsx3 / Windows SAPI if present
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.save_to_file(clean_text, str(target_file))
            engine.runAndWait()
            if target_file.exists():
                return target_file.name
        except Exception:
            pass

        return None

    def _is_piper_available(self) -> bool:
        if shutil.which(self.piper_exe) is not None:
            return True
        # Check relative piper binary or onnx model
        custom_piper = Path("piper.exe")
        return custom_piper.exists()

    def _synthesize_piper(self, text: str, output_path: Path, voice_model: str) -> bool:
        try:
            cmd = [
                self.piper_exe,
                "--model", voice_model,
                "--output_file", str(output_path)
            ]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=text, timeout=10)
            return process.returncode == 0
        except Exception as e:
            print(f"[TTS Warning] Piper subprocess error: {e}")
            return False

tts_service = TTSService()
