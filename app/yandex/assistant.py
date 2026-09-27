import logging
import json
import re
import httpx
import openai

from pathlib import Path


from app.config import (
    YANDEX_API_KEY,
    YANDEX_FOLDER_ID,
    YANDEX_MODEL,
    YA_SEARCH_INDEX_ID,
)

logger = logging.getLogger(__name__)

_METHOD_URLS_FILE = Path("data/method_urls.json")
_method_urls_cache: dict[str, str] | None = None

_SOURCES_BLOCK = re.compile(
    r"\n*[^\n]*Источники[^\n]*\n(?:[^\n]*\n?)*\Z",
    re.IGNORECASE,
)
_METHOD_RE = re.compile(
    r"\b([a-z][a-z0-9_]*\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?)\b"
)

_LEAD_MARKERS = re.compile(
    r"^\s*(intrpt\s*:\s*|think\w*\s*:\s*|debug\s*:\s*)+",
    re.IGNORECASE,
)

_INTROSPECTION_JSON = re.compile(
    r"^\s*\{\s*\"(?:searchQuery|description|answer)\".*?\}\s*$",
    re.DOTALL,
)

_SEARCH_QUERY_JSON = re.compile(
    r"\{\s*\"searchQuery\"\s*:\s*\"[^\"]*\"\s*\}",
    re.DOTALL,
)

class YandexGPTService:
    BASE_URL = "https://rest-assistant.api.cloud.yandex.net/v1"

    SYSTEM_PROMPT = """Ты — технический ассистент разработчика по Bitrix24.

Помогаешь разбираться с REST API Bitrix24: методами, параметрами,
возвращаемыми значениями, примерами использования.

Опирайся на найденную документацию Bitrix24.
Приводи точные названия методов, параметров и значений — как в документации.
Не выдумывай методы, параметры или поведение API.
Не пиши URL и блок "Источники:" — они добавляются автоматически.
Если примера нет — не выдумывай
Если вопрос не связан с Bitrix24 — коротко скажи, что специализируешься
на Bitrix24.
ЗАПОМНИ: никогда не выводи слова search_index, file_search, retrieval, 
vector_store, rag, query — ни в каком виде.
Отвечай подробно, приводи примеры и параметры, если они есть в документации.
"""

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
        self.search_index_id = search_index_id or YA_SEARCH_INDEX_ID or None
        self.timeout = timeout

        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.BASE_URL,
            project=self.folder_id,
            timeout=self.timeout,
        )


    def _strip_introspection(self, answer: str) -> str:
        answer = _LEAD_MARKERS.sub("", answer)

        answer = _SEARCH_QUERY_JSON.sub("", answer)

        lines = answer.split("\n")
        while lines and lines[0].strip().lower() in {
            "приостановленные", "приостановлен", "suspended",
            "processing", "creating", "pending",
        }:
            lines.pop(0)
        answer = "\n".join(lines)

        stripped = answer.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                data = json.loads(stripped)
                if isinstance(data, dict):
                    val = data.get("answer") or data.get("text")
                    if isinstance(val, str) and len(val.strip()) >= 20:
                        return val.strip()
            except Exception:
                pass
            return ""

        return answer.strip()
    
    def _load_method_urls(self) -> dict[str, str]:
        global _method_urls_cache
        if _method_urls_cache is None:
            if _METHOD_URLS_FILE.exists():
                try:
                    _method_urls_cache = json.loads(
                        _METHOD_URLS_FILE.read_text(encoding="utf-8")
                    )
                except Exception:
                    logger.exception("Не удалось прочитать карту методов")
                    _method_urls_cache = {}
            else:
                _method_urls_cache = {}
        return _method_urls_cache


    def _attach_real_sources(self, answer: str) -> str:
        """Вырезает блок источников от LLM и собирает его из карты методов."""
        urls = self._load_method_urls()

        body = _SOURCES_BLOCK.sub("", answer).rstrip()

        seen: list[str] = []
        for m in _METHOD_RE.finditer(body):
            name = m.group(1)
            if name in urls and name not in seen:
                seen.append(name)
            if len(seen) >= 5:
                break

        if not seen:
            return body

        lines = ["Источники:"]
        for name in seen:
            lines.append(f"- {name} — {urls[name]}")
        return body + "\n\n" + "\n".join(lines)


    def _extract_file_citations(self, response) -> list[str]:
        """Достаёт filename из аннотаций file_search, если они есть."""
        filenames: list[str] = []
        try:
            for item in getattr(response, "output", []) or []:
                if getattr(item, "type", None) != "message":
                    continue
                for content in getattr(item, "content", []) or []:
                    for ann in getattr(content, "annotations", []) or []:
                        if getattr(ann, "type", None) == "file_citation":
                            name = getattr(ann, "filename", None)
                            if name and name not in filenames:
                                filenames.append(name)
        except Exception:
            logger.exception("Не удалось извлечь цитаты из ответа")
        return filenames


    def ask(self, question: str) -> str:
        if not question or not question.strip():
            logger.warning("YandexGPT вернул пустой ответ")
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
            answer = self._strip_introspection(answer) 
            if len(answer) < 10:
                logger.warning("Ответ после санитайза пустой/битый: %r", response.output_text[:300])
                return "Не удалось получить ответ. Попробуйте переформулировать вопрос или повторить чуть позже"
            answer = self._attach_real_sources(answer)

            if not answer:
                logger.warning("YandexGPT вернул пустой ответ")
                return "Не удалось получить ответ от YandexGPT"

            if any(m in answer.lower() for m in ("fair_usage_limit", "quota", "rate limit")) and len(answer) < 300:
                logger.warning("Yandex quota: %s", answer[:200])
                return "Не удалось получить ответ. Попробуйте переформулировать вопрос."

            citations = self._extract_file_citations(response)
            if citations:
                logger.info("Ответ ссылается на файлы: %s", ", ".join(citations))

            logger.info("Ответ YandexGPT получен: %d символов", len(answer))

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