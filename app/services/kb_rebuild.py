import json
import logging
from pathlib import Path

from app.bitrix.docs_parser import build_documents
from app.yandex.knowledge_base import BitrixKnowledgeBase

logger = logging.getLogger(__name__)

ENV_FILE = Path(".env")
METHOD_URLS_FILE = Path("data/method_urls.json")


class KnowledgeBaseService:

    def __init__(self):
        self.kb = BitrixKnowledgeBase()

    def rebuild(self) -> str:
        logger.info("Начало пересборки базы знаний")

        documents = build_documents()
        logger.info("Документация собрана: %d документов", len(documents))

        if not documents:
            raise RuntimeError("Не удалось собрать документы")

        self._save_method_urls(documents)

        new_index_id = self.kb.build_index(documents)
        logger.info("Индекс пересобран: %s", new_index_id)
        self._save_index_id(new_index_id)

        return new_index_id

    @staticmethod
    def _save_method_urls(documents: list[dict[str, str]]) -> None:
        mapping: dict[str, str] = {}
        for doc in documents:
            src = (doc.get("source") or "").strip()
            url = (doc.get("url") or "").strip()
            if src and url:
                mapping[src] = url

        METHOD_URLS_FILE.parent.mkdir(parents=True, exist_ok=True)
        METHOD_URLS_FILE.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(
            "Карта методов сохранена: %d записей → %s",
            len(mapping), METHOD_URLS_FILE,
        )

    @staticmethod
    def _read_index_id() -> str | None:
        if not ENV_FILE.exists():
            return None
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("YA_SEARCH_INDEX_ID="):
                return line.split("=", 1)[1].strip() or None
        return None

    @staticmethod
    def _save_index_id(index_id: str) -> None:
        lines = (
            ENV_FILE.read_text(encoding="utf-8").splitlines()
            if ENV_FILE.exists() else []
        )
        for i, line in enumerate(lines):
            if line.startswith("YA_SEARCH_INDEX_ID="):
                lines[i] = f"YA_SEARCH_INDEX_ID={index_id}"
                break
        else:
            lines.append(f"YA_SEARCH_INDEX_ID={index_id}")
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


knowledge_base_service = KnowledgeBaseService()

