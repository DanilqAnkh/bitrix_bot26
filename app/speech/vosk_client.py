import asyncio
import json
import os
import subprocess
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import vosk


class Vosk_Client_STT:
    """Оффлайн клиент распознавания речи Vosk."""

    def __init__(self, model_path: Optional[str] = None):
        if model_path is None:
            model_path = (
                Path(__file__).parent
                / "models"
                / "vosk-model-small-ru-0.22"
            )

        model_path = Path(model_path)

        if not model_path.exists():
            raise FileNotFoundError(
                f"Модель Vosk не найдена: {model_path}"
            )

        print(f"Загрузка модели Vosk из: {model_path}")

        self.model = vosk.Model(str(model_path))
        self.executor = ThreadPoolExecutor(max_workers=2)

        print("Модель Vosk запущена!")

    async def recognize_audio(
        self,
        audio_data: bytes
    ) -> Optional[str]:

        if not audio_data:
            print("[VOSK] Получены пустые аудиоданные")
            return None

        print(
            f"[VOSK] Получено аудио: {len(audio_data)} байт"
        )

        try:
            wav_data = self._convert_to_wav(audio_data)

            if not wav_data:
                print("[VOSK] Не удалось получить WAV")
                return None

            print(
                f"[VOSK] WAV получен: {len(wav_data)} байт"
            )

            loop = asyncio.get_running_loop()

            result = await loop.run_in_executor(
                self.executor,
                self._recognize_sync,
                wav_data
            )

            print(f"[VOSK] Итоговый текст: {result!r}")

            return result

        except Exception as e:
            print(f"[VOSK] Ошибка распознавания: {e}")
            return None

    def _convert_to_wav(
        self,
        audio_data: bytes
    ) -> Optional[bytes]:

        ogg_path = None
        wav_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".ogg",
                delete=False
            ) as tmp_ogg:
                tmp_ogg.write(audio_data)
                ogg_path = tmp_ogg.name

            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False
            ) as tmp_wav:
                wav_path = tmp_wav.name

            command = [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                ogg_path,
                "-ac",
                "1",
                "-ar",
                "16000",
                "-sample_fmt",
                "s16",
                "-f",
                "wav",
                wav_path,
            ]

            print("[VOSK] Конвертируем OGG → WAV...")

            result = subprocess.run(
                command,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(
                    f"[VOSK] FFmpeg ошибка:\n{result.stderr}"
                )
                return None

            with open(wav_path, "rb") as file:
                wav_data = file.read()

            print("[VOSK] Конвертация успешно завершена")

            return wav_data

        except Exception as e:
            print(
                f"[VOSK] Ошибка конвертации: {e}"
            )
            return None

        finally:
            if ogg_path and os.path.exists(ogg_path):
                os.unlink(ogg_path)

            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)

    def _recognize_sync(
        self,
        wav_data: bytes
    ) -> Optional[str]:

        tmp_path = None
        wf = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False
            ) as tmp_file:
                tmp_file.write(wav_data)
                tmp_path = tmp_file.name

            wf = wave.open(tmp_path, "rb")

            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()

            print(
                "[VOSK] WAV параметры:"
                f" channels={channels},"
                f" sample_width={sample_width},"
                f" sample_rate={sample_rate}"
            )

            if channels != 1:
                print("[VOSK] ОШИБКА: WAV должен быть mono")
                return None

            if sample_width != 2:
                print("[VOSK] ОШИБКА: WAV должен быть 16-bit")
                return None

            if sample_rate != 16000:
                print("[VOSK] ОШИБКА: sample rate должен быть 16000")
                return None

            recognizer = vosk.KaldiRecognizer(self.model, sample_rate)

            recognizer.SetWords(True)

            result_text = []

            while True:
                data = wf.readframes(4000)

                if not data:
                    break

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())

                    text = result.get("text", "").strip()

                    if text:
                        result_text.append(text)

            final_result = json.loads(recognizer.FinalResult())

            final_text = final_result.get("text", "").strip()

            if final_text:
                result_text.append(final_text)

            full_text = " ".join(result_text).strip()

            print(f"[VOSK] Распознано: {full_text!r}")

            return full_text or None

        except Exception as e:
            print(f"[VOSK] Ошибка обработки WAV: {e}")
            return None

        finally:
            if wf:
                wf.close()

            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def close(self):
        self.executor.shutdown(wait=False)

    def __del__(self):
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)