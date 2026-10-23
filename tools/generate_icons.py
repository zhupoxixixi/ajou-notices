#!/usr/bin/env python3
"""Generate Ajou Notices app and social preview icons with Pillow.

Run from any directory: python tools/generate_icons.py
The artwork is a notice sheet with a small alert badge, kept inside the
central 80% safe area used by maskable home-screen icons.
"""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "icons"
BLUE = "#0088FF"
WHITE = "#FFFFFF"
INK = "#17212F"
MUTED = "#667085"
PAGE = "#F7F9FC"


def draw_notice_mark(size: int, supersample: int = 4) -> Image.Image:
    """Return a square blue icon with a centered white notice and alert badge."""
    scale = size * supersample / 64
    canvas_size = size * supersample
    image = Image.new("RGB", (canvas_size, canvas_size), BLUE)
    draw = ImageDraw.Draw(image)

    def xy(point):
        return tuple(round(value * scale) for value in point)

    def width(value):
        return max(1, round(value * scale))

    # Document outline, folded corner, and three readable notice lines.
    outline = [(17, 11), (37, 11), (47, 21), (47, 52), (17, 52), (17, 11)]
    draw.line([xy(point) for point in outline], fill=WHITE, width=width(3.2), joint="curve")
    draw.line([xy(point) for point in [(37, 12), (37, 21), (46, 21)]], fill=WHITE, width=width(3.0), joint="curve")
    for y, end in ((29, 40), (36, 40), (43, 35)):
        draw.line([xy((23, y)), xy((end, y))], fill=WHITE, width=width(3.0))

    # The badge intentionally overlaps the sheet and uses the system blue for contrast.
    center = xy((46, 45))
    radius = width(7)
    bounds = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    draw.ellipse(bounds, fill=WHITE, outline=BLUE, width=width(1.5))
    draw.line([xy((46, 41.5)), xy((46, 45.5))], fill=BLUE, width=width(2.0))
    dot_radius = max(1, width(0.8))
    dot = xy((46, 48))
    draw.ellipse((dot[0] - dot_radius, dot[1] - dot_radius, dot[0] + dot_radius, dot[1] + dot_radius), fill=BLUE)

    return image.resize((size, size), Image.Resampling.LANCZOS)


def find_font(bold: bool = False) -> Path:
    candidates = (
        [Path(r"C:\Windows\Fonts\msyhbd.ttc"), Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc")]
        if bold else
        [Path(r"C:\Windows\Fonts\msyh.ttc"), Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc")]
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("需要 Microsoft YaHei 或 Noto Sans CJK 字体来生成中文分享预览图。")


def make_share_card() -> Image.Image:
    """Build the 1200x630 Open Graph preview using the same blue notice mark."""
    factor = 3
    width, height = 1200, 630
    image = Image.new("RGB", (width * factor, height * factor), PAGE)
    draw = ImageDraw.Draw(image)

    def p(value):
        return round(value * factor)

    def box(values):
        return tuple(p(value) for value in values)

    draw.rounded_rectangle(box((60, 60, 1140, 570)), radius=p(32), fill=WHITE, outline="#D9E1EA", width=p(2))

    icon = draw_notice_mark(72, supersample=3)
    icon = icon.resize((p(64), p(64)), Image.Resampling.LANCZOS)
    image.paste(icon, (p(110), p(98)))
    draw = ImageDraw.Draw(image)
    bold = ImageFont.truetype(str(find_font(True)), p(30))
    regular = ImageFont.truetype(str(find_font(False)), p(62))
    sub = ImageFont.truetype(str(find_font(False)), p(28))
    label = ImageFont.truetype(str(find_font(True)), p(25))

    draw.text((p(196), p(111)), "AJOU NOTICE", font=label, fill=BLUE)
    draw.text((p(110), p(212)), "亚洲大学中文公告", font=regular, fill=INK, stroke_width=0)
    draw.text((p(110), p(322)), "外国留学生 · 一般大学院 · 网络安全", font=sub, fill=MUTED)
    draw.text((p(110), p(437)), "中文要点 / 截止日期 / 官方原文", font=bold, fill=BLUE)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def validate_maskable(image: Image.Image, name: str) -> None:
    """Fail if visible artwork intrudes into the outer 10% maskable margin."""
    diff = ImageChops.difference(image, Image.new("RGB", image.size, BLUE))
    bounds = diff.getbbox()
    if bounds is None:
        raise ValueError(f"{name}: icon artwork is blank")
    w, h = image.size
    safe = (round(w * 0.10), round(h * 0.10), round(w * 0.90), round(h * 0.90))
    if bounds[0] < safe[0] or bounds[1] < safe[1] or bounds[2] > safe[2] or bounds[3] > safe[3]:
        raise ValueError(f"{name}: artwork bbox {bounds} exceeds central safe area {safe}")
    margin = min(bounds[0], bounds[1], w - bounds[2], h - bounds[3])
    print(f"{name}: {w}x{h}, artwork bbox={bounds}, minimum safe margin={margin}px")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)):
        icon = draw_notice_mark(size)
        validate_maskable(icon, name)
        icon.save(OUT / name, format="PNG", optimize=True)
    share = make_share_card()
    share.save(OUT / "share.png", format="PNG", optimize=True)
    print(f"share.png: {share.width}x{share.height}")


if __name__ == "__main__":
    main()
