
import logging
import io
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from typing import List

logger = logging.getLogger(__name__)

# Colors (Modern Theme)
BG_COLOR = "#0F172A"       # Deep Dark Blue
CARD_BG = "#1E293B"       # Slate Blue
TEXT_COLOR = "#F8FAFC"     # Ghost White
ACCENT_GREEN = "#10B981"  # Emerald Green
ACCENT_RED = "#EF4444"    # Rose Red
ACCENT_GRAY = "#64748B"   # Cool Gray
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def draw_rounded_rectangle(draw, xy, rad, fill):
    x0, y0, x1, y1 = xy
    draw.pieslice([x0, y0, x0 + rad * 2, y0 + rad * 2], 180, 270, fill=fill)
    draw.pieslice([x1 - rad * 2, y0, x1, y0 + rad * 2], 270, 360, fill=fill)
    draw.pieslice([x1 - rad * 2, y1 - rad * 2, x1, y1], 0, 90, fill=fill)
    draw.pieslice([x0, y1 - rad * 2, x0 + rad * 2, y1], 90, 180, fill=fill)
    draw.rectangle([x0, y0 + rad, x1, y1 - rad], fill=fill)
    draw.rectangle([x0 + rad, y0, x1 - rad, y1], fill=fill)

def get_calendar_as_image(schedule) -> io.BytesIO:
    """
    Generates a stylish modern grid of cards for the schedule.
    """
    # UI Constants
    card_width = 320
    card_height = 200
    margin = 25
    cols = 2
    header_h = 45
    rows = (len(schedule) + 1) // cols
    
    img_width = (card_width + margin) * cols + margin
    img_height = (card_height + margin) * rows + margin + 120 # +120 for title
    
    img = Image.new("RGB", (img_width, img_height), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype(FONT_BOLD_PATH, 36)
        date_font = ImageFont.truetype(FONT_BOLD_PATH, 22)
        slot_font = ImageFont.truetype(FONT_REGULAR_PATH, 19)
        info_font = ImageFont.truetype(FONT_REGULAR_PATH, 16)
        status_font = ImageFont.truetype(FONT_BOLD_PATH, 24)
    except:
        title_font = ImageFont.load_default()
        date_font = ImageFont.load_default()
        slot_font = ImageFont.load_default()
        info_font = ImageFont.load_default()
        status_font = ImageFont.load_default()

    # Draw Title Section
    draw.text((margin, 35), "Розклад WaxHubStudio", fill=TEXT_COLOR, font=title_font)
    draw.text((margin, 80), "Анна Карпова • Доступні вікна", fill=ACCENT_GRAY, font=info_font)
    
    y_start = 140
    
    for i, day in enumerate(schedule):
        row = i // cols
        col = i % cols
        
        x0 = margin + col * (card_width + margin)
        y0 = y_start + row * (card_height + margin)
        x1 = x0 + card_width
        y1 = y0 + card_height
        
        # Status Logic
        if not day.is_working:
            accent = ACCENT_RED
            status_text = "ВИХІДНИЙ"
        elif not day.slots:
            accent = ACCENT_GRAY
            status_text = "ЗАЙНЯТО"
        else:
            accent = ACCENT_GREEN
            status_text = "ВІЛЬНО"

        # 1. Main Card Background
        draw_rounded_rectangle(draw, [x0, y0, x1, y1], 15, CARD_BG)
        
        # 2. Header (Top Rounded)
        # We fill the top part with the accent color
        draw.rectangle([x0, y0 + 15, x1, y0 + header_h], fill=accent)
        draw.pieslice([x0, y0, x0 + 30, y0 + 30], 180, 270, fill=accent)
        draw.pieslice([x1 - 30, y0, x1, y0 + 30], 270, 360, fill=accent)
        draw.rectangle([x0 + 15, y0, x1 - 15, y0 + 15], fill=accent)

        # 3. Date Text
        # day.date_label format: "Ср, 04.03.2026"
        parts = day.date_label.split(",")
        weekday_label = parts[0].strip() if len(parts) > 0 else ""
        date_num = parts[1].strip() if len(parts) > 1 else ""
        
        draw.text((x0 + 15, y0 + 8), weekday_label, fill=BG_COLOR, font=date_font)
        draw.text((x0 + 60, y0 + 10), date_num, fill=BG_COLOR, font=info_font)

        # 4. Slots or Central Status
        if day.is_working and day.slots:
            # Render slots in a 3x3 grid
            for idx, slot in enumerate(day.slots[:9]):
                sx = x0 + 20 + (idx % 3) * 95
                sy = y0 + 65 + (idx // 3) * 40
                # Draw a mini-button for each slot
                draw_rounded_rectangle(draw, [sx - 5, sy - 2, sx + 75, sy + 30], 5, BG_COLOR)
                draw.text((sx + 8, sy + 3), slot.time_str, fill=ACCENT_GREEN, font=slot_font)
            
            if len(day.slots) > 9:
                draw.text((x1 - 50, y1 - 30), f"+{len(day.slots) - 9}", fill=ACCENT_GRAY, font=info_font)
        else:
            # Centered Status Text
            tw = draw.textlength(status_text, font=status_font)
            draw.text((x0 + (card_width - tw) / 2, y0 + 100), status_text, fill=accent, font=status_font)

    # Footer or Timestamp
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    draw.text((img_width - 250, img_height - 35), f"Оновлено: {now_str}", fill=ACCENT_GRAY, font=info_font)

    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio
