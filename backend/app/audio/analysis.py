from pathlib import Path
import logging
import subprocess

import librosa
import numpy as np


logger = logging.getLogger(__name__)
FALLBACK_SAMPLE_RATE = 16000


def _unavailable_features() -> dict:
    return {
        "status": "unavailable",
        "volume_stability": None,
        "pause_ratio": None,
        "speech_rate": None,
        "pitch_variation": None,
        "voiced_ratio": None,
    }


def _load_audio_signal(audio_path: Path) -> tuple[np.ndarray, int] | None:
    try:
        return librosa.load(audio_path, sr=None)
    except Exception:
        return _load_audio_with_ffmpeg(audio_path)


def _load_audio_with_ffmpeg(audio_path: Path) -> tuple[np.ndarray, int] | None:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except ImportError:
        return None

    try:
        result = subprocess.run(
            [
                get_ffmpeg_exe(),
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(audio_path),
                "-f",
                "f32le",
                "-ac",
                "1",
                "-ar",
                str(FALLBACK_SAMPLE_RATE),
                "pipe:1",
            ],
            capture_output=True,
            check=False,
        )
    except Exception:
        logger.exception("ffmpeg audio decode failed | path=%s", audio_path)
        return None

    if result.returncode != 0 or not result.stdout:
        if result.stderr:
            logger.warning(
                "ffmpeg audio decode returned non-zero exit code | path=%s returncode=%s stderr=%s",
                audio_path,
                result.returncode,
                result.stderr.decode("utf-8", errors="ignore").strip(),
            )
        return None

    signal = np.frombuffer(result.stdout, dtype=np.float32)
    if signal.size == 0:
        return None
    return signal, FALLBACK_SAMPLE_RATE


# Keep the acoustic analysis intentionally lightweight so the scoring pipeline
# still works when no external speech provider is available.
def analyze_audio(audio_path: Path) -> dict:
    audio = _load_audio_signal(audio_path)
    if audio is None:
        return _unavailable_features()
    signal, sample_rate = audio

    if len(signal) == 0:
        return _unavailable_features()

    rms = librosa.feature.rms(y=signal)[0]
    zcr = librosa.feature.zero_crossing_rate(y=signal)[0]
    pitches, magnitudes = librosa.piptrack(y=signal, sr=sample_rate)
    pitch_values = pitches[magnitudes > np.median(magnitudes)]

    duration_seconds = librosa.get_duration(y=signal, sr=sample_rate) or 1.0
    silence_frames = np.sum(rms < np.percentile(rms, 25))
    pause_ratio = float(silence_frames / max(len(rms), 1))
    voiced_ratio = float(1.0 - pause_ratio)
    volume_stability = float(1.0 / (1.0 + np.std(rms)))
    pitch_variation = float(np.std(pitch_values) if len(pitch_values) else 0.0)
    speech_rate = float((len(zcr) / duration_seconds) * 0.8)

    return {
        "status": "available",
        "volume_stability": round(volume_stability * 100, 2),
        "pause_ratio": round(pause_ratio * 100, 2),
        "speech_rate": round(speech_rate, 2),
        "pitch_variation": round(pitch_variation, 2),
        "voiced_ratio": round(voiced_ratio * 100, 2),
    }


def measure_audio_duration_seconds(audio_path: Path) -> float | None:
    audio = _load_audio_signal(audio_path)
    if audio is None:
        return None
    signal, sample_rate = audio
    if len(signal) == 0:
        return None
    duration_seconds = librosa.get_duration(y=signal, sr=sample_rate)
    if not duration_seconds:
        return None
    return round(float(duration_seconds), 2)


def map_audio_scores(features: dict) -> dict:
    if features.get("status") != "available":
        return {
            "status": "unavailable",
            "confidence": None,
            "clarity": None,
            "fluency": None,
            "emotion": None,
            "speech_rate_comment": "未提供语音",
            "pause_comment": "未提供语音",
        }

    confidence = min(100.0, max(0.0, features["voiced_ratio"] * 0.55 + features["volume_stability"] * 0.45))
    clarity = min(100.0, max(0.0, features["volume_stability"] * 0.6 + (100 - features["pause_ratio"]) * 0.4))
    fluency = min(100.0, max(0.0, (100 - features["pause_ratio"]) * 0.65 + min(features["speech_rate"] * 2.0, 100) * 0.35))
    emotion = min(100.0, max(0.0, 55 + min(features["pitch_variation"] / 3.0, 45)))

    speech_rate_comment = "语速偏快" if features["speech_rate"] > 6 else "语速平稳"
    if features["speech_rate"] < 3:
        speech_rate_comment = "语速偏慢"
    pause_comment = "停顿较多" if features["pause_ratio"] > 35 else "停顿控制较好"

    return {
        "status": "available",
        "confidence": round(confidence, 2),
        "clarity": round(clarity, 2),
        "fluency": round(fluency, 2),
        "emotion": round(emotion, 2),
        "speech_rate_comment": speech_rate_comment,
        "pause_comment": pause_comment,
    }
