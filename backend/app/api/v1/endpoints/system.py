from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.responses import ok
from app.schemas.system import InterviewCapabilityRead, SpeechSynthesisRead, SpeechSynthesisRequest
from app.audio.tts import get_tts_service


router = APIRouter()


@router.get('/capabilities')
def get_capabilities(_: object = Depends(get_current_user)):
    settings = get_settings()
    return ok(
        InterviewCapabilityRead(
            llm_ready=settings.llm_ready,
            embedding_ready=settings.embedding_ready,
            speech_ready=settings.speech_ready,
            tts_ready=settings.tts_ready,
            immersive_voice_interview_ready=settings.immersive_voice_interview_ready,
            llm_provider=settings.llm_provider,
            embedding_provider=settings.embedding_provider,
            tts_provider=settings.tts_provider,
            tts_model=settings.tts_model,
            tts_voice=settings.tts_voice,
        )
    )


@router.post('/tts')
def synthesize_speech(payload: SpeechSynthesisRequest, _: object = Depends(get_current_user)):
    result = get_tts_service().synthesize(payload.text)
    return ok(
        SpeechSynthesisRead(
            audio_base64=result.audio_base64,
            mime_type=result.mime_type,
            model=result.model,
            voice=result.voice,
        )
    )
