"""
Draw the app icon and write icon.png, icon.ico (Windows) and icon.icns (macOS).

The icon is the 20-minute abyss timer: a dark tile with an orange arc for the
time used and a faint track for the time left.

Run with:  pip install pillow && python make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent / "assets"
SIZE = 1024
SCALE = 4  # draw large, then downsample for smooth edges

BG = "#100e16"     # NEUTRAL_THEME.bg
TRACK = "#3b3550"  # NEUTRAL_THEME.line
ACCENT = "#d95926"  # Abyss colour


def draw():
    s = SIZE * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # macOS-style tile: content inset ~10% with a rounded square
    inset = s * 0.1
    d.rounded_rectangle((inset, inset, s - inset, s - inset), radius=s * 0.18, fill=BG)

    box = (s * 0.27, s * 0.27, s * 0.73, s * 0.73)
    width = int(s * 0.07)
    d.arc(box, 0, 360, fill=TRACK, width=width)
    # 14 of 20 minutes used, starting at 12 o'clock
    d.arc(box, -90, -90 + 360 * 14 / 20, fill=ACCENT, width=width)
    # centre dot
    r = s * 0.045
    d.ellipse((s / 2 - r, s / 2 - r, s / 2 + r, s / 2 + r), fill=ACCENT)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    img = draw()
    img.save(HERE / "icon.png")
    img.save(HERE / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.save(HERE / "icon.icns")


if __name__ == "__main__":
    main()
