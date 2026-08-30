import logging

from app.database.db import SessionLocal
from app.database.crud import get_user, create_message
from app.yandex.assistant import yandex_gpt

logger = logging.getLogger(__name__)


class ChatService:
    async def process_question(self, question: str, telegram_id: int) -> str:
        db = SessionLocal()

        try:
            user = get_user(db, telegram_id)

            if user is None:
                return "Пользователь не найден"

            create_message(db, user.id, "user", question)

            answer = yandex_gpt.ask(question)

            create_message(db, user.id, "assistant", answer)

            return answer

        except Exception:
            logger.exception("Ошибка обработки вопроса пользователя %s", telegram_id)

            return """
Произошла техническая ошибка! 
Возник неожиданный сбой запроса. 
Если ошибка повторяется, пожалуйста напишите в поддержку: @B24_supportbot
"""

        finally:
            db.close()
