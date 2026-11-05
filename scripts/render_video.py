from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "src" / "data.json").read_text(encoding="utf-8"))
WIDTH, HEIGHT, FPS, DURATION = 1920, 1080, 30, 60
TOTAL_FRAMES = FPS * DURATION
MAP = (54, 174, 1454, 964)
BOUNDS = (121.395, 121.565, 31.175, 31.305)

PAPER = "#e8e0cf"
INK = "#171b1d"
MUTED = "#5d625e"
MILITIA = "#b6342e"
MILITIA_SOFT = "#d96a56"
SUPPRESSION = "#31566a"
SUPPRESSION_SOFT = "#6c8994"
RIVER = "#819da2"
WHITE = "#f7f3e9"
GOLD = "#a77723"

FONT_REG = Path("C:/Windows/Fonts/msyh.ttc")
FONT_BOLD = Path("C:/Windows/Fonts/msyhbd.ttc")
FONT_KAI = Path("C:/Windows/Fonts/simkai.ttf")
_fonts: dict[tuple[int, bool, bool], ImageFont.FreeTypeFont] = {}


def font(size: int, bold: bool = False, kai: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold, kai)
    if key not in _fonts:
        path = FONT_KAI if kai and FONT_KAI.exists() else (FONT_BOLD if bold else FONT_REG)
        _fonts[key] = ImageFont.truetype(str(path), size)
    return _fonts[key]


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def ease(value: float) -> float:
    value = clamp(value)
    return value * value * (3 - 2 * value)


def between(frame: int, start: int, end: int, edge: int = 24) -> float:
    return min(clamp((frame - start) / edge), clamp((end - frame) / edge))


def alpha(color: str, opacity: float) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4)) + (int(255 * clamp(opacity)),)


def project(lon: float, lat: float) -> tuple[float, float]:
    min_lon, max_lon, min_lat, max_lat = BOUNDS
    x0, y0, x1, y1 = MAP
    x = x0 + (lon - min_lon) / (max_lon - min_lon) * (x1 - x0)
    y = y0 + (1 - (lat - min_lat) / (max_lat - min_lat)) * (y1 - y0)
    return x, y


def line_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int, fill: str, bold: bool = False, anchor: str | None = None, kai: bool = False) -> None:
    draw.text(xy, text, font=font(size, bold, kai), fill=fill, anchor=anchor)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 2) -> list[str]:
    lines: list[str] = []
    rest = text
    while rest and len(lines) < max_lines:
        fit = 0
        for index in range(1, len(rest) + 1):
            if draw.textlength(rest[:index], font=text_font) <= max_width:
                fit = index
            else:
                break
        if fit >= len(rest):
            lines.append(rest)
            rest = ""
            break
        split = fit
        punctuation = max(rest.rfind(mark, 0, fit + 1) for mark in "，；。")
        if punctuation >= max(1, fit // 2):
            split = punctuation + 1
        lines.append(rest[:split])
        rest = rest[split:]
    if rest and lines:
        suffix = "…"
        last = lines[-1]
        while last and draw.textlength(last + suffix, font=text_font) > max_width:
            last = last[:-1]
        lines[-1] = last + suffix
    return lines


def tag(draw: ImageDraw.ImageDraw, x: int, y: int, text: str) -> None:
    f = font(15, True)
    box = draw.textbbox((0, 0), text, font=f)
    w = box[2] - box[0] + 14
    draw.rectangle((x, y, x + w, y + 25), fill=INK)
    draw.text((x + 7, y + 3), text, font=f, fill=WHITE)


def polyline(draw: ImageDraw.ImageDraw, pts: Iterable[tuple[float, float]], fill: str, width: int, dash: tuple[int, int] | None = None) -> None:
    points = list(pts)
    if not dash:
        draw.line(points, fill=fill, width=width, joint="curve")
        return
    on, off = dash
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        ux, uy = dx / length, dy / length
        pos = 0.0
        while pos < length:
            end = min(length, pos + on)
            draw.line((a[0] + ux * pos, a[1] + uy * pos, a[0] + ux * end, a[1] + uy * end), fill=fill, width=width)
            pos += on + off


def quadratic(a: tuple[float, float], b: tuple[float, float], bend: float, progress: float, samples: int = 80) -> list[tuple[float, float]]:
    cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + bend
    count = max(2, int(samples * clamp(progress)))
    points = []
    for index in range(count):
        t = progress * index / (count - 1)
        x = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * cx + t ** 2 * b[0]
        y = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * cy + t ** 2 * b[1]
        points.append((x, y))
    return points


def arrow(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], color: str, width: int = 5) -> None:
    if len(points) < 2:
        return
    polyline(draw, points, color, width, (12, 10))
    a, b = points[-2], points[-1]
    angle = math.atan2(b[1] - a[1], b[0] - a[0])
    size = 16
    p1 = (b[0] - size * math.cos(angle - 0.5), b[1] - size * math.sin(angle - 0.5))
    p2 = (b[0] - size * math.cos(angle + 0.5), b[1] - size * math.sin(angle + 0.5))
    draw.polygon((b, p1, p2), fill=color)


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], accent: str, dark: bool = False) -> None:
    draw.rectangle(box, fill=alpha(INK if dark else WHITE, 0.94))
    x0, y0, x1, _ = box
    draw.rectangle((x0, y0, x1, y0 + 7), fill=accent)


