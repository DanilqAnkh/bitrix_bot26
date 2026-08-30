import math
from pathlib import Path

from yandex_ai_studio_sdk import AIStudio

from app.config import YANDEX_API_KEY, YANDEX_FOLDER_ID


MAX_FILES_PER_INDEX = 500
UPLOAD_DIR = Path("data/knowledge_uploads")


class BitrixKnowledgeBase:
    def __init__(
        self,
        api_key: str = YANDEX_API_KEY,
        folder_id: str = YANDEX_FOLDER_ID
    ):
        if not api_key:
            raise ValueError("YANDEX_API_KEY не был задан!")

        if not folder_id:
            raise ValueError("YANDEX_FOLDER_ID не был задан!")

        self.sdk = AIStudio(folder_id=folder_id,auth=api_key)

    def build_index(self, documents: list[dict[str, str]]) -> str:
        documents = [document for document in documents if document.get("content", "").strip()]

        if not documents:
            raise ValueError("Нет документов для индексации!")

        bundle_size = max(1, math.ceil(len(documents) / MAX_FILES_PER_INDEX))

        total_files = math.ceil(len(documents) / bundle_size)

        print(f"Документов: {len(documents)}")
        print(f"Объединяю по {bundle_size} документов в файл")
        print(f"Файлов для индекса: {total_files}")

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        uploaded_files = []

        for number, start in enumerate(range(0, len(documents), bundle_size), 1):
            group = documents[start:start + bundle_size]

            content = "\n\n".join(
                f"--- SOURCE: {document.get('source', 'unknown')} ---\n\n"
                f"{document['content']}"
                for document in group)

            temp_file = (UPLOAD_DIR/ f"bitrix_docs_{number}.txt")

            temp_file.write_text(content, encoding="utf-8")

            try:
                uploaded_file = self.sdk.files.upload(path=temp_file,
                name=f"bitrix24_docs_{number}.txt",)

                if uploaded_file:
                    uploaded_files.append(uploaded_file)

            finally:
                temp_file.unlink(missing_ok=True)

            if number % 50 == 0 or number == total_files:
                print(f"Загружено файлов: {number}/{total_files}")

        if not uploaded_files:
            raise RuntimeError("Не удалось загрузить документы")

        print(f"Загружено файлов: {len(uploaded_files)}")

        print("Создаю Search Index...")

        operation = self.sdk.search_indexes.create_deferred(
            name="bitrix24-api-docs",
            description=("База знаний документации Bitrix24 API"),
            files=uploaded_files)

        search_index = operation.wait()

        print(f"Search Index создан: {search_index.id}")

        return search_index.id
