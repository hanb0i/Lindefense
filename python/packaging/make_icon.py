"""Renders the Lindefense emblem into packaging/Lindefense.icns (macOS app icon) with the game's own art code."""
import os
import subprocess
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import skia  # noqa: E402

from lindefense.ui.jawt import Graphics2D, reset_canvas_state  # noqa: E402
from lindefense.ui.logo_emblem import LogoEmblem  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def render(n, path):
    surf = skia.Surface.MakeRasterN32Premul(n, n)
    cv = surf.getCanvas()
    cv.clear(0)
    # dark rounded tile behind the emblem, like a macOS app icon
    p = skia.Paint(AntiAlias=True, Color=0xFF05070F)
    m = n * 0.06
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(m, m, n - 2 * m, n - 2 * m), n * 0.2, n * 0.2), p)
    reset_canvas_state(cv)
    g = Graphics2D(cv)
    g.translate(n / 2.0, n / 2.0)
    e = LogoEmblem(n * 0.78)
    e.animate(0.4)
    e.paint(g)
    reset_canvas_state(cv)
    surf.makeImageSnapshot().save(path, skia.kPNG)


def main():
    iconset = os.path.join(HERE, "Lindefense.iconset")
    os.makedirs(iconset, exist_ok=True)
    for s in (16, 32, 128, 256, 512):
        render(s, os.path.join(iconset, "icon_%dx%d.png" % (s, s)))
        render(s * 2, os.path.join(iconset, "icon_%dx%d@2x.png" % (s, s)))
    subprocess.check_call(["iconutil", "-c", "icns", iconset, "-o", os.path.join(HERE, "Lindefense.icns")])
    print("wrote", os.path.join(HERE, "Lindefense.icns"))


if __name__ == "__main__":
    main()