def base_map(draw: ImageDraw.ImageDraw) -> None:
    x0, y0, x1, y1 = MAP
    draw.rectangle(MAP, fill=alpha("#d9d0bd", 0.82), outline=INK, width=3)
    roads = [
        [(80, 730), (310, 610), (520, 560), (760, 580), (1140, 700), (1430, 610)],
        [(90, 520), (360, 500), (580, 410), (810, 440), (1190, 520), (1430, 420)],
        [(180, 270), (390, 350), (620, 310), (840, 330), (1180, 260), (1410, 330)],
        [(270, 190), (330, 380), (390, 620), (360, 930)],
        [(560, 180), (610, 390), (580, 650), (650, 950)],
        [(870, 180), (830, 430), (900, 710), (870, 960)],
        [(1190, 180), (1130, 390), (1220, 650), (1260, 950)],
    ]
    for road in roads:
        draw.line(road, fill=alpha("#7a766b", 0.32), width=2, joint="curve")
    river = [(1030, 168), (990, 260), (1010, 350), (1080, 430), (1130, 520), (1080, 610), (1110, 700), (1210, 790), (1435, 880)]
    draw.line(river, fill=alpha(RIVER, 0.57), width=74, joint="curve")
    draw.line(river, fill=alpha("#dce6e4", 0.8), width=2, joint="curve")
    for text, xy in [("长宁", (104, 914)), ("徐汇", (520, 745)), ("黄浦", (790, 525)), ("虹口", (920, 285)), ("杨浦", (1210, 245))]:
        line_text(draw, xy, text, 16, MUTED, True)
    line_text(draw, (1100, 530), "黄浦江", 17, SUPPRESSION, True)


LABEL_OFFSETS = {
    "militia_hq": (18, -44),
    "jiangnan": (-218, -48),
    "textile": (-218, -48),
    "kangping": (-206, 16),
    "dingxiang": (-208, -54),
    "donghu": (18, 18),
    "huangpu_district": (18, 12),
    "changning_district": (18, 14),
    "yangpu_district": (-240, 14),
    "naval_base": (-240, 16),
    "garrison": (-228, -54),
}


def node(draw: ImageDraw.ImageDraw, location: dict, opacity: float = 1.0) -> None:
    x, y = project(location["lon"], location["lat"])
    color = SUPPRESSION if location["side"] == "suppression" else MILITIA
    draw.ellipse((x - 16, y - 16, x + 16, y + 16), fill=alpha(color, 0.16 * opacity))
    draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=WHITE, outline=color, width=4)
    if location["kind"] == "disputed_command":
        draw.ellipse((x - 13, y - 13, x + 13, y + 13), outline=color, width=2)
    ox, oy = LABEL_OFFSETS.get(location["id"], (18, -38))
    lx, ly = int(x + ox), int(y + oy)
    distribution = location["kind"] == "distribution"
    w, h = (225, 68) if distribution else (205, 54)
    draw.rounded_rectangle((lx, ly, lx + w, ly + h), radius=3, fill=alpha(WHITE, 0.96), outline=color, width=2)
    line_text(draw, (lx + 10, ly + 7), location["short"], 18, INK, True)
    if distribution:
        line_text(draw, (lx + 10, ly + 37), f'枪 {location["weapons"]}支 · 弹 {location["rounds"]:,}发', 16, color, True)
    elif location["side"] == "suppression":
        line_text(draw, (lx + 10, ly + 33), "兵力未见可靠分项", 13, MUTED)
    else:
        line_text(draw, (lx + 10, ly + 33), location["address"], 13, MUTED)


