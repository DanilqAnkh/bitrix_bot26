import logging
import os

import httpx
import openai

from app.config import YANDEX_API_KEY, YANDEX_FOLDER_ID, YANDEX_MODEL

logger = logging.getLogger(__name__)


class YandexGPTService:
    BASE_URL = "https://rest-assistant.api.cloud.yandex.net/v1"

    SYSTEM_PROMPT = ("""Ты — технический ассистент разработчика по Bitrix24.
Твоя основная задача — помогать пользователю работать с документацией 
Bitrix24 и разбираться с API, методами, параметрами, настройкой и 
использованием возможностей Bitrix24.
Используй найденную через file_search документацию Bitrix24 как основной
источник информации.
Если ответ можно подтвердить документацией, опирайся на неё.
Приводи точные названия методов, параметров и значений из документации.
Не придумывай методы API, параметры или поведение Bitrix24.
Если в документации недостаточно информации для точного ответа, прямо 
скажи об этом.
На общие вопросы о Bitrix24 и его документации отвечай нормально, если 
они связаны с задачей пользователя.
Например, вопросы о назначении документации, способах работы с API,
структуре документации и выборе подходящего метода являются допустимыми.
Если вопрос совершенно не связан с Bitrix24, его API или разработкой
для Bitrix24, кратко объясни, что твоя специализация — помощь с
Bitrix24.""")

    def __init__(
        self,
        api_key: str = YANDEX_API_KEY,
        folder_id: str = YANDEX_FOLDER_ID,
        model: str = YANDEX_MODEL,
        search_index_id: str | None = None,
        timeout: float = 30.0,
    ):
        if not api_key:
            raise ValueError("YANDEX_API_KEY не был задан!")

        if not folder_id:
            raise ValueError("YANDEX_FOLDER_ID не был задан!")

        if not model:
            raise ValueError("YANDEX_MODEL не был задан!")

        self.api_key = api_key
        self.folder_id = folder_id
        self.model = model
        self.search_index_id = search_index_id or os.getenv("YA_SEARCH_INDEX_ID")
        self.timeout = timeout

        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.BASE_URL,
            project=self.folder_id,
            timeout=self.timeout,
        )

    def ask(self, question: str) -> str:
        if not question or not question.strip():
            return "Не удалось обработать пустой вопрос"

        if not self.search_index_id:
            logger.error("YA_SEARCH_INDEX_ID не задан")
            return "База знаний Bitrix24 не настроена"

        try:
            response = self.client.responses.create(
                model=f"gpt://{self.folder_id}/{self.model}",
                instructions=self.SYSTEM_PROMPT,
                input=question,
                tools=[
                    {
                        "type": "file_search",
                        "vector_store_ids": [self.search_index_id],
                        "max_num_results": 8,
                    }
                ],
            )

            answer = response.output_text.strip()

            if not answer:
                logger.warning("YandexGPT вернул пустой ответ")
                return "Не удалось получить ответ от YandexGPT"

            logger.info(
                "Ответ YandexGPT получен: %d символов",
                len(answer),
            )

            return answer

        except Exception:
            logger.exception("Ошибка при обращении к YandexGPT")

            return (
                "Произошла техническая ошибка!\n"
                "Возникла ошибка при обращении к YandexGPT.\n"
                "Если ошибка повторяется, пожалуйста напишите в поддержку: "
                "@B24_supportbot"
            )

    def close(self) -> None:
        logger.info("Сервис прекращает работу")


yandex_gpt = YandexGPTService()