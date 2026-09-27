import asyncio
import logging

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

from app.config import TELEGRAM_BOT_TOKEN, ADMIN_IDS

from app.services.kb_rebuild import knowledge_base_service
from app.yandex.assistant import yandex_gpt 
from app.telegram.utils import split_message

from app.services.chat_service import ChatService
from app.services.voice_service import voice_service

logger = logging.getLogger(__name__)

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

_rebuild_lock = asyncio.Lock()


async def rebuild_kb_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if user is None or user.id not in ADMIN_IDS:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return

    if _rebuild_lock.locked():
        await update.message.reply_text("Пересборка уже идёт, подождите.")
        return

    async with _rebuild_lock:
        await update.message.reply_text(
            "Пересборка базы знаний запущена. Это может занять несколько минут."
        )

        try:
            new_index_id = await asyncio.to_thread(
                knowledge_base_service.rebuild
            )
        except Exception as e:
            logging.exception("Ошибка пересборки KB")
            await update.message.reply_text(f"Не удалось пересобрать БД: {e}")
            return

        yandex_gpt.search_index_id = new_index_id

        await update.message.reply_text(
            f"База знаний пересобрана. Индекс: {new_index_id}"
        )


async def text_mes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    telegram_user = update.effective_user

    answer = await chat_service.process_question(question = update.message.text, telegram_id=telegram_user.id)

    for part in split_message(answer):
        await update.message.reply_text(part)


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

    for part in split_message(answer):
        await update.message.reply_text(part)


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
    app.add_handler(CommandHandler("rebuild_kb", rebuild_kb_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_mes))
    app.add_handler(MessageHandler(filters.VOICE, voice_mes))
    
    return app