def timeline(draw: ImageDraw.ImageDraw, frame: int) -> None:
    x0 = 1500
    draw.rectangle((x0, 0, WIDTH, HEIGHT), fill=alpha(INK, 0.97))
    line_text(draw, (1538, 54), "1976 · SHANGHAI", 18, "#b9c2bf", True)
    line_text(draw, (1538, 92), "事件时间线", 36, WHITE, True)
    starts = [90, 390, 720, 1200, 1510]
    active = max((i for i, value in enumerate(starts) if frame >= value), default=0)
    draw.line((1552, 195, 1552, 890), fill="#596266", width=2)
    for index, item in enumerate(DATA["timeline"]):
        y = 188 + index * 145
        on = index == active
        radius = 12 if on else 8
        color = (MILITIA if index < 3 else SUPPRESSION_SOFT) if on else "#8c9491"
        draw.ellipse((1552 - radius, y - radius, 1552 + radius, y + radius), fill=color, outline=INK, width=3)
        line_text(draw, (1586, y - 10), item["date"], 18, "#efc66f" if on else "#b9c2bf", True)
        line_text(draw, (1586, y + 19), item["title"], 24, WHITE, True)
        detail = item["detail"]
        detail_font = font(14)
        chunks = wrap_text(draw, detail, detail_font, 292, 2)
        for j, chunk in enumerate(chunks):
            line_text(draw, (1586, y + 54 + j * 24), chunk, 14, "#cbd1cf")
    line_text(draw, (1538, 1004), "虚线仅表示关系/战略方向，不冒充逐日行军轨迹", 13, "#9ba6a3")


def title(draw: ImageDraw.ImageDraw) -> None:
    line_text(draw, (54, 43), "1976年10月 上海敌我形势", 50, INK, True)
    line_text(draw, (54, 112), "兵力、武器与指挥节点的史料分层重建", 20, MUTED)
    line_text(draw, (1435, 72), "红：民兵武装　蓝：走资派弹压军", 15, MUTED, anchor="ra")
    line_text(draw, (1435, 100), "虚线：争议 / 关系 / 方向示意", 15, MUTED, anchor="ra")


def command_scene(draw: ImageDraw.ImageDraw, frame: int) -> None:
    visible = ease((frame - 90) / 60)
    if visible <= 0:
        return
    for location in DATA["locations"]:
        if location["side"] == "militia" and location["kind"] != "distribution":
            node(draw, location, visible)
    op = between(frame, 110, 485, 28)
    if op > 0:
        panel(draw, (82, 204, 570, 450), MILITIA)
        line_text(draw, (108, 230), "10月8日批注所见", 21, MILITIA, True)
        reveal = ease((frame - 135) / 90)
        line_text(draw, (108, 282), f"{round(2500 * reveal):,}", 52, INK, True)
        line_text(draw, (315, 282), f"{round(31000 * reveal):,}", 52, INK, True)
        line_text(draw, (110, 348), "人集中", 19, MUTED)
        line_text(draw, (316, 348), "人待命", 19, MUTED)
        line_text(draw, (108, 398), "全市汇总，没有可靠逐点/逐区人员拆分", 17, INK, True)
        tag(draw, 468, 397, "S1")
        panel(draw, (925, 205, 1418, 356), GOLD)
        line_text(draw, (1390, 225), "训令", 19, GOLD, True, anchor="ra")
        line_text(draw, (1390, 260), "“准备接受严重考验”", 31, INK, True, anchor="ra", kai=True)
        line_text(draw, (1390, 311), "据后出材料转述；未见可独立核验原始手令", 14, MUTED, anchor="ra")
        tag(draw, 1345, 326, "S5")


