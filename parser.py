"""
Парсер доступних слотів з bumpix.net API.
"""

import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

import httpx

from config import BUMPIX_API_URL, GENERAL_ID, INSIDE_ID, DAYS_AHEAD, SERVICE_DURATION, LOCAL_TZ

logger = logging.getLogger(__name__)

# ── Типи даних ──────────────────────────────────────────────────────────────

@dataclass
class TimeSlot:
    """Один доступний слот для запису."""
    time_str: str        # "17:00"
    minutes: int         # хвилини з початку доби (1020 = 17:00)


@dataclass
class DaySchedule:
    """Розклад на один день."""
    date: datetime
    date_label: str       # "Ср, 04.03.2026"
    is_working: bool
    slots: list[TimeSlot] = field(default_factory=list)


# ── Допоміжні функції ────────────────────────────────────────────────────────

def _minutes_to_time(minutes: int) -> str:
    """Перетворює хвилини з початку доби у формат HH:MM."""
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def _is_collide(start: int, end: int, blocks: list[list[int]]) -> list[int] | None:
    """Перевіряє перетин інтервалу [start, end) з масивом блоків."""
    for block in blocks:
        if not (start >= block[1] or block[0] >= end):
            return block
    return None


def _get_free_times_normal(
    start_work: int,
    end_work: int,
    events: list[list[int]],
    breaks: list[list[int]],
    interval: int,
    need_minutes: int,
    allow_last: bool,
) -> list[int]:
    """Обчислити вільні слоти у звичайному режимі (як у JS-коді Bumpix)."""
    free = []
    current = start_work
    while current < end_work:
        collide = _is_collide(current, current + need_minutes, events)
        if not collide:
            collide = _is_collide(current, current + need_minutes, breaks)
        
        if not collide and current + need_minutes > end_work:
            if not allow_last:
                collide = [0, end_work]
        
        if not collide:
            free.append(current)
            current += interval
        else:
            # Стрибаємо за блок і вирівнюємо за інтервалом, щоб залишатися на сітці
            current = collide[1]
            passed = current - start_work
            if passed > 0 and interval > 0:
                remainder = passed % interval
                if remainder > 0:
                    current += (interval - remainder)
            elif passed < 0:
                current = start_work
    return free


def _get_free_times_static(
    start_work: int,
    end_work: int,
    events: list[list[int]],
    breaks: list[list[int]],
    times_array: list[int],
    need_minutes: int,
    allow_last: bool,
) -> list[int]:
    """Обчислити вільні слоти у режимі статичних часів."""
    free = []
    for current in times_array:
        if current < start_work or current >= end_work:
            continue
        collide = _is_collide(current, current + need_minutes, events)
        if not collide:
            collide = _is_collide(current, current + need_minutes, breaks)
        if not collide and current + need_minutes > end_work:
            if not allow_last:
                collide = [0, end_work]
        if not collide:
            free.append(current)
    return free


# ── Основний парсер ──────────────────────────────────────────────────────────

async def fetch_schedule(
    days_ahead: int = DAYS_AHEAD,
    need_minutes: int = SERVICE_DURATION,
) -> list[DaySchedule]:
    """
    Запитує API bumpix.net та повертає список DaySchedule на наступні дні.
    """
    # Визначаємо "сьогодні" за київським часом
    now_local = datetime.now(LOCAL_TZ)
    # Створюємо UTC midnight для цього ж числа (як очікує Bumpix)
    today = datetime(now_local.year, now_local.month, now_local.day, tzinfo=timezone.utc)

    from_ts = int(today.timestamp())
    to_ts = int((today + timedelta(days=days_ahead + 7)).timestamp())

    payload = {
        "generalId": GENERAL_ID,
        "insideId": INSIDE_ID,
        "from": from_ts,
        "to": to_ts,
        "teid": -1,
    }

    logger.info("Запит до Bumpix API: from=%s, to=%s", from_ts, to_ts)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            BUMPIX_API_URL,
            data=payload,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://bumpix.net/",
                "Origin": "https://bumpix.net",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if not data:
        return []

    time_data: dict = data.get("time", {})
    events_data: dict = data.get("events", {})
    interval = data.get("it", 15)
    interval_week = data.get("itw")
    static_times = data.get("sa", False)
    allow_last = "al" in data

    results: list[DaySchedule] = []

    for day_offset in range(days_ahead):
        current_day = today + timedelta(days=day_offset)
        day_ts = int(current_day.timestamp())
        day_ts_str = str(day_ts)

        py_wd = current_day.weekday() 
        java_wd = (py_wd + 2) % 7 
        if java_wd == 0: java_wd = 7

        day_interval = interval
        if interval_week and str(java_wd) in interval_week:
            day_interval = interval_week[str(java_wd)]

        weekdays_uk = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        date_label = f"{weekdays_uk[py_wd]}, {current_day.strftime('%d.%m.%Y')}"

        if day_ts_str not in time_data and day_ts not in time_data:
            results.append(DaySchedule(date=current_day, date_label=date_label, is_working=False))
            continue

        day_info = time_data.get(day_ts_str) or time_data.get(day_ts)
        if not day_info or "w" not in day_info:
            results.append(DaySchedule(date=current_day, date_label=date_label, is_working=False))
            continue

        start_work = day_info["w"][0]
        end_work = day_info["w"][1]
        breaks = day_info.get("b", [])
        events = events_data.get(day_ts_str) or events_data.get(str(day_ts)) or events_data.get(day_ts, [])

        if static_times:
            free_times = _get_free_times_static(start_work, end_work, events, breaks, static_times, need_minutes, allow_last)
        else:
            free_times = _get_free_times_normal(start_work, end_work, events, breaks, day_interval, need_minutes, allow_last)

        slots = [TimeSlot(time_str=_minutes_to_time(m), minutes=m) for m in free_times]
        results.append(DaySchedule(date=current_day, date_label=date_label, is_working=True, slots=slots))

    return results


def format_schedule(schedule: list[DaySchedule], compact: bool = False) -> str:
    """Formats the schedule into a text message."""
    if not schedule:
        return "❌ Не вдалось отримати розклад."

    lines = ["📅 <b>Розклад Анна Карпова (WaxHubStudio)</b>", f"🔗 <a href='https://bumpix.net/uk/waxhubstudio'>Записатися онлайн</a>", ""]
    has_any_slots = False

    for day in schedule:
        if not day.is_working:
            if not compact: lines.append(f"🔴 <b>{day.date_label}</b> — вихідний")
            continue
        if not day.slots:
            if not compact: lines.append(f"🟡 <b>{day.date_label}</b> — немає вільних слотів")
            continue
        has_any_slots = True
        times = ", ".join(s.time_str for s in day.slots)
        lines.append(f"🟢 <b>{day.date_label}</b>")
        lines.append(f"    ⏰ {times}")

    if not has_any_slots:
        lines.append("\n😔 На жаль, вільних слотів не знайдено.")

    return "\n".join(lines)


def format_schedule_short(schedule: list[DaySchedule]) -> str:
    """Short format for schedule."""
    return format_schedule(schedule, compact=True)
