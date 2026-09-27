import logging
import math
from pathlib import Path

from yandex_ai_studio_sdk import AIStudio

from app.config import YANDEX_API_KEY, YANDEX_FOLDER_ID

logger = logging.getLogger(__name__)

MAX_FILES_PER_INDEX = 500
UPLOAD_DIR = Path("data/knowledge_uploads")

INDEX_NAME = "bitrix24-api-docs"
INDEX_DESCRIPTION = "База знаний документации Bitrix24 API"


class BitrixKnowledgeBase:
    def __init__(
        self,
        api_key: str = YANDEX_API_KEY,
        folder_id: str = YANDEX_FOLDER_ID,
    ):
        if not api_key:
            raise ValueError("YANDEX_API_KEY не был задан!")

        if not folder_id:
            raise ValueError("YANDEX_FOLDER_ID не был задан!")

        self.sdk = AIStudio(folder_id=folder_id, auth=api_key)

    def build_index(self, documents: list[dict[str, str]]) -> str:
        documents = [
            doc for doc in documents if doc.get("content", "").strip()
        ]
        if not documents:
            raise ValueError("Нет документов для индексации!")

        bundle_size = max(1, math.ceil(len(documents) / MAX_FILES_PER_INDEX))
        total_files = math.ceil(len(documents) / bundle_size)

        logger.info(
            "Индексация: документов=%d, размер бандла=%d, файлов=%d",
            len(documents), bundle_size, total_files,
        )

        uploaded_files = self._upload_bundles(documents, bundle_size)

        if not uploaded_files:
            raise RuntimeError("Не удалось загрузить ни одного файла")

        logger.info("Загружено файлов: %d. Создаю Search Index...",
                    len(uploaded_files))

        try:
            operation = self.sdk.search_indexes.create_deferred(
                name=INDEX_NAME,
                description=INDEX_DESCRIPTION,
                files=uploaded_files,
            )
            search_index = operation.wait()
        except Exception:
            logger.exception("Ошибка создания Search Index")
            raise

        logger.info("Search Index создан: %s", search_index.id)
        return search_index.id


    def _upload_bundles(
        self,
        documents: list[dict[str, str]],
        bundle_size: int,
    ) -> list:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        total_files = math.ceil(len(documents) / bundle_size)
        uploaded_files = []
        failures = 0

        for number, start in enumerate(
            range(0, len(documents), bundle_size), 1
        ):
            group = documents[start:start + bundle_size]
            content = self._render_bundle(group)

            temp_file = UPLOAD_DIR / f"bitrix_docs_{number}.txt"
            temp_file.write_text(content, encoding="utf-8")

            try:
                uploaded_file = self.sdk.files.upload(
                    path=temp_file,
                    name=f"bitrix24_docs_{number}.txt",
                )
                if uploaded_file:
                    uploaded_files.append(uploaded_file)
            except Exception:
                failures += 1
                logger.exception(
                    "Не удалось загрузить файл %d/%d", number, total_files
                )
            finally:
                temp_file.unlink(missing_ok=True)

            if number % 25 == 0 or number == total_files:
                logger.info("Загружено файлов: %d/%d", number, total_files)

        if failures:
            logger.warning(
                "Неудачных загрузок: %d из %d", failures, total_files
            )

        return uploaded_files

    @staticmethod
    def _render_bundle(group: list[dict[str, str]]) -> str:
        """Собирает один txt-файл из группы документов."""
        parts = []
        for doc in group:
            parts.append(
                f"--- SOURCE: {doc.get('source', 'unknown')} ---\n"
                f"URL: {doc.get('url', '')}\n"
                f"FILE: {doc.get('file_path', '')}\n\n"
                f"{doc['content']}"
            )
        return "\n\n".join(parts)
