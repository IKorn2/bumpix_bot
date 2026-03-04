import asyncio
import datetime
import io
import logging
from playwright.async_api import async_playwright
from jinja2 import Template

logger = logging.getLogger(__name__)

# Оновлений HTML Template (Modern Specialist Schedule Style)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;800&display=swap');

        body {
            font-family: 'Manrope', sans-serif;
            margin: 0;
            padding: 40px;
            background-color: #f0f2f5;
            display: inline-block;
        }

        .schedule-container {
            background-color: #ffffff;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.08);
            overflow: hidden;
            display: inline-block;
            min-width: 1000px;
            border: 1px solid #eef0f2;
        }

        /* HEADER */
        .header {
            background: linear-gradient(135deg, #10B981 0%, #059669 100%);
            color: #fff;
            padding: 24px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 4px solid #ffffff;
        }

        .header-title {
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }

        .header-title span {
            color: #ffffff;
            opacity: 0.9;
        }

        .header-subtitle {
            font-size: 16px;
            font-weight: 600;
            opacity: 0.9;
            background: rgba(255, 255, 255, 0.2);
            padding: 6px 16px;
            border-radius: 20px;
        }

        /* TABLE STRUCTURE */
        table {
            border-collapse: separate;
            border-spacing: 4px 12px;
            width: 100%;
            padding: 0 20px;
            margin-bottom: 20px;
        }

        /* HEADERS (HOURS) */
        th {
            color: #8898aa;
            font-weight: 600;
            font-size: 10px;
            text-align: center;
            padding-bottom: 5px;
            width: 32px;
            white-space: nowrap;
        }

        .date-col {
            width: 120px;
            font-size: 16px;
            font-weight: 800;
            color: #2d3748;
            padding-right: 15px;
        }
        
        .date-day {
            display: block;
            font-size: 12px;
            font-weight: 600;
            color: #718096;
            margin-top: 2px;
        }

        .current-date-row .date-col {
            color: #10B981;
        }

        /* SLOTS (CELLS) */
        td.slot {
            height: 45px;
            border-radius: 6px;
            position: relative;
        }

        /* STATUS STYLES */

        /* ВІЛЬНО (Available) */
        .status-available {
            background-color: #ecfdf5;
            border: 1px solid #10B981;
        }
        
        /* ЗАЙНЯТО (Occupied) */
        .status-busy {
            background-color: #f7fafc;
            border: 1px solid #e2e8f0;
        }

        /* ВИХІДНИЙ (Day Off) */
        .status-off {
            background-color: #fff1f2;
            border: 1px solid #fda4af;
            background-image: repeating-linear-gradient(
                45deg,
                transparent,
                transparent 5px,
                rgba(244, 63, 94, 0.05) 5px,
                rgba(244, 63, 94, 0.05) 10px
            );
        }

        /* LEGEND */
        .legend {
            display: flex;
            justify-content: center;
            gap: 25px;
            padding: 20px 0;
            border-top: 1px solid #e2e8f0;
            background-color: #fff;
        }

        .legend-item {
            display: flex;
            align-items: center;
            font-size: 14px;
            font-weight: 600;
            color: #4a5568;
        }

        .legend-box {
            width: 20px;
            height: 20px;
            border-radius: 4px;
            margin-right: 8px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }

        .footer {
            background-color: #f7fafc;
            color: #a0aec0;
            font-size: 11px;
            padding: 12px 30px;
            text-align: right;
            border-top: 1px solid #edf2f7;
        }

        th.hour {
            font-size: 13px;
            font-weight: 800;
            color: #4a5568;
            padding: 10px 0;
            letter-spacing: -0.2px;
        }

    </style>
</head>
<body>
    <div class="schedule-container">
        <div class="header">
            <div class="header-title">📅 Розклад <span>записів</span></div>
            <div class="header-subtitle">Анна Карпова (WaxHubStudio)</div>
        </div>

        <table>
            <thead>
                <tr>
                    <th></th>
                    {% for h in range(8, 22) %}
                        <th class="hour">{{ '%02d' % h }}</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for day in days %}
                <tr class="{{ 'current-date-row' if day.is_today else '' }}">
                    <td class="date-col">
                        {{ day.date_str }}
                        <span class="date-day">{{ day.weekday_name }}</span>
                    </td>
                    {% for h in range(8, 22) %}
                        <td class="slot status-{{ day.schedule[h|string] }}"></td>
                    {% endfor %}
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <div class="legend">
            <div class="legend-item">
                <div class="legend-box status-available"></div>
                <span>Є вільні вікна</span>
            </div>
            <div class="legend-item">
                <div class="legend-box status-busy"></div>
                <span>Все зайнято</span>
            </div>
             <div class="legend-item">
                <div class="legend-box status-off"></div>
                <span>Вихідний</span>
            </div>
        </div>

        <div class="footer">Згенеровано: {{ generated_at }}</div>
    </div>
</body>
</html>
"""

def get_weekday_name(dt: datetime.datetime) -> str:
    days = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
    return days[dt.weekday()]

async def get_calendar_as_image(schedule) -> io.BytesIO:
    """
    Generates a stylish modern calendar image using Playwright.
    """
    try:
        today = datetime.datetime.now()
        today_str = today.strftime("%d.%m.%Y")
        
        days = []
        for day in schedule:
            dt = day.date
            is_today = (dt.strftime("%d.%m.%Y") == today_str)
            
            # Map slots to hours (8:00 to 21:00)
            hour_status = {}
            if not day.is_working:
                for h in range(8, 22):
                    hour_status[str(h)] = "off"
            else:
                # Default to busy
                for h in range(8, 22):
                    hour_status[str(h)] = "busy"
                
                # Mark as available if there's any slot in that hour
                for slot in day.slots:
                    try:
                        h = int(slot.time_str.split(":")[0])
                        if 8 <= h < 22:
                            hour_status[str(h)] = "available"
                    except:
                        continue
            
            days.append({
                "date_str": dt.strftime("%d.%m"),
                "weekday_name": get_weekday_name(dt),
                "is_today": is_today,
                "schedule": hour_status
            })

        template = Template(HTML_TEMPLATE)
        html_content = template.render(
            days=days,
            generated_at=datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1100, "height": 1000})
            await page.set_content(html_content)

            element = await page.query_selector(".schedule-container")
            if not element:
                screenshot_bytes = await page.screenshot(type="png", full_page=True)
            else:
                screenshot_bytes = await element.screenshot(type="png")

            await browser.close()
            
            bio = io.BytesIO(screenshot_bytes)
            bio.seek(0)
            return bio

    except Exception as e:
        logger.error(f"Помилка при генерації календаря: {e}", exc_info=True)
        # Fallback to a simple image if playwright fails
        from PIL import Image
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        return bio
