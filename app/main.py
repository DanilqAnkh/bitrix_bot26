from app.telegram.bot import create_bot
from app.database import init_db


def main():
    print("Инициализация базы данных")
    init_db()
    print("База данных инициализирована!")

    print("Запуск Telegram-бота")
    app = create_bot()
    app.run_polling()


if __name__ == "__main__":
    main()