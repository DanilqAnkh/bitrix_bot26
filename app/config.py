from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str

    db_host: str
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: str

    yandex_api_key: str
    yandex_folder_id: str
    yandex_model: str
    ya_search_index_id: str = "" 

    admin_ids: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",extra="ignore")

    @property
    def database_url(self) -> str:
        return (f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}")

    @property
    def admin_id_list(self) -> set[int]:
        if not self.admin_ids.strip():
            return set()

        return {
            int(user_id.strip())
            for user_id in self.admin_ids.split(",")
            if user_id.strip()
        }


settings = Settings()

TELEGRAM_BOT_TOKEN = settings.telegram_bot_token

DB_HOST = settings.db_host
DB_PORT = settings.db_port
DB_NAME = settings.db_name
DB_USER = settings.db_user
DB_PASSWORD = settings.db_password
DB_URL = settings.database_url

YANDEX_API_KEY = settings.yandex_api_key
YANDEX_FOLDER_ID = settings.yandex_folder_id
YANDEX_MODEL = settings.yandex_model
YA_SEARCH_INDEX_ID = settings.ya_search_index_id

ADMIN_IDS = settings.admin_id_list