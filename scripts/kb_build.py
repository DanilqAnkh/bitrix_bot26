import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


from app.bitrix.docs_parser import build_documents
from app.yandex.knowledge_base import BitrixKnowledgeBase


ENV_FILE = ROOT / ".env"


def save_index_id(index_id: str) -> None:
    lines = (
        ENV_FILE.read_text(encoding="utf-8").splitlines()
        if ENV_FILE.exists()
        else []
    )

    for i, line in enumerate(lines):
        if line.startswith("YA_SEARCH_INDEX_ID="):
            lines[i] = f"YA_SEARCH_INDEX_ID={index_id}"
            break
    else:
        lines.append(f"YA_SEARCH_INDEX_ID={index_id}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    print("Скачиваю документацию Bitrix24...")

    documents = build_documents()

    print(f"Подготовлено документов: {len(documents)}")

    if not documents:
        print("Документы не найдены")
        sys.exit(1)

    knowledge_base = BitrixKnowledgeBase()

    index_id = knowledge_base.build_index(documents)

    save_index_id(index_id)

    print(f"YA_SEARCH_INDEX_ID сохранён в {ENV_FILE}")


if __name__ == "__main__":
    main()
