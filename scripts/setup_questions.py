import asyncio

from app.services.chat_service import ChatService

chat_service = ChatService()

TEST_QUESTIONS = [
    "Что такое REST API в Битрикс24?",
    "Как получить информацию о сделке?",
    "Какой метод используется для создания контакта?",
    "Какие параметры принимает crm.deal.get?",
    "Как получить список пользователей?",
    "Что возвращает метод user.get?",
    "Как создать задачу через REST API?",
    "Какие права необходимы для работы с методом?",
    
    # Проверка поведения при отсутствии информации
    "Как через Bitrix24 REST API покорить галактику?",
    
    # Проверка вопроса не по документации
    "Что такое солнце?",
]


async def main():
    for question in TEST_QUESTIONS:
        print("-=-" * 25)
        print(f"ВОПРОС: {question}")

        try:
            answer = await chat_service.process_question(question=question, telegram_id=0)

            print(f"ОТВЕТ: {answer}")

        except Exception as error:
            print(f"ОШИБКА: {error}")


if __name__ == "__main__":
    asyncio.run(main())