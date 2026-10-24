"""
Draw the app icon and write icon.png, icon.ico (Windows) and icon.icns (macOS).

The icon is the 20-minute abyss timer: a dark tile with an orange arc for the
time used and a faint track for the time left.

Run with:  pip install pillow && python make_icon.py
"""
from PIL import Image, ImageDraw

from theme import ASSETS, NEUTRAL_THEME

SIZE = 1024
SCALE = 4  # draw large, then downsample for smooth edges

ACCENT = "#d95926"  # gui.KIND_COLOR[ABYSS]; gui imports customtkinter, so not imported here


def draw():
    side = SIZE * SCALE
    img = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    pen = ImageDraw.Draw(img)
    # macOS-style tile: content inset ~10% with a rounded square
    inset = side * 0.1
    pen.rounded_rectangle((inset, inset, side - inset, side - inset), radius=side * 0.18, fill=NEUTRAL_THEME.bg)

    box = (side * 0.27, side * 0.27, side * 0.73, side * 0.73)
    width = int(side * 0.07)
    pen.arc(box, 0, 360, fill=NEUTRAL_THEME.line, width=width)
    # 14 of 20 minutes used, starting at 12 o'clock
    pen.arc(box, -90, -90 + 360 * 14 / 20, fill=ACCENT, width=width)
    # centre dot
    dot = side * 0.045
    pen.ellipse((side / 2 - dot, side / 2 - dot, side / 2 + dot, side / 2 + dot), fill=ACCENT)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    img = draw()
    img.save(ASSETS / "icon.png")
    img.save(ASSETS / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.save(ASSETS / "icon.icns")


if __name__ == "__main__":
    main()
