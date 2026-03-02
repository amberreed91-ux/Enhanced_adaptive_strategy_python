from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path('/Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20')
DATA_PATH = ROOT / 'portfolio_site' / 'assets' / 'projects.json'
MEDIA_ROOT = ROOT / 'portfolio_site' / 'assets' / 'project_media'

W, H = 1280, 720

PALETTES = [
    {'bg': (8, 23, 32), 'panel': (16, 49, 66), 'accent': (255, 140, 72), 'ink': (232, 246, 245)},
    {'bg': (18, 18, 32), 'panel': (40, 32, 68), 'accent': (89, 207, 255), 'ink': (240, 243, 255)},
    {'bg': (11, 32, 19), 'panel': (24, 64, 42), 'accent': (252, 201, 77), 'ink': (238, 250, 237)},
    {'bg': (33, 18, 15), 'panel': (74, 38, 26), 'accent': (107, 220, 176), 'ink': (253, 238, 226)},
    {'bg': (17, 14, 36), 'panel': (39, 31, 79), 'accent': (255, 116, 195), 'ink': (246, 235, 255)},
]

FONT_CANDIDATES = [
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/System/Library/Fonts/Supplemental/Helvetica.ttc',
    '/System/Library/Fonts/Supplemental/Menlo.ttc',
]


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


FONT_TITLE = load_font(38)
FONT_SUB = load_font(21)
FONT_BODY = load_font(18)
FONT_SMALL = load_font(15)


def rng_for_slug(slug: str) -> random.Random:
    digest = hashlib.sha1(slug.encode()).digest()
    seed = int.from_bytes(digest[:8], 'big')
    return random.Random(seed)


def short(text: str, n: int = 94) -> str:
    t = text.strip().replace('\n', ' ')
    return t if len(t) <= n else t[: n - 3] + '...'


def parse_metric(metrics: list[str], key: str, default: float) -> float:
    for line in metrics:
        if key in line:
            parts = ''.join(ch if (ch.isdigit() or ch == '.' or ch == '-') else ' ' for ch in line).split()
            for p in parts:
                try:
                    return float(p)
                except ValueError:
                    continue
    return default


