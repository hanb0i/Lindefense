"""Regression tests for the Java runtime / Java2D shims under the ported UI (lindefense.ui.jrt, jawt): the values
must match what the Java build computes, because the transpiled UI lays text and art out with them. Expected numbers
were measured with the real JDK (FontDesignMetrics, Font.getLineMetrics, String.format, Math)."""
import gc
import math
import os
import weakref

import skia

from lindefense import assets
from lindefense.ui import jawt
from lindefense.ui import jrt as _j
from lindefense.ui.cyber import Cyber
from lindefense.ui.jawt import BufferedImage, Color, Font, FontRenderContext, font_metrics, reset_canvas_state


def _bundled(name, size):
    return Font.create_font(Font.TRUETYPE_FONT, os.path.join(assets.path("assets/fonts"), name)).derive_font(float(size))


def test_double_min_max_promote_to_double(check):
    # Math.max(int, double) is a double in Java; an int result made Font.deriveFont(float) pick deriveFont(int style)
    check(type(_j.dmax(11, 10.5)) is float and _j.dmax(11, 10.5) == 11.0, "dmax(11, 10.5) -> 11.0")
    check(type(_j.dmin(3, 7.5)) is float and _j.dmin(3, 7.5) == 3.0, "dmin(3, 7.5) -> 3.0")
    check(math.isnan(_j.dmax(float("nan"), 1)) and math.isnan(_j.dmin(1, float("nan"))), "NaN propagates")
    for size in (6, 8, 10, 11, 12):
        f = Cyber.display(Font.BOLD, size)
        check(f.get_style() == Font.PLAIN and f.get_size2_d() >= 11.0,
              "Cyber.display(BOLD, %d) is the 11pt floor font, got %r size %s" % (size, f, f.get_size2_d()))
    for size in (6, 9, 10):
        f = Cyber.display_compact(Font.BOLD, size)
        check(f.get_size2_d() >= 9.0, "Cyber.display_compact(BOLD, %d) is at least 9pt, got %s" % (size, f.get_size2_d()))
    # the visible symptom: a 1pt font measured (and drew) labels at a tiny fraction of their real width
    label = Cyber.Text("BELLARMINE")
    label.set_font(Cyber.display(Font.BOLD, 6))
    check(label.get_width() > 50, "6pt display label width %s" % label.get_width())


def test_font_size_rounds_like_java(check):
    # java.awt.Font: size = (int) (pointSize + 0.5)
    check(Font("Dialog", 0, 12.5).get_size() == 13, "12.5pt -> getSize 13")
    check(Font("Dialog", 0, 10.4).get_size() == 10, "10.4pt -> getSize 10")
    check(_bundled("IBMPlexMono-Bold.ttf", 57.6).get_size() == 58, "57.6pt -> getSize 58")
    check(Cyber.display(Font.BOLD, 14).get_size() == 13, "display(BOLD, 14) is 12.5pt -> 13")


def test_font_metrics_match_java(check):
    frc = FontRenderContext(None, True, True)
    # (file, size, FontMetrics ascent / descent / leading / height, LineMetrics ascent / descent), from the JDK
    cases = [("IBMPlexMono-Bold.ttf", 9, 10, 3, 0, 13, 9.2251, 2.4750),
             ("IBMPlexMono-Bold.ttf", 10.8, 12, 3, 0, 15, 11.0667, 2.9691),
             ("Barlow-Regular.ttf", 12, 12, 3, 0, 15, 12.0001, 2.4000),
             ("Barlow-SemiBold.ttf", 14, 14, 3, 0, 17, 13.9999, 2.8000),
             ("Rajdhani-Bold.ttf", 9, 9, 4, 0, 13, 8.3701, 3.1140),
             ("Rajdhani-Bold.ttf", 18, 17, 7, 0, 24, 16.7399, 6.2280)]
    for name, size, a, d, l, h, la, ld in cases:
        f = _bundled(name, size)
        fm = font_metrics(f)
        got = (fm.get_ascent(), fm.get_descent(), fm.get_leading(), fm.get_height())
        check(got == (a, d, l, h), "%s %s FontMetrics %r, Java (%d, %d, %d, %d)" % (name, size, got, a, d, l, h))
        lm = f.get_line_metrics("Ag", frc)
        check(abs(lm.get_ascent() - la) < 0.02 and abs(lm.get_descent() - ld) < 0.02,
              "%s %s LineMetrics %.4f / %.4f, Java %.4f / %.4f" % (name, size, lm.get_ascent(), lm.get_descent(), la, ld))
        check(abs(lm.get_height() - (lm.get_ascent() + lm.get_descent() + lm.get_leading())) < 1e-9, "LineMetrics height")
    # Cyber.Text (every HUD / panel label) centres and stacks with the fractional line metrics
    t = Cyber.Text("Ag")
    t.set_font(_bundled("Barlow-Regular.ttf", 12))
    check(abs(t.get_height() - 14.4) < 0.02, "Cyber.Text height %.4f, Java 14.4" % t.get_height())


