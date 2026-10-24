import os
import sys
import re
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from app.config import Config

# Ensure ffmpeg from imageio_ffmpeg is in PATH for Whisper
try:
    import imageio_ffmpeg
    ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
except Exception as e:
    print(f"[STT Warning] Could not auto-add imageio_ffmpeg to PATH: {e}")


import math

def normalize_speech_text(raw_text: str, detected_lang: str = "en") -> str:
    """
    Normalizes common Indian colloquial speech patterns and transliteration artifacts
    while preserving exact patient meaning without inventing unmentioned symptoms.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()

    # Normalization dictionary for common Indian phonetic/code-switching artifacts
    replacements = [
        (r'\b(2|two)\s*days?\s*ah\b', '2 days-ஆ', re.IGNORECASE),
        (r'\b(3|three)\s*days?\s*ah\b', '3 days-ஆ', re.IGNORECASE),
        (r'\b(1|one)\s*days?\s*ah\b', '1 day-ஆ', re.IGNORECASE),
        (r'\b(10|ten)\s*days?\s*ah\b', '10 days-ஆ', re.IGNORECASE),
        (r'\benaku\b', 'enakku', re.IGNORECASE),
        (r'\biruku\b', 'irukku', re.IGNORECASE),
        (r'\brendu\s+nala\b', 'rendu naala', re.IGNORECASE),
        (r'\bkonjam\s+pain\b', 'konjam pain', re.IGNORECASE),
        (r'\bnenju\s+vali\b', 'nenju vali', re.IGNORECASE),
        (r'\bthala\s*vali\b', 'thalaivali', re.IGNORECASE),
        (r'\bbukhar\s+h\b', 'bukhar hai', re.IGNORECASE),
        (r'\bdard\s+ho\s+ra\b', 'dard ho raha hai', re.IGNORECASE),
        (r'\bfever\s+h\b', 'fever hai', re.IGNORECASE),
    ]

    for pattern, repl, flags in [(r[0], r[1], r[2]) for r in replacements]:
        text = re.sub(pattern, repl, text, flags=flags)

    # Clean redundant whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _clean_hallucinated_text(raw_text: str) -> str:
    """
    Cleans known Whisper hallucination artifacts (silence loops, YouTube subtitles, repeated phrases).
    """
    if not raw_text:
        return ""

    text = raw_text.strip()
    normalized = re.sub(r'[^\w\s]', '', text).strip().lower()

    # Common Whisper phantom transcriptions on background noise/silence
    phantom_phrases = [
        r"thank you for watching",
        r"thanks for watching",
        r"please subscribe",
        r"like and subscribe",
        r"subtitles by",
        r"music",
        r"applause",
        r"you",
        r"bye"
    ]

    for p in phantom_phrases:
        if normalized == p or re.fullmatch(p, normalized):
            return ""

    # Collapse repetitive word/phrase loops: "fever fever fever fever" -> "fever"
    words = text.split()
    if len(words) >= 4:
        # Check if single word repeated 4+ times
        if len(set(w.lower().strip('.!,?') for w in words)) == 1:
            return words[0].strip('.!,?')
        # Check for 2-word phrase loops
        phrase_2 = f"{words[0]} {words[1]}".lower().strip()
        if text.lower().count(phrase_2) >= 3 and len(text) / len(phrase_2) >= 2.5:
            return f"{words[0]} {words[1]}"

    return text.strip()




class STTService:
    def __init__(self):
        self.model = None
        self.model_name = Config.WHISPER_MODEL
        self.device = Config.WHISPER_DEVICE

    def _get_model(self):
        if self.model is None:
            try:
                import whisper
                print(f"[STT] Loading Whisper model '{self.model_name}' on device '{self.device}'...")
                self.model = whisper.load_model(self.model_name, device=self.device)
                print(f"[STT] Whisper model loaded successfully.")
            except Exception as e:
                print(f"[STT Error] Failed to load Whisper model: {e}")
                raise e
        return self.model

    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        try:
            segments = result.get("segments", [])
            if not segments:
                return 0.85 if result.get("text") else 0.0
            avg_logprobs = [s.get("avg_logprob", -0.5) for s in segments if "avg_logprob" in s]
            no_speech_probs = [s.get("no_speech_prob", 0.0) for s in segments if "no_speech_prob" in s]
            mean_logprob = sum(avg_logprobs) / len(avg_logprobs) if avg_logprobs else -0.4
            mean_no_speech = sum(no_speech_probs) / len(no_speech_probs) if no_speech_probs else 0.0
            conf = math.exp(max(-3.0, min(0.0, mean_logprob))) * (1.0 - mean_no_speech)
            return round(max(0.0, min(1.0, conf)), 3)
        except Exception:
            return 0.85

    def transcribe_audio_file(self, audio_path: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribes an audio file path using Whisper with automatic language detection.
        """
        try:
            model = self._get_model()
            options = {
                "temperature": (0.0, 0.2, 0.4),
                "condition_on_previous_text": False,
                "compression_ratio_threshold": 2.4,
                "no_speech_threshold": 0.6
            }

            if language and language not in ["auto", "all", "detect", ""]:
                options["language"] = language.lower().split("-")[0]

            result = model.transcribe(audio_path, **options)
            raw_text = result.get("text", "").strip()
            detected_lang = result.get("language", "en")

            cleaned_text = _clean_hallucinated_text(raw_text)
            normalized_text = normalize_speech_text(cleaned_text, detected_lang=detected_lang)
            confidence = self._calculate_confidence(result)

            return {
                "text": normalized_text,
                "raw_text": raw_text,
                "language": detected_lang,
                "confidence": confidence,
                "speech_detected": bool(normalized_text),
                "success": bool(normalized_text)
            }
        except Exception as e:
            print(f"[STT Error] Transcription failed: {e}")
            return {
                "text": "",
                "raw_text": "",
                "confidence": 0.0,
                "speech_detected": False,
                "error": str(e),
                "success": False
            }

    def transcribe_pcm_bytes(self, pcm_bytes: bytes, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Directly transcribes 16kHz 16-bit Mono PCM bytes in-memory using NumPy with zero disk I/O.
        """
        if not pcm_bytes or len(pcm_bytes) < 3200: # less than 100ms
            return {
                "text": "",
                "raw_text": "",
                "language": "en",
                "confidence": 0.0,
                "speech_detected": False,
                "success": False,
                "error": "Audio payload too small or empty"
            }

        try:
            import numpy as np
            model = self._get_model()
            audio_np = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            options = {
                "temperature": (0.0, 0.2),
                "condition_on_previous_text": False,
                "compression_ratio_threshold": 2.4,
                "no_speech_threshold": 0.6
            }
            if language and language not in ["auto", "all", "detect", ""]:
                options["language"] = language.lower().split("-")[0]

            result = model.transcribe(audio_np, **options)
            raw_text = result.get("text", "").strip()
            detected_lang = result.get("language", "en")
            cleaned_text = _clean_hallucinated_text(raw_text)
            normalized_text = normalize_speech_text(cleaned_text, detected_lang=detected_lang)
            confidence = self._calculate_confidence(result)

            return {
                "text": normalized_text,
                "raw_text": raw_text,
                "language": detected_lang,
                "confidence": confidence,
                "speech_detected": bool(normalized_text),
                "success": bool(normalized_text)
            }
        except Exception as e:
            print(f"[STT Error] PCM transcription failed: {e}")
            return {
                "text": "",
                "raw_text": "",
                "confidence": 0.0,
                "speech_detected": False,
                "error": str(e),
                "success": False
            }

    def transcribe_audio_bytes(self, audio_bytes: bytes, file_ext: str = ".webm", language: Optional[str] = None) -> Dict[str, Any]:
        """
        Saves raw bytes to a temporary file, runs Whisper transcription, and removes temporary file.
        """
        if not audio_bytes or len(audio_bytes) < 100:
            return {
                "text": "",
                "language": "en",
                "success": False,
                "error": "Audio payload too small or empty"
            }

        temp_file = None
        try:
            clean_ext = file_ext if file_ext.startswith(".") else f".{file_ext}"
            with tempfile.NamedTemporaryFile(suffix=clean_ext, delete=False) as f:
                f.write(audio_bytes)
                temp_file = f.name

            return self.transcribe_audio_file(temp_file, language=language)
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass


stt_service = STTService()