def draw_background(draw: ImageDraw.ImageDraw, palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    bg = palette['bg']
    panel = palette['panel']
    accent = palette['accent']

    draw.rectangle((0, 0, W, H), fill=bg)
    for y in range(0, H, 8):
        ratio = y / H
        r = int(bg[0] * (1 - ratio) + panel[0] * ratio)
        g = int(bg[1] * (1 - ratio) + panel[1] * ratio)
        b = int(bg[2] * (1 - ratio) + panel[2] * ratio)
        draw.rectangle((0, y, W, y + 8), fill=(r, g, b))

    orb_x = 90 + phase * 26
    draw.ellipse((orb_x, -130, orb_x + 330, 190), fill=(accent[0], accent[1], accent[2]))
    draw.ellipse((W - 300, H - 230, W + 40, H + 120), fill=(panel[0] + 10, panel[1] + 18, panel[2] + 20))


def draw_header(draw: ImageDraw.ImageDraw, project: dict[str, object], palette: dict[str, tuple[int, int, int]]) -> tuple[int, int, int, int]:
    ink = palette['ink']
    accent = palette['accent']

    draw.rounded_rectangle((36, 28, W - 36, 142), radius=18, fill=(10, 30, 42), outline=accent, width=2)
    draw.text((56, 48), str(project['title']), fill=ink, font=FONT_TITLE)
    draw.text((56, 96), f"{project['slug']}  |  {project.get('category','General')}", fill=(194, 221, 226), font=FONT_SUB)

    return (52, 172, W - 52, H - 42)


def bar_chart(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], labels: list[str], values: list[float], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    draw.rounded_rectangle(box, radius=16, fill=(8, 27, 39), outline=palette['accent'], width=2)

    if not values:
        values = [1.0]
        labels = ['n/a']

    vmax = max(abs(v) for v in values) or 1.0
    n = len(values)
    gap = 12
    bw = (w - 40 - gap * (n - 1)) / max(1, n)
    baseline = y1 - 46

    for i, (label, val) in enumerate(zip(labels, values, strict=False)):
        x = x0 + 20 + i * (bw + gap)
        amp = (abs(val) / vmax) * (h - 120)
        glow = phase % n == i
        color = palette['accent'] if glow else (89, 180, 255)
        draw.rounded_rectangle((x, baseline - amp, x + bw, baseline), radius=10, fill=color)
        draw.text((x, baseline + 10), short(label, 10), fill=(208, 230, 235), font=FONT_SMALL)


def template_finance(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    summary = (project.get('demo_output') or {}).get('summary') or {}
    labels = list(summary.keys())
    values = [float(summary[k]) for k in labels] if labels else [1200, -350, -210]
    if not labels:
        labels = ['income', 'rent', 'food']
    bar_chart(draw, box, labels, values, palette, phase)


def template_password(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(14, 26, 45), outline=palette['accent'], width=2)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    draw.ellipse((cx - 90, y0 + 90, cx + 90, y0 + 270), outline=(190, 220, 248), width=8)
    draw.rounded_rectangle((cx - 150, cy - 40, cx + 150, cy + 160), radius=24, fill=(35, 60, 88), outline=(210, 236, 255), width=3)
    key_y = cy + 40 + (phase % 4) * 6
    draw.ellipse((cx - 22, key_y - 22, cx + 22, key_y + 22), fill=palette['accent'])
    draw.rectangle((cx - 7, key_y + 12, cx + 7, key_y + 72), fill=palette['accent'])
    draw.text((x0 + 30, y1 - 60), 'Round-trip encryption verified', fill=palette['ink'], font=FONT_BODY)


def template_scraper(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(21, 39, 48), outline=palette['accent'], width=2)
    cols = ['Symbol', 'Price', 'Change']
    rows = [
        ['BTC', '102,500.15', '+1.8%'],
        ['ETH', '4,880.62', '+0.9%'],
        ['SOL', '210.44', '-0.4%'],
    ]
    row_h = 72
    for i, col in enumerate(cols):
        draw.text((x0 + 44 + i * 280, y0 + 36), col, fill=(228, 244, 245), font=FONT_SUB)
    for r, row in enumerate(rows):
        y = y0 + 86 + r * row_h
        fill = (24, 64, 80) if r == phase % len(rows) else (18, 47, 60)
        draw.rounded_rectangle((x0 + 24, y, x1 - 24, y + 56), radius=10, fill=fill)
        for i, cell in enumerate(row):
            color = (129, 246, 166) if cell.startswith('+') else ((255, 154, 154) if cell.startswith('-') else palette['ink'])
            draw.text((x0 + 44 + i * 280, y + 16), cell, fill=color, font=FONT_BODY)


def template_api(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(15, 33, 50), outline=palette['accent'], width=2)
    endpoints = [('POST', '/items'), ('GET', '/items'), ('GET', '/health')]
    for i, (method, path) in enumerate(endpoints):
        y = y0 + 42 + i * 94
        active = i == phase % len(endpoints)
        fill = (39, 78, 96) if active else (24, 52, 68)
        draw.rounded_rectangle((x0 + 30, y, x1 - 30, y + 70), radius=12, fill=fill)
        method_color = (113, 220, 144) if method == 'GET' else (255, 199, 102)
        draw.text((x0 + 48, y + 19), method, fill=method_color, font=FONT_SUB)
        draw.text((x0 + 190, y + 19), path, fill=palette['ink'], font=FONT_SUB)
    draw.text((x0 + 34, y1 - 52), 'Validation boundaries + service layer design', fill=(197, 223, 229), font=FONT_BODY)


def template_tasks(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(16, 35, 44), outline=palette['accent'], width=2)
    cols = ['To Do', 'Doing', 'Done']
    cw = (x1 - x0 - 48) // 3
    for i, col in enumerate(cols):
        cx = x0 + 24 + i * (cw + 12)
        draw.rounded_rectangle((cx, y0 + 30, cx + cw, y1 - 30), radius=10, fill=(22, 54, 66))
        draw.text((cx + 16, y0 + 44), col, fill=palette['ink'], font=FONT_SUB)
        for j in range(3):
            yy = y0 + 92 + j * 78
            fill = (57, 124, 147) if (i + j + phase) % 4 == 0 else (35, 75, 91)
            draw.rounded_rectangle((cx + 14, yy, cx + cw - 14, yy + 54), radius=8, fill=fill)


def template_jwt(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(22, 27, 47), outline=palette['accent'], width=2)
    token_parts = ['header', 'payload', 'signature']
    for i, part in enumerate(token_parts):
        xx = x0 + 40 + i * ((x1 - x0 - 120) // 3)
        w = (x1 - x0 - 160) // 3
        fill = (66, 86, 154) if i == phase % 3 else (46, 61, 112)
        draw.rounded_rectangle((xx, y0 + 120, xx + w, y0 + 280), radius=14, fill=fill)
        draw.text((xx + 20, y0 + 185), part, fill=(236, 241, 255), font=FONT_SUB)
        if i < 2:
            draw.text((xx + w + 12, y0 + 192), '.', fill=palette['accent'], font=FONT_TITLE)
    draw.text((x0 + 46, y1 - 70), 'HMAC signing + verification', fill=palette['ink'], font=FONT_BODY)


def template_pipeline(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(15, 42, 27), outline=palette['accent'], width=2)
    steps = ['Extract', 'Transform', 'Load']
    sx = x0 + 46
    for i, step in enumerate(steps):
        xx = sx + i * 360
        active = i == phase % 3
        fill = (57, 130, 94) if active else (36, 92, 66)
        draw.rounded_rectangle((xx, y0 + 180, xx + 230, y0 + 320), radius=14, fill=fill)
        draw.text((xx + 58, y0 + 240), step, fill=(235, 251, 240), font=FONT_SUB)
        if i < 2:
            draw.polygon([(xx + 250, y0 + 246), (xx + 308, y0 + 246), (xx + 308, y0 + 232), (xx + 346, y0 + 260), (xx + 308, y0 + 288), (xx + 308, y0 + 274), (xx + 250, y0 + 274)], fill=palette['accent'])


def template_dashboard(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(12, 32, 56), outline=palette['accent'], width=2)
    draw.rounded_rectangle((x0 + 28, y0 + 28, x0 + 340, y0 + 180), radius=12, fill=(24, 62, 96))
    draw.text((x0 + 48, y0 + 50), 'Avg KPI', fill=palette['ink'], font=FONT_SUB)
    draw.text((x0 + 54, y0 + 102), str((project.get('demo_output') or {}).get('avg', '14.25')), fill=palette['accent'], font=FONT_TITLE)

    chart = (x0 + 380, y0 + 42, x1 - 34, y1 - 46)
    draw.rounded_rectangle(chart, radius=12, fill=(18, 48, 76))
    points = []
    for i in range(8):
        x = chart[0] + 26 + i * ((chart[2] - chart[0] - 52) // 7)
        y = chart[3] - 40 - int((math.sin((i + phase) / 2) + 1.4) * 78)
        points.append((x, y))
    draw.line(points, fill=palette['accent'], width=4)
    for p in points:
        draw.ellipse((p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5), fill=(227, 247, 246))


def template_alert(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(24, 21, 46), outline=palette['accent'], width=2)
    mid = (y0 + y1) // 2
    high, low = mid - 90, mid + 90
    draw.line((x0 + 40, high, x1 - 40, high), fill=(255, 154, 154), width=3)
    draw.line((x0 + 40, low, x1 - 40, low), fill=(123, 244, 164), width=3)
    points = []
    rr = rng_for_slug(str(project['slug']))
    for i in range(20):
        x = x0 + 40 + i * ((x1 - x0 - 80) // 19)
        y = mid + int(rr.uniform(-130, 130))
        points.append((x, y))
    draw.line(points, fill=(163, 211, 255), width=3)
    pulse = points[phase % len(points)]
    draw.ellipse((pulse[0] - 10, pulse[1] - 10, pulse[0] + 10, pulse[1] + 10), fill=palette['accent'])


def template_logs(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(22, 18, 18), outline=palette['accent'], width=2)
    logs = ['[INFO] boot', '[ERROR] timeout', '[INFO] retry', '[ERROR] failed', '[WARN] backoff']
    for i, line in enumerate(logs):
        y = y0 + 44 + i * 74
        active = i == phase % len(logs)
        fill = (66, 36, 36) if active else (40, 27, 27)
        draw.rounded_rectangle((x0 + 26, y, x1 - 26, y + 56), radius=10, fill=fill)
        color = (255, 118, 118) if 'ERROR' in line else ((248, 198, 126) if 'WARN' in line else (214, 235, 239))
        draw.text((x0 + 44, y + 16), line, fill=color, font=FONT_BODY)


def template_async(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(14, 34, 40), outline=palette['accent'], width=2)
    center = ((x0 + x1) // 2, (y0 + y1) // 2)
    draw.ellipse((center[0] - 92, center[1] - 52, center[0] + 92, center[1] + 52), fill=(50, 106, 120))
    draw.text((center[0] - 58, center[1] - 12), 'Aggregator', fill=palette['ink'], font=FONT_SUB)
    nodes = [(x0 + 170, y0 + 130), (x1 - 190, y0 + 130), (x0 + 170, y1 - 130), (x1 - 190, y1 - 130)]
    for i, (nx, ny) in enumerate(nodes):
        fill = palette['accent'] if i == phase % len(nodes) else (77, 150, 164)
        draw.rounded_rectangle((nx - 80, ny - 40, nx + 80, ny + 40), radius=12, fill=fill)
        draw.text((nx - 30, ny - 10), f'src{i+1}', fill=(13, 31, 37), font=FONT_BODY)
        draw.line((nx, ny, center[0], center[1]), fill=(205, 233, 235), width=3)


def template_chat(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(18, 31, 50), outline=palette['accent'], width=2)
    bubbles = [
        (x0 + 40, y0 + 60, x0 + 520, y0 + 140, (61, 107, 169), '/start -> session started'),
        (x1 - 560, y0 + 180, x1 - 40, y0 + 260, (39, 156, 122), '/ping -> pong 1'),
        (x0 + 40, y0 + 300, x0 + 560, y0 + 380, (61, 107, 169), '/ping -> pong 2'),
    ]
    for i, (a, b, c, d, color, text) in enumerate(bubbles):
        if i == phase % len(bubbles):
            color = tuple(min(255, x + 30) for x in color)
        draw.rounded_rectangle((a, b, c, d), radius=14, fill=color)
        draw.text((a + 20, b + 24), text, fill=(240, 249, 251), font=FONT_BODY)


def template_reco(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    labels = ['item_a', 'item_c', 'item_b']
    vals = [0.98, 0.66, 0.12]
    bar_chart(draw, box, labels, vals, palette, phase)


def template_nlp(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(28, 22, 45), outline=palette['accent'], width=2)
    terms = [('buy', 0.9), ('offer', 0.82), ('meeting', 0.2), ('schedule', 0.15), ('spam', 1.0)]
    for i, (term, score) in enumerate(terms):
        size = int(18 + score * 26)
        f = load_font(size)
        xx = x0 + 50 + (i % 3) * 320 + (phase * 4 if i == phase % len(terms) else 0)
        yy = y0 + 80 + (i // 3) * 190
        color = palette['accent'] if i == phase % len(terms) else (209, 231, 236)
        draw.text((xx, yy), term, fill=color, font=f)
    draw.text((x0 + 52, y1 - 58), "prediction: spam", fill=palette['ink'], font=FONT_SUB)


def template_forecast(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(12, 37, 34), outline=palette['accent'], width=2)
    hist = [100, 102, 101, 105, 107]
    fc = [104.33, 105.44]
    allv = hist + fc
    vmin, vmax = min(allv), max(allv)

    def map_point(i: int, v: float, n: int) -> tuple[int, int]:
        x = x0 + 70 + int(i * ((x1 - x0 - 140) / (n - 1)))
        y = y1 - 80 - int(((v - vmin) / (vmax - vmin + 1e-9)) * (y1 - y0 - 170))
        return x, y

    hist_pts = [map_point(i, v, len(allv)) for i, v in enumerate(hist)]
    fc_pts = [map_point(i + len(hist) - 1, v, len(allv)) for i, v in enumerate([hist[-1]] + fc)]

    draw.line(hist_pts, fill=(155, 230, 187), width=4)
    draw.line(fc_pts, fill=palette['accent'], width=4)
    for p in hist_pts + fc_pts:
        draw.ellipse((p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5), fill=(235, 248, 239))

    pulse = fc_pts[min(phase, len(fc_pts)-1)]
    draw.ellipse((pulse[0] - 10, pulse[1] - 10, pulse[0] + 10, pulse[1] + 10), outline=palette['accent'], width=3)


def template_cv(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(20, 23, 38), outline=palette['accent'], width=2)
    gx0, gy0 = x0 + 80, y0 + 80
    cell = 52
    values = [[10, 12, 19, 24, 18], [8, 10, 16, 20, 19], [7, 9, 13, 17, 16]]
    for r, row in enumerate(values):
        for c, v in enumerate(row):
            gray = int(40 + v * 7)
            draw.rectangle((gx0 + c*cell, gy0 + r*cell, gx0 + c*cell + cell - 4, gy0 + r*cell + cell - 4), fill=(gray, gray, gray))
    ex0 = gx0 + 420
    draw.text((ex0, gy0 - 16), 'Edge response', fill=palette['ink'], font=FONT_SUB)
    edges = [2, 7, 5, 6]
    for i, e in enumerate(edges):
        y = gy0 + i * 62
        w = e * 35 + (phase % 2) * 6
        draw.rounded_rectangle((ex0, y, ex0 + w, y + 44), radius=8, fill=palette['accent'])


def template_docker(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(17, 36, 54), outline=palette['accent'], width=2)
    names = ['api', 'worker', 'redis', 'db']
    for i, name in enumerate(names):
        xx = x0 + 120 + (i % 2) * 420
        yy = y0 + 120 + (i // 2) * 180
        fill = (56, 128, 176) if i == phase % len(names) else (40, 95, 133)
        draw.rounded_rectangle((xx, yy, xx + 320, yy + 120), radius=14, fill=fill)
        draw.text((xx + 30, yy + 44), f'container: {name}', fill=(233, 247, 252), font=FONT_SUB)


def template_cicd(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(20, 32, 36), outline=palette['accent'], width=2)
    steps = ['tests', 'lint', 'types', 'deploy']
    for i, step in enumerate(steps):
        xx = x0 + 54 + i * 284
        ok = step != 'types'
        fill = (53, 151, 106) if ok else (167, 71, 71)
        if i == phase % len(steps):
            fill = tuple(min(255, c + 25) for c in fill)
        draw.rounded_rectangle((xx, y0 + 220, xx + 220, y0 + 320), radius=12, fill=fill)
        draw.text((xx + 28, y0 + 258), step, fill=(241, 250, 246), font=FONT_SUB)
        if i < len(steps)-1:
            draw.line((xx + 228, y0 + 270, xx + 276, y0 + 270), fill=palette['ink'], width=4)


def template_queue(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(24, 26, 44), outline=palette['accent'], width=2)
    jobs = [('fail-once-task', 1), ('email', 2), ('reconcile', 3), ('notify', 4)]
    for i, (name, pri) in enumerate(jobs):
        y = y0 + 70 + i * 94
        active = i == phase % len(jobs)
        fill = (86, 112, 189) if active else (56, 75, 132)
        draw.rounded_rectangle((x0 + 44, y, x1 - 44, y + 70), radius=10, fill=fill)
        draw.text((x0 + 62, y + 23), f'P{pri}  {name}', fill=(232, 241, 255), font=FONT_BODY)


def template_ml(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], project: dict[str, object], palette: dict[str, tuple[int, int, int]], phase: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=(22, 29, 22), outline=palette['accent'], width=2)
    px0, py0, px1, py1 = x0 + 70, y0 + 70, x1 - 70, y1 - 90
    rr = rng_for_slug(str(project['slug']))
    pts = []
    for i in range(10):
        x = px0 + i * ((px1 - px0) // 9)
        y = py1 - int((i / 9) * (py1 - py0)) + rr.randint(-18, 18)
        pts.append((x, y))
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(160, 237, 190))
    draw.line((px0, py1, px1, py0), fill=palette['accent'], width=4)
    pulse = pts[phase % len(pts)]
    draw.ellipse((pulse[0] - 11, pulse[1] - 11, pulse[0] + 11, pulse[1] + 11), outline=palette['accent'], width=3)


TEMPLATES: dict[str, Callable[[ImageDraw.ImageDraw, tuple[int, int, int, int], dict[str, object], dict[str, tuple[int, int, int]], int], None]] = {
    '01_finance_tracker_cli': template_finance,
    '02_password_manager_encrypted': template_password,
    '03_web_scraper_data_cleaner': template_scraper,
    '04_rest_api_fastapi_style': template_api,
    '05_task_manager_webapp': template_tasks,
    '06_jwt_auth_service': template_jwt,
    '07_etl_pipeline': template_pipeline,
    '08_data_dashboard': template_dashboard,
    '09_price_alert_bot': template_alert,
    '10_log_analyzer_monitor': template_logs,
    '11_async_api_aggregator': template_async,
    '12_chat_bot': template_chat,
    '13_recommender_system': template_reco,
    '14_nlp_text_classifier': template_nlp,
    '15_time_series_forecaster': template_forecast,
    '16_computer_vision_mini_app': template_cv,
    '17_dockerized_microservice': template_docker,
    '18_ci_cd_project_template': template_cicd,
    '19_distributed_job_queue': template_queue,
    '20_capstone_end_to_end_ml_product': template_ml,
}


def render_frame(project: dict[str, object], phase: int) -> Image.Image:
    slug = str(project['slug'])
    idx = int(slug.split('_', 1)[0]) - 1
    palette = PALETTES[idx % len(PALETTES)]

    image = Image.new('RGB', (W, H), palette['bg'])
    draw = ImageDraw.Draw(image)

    draw_background(draw, palette, phase)
    box = draw_header(draw, project, palette)

    template = TEMPLATES.get(slug, template_tasks)
    template(draw, box, project, palette, phase)

    draw.text((58, H - 30), short(str(project.get('summary', ''))), fill=(205, 228, 232), font=FONT_SMALL)
    return image


def write_visuals(project: dict[str, object]) -> None:
    slug = str(project['slug'])
    target = MEDIA_ROOT / slug
    target.mkdir(parents=True, exist_ok=True)

    first = render_frame(project, phase=0)
    first.save(target / 'preview.png')

    frames = [render_frame(project, phase=i) for i in range(4)]
    frames[0].save(
        target / 'demo.gif',
        save_all=True,
        append_images=frames[1:],
        duration=300,
        loop=0,
        optimize=True,
    )


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    projects = payload.get('projects', [])
    for project in projects:
        write_visuals(project)
    print(f'Generated distinct visuals for {len(projects)} projects at {MEDIA_ROOT}')


if __name__ == '__main__':
    main()
