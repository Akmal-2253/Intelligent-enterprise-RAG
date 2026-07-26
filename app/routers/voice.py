from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response

from app.services.voice_service import speech_to_text, text_to_speech
from app.models.schemas import TextToSpeechRequest, TranscriptionResponse

router = APIRouter(prefix="/voice", tags=["Voice"])


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    try:
        text = speech_to_text(audio_bytes, mimetype=file.content_type or "audio/wav")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Deepgram transcription failed: {e}")

    return TranscriptionResponse(text=text)


@router.post("/speak")
def speak_text(payload: TextToSpeechRequest):
    try:
        audio_bytes = text_to_speech(payload.text)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Deepgram speech synthesis failed: {e}")

    return Response(content=audio_bytes, media_type="audio/mpeg")