def distribution_scene(draw: ImageDraw.ImageDraw, frame: int) -> None:
    if frame < 420 or frame > 960:
        return
    for location in DATA["locations"]:
        if location["kind"] in {"distribution", "disputed_command", "command"} and location["side"] == "militia":
            node(draw, location)
    hq = next(x for x in DATA["locations"] if x["id"] == "militia_hq")
    for target_id, bend in (("jiangnan", 70), ("textile", -55)):
        target = next(x for x in DATA["locations"] if x["id"] == target_id)
        progress = ease((frame - 500) / 170)
        points = quadratic(project(hq["lon"], hq["lat"]), project(target["lon"], target["lat"]), bend, progress)
        arrow(draw, points, MILITIA)
    panel(draw, (78, 716, 655, 934), MILITIA, dark=True)
    line_text(draw, (104, 739), "事后官方清查口径", 20, "#efc66f", True)
    for index, (number, label) in enumerate((("27,000", "件/支武器"), ("225", "辆车辆"), ("15", "部电台"))):
        x = 104 + index * 168
        line_text(draw, (x, 786), number, 33, WHITE, True)
        line_text(draw, (x, 831), label, 15, "#cfd5d2")
    line_text(draw, (104, 881), "指控性材料，不自动等同于中性统计", 15, "#e8d8b7")
    tag(draw, 555, 878, "S3")
    panel(draw, (735, 743, 1418, 934), MILITIA)
    line_text(draw, (761, 769), "江南造船厂 · 中纺机：节点性质有争议", 21, INK, True)
    line_text(draw, (761, 815), "事后官方材料：称“秘密指挥点”", 17, MILITIA, True)
    tag(draw, 1115, 814, "S3")
    line_text(draw, (761, 854), "回忆与研究：认为更接近联络点", 17, SUPPRESSION, True)
    tag(draw, 1115, 853, "S6")
    line_text(draw, (761, 895), "动画以虚线圆环表示分歧，不强行裁决。", 15, MUTED)


def regional_scene(draw: ImageDraw.ImageDraw, frame: int) -> None:
    if frame < 840 or frame > 1260:
        return
    panel(draw, (80, 202, 710, 748), SUPPRESSION)
    line_text(draw, (106, 229), "走资派弹压军 · 外围压力", 22, SUPPRESSION, True)
    line_text(draw, (680, 231), "人数：未见可靠分项", 15, MILITIA, True, anchor="ra")
    positions = {"无锡": (245, 370), "苏州": (362, 450), "上海": (590, 510), "宁波": (620, 650)}
    draw.polygon(((105, 300), (350, 275), (680, 330), (680, 710), (150, 700)), fill="#ded6c6")
    progress = ease((frame - 900) / 190)
    a = quadratic(positions["无锡"], positions["苏州"], -10, min(1, progress * 1.5), 30)
    b = quadratic(positions["苏州"], positions["上海"], -20, max(0, (progress - 0.25) / 0.75), 45)
    c = quadratic(positions["宁波"], positions["上海"], -45, progress, 45)
    arrow(draw, a + b[1:] if len(b) > 1 else a, SUPPRESSION)
    arrow(draw, c, SUPPRESSION)
    for name, (x, y) in positions.items():
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=MILITIA if name == "上海" else SUPPRESSION)
        line_text(draw, (x + 12, y - 24), name, 17, INK, True)
    line_text(draw, (110, 586), "陆军第60军", 19, SUPPRESSION, True)
    line_text(draw, (110, 616), "无锡—苏州—上海战略方向示意", 15, MUTED)
    line_text(draw, (110, 655), "东海舰队 / 海军上海基地", 19, SUPPRESSION, True)
    line_text(draw, (110, 685), "指挥与控制关系示意", 15, MUTED)


def takeover_scene(draw: ImageDraw.ImageDraw, frame: int) -> None:
    if frame < 1170 or frame > 1590:
        return
    shown = {"militia_hq", "naval_base", "garrison"}
    for location in DATA["locations"]:
        if location["id"] in shown:
            node(draw, location)
    naval = next(x for x in DATA["locations"] if x["id"] == "naval_base")
    garrison = next(x for x in DATA["locations"] if x["id"] == "garrison")
    hq = next(x for x in DATA["locations"] if x["id"] == "militia_hq")
    progress = ease((frame - 1210) / 190)
    arrow(draw, quadratic(project(naval["lon"], naval["lat"]), project(garrison["lon"], garrison["lat"]), 35, progress), SUPPRESSION)
    arrow(draw, quadratic(project(garrison["lon"], garrison["lat"]), project(hq["lon"], hq["lat"]), -20, progress), SUPPRESSION)
    draw.rectangle((80, 760, 1418, 936), fill=alpha(SUPPRESSION, 0.96))
    line_text(draw, (108, 786), "10月20日", 36, WHITE, True)
    line_text(draw, (108, 837), "中央工作组抵沪", 17, "#cbd9de")
    line_text(draw, (350, 789), "虹桥机场 → 水电路海军上海基地 → 联络上海警备区及驻沪部队", 21, WHITE, True)
    line_text(draw, (350, 836), "公开材料确认指挥节点，但不支持给各部队补写人数", 16, "#d8e1e4")
    tag(draw, 1180, 833, "S5")


