"""
Парсер документации Bitrix24.
Источник:
https://github.com/bitrix-tools/b24-rest-docs

Возвращает список документов для загрузки в Yandex Search Index.
"""

import io
import re
import zipfile
from pathlib import Path

import httpx

APIDOCS_BASE = "https://apidocs.bitrix24.com/"

METHOD_RE = re.compile(
    r"\b([a-z][a-z0-9_]*\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?)\b"
)

SOURCE_URL = "https://github.com/bitrix-tools/b24-rest-docs/archive/refs/heads/main.zip"
DATA_PATH = Path("data/bitrix")

DIRS_SELECT = {
    "first-steps",
    "api-reference",
    "tutorials",
    "settings",
    "local-integrations",
    "sdk"
}

def extract_method_from_content(text: str) -> str | None:
    h1 = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    if h1:
        m = METHOD_RE.search(h1.group(1))
        if m:
            return m.group(1)

    m = METHOD_RE.search(text[:2000])
    return m.group(1) if m else None


def build_metadata(repo_path: Path, file_path: Path, raw_content: str) -> dict:
    rel = file_path.relative_to(repo_path).as_posix()

    method = extract_method_from_content(raw_content) or file_path.stem.replace("-", ".")

    url_path = rel.removesuffix(".md") + ".html"
    url = APIDOCS_BASE + url_path

    return {
        "source": method, 
        "url": url,      
        "file_path": rel,  
    }

def download_repo() -> Path: #Установщик Bitrix24.
    DATA_PATH.mkdir(parents=True, exist_ok=True)

    existing_roots = [path for path in DATA_PATH.iterdir() 
    if path.is_dir() and path.name.startswith("b24-rest-docs-")]

    if existing_roots:
        print(f"Использую существующую документацию: {existing_roots[0]}")
        return existing_roots[0]

    print("Репозиторий документации не найден, скачиваю...")
    
    try:
        response = httpx.get(
            SOURCE_URL,
            timeout=httpx.Timeout(120.0, connect=30.0),
            follow_redirects=True
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise RuntimeError(
            f"Не удалось скачать документацию Bitrix24: {error}"
        ) from error
    
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(DATA_PATH)

    roots = [
        path
        for path in DATA_PATH.iterdir()
        if path.is_dir() and path.name.startswith("b24-rest-docs-")
    ]

    if not roots:
        raise RuntimeError("Корень репозитория Bitrix24 не найден")

    return roots[0]


def normalize_document(text: str) -> str:
    """Очищает Markdown от элементов, не нужных для поиска."""
    text = re.sub(r"\A---.*?---", "", text, flags=re.DOTALL)
    text = re.sub(r"{%.*?%}", "", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def find_documents(repo_path: Path) -> list[Path]:
    """Находит Markdown-файлы в нужных разделах документации."""
    result = []
    for section in DIRS_SELECT:
        current = repo_path / section
        if current.is_dir():
            result.extend(current.rglob("*.md"))
    return result


def build_documents() -> list[dict[str, str]]:
    """Собирает и очищает документы для загрузки в Search Index."""
    repository = download_repo()
    files = find_documents(repository)

    documents = []

    for file in files:
        try:
            raw_content = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        meta = build_metadata(repository, file, raw_content)
        content = normalize_document(raw_content)
    
        if content:
            documents.append({**meta, "content": content})

    return documents


def main() -> None:
    documents = build_documents()
    print(f"Подготовлено документов: {len(documents)}")

    if not documents:
        return

    first = documents[0]
    print(f"\nИсточник: {first['source']}")
    print("Содержимое:")
    print(first["content"][:500])


if __name__ == "__main__":
    main()