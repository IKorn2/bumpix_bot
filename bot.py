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

from config import BOT_TOKEN, AUTO_CHECK_INTERVAL, NOTIFY_CHAT_IDS, DAYS_AHEAD, LOCAL_TZ
from parser import fetch_schedule, format_schedule, format_schedule_short
from database import (
    init_db, add_subscription, remove_subscription, get_subscriptions,
    get_last_known_slots, update_last_known_slots
)
from calendar_drawer import get_calendar_as_image
from aiogram.types import BotCommand, BufferedInputFile

# ── Логування ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Роутер ───────────────────────────────────────────────────────────────────

router = Router()

# (Стан тепер зберігається в БД через get_last_known_slots / update_last_known_slots)


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Привіт!</b>\n\n"
        "Я бот-парсер розкладу <b>Анна Карпова (WaxHubStudio)</b> з bumpix.net.\n\n"
        "📋 <b>Доступні команди:</b>\n"
        "  /check — 🟢 Перевірити вільні слоти (тільки доступні часи)\n"
        "  /full  — 📅 Повний розклад на 14 днів (включаючи вихідні)\n"
        "  /calendar — 🎨 Генерований календар (фото)\n"
        "  /notify — 🔔 Увімкнути/вимкнути авто-сповіщення про нові слоти\n"
        #"  /test_notify — 🔍 Тестова перевірка (яка зазвичай йде у фоні)\n"
        "  /help  — ❓ Довідка\n\n"
        "Натисніть /check щоб почати!",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "❓ <b>Довідка</b>\n\n"
        "Цей бот моніторить вільні слоти для запису до спеціаліста "
        "<b>Анна Карпова</b> (WaxHubStudio, Чабани) через API bumpix.net.\n\n"
        "📋 <b>Команди:</b>\n"
        "  /check — показати дні, в яких є хоча б один вільний слот\n"
        "  /full  — показати розклад на 14 днів, включаючи заповнені дні та вихідні\n"
        "  /calendar — згенерувати стильну картинку-календар\n"
        "  /notify — підписатися на нотифікації. Бот надішле повідомлення, як тільки з'явиться новий вільний час\n"
        #"  /test_notify — примусово запустити алгоритм виявлення нових слотів та надіслати повідомлення, якщо вони є\n\n"
        "🔴 — вихідний\n"
        "🟡 — все зайнято\n"
        "🟢 — є вільні слоти\n\n"
        f"Стандартна перевірка виконується на <b>{DAYS_AHEAD}</b> днів вперед.",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("check"))
async def cmd_check(message: types.Message):
    wait_msg = await message.answer("⏳ Зв'язуюсь з Bumpix API...")

    try:
        schedule = await fetch_schedule()
        text = format_schedule_short(schedule)
    except Exception as e:
        logger.error("Помилка при отриманні розкладу: %s", e, exc_info=True)
        text = f"❌ Помилка при отриманні даних: <code>{e}</code>\nСпробуйте пізніше."

    now_str = datetime.now(LOCAL_TZ).strftime("%d.%m.%Y %H:%M")
    text += f"\n\n🕐 <i>Оновлено: {now_str}</i>"

    try:
        image_data = await get_calendar_as_image(schedule)
        photo = BufferedInputFile(image_data.read(), filename="calendar.png")
        
        # Обмеження Telegram на довжину caption: 1024 символи
        if len(text) <= 1024:
            await message.answer_photo(
                photo=photo,
                caption=text,
                parse_mode=ParseMode.HTML
            )
        else:
            # Якщо текст задовгий, надсилаємо картинку окремо, а текст окремо
            await message.answer_photo(
                photo=photo,
                caption="🎨 Календар вільних вікон",
                parse_mode=ParseMode.HTML
            )
            await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        await wait_msg.delete()
    except Exception as e:
        logger.error("Помилка при генерації календаря для /check: %s", e)
        await wait_msg.edit_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@router.message(Command("full"))
async def cmd_full(message: types.Message):
    wait_msg = await message.answer("⏳ Завантажую повний календар...")

    try:
        schedule = await fetch_schedule()
        text = format_schedule(schedule, compact=False)
    except Exception as e:
        logger.error("Помилка при отриманні розкладу: %s", e, exc_info=True)
        text = f"❌ Помилка при отриманні даних: <code>{e}</code>\nСпробуйте пізніше."

    now_str = datetime.now(LOCAL_TZ).strftime("%d.%m.%Y %H:%M")
    text += f"\n\n🕐 <i>Оновлено: {now_str}</i>"

    try:
        image_data = await get_calendar_as_image(schedule)
        photo = BufferedInputFile(image_data.read(), filename="calendar.png")
        
        if len(text) <= 1024:
            await message.answer_photo(
                photo=photo,
                caption=text,
                parse_mode=ParseMode.HTML
            )
        else:
            await message.answer_photo(
                photo=photo,
                caption="📅 Повний розклад",
                parse_mode=ParseMode.HTML
            )
            await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        await wait_msg.delete()
    except Exception as e:
        logger.error("Помилка при генерації календаря для /full: %s", e)
        await wait_msg.edit_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@router.message(Command("notify"))
async def cmd_notify(message: types.Message):
    chat_id = message.chat.id
    current_subs = get_subscriptions()
    
    if chat_id in current_subs:
        remove_subscription(chat_id)
        await message.answer(
            "🔕 Авто-сповіщення <b>вимкнено</b>.\nБот більше не турбуватиме вас фоновими повідомленнями.",
            parse_mode=ParseMode.HTML,
        )
    else:
        add_subscription(chat_id)
        await message.answer(
            "🔔 Авто-сповіщення <b>увімкнено</b>!\n"
            "Я надішлю повідомлення сюди, як тільки в системі з'явиться новий вільний час для запису.",
            parse_mode=ParseMode.HTML,
        )


@router.message(Command("calendar"))
async def cmd_calendar(message: types.Message):
    wait_msg = await message.answer("⏳ Генерую стильний календар...")
    try:
        schedule = await fetch_schedule()
        image_data = await get_calendar_as_image(schedule)
        
        photo = BufferedInputFile(image_data.read(), filename="calendar.png")
        await message.answer_photo(
            photo=photo,
            caption="🎨 <b>Ваш календар вільних вікон</b>\n"
                    "Анна Карпова (WaxHubStudio)\n\n"
                    "🔗 <a href='https://bumpix.net/uk/waxhubstudio'>Записатися онлайн</a>",
            parse_mode=ParseMode.HTML
        )
        await wait_msg.delete()
    except Exception as e:
        logger.error("Помилка при генерації календаря: %s", e, exc_info=True)
        await wait_msg.edit_text(f"❌ Помилка при генерації: <code>{e}</code>")


