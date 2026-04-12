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


def _build_voiced_mask(rms: np.ndarray) -> np.ndarray:
    if rms.size == 0:
        return np.zeros(0, dtype=bool)
    strong_level = float(np.percentile(rms, 95))
    median_level = float(np.median(rms))
    threshold = max(strong_level * 0.12, min(median_level * 1.5, strong_level * 0.7), 1e-4)
    return rms >= threshold


def _estimate_volume_stability(rms: np.ndarray, voiced_mask: np.ndarray) -> float:
    voiced_rms = rms[voiced_mask]
    if voiced_rms.size == 0:
        return 0.0
    coeff = float(np.std(voiced_rms) / max(np.mean(voiced_rms), 1e-4))
    return max(0.0, 100.0 - min(coeff * 55.0, 100.0))


def _estimate_speech_rate(signal: np.ndarray, sample_rate: int, duration_seconds: float) -> float:
    onset_env = librosa.onset.onset_strength(y=signal, sr=sample_rate)
    if onset_env.size == 0:
        return 0.0
    delta = max(float(np.std(onset_env) * 0.5), float(np.mean(onset_env) * 0.2), 0.05)
    peaks = librosa.util.peak_pick(
        onset_env,
        pre_max=2,
        post_max=2,
        pre_avg=4,
        post_avg=4,
        delta=delta,
        wait=2,
    )
    return float(len(peaks) / max(duration_seconds, 1e-4))


def _estimate_pitch_variation(pitches: np.ndarray, magnitudes: np.ndarray) -> float:
    positive_magnitudes = magnitudes[magnitudes > 0]
    if positive_magnitudes.size == 0:
        return 0.0
    magnitude_threshold = float(np.percentile(positive_magnitudes, 75))
    pitch_values = pitches[magnitudes >= magnitude_threshold]
    pitch_values = pitch_values[(pitch_values >= 70) & (pitch_values <= 500)]
    if pitch_values.size < 4:
        return 0.0
    pitch_median = float(np.median(pitch_values))
    if pitch_median <= 0:
        return 0.0
    semitone_offsets = 12.0 * np.log2(pitch_values / pitch_median)
    return float(np.percentile(np.abs(semitone_offsets), 75))


def _speech_rate_score(speech_rate: float) -> float:
    return max(0.0, 100.0 - min(abs(speech_rate - 3.8) * 28.0, 100.0))


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
    pitches, magnitudes = librosa.piptrack(y=signal, sr=sample_rate)

    duration_seconds = librosa.get_duration(y=signal, sr=sample_rate) or 1.0
    voiced_mask = _build_voiced_mask(rms)
    voiced_ratio = float(np.mean(voiced_mask)) if voiced_mask.size else 0.0
    pause_ratio = float(1.0 - voiced_ratio)
    volume_stability = _estimate_volume_stability(rms, voiced_mask)
    pitch_variation = _estimate_pitch_variation(pitches, magnitudes)
    speech_rate = _estimate_speech_rate(signal, sample_rate, duration_seconds)

    return {
        "status": "available",
        "volume_stability": round(volume_stability, 2),
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

    speech_rate = float(features["speech_rate"])
    pitch_variation = float(features["pitch_variation"])
    speech_rate_score = _speech_rate_score(speech_rate)
    pitch_stability_score = max(0.0, 100.0 - min(abs(pitch_variation - 4.5) * 18.0, 100.0))

    confidence = min(100.0, max(0.0, features["voiced_ratio"] * 0.5 + features["volume_stability"] * 0.5))
    clarity = min(100.0, max(0.0, (100 - features["pause_ratio"]) * 0.45 + features["volume_stability"] * 0.55))
    fluency = min(100.0, max(0.0, (100 - features["pause_ratio"]) * 0.55 + speech_rate_score * 0.45))
    emotion = min(100.0, max(0.0, pitch_stability_score * 0.65 + features["volume_stability"] * 0.35))

    speech_rate_comment = "语速偏快" if speech_rate > 5.5 else "语速平稳"
    if speech_rate < 2.0:
        speech_rate_comment = "语速偏慢"
    pause_comment = "停顿较多" if features["pause_ratio"] > 50 else "停顿控制较好"

    return {
        "status": "available",
        "confidence": round(confidence, 2),
        "clarity": round(clarity, 2),
        "fluency": round(fluency, 2),
        "emotion": round(emotion, 2),
        "speech_rate_comment": speech_rate_comment,
        "pause_comment": pause_comment,
    }