def ledger_scene(draw: ImageDraw.ImageDraw, frame: int) -> None:
    if frame < 1530:
        return
    draw.rectangle(MAP, fill=alpha(PAPER, 0.99))
    line_text(draw, (120, 226), "剩余风险与史料边界", 23, MILITIA, True)
    line_text(draw, (120, 268), "知道什么，也标出不知道什么", 47, INK, True)
    tiers = (("A级", "批注影印或可追原始记录", "S1"), ("B级", "档案/口述研究与交叉解释", "S2 · S6"), ("C级", "事后官方、审判或批判材料", "S3 · S4 · S5"))
    for index, (tier, label, ids) in enumerate(tiers):
        y = 380 + index * 116
        draw.rectangle((120, y, 202, y + 44), fill=INK)
        line_text(draw, (161, y + 8), tier, 20, WHITE, True, anchor="ma")
        line_text(draw, (230, y), label, 21, INK, True)
        line_text(draw, (230, y + 34), ids, 16, MUTED)
    risks = (
        (MILITIA, "人员", "只确认全市2,500人集中、31,000人待命；不把33,500人塞进一个指挥部。"),
        (SUPPRESSION, "弹压军", "60军、东海舰队与警备区的分项人数不足，故只画方向与关系。"),
        (GOLD, "训令", "保留“准备接受严重考验”，同时注明未见可独立核验的原始手令。"),
    )
    for index, (color, head, body) in enumerate(risks):
        y = 380 + index * 116
        draw.rectangle((700, y, 708, y + 82), fill=color)
        line_text(draw, (728, y), f"{head}：", 20, INK, True)
        line_text(draw, (810, y), body[:24], 18, INK)
        line_text(draw, (810, y + 32), body[24:], 18, INK)
    draw.line((120, 870, 1390, 870), fill="#7a766b", width=2)
    line_text(draw, (120, 892), "完整URL、来源说明、坐标与数字均保存在 src/data.json；地图为态势示意，不是精确测绘成果。", 16, MUTED)


def render_frame(frame: int, texture: Image.Image) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    image = Image.blend(image, texture, 0.22)
    draw = ImageDraw.Draw(image, "RGBA")
    if frame >= 70:
        title(draw)
        base_map(draw)
        timeline(draw, frame)
        command_scene(draw, frame)
        distribution_scene(draw, frame)
        regional_scene(draw, frame)
        takeover_scene(draw, frame)
        ledger_scene(draw, frame)
    if frame < 125:
        opacity = 1 - ease(max(0, frame - 70) / 55)
        draw.rectangle((0, 0, WIDTH, HEIGHT), fill=alpha(PAPER, 0.94 * opacity))
        line_text(draw, (960, 330), "史料分层 · 确定性地图动画", 22, MILITIA, True, anchor="ma")
        line_text(draw, (960, 415), "1976年10月", 74, INK, True, anchor="ma")
        line_text(draw, (960, 520), "上海敌我形势", 80, INK, True, anchor="ma")
        line_text(draw, (960, 655), "数字有出处 · 未知不补写 · 路线标明性质", 23, MUTED, anchor="ma")
    return image


def write_keyframes(texture: Image.Image) -> list[Path]:
    out = ROOT / "output" / "keyframes"
    out.mkdir(parents=True, exist_ok=True)
    frames = [0, 210, 600, 1000, 1350, 1650]
    paths = []
    for value in frames:
        path = out / f"frame-{value:04d}.png"
        render_frame(value, texture).save(path, optimize=True)
        paths.append(path)
        print(f"Wrote {path}")
    return paths


def write_video(texture: Image.Image, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
        "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for frame in range(TOTAL_FRAMES):
            process.stdin.write(render_frame(frame, texture).tobytes())
            if frame % 150 == 0:
                print(f"Rendered {frame}/{TOTAL_FRAMES}", flush=True)
    finally:
        process.stdin.close()
    code = process.wait()
    if code:
        raise SystemExit(code)
    print(f"Wrote {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyframes-only", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "shanghai-1976-force-map.mp4")
    args = parser.parse_args()
    texture_path = ROOT / "public" / "assets" / "archive-paper.png"
    if not texture_path.exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_local_texture.py")], check=True)
    texture = Image.open(texture_path).convert("RGB").resize((WIDTH, HEIGHT))
    write_keyframes(texture)
    if not args.keyframes_only:
        write_video(texture, args.output)


if __name__ == "__main__":
    main()
