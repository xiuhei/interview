from pydantic import BaseModel


class InterviewCapabilityRead(BaseModel):
    llm_ready: bool
    embedding_ready: bool
    speech_ready: bool
    tts_ready: bool
    immersive_voice_interview_ready: bool
    llm_provider: str
    embedding_provider: str
    tts_provider: str
    tts_model: str
    tts_voice: str


class SpeechSynthesisRequest(BaseModel):
    text: str


class SpeechSynthesisRead(BaseModel):
    audio_base64: str
    mime_type: str
    model: str
    voice: str
