"""
Telegram-бот для парсингу розкладу bumpix.net (Анна Карпова, WaxHubStudio).

Команди:
  /start   — привітання та інструкція
  /check   — перевірити вільні слоти на 14 днів
  /full    — повний розклад (включно з вихідними)
  /help    — допомога
  /notify  — увімкнути/вимкнути автоповідомлення (якщо налаштовано)
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, AUTO_CHECK_INTERVAL, NOTIFY_CHAT_IDS, DAYS_AHEAD
from parser import fetch_schedule, format_schedule, format_schedule_short

# ── Логування ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Роутер ───────────────────────────────────────────────────────────────────

router = Router()

# Для зберігання останнього відомого стану (для авто-нотифікацій)
_last_known_slots: dict[str, set[str]] = {}
# Чати з увімкненими нотифікаціями
_notify_chats: set[int] = set(NOTIFY_CHAT_IDS)


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Привіт!</b>\n\n"
        "Я бот-парсер розкладу <b>Анна Карпова (WaxHubStudio)</b> з bumpix.net.\n\n"
        "📋 <b>Команди:</b>\n"
        "  /check — 🟢 перевірити вільні слоти на найближчі 14 днів\n"
        "  /full  — 📅 повний розклад (з вихідними)\n"
        "  /help  — ❓ допомога\n\n"
        "Натисніть /check щоб почати!",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "❓ <b>Допомога</b>\n\n"
        "Цей бот перевіряє вільні слоти для запису до спеціаліста "
        "<b>Анна Карпова</b> (WaxHubStudio, Чабани) через сайт bumpix.net.\n\n"
        "📋 <b>Команди:</b>\n"
        "  /check — показати тільки дні з вільними слотами\n"
        "  /full  — повний розклад на 14 днів\n"
        "  /notify — увімкнути/вимкнути авто-сповіщення\n\n"
        "🟢 — є вільні слоти\n"
        "🟡 — робочий день, але все зайнято\n"
        "🔴 — вихідний\n\n"
        f"⏱ Перевірка на <b>{DAYS_AHEAD}</b> днів наперед.",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("check"))
async def cmd_check(message: types.Message):
    wait_msg = await message.answer("⏳ Перевіряю вільні слоти...")

    try:
        schedule = await fetch_schedule()
        text = format_schedule_short(schedule)
    except Exception as e:
        logger.error("Помилка при отриманні розкладу: %s", e, exc_info=True)
        text = f"❌ Помилка при отриманні даних: <code>{e}</code>\nСпробуйте пізніше."

    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    text += f"\n\n🕐 <i>Оновлено: {now_str}</i>"

    await wait_msg.edit_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@router.message(Command("full"))
async def cmd_full(message: types.Message):
    wait_msg = await message.answer("⏳ Завантажую повний розклад...")

    try:
        schedule = await fetch_schedule()
        text = format_schedule(schedule, compact=False)
    except Exception as e:
        logger.error("Помилка при отриманні розкладу: %s", e, exc_info=True)
        text = f"❌ Помилка при отриманні даних: <code>{e}</code>\nСпробуйте пізніше."

    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    text += f"\n\n🕐 <i>Оновлено: {now_str}</i>"

    await wait_msg.edit_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@router.message(Command("notify"))
async def cmd_notify(message: types.Message):
    chat_id = message.chat.id
    if chat_id in _notify_chats:
        _notify_chats.discard(chat_id)
        await message.answer(
            "🔕 Авто-сповіщення <b>вимкнено</b> для цього чату.",
            parse_mode=ParseMode.HTML,
        )
    else:
        _notify_chats.add(chat_id)
        await message.answer(
            "🔔 Авто-сповіщення <b>увімкнено</b>!\n"
            "Я повідомлю, коли з'являться нові вільні слоти.",
            parse_mode=ParseMode.HTML,
        )


# ── Авто-перевірка (фоновий таск) ───────────────────────────────────────────

async def _auto_check_loop(bot: Bot):
    """Періодично перевіряє розклад і надсилає повідомлення при змінах."""
    global _last_known_slots

    if AUTO_CHECK_INTERVAL <= 0:
        logger.info("Авто-перевірка вимкнена (AUTO_CHECK_INTERVAL=%s)", AUTO_CHECK_INTERVAL)
        return

    logger.info("Авто-перевірка запущена. Інтервал: %s сек.", AUTO_CHECK_INTERVAL)

    while True:
        await asyncio.sleep(AUTO_CHECK_INTERVAL)

        if not _notify_chats:
            continue

        try:
            schedule = await fetch_schedule()
        except Exception as e:
            logger.error("Авто-перевірка: помилка %s", e)
            continue

        # Визначити нові слоти
        current_slots: dict[str, set[str]] = {}
        new_slots_text_parts: list[str] = []

        for day in schedule:
            if not day.is_working or not day.slots:
                continue
            slot_set = {s.time_str for s in day.slots}
            current_slots[day.date_label] = slot_set

            prev_set = _last_known_slots.get(day.date_label, set())
            new_times = slot_set - prev_set
            if new_times:
                times_str = ", ".join(sorted(new_times))
                new_slots_text_parts.append(
                    f"🆕 <b>{day.date_label}</b>: {times_str}"
                )

        _last_known_slots = current_slots

        if new_slots_text_parts:
            text = (
                "🔔 <b>Нові вільні слоти!</b>\n\n"
                + "\n".join(new_slots_text_parts)
                + "\n\n🔗 <a href='https://bumpix.net/uk/waxhubstudio'>Записатися</a>"
            )
            for chat_id in list(_notify_chats):
                try:
                    await bot.send_message(
                        chat_id, text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                except Exception as e:
                    logger.error("Не вдалось надіслати в чат %s: %s", chat_id, e)


# ── Запуск бота ──────────────────────────────────────────────────────────────

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задано! Встановіть змінну оточення або .env файл.")
        sys.exit(1)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    # Запуск фонової перевірки
    asyncio.create_task(_auto_check_loop(bot))

    logger.info("🚀 Бот запущено!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
