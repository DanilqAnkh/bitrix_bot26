from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

from app.config import TELEGRAM_BOT_TOKEN

from app.services.chat_service import ChatService
from app.services.voice_service import voice_service

chat_service = ChatService()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!" + """
Добрый день!
Этот бот создан для работы с документацией Bitrix24, введите /help для справки        
        """,
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("На данный момент бот не подключен к сети bitrix24, пожалуйста подождите")


async def text_mes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    telegram_user = update.effective_user

    answer = await chat_service.process_question(question = update.message.text, telegram_id=telegram_user.id)

    await update.message.reply_text(answer)


async def voice_mes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    voice = update.message.voice

    if voice is None:
        await update.message.reply_text("Не удалось получить голосовое сообщение.")
        return

    await update.message.reply_text("Голосовое сообщение было получено, распознаю...")

    try:
        print(f"[VOICE] Получено голосовое сообщение: {voice.file_id}")
        print("[VOICE] Получаем информацию о файле в Telegram")
        telegram_file = await voice.get_file()

        print("[VOICE] Скачиваем аудио")
        audio_data = await telegram_file.download_as_bytearray()

        print(
            f"[VOICE] Аудио скачано: {len(audio_data)} байт"
        )

    except Exception as e:
        print(f"[VOICE] Ошибка получения аудио из Telegram: {e}")

        await update.message.reply_text(
            "Не удалось получить голосовое сообщение из Telegram. "
            "Попробуйте отправить его ещё раз."
        )
        return

    try:
        print("[VOICE] Передаём аудио в Vosk")
        text = await voice_service.recognize(
            bytes(audio_data)
        )

        print(f"[VOICE] Результат распознавания: {text!r}")

    except Exception as e:
        print(f"[VOICE] Ошибка распознавания: {e}")
        await update.message.reply_text(
            "Произошла ошибка при распознавании голосового сообщения."
        )
        return

    if not text:
        await update.message.reply_text(
            "Не удалось распознать голосовое сообщение."
        )
        return

    answer = await chat_service.process_question(question=text, telegram_id=update.effective_user.id)

    await update.message.reply_text(answer)


async def error_handler(update, context):
    logger.exception("Ошибка Telegram: %s", context.error)

def create_bot():

    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=30.0,
    )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_error_handler(error_handler)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_mes))
    app.add_handler(MessageHandler(filters.VOICE, voice_mes))
    
    return app