def test_string_format_matches_java(check):
    cases = [("%.1f", -0.04, "-0.0"), ("%.0f", -0.4, "-0"), ("%.1f", -0.0, "-0.0"), ("%.2f", -0.001, "-0.00"),
             ("%.1f", 0.25, "0.3"), ("%.1f", 0.35, "0.4"), ("%.0f", 2.5, "3"), ("%.0f", -0.5, "-1"),
             ("%,d", -1234567, "-1,234,567"), ("%05d", -42, "-0042"), ("%,.2f", -9876.545, "-9,876.55"),
             ("%5s|", "ab", "   ab|"), ("%-5s|", "ab", "ab   |"), ("%x", 255, "ff"), ("%x", -1, "ffffffff"),
             ("%.1f", float("nan"), "NaN"), ("%08.2f", -3.14159, "-0003.14")]
    for fmt, v, want in cases:
        try:
            got = _j.format(fmt, v)
        except Exception as e:   # used to raise ZeroDivisionError for negative values that round to zero
            got = "%s: %s" % (type(e).__name__, e)
        check(got == want, "String.format(%r, %r) = %r, Java %r" % (fmt, v, got, want))


def test_math_rounding_matches_java(check):
    check(_j.jround(0.49999999999999994) == 0, "Math.round(0.49999999999999994) == 0")
    check(_j.jround(-2.5) == -2 and _j.jround(2.5) == 3 and _j.jround(-0.5) == 0, "Math.round ties go up")
    check(_j.jround(1e20) == (1 << 63) - 1 and _j.jround(-1e20) == -(1 << 63), "Math.round saturates")
    check(_j.jround(float("nan")) == 0, "Math.round(NaN) == 0")
    check(_j.rint(2.5) == 2.0 and _j.rint(3.5) == 4.0, "Math.rint ties to even")
    check(math.isnan(_j.rint(float("nan"))) and _j.rint(float("inf")) == float("inf"), "Math.rint passes NaN / inf")
    check(math.copysign(1.0, _j.rint(-0.4)) < 0, "Math.rint(-0.4) is -0.0")
    from lindefense.ui.ui import Ui
    check(Ui.fmt(float("nan")) == "NaN" and Ui.fmt(float("inf")) == "Infinity", "Ui.fmt(NaN / inf) does not crash")


def test_canvas_state_does_not_keep_surfaces_alive(check):
    # a BufferedImage canvas (map bitmaps, icon caches) must die with its image
    img = BufferedImage(64, 64)
    g = img.create_graphics()
    g.clip_rect(0, 0, 10, 10)
    g.set_color(Color.RED)
    g.fill_rect(0, 0, 64, 64)
    g.dispose()
    ref = weakref.ref(img._surface.getCanvas())
    del img, g
    gc.collect()
    check(ref() is None, "BufferedImage canvas is freed with the image")
    # an owner-less canvas (the window surface, replaced on every resize) must not be kept by its state either
    surf = skia.Surface.MakeRasterN32Premul(32, 32)
    cv = surf.getCanvas()
    reset_canvas_state(cv)
    jawt.Graphics2D(cv).fill_rect(0, 0, 4, 4)
    reset_canvas_state(cv)
    ref = weakref.ref(cv)
    del surf, cv
    gc.collect()
    check(ref() is None, "window canvas is freed once the app drops its surface")


def test_image_graphics_do_not_inherit_a_stale_clip(check):
    img = BufferedImage(20, 20)
    g1 = img.create_graphics()
    g1.clip_rect(0, 0, 5, 5)
    g1.set_color(Color.RED)
    g1.fill_rect(0, 0, 20, 20)
    g1.dispose()
    g2 = img.create_graphics()
    g2.set_color(Color.BLUE)
    g2.fill_rect(0, 0, 20, 20)
    g2.dispose()
    check((img.get_rgb(15, 15) & 0xFFFFFF) == 0x0000FF, "second Graphics on the image is not clipped by the first")