@router.message(Command("test_notify"))
async def cmd_test_notify(message: types.Message):
    """
    Мануально запускає перевірку на нові слоти (аналогічно фоновому процесу).
    """
    await message.answer("🔍 Запускаю позачергову перевірку на нові слоти...")
    
    try:
        schedule = await fetch_schedule()
        
        last_known = get_last_known_slots()
        current_slots: dict[str, set[str]] = {}
        new_slots_text_parts: list[str] = []

        for day in schedule:
            if not day.is_working or not day.slots:
                continue
            slot_set = {s.time_str for s in day.slots}
            current_slots[day.date_label] = slot_set
            
            prev_set = last_known.get(day.date_label, set())
            new_times = slot_set - prev_set
            
            if new_times:
                times_str = ", ".join(sorted(new_times))
                new_slots_text_parts.append(f"🆕 <b>{day.date_label}</b>: {times_str}")
        
        # Оновлюємо стан у БД
        update_last_known_slots(current_slots)

        if new_slots_text_parts:
            text = (
                "🔔 <b>Виявлено нові вільні слоти!</b>\n\n"
                + "\n".join(new_slots_text_parts)
                + "\n\n🔗 <a href='https://bumpix.net/uk/waxhubstudio'>Записатися</a>"
            )
            
            try:
                image_data = await get_calendar_as_image(schedule)
                photo = BufferedInputFile(image_data.read(), filename="calendar.png")
                await message.answer_photo(
                    photo=photo,
                    caption=text,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error("Помилка при генерації календаря для /test_notify: %s", e)
                await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        else:
            await message.answer("✅ Нових слотів відносно останньої перевірки не знайдено.")
            
    except Exception as e:
        logger.error("Помилка при виконанні /test_notify: %s", e)
        await message.answer(f"❌ Помилка під час перевірки: {e}")


# ── Авто-перевірка (фоновий таск) ───────────────────────────────────────────

async def perform_check(bot: Bot):
    """Виконує одну перевірку розкладу та надсилає сповіщення при змінах."""
    notify_chats = get_subscriptions()
    # Також додаємо чати з конфигу (якщо вони були задані через .env)
    for cid in NOTIFY_CHAT_IDS:
        notify_chats.add(cid)

    if not notify_chats:
        return

    try:
        schedule = await fetch_schedule()
    except Exception as e:
        logger.error("Помилка під час перевірки: %s", e)
        return

    # Визначити нові слоти
    last_known = get_last_known_slots()
    current_slots: dict[str, set[str]] = {}
    new_slots_text_parts: list[str] = []

    for day in schedule:
        if not day.is_working or not day.slots:
            continue
        slot_set = {s.time_str for s in day.slots}
        current_slots[day.date_label] = slot_set

        prev_set = last_known.get(day.date_label, set())
        new_times = slot_set - prev_set
        if new_times:
            times_str = ", ".join(sorted(new_times))
            new_slots_text_parts.append(
                f"🆕 <b>{day.date_label}</b>: {times_str}"
            )

    update_last_known_slots(current_slots)

    if new_slots_text_parts:
        text = (
            "🔔 <b>Нові вільні слоти!</b>\n\n"
            + "\n".join(new_slots_text_parts)
            + "\n\n🔗 <a href='https://bumpix.net/uk/waxhubstudio'>Записатися</a>"
        )
        
        # Генеруємо картинку для авто-сповіщення
        photo_bytes = None
        try:
            image_data = await get_calendar_as_image(schedule)
            photo_bytes = image_data.read()
        except Exception as e:
            logger.error("Помилка генерації картинки: %s", e)

        for chat_id in list(notify_chats):
            try:
                if photo_bytes:
                    photo = BufferedInputFile(photo_bytes, filename="calendar.png")
                    
                    if len(text) <= 1024:
                        await bot.send_photo(
                            chat_id, 
                            photo=photo,
                            caption=text,
                            parse_mode=ParseMode.HTML,
                        )
                    else:
                        await bot.send_photo(
                            chat_id, 
                            photo=photo,
                            caption="🔔 Виявлено нові вільні слоти!",
                            parse_mode=ParseMode.HTML,
                        )
                        await bot.send_message(
                            chat_id, text,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True,
                        )
                else:
                    await bot.send_message(
                        chat_id, text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
            except Exception as e:
                logger.error("Не вдалось надіслати в чат %s: %s", chat_id, e)


# ── Авто-перевірка (фоновий таск) ───────────────────────────────────────────

async def _auto_check_loop(bot: Bot):
    """Періодично перевіряє розклад і надсилає повідомлення при змінах."""
    if AUTO_CHECK_INTERVAL <= 0:
        logger.info("Авто-перевірка вимкнена (AUTO_CHECK_INTERVAL=%s)", AUTO_CHECK_INTERVAL)
        return

    logger.info("Авто-перевірка запущена. Інтервал: %s сек.", AUTO_CHECK_INTERVAL)

    # Перша перевірка одразу при запуску
    await perform_check(bot)

    while True:
        await asyncio.sleep(AUTO_CHECK_INTERVAL)
        await perform_check(bot)


# ── Запуск бота ──────────────────────────────────────────────────────────────

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задано! Встановіть змінну оточення або .env файл.")
        sys.exit(1)

    # Ініціалізація бази даних
    init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    # Встановлення підказок команд у меню Telegram
    await bot.set_my_commands([
        BotCommand(command="check", description="🟢 Вільні слоти"),
        BotCommand(command="full", description="📅 Повний розклад"),
        BotCommand(command="calendar", description="🎨 Календар (фото)"),
        BotCommand(command="notify", description="🔔 Авто-сповіщення"),
        #BotCommand(command="test_notify", description="🔍 Тестова перевірка"),
        BotCommand(command="help", description="❓ Допомога"),
    ])

    # Запуск фонової перевірки
    asyncio.create_task(_auto_check_loop(bot))

    logger.info("🚀 Бот запущено з підказками команд!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
