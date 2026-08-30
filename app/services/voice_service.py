from typing import Optional

from app.speech.vosk_client import Vosk_Client_STT


class VoiceService:

    def __init__(self):
        self.stt = Vosk_Client_STT()

    async def recognize(
        self,
        audio_data: bytes
    ) -> Optional[str]:

        return await self.stt.recognize_audio(audio_data)


voice_service = VoiceService()
