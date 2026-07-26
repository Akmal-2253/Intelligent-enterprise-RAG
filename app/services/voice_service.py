"""
Deepgram wrapper for speech-to-text and text-to-speech. Uses plain HTTP
(requests) against Deepgram's REST API directly -- no SDK needed, keeps
this dependency-light, same reasoning as choosing FastEmbed over
sentence-transformers earlier.

STT: Deepgram Nova-3 (current flagship transcription model)
TTS: Deepgram Aura-2 (current flagship voice model)

The Deepgram API key stays server-side here -- Streamlit never sees it,
it only ever talks to OUR backend, which then talks to Deepgram. This
matters: any API key handed to a frontend (even Streamlit, which runs
server-side but whose code a user could inspect) is a real exposure risk.
"""

import requests

from app.config import get_settings
from app.utils.logger import logger

settings = get_settings()

_DEEPGRAM_STT_URL = "https://api.deepgram.com/v1/listen"
_DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"


def speech_to_text(audio_bytes: bytes, mimetype: str = "audio/wav") -> str:
    """
    Sends raw audio bytes to Deepgram, returns the transcribed text.
    Raises requests.HTTPError if Deepgram rejects the request (bad key,
    unsupported audio format, etc.) -- caller is responsible for turning
    that into a clean API error, same pattern as llm_service/embedding_service.
    """
    if not settings.deepgram_api_key:
        raise ValueError("DEEPGRAM_API_KEY is not set in .env")

    params = {"model": settings.deepgram_stt_model, "smart_format": "true"}
    headers = {
        "Authorization": f"Token {settings.deepgram_api_key}",
        "Content-Type": mimetype,
    }

    response = requests.post(_DEEPGRAM_STT_URL, params=params, headers=headers, data=audio_bytes, timeout=30)
    response.raise_for_status()

    result = response.json()
    try:
        transcript = result["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError):
        logger.error(f"Unexpected Deepgram STT response shape: {result}")
        raise ValueError("Could not parse transcript from Deepgram response")

    return transcript.strip()


def text_to_speech(text: str) -> bytes:
    """
    Sends text to Deepgram, returns raw MP3 audio bytes ready to play
    back directly (e.g. via Streamlit's st.audio()).
    """
    if not settings.deepgram_api_key:
        raise ValueError("DEEPGRAM_API_KEY is not set in .env")

    params = {"model": settings.deepgram_tts_model}
    headers = {
        "Authorization": f"Token {settings.deepgram_api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(_DEEPGRAM_TTS_URL, params=params, headers=headers, json={"text": text}, timeout=30)
    response.raise_for_status()

    return response.content