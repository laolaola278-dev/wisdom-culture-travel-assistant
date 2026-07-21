"""Multi-modal stub: text-to-speech placeholder."""


def synthesize(text: str) -> dict:
    return {
        "text": text,
        "audio_url": None,
        "duration_seconds": 0,
        "format": "wav",
        "source": "placeholder (TTS not configured)",
    }
