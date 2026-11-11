"""End-of-run report: the SUMMARY / REPORT tabs of the victory / defeat panel, the records line under the summary
stats, and the REPORT page (leaks, game time, bosses, map record, the top-5 towers by damage incl. sold ones, and
the achievements this run unlocked). Built from a RunSummary plus the RunReport the records returned (None when the
screen has no records attached, e.g. in tests)."""
from lindefense.ui.jawt import Color, Font
import math

from lindefense.ui.acm import GPolygon
from lindefense.sim import records as rec
from lindefense.sim.difficulty import Difficulty
from lindefense.ui.cyber import Cyber
from lindefense.ui.ui import Ui
from lindefense.ui.ui_button import UIButton

TAB_W = 112.0
TAB_H = 28.0


def fmt_time(seconds):
    """1:02:03 / 12:34 (whole seconds)."""
    s = int(max(0.0, seconds))
    h, m, sec = s // 3600, (s // 60) % 60, s % 60
    return "%d:%02d:%02d" % (h, m, sec) if h else "%d:%02d" % (m, sec)


def diff_text(did):
    d = Difficulty.parse(did) if isinstance(did, str) else did
    if d is None:
        return str(did)
    return d.ascii_label if "ᴺ" in d.label else d.label


def tab_buttons(px, py, pw, page, on_page):
    """SUMMARY / REPORT segmented tabs in the panel's top-right corner; returns the two buttons (caller adds them)."""
    out = []
    x = px + pw - 30 - 2 * TAB_W - 6
    for i, label in enumerate(("SUMMARY", "REPORT")):
        b = UIButton(x + i * (TAB_W + 6), py + 22, TAB_W, TAB_H, label, Cyber.display(Font.BOLD, 14),
                     lambda i=i: on_page(i))
        b.set_flat(True)
        b.set_accent(Cyber.CYAN)
        b.set_selected(i == page)
        b.animate(1.0)   # settle the flat / selected look now: the panel is rebuilt on every switch (no one-frame flash)
        out.append(b)
    return out


def records_line(summary, report):
    """(text, colour) for the line under the summary stats: new bests and unlocked achievements, the standing best,
    or why the run is not recorded."""
    why = report.excluded if report is not None else summary.excluded_reason()
    ach = len(report.unlocked) if report is not None else 0
    tail = ("   ·   +%d ACHIEVEMENT%s" % (ach, "" if ach == 1 else "S")) if ach else ""
    if why == "tutorial":
        return "TRAINING RUN  ·  NOT RECORDED", Cyber.MUTED
    if why == "admin":
        return "ADMIN MODE  ·  RECORDS AND ACHIEVEMENTS OFF", Cyber.MUTED
    if why == "reverse":
        return "TRAINING MATCH  ·  MAP RECORDS UNCHANGED" + tail, (Cyber.YELLOW if ach else Cyber.MUTED)
    if report is None:
        return "", Cyber.MUTED
    if report.new_bests:
        return "  +  ".join(lbl for _, lbl in report.new_bests) + tail, Cyber.YELLOW
    a = report.after
    best = "BEST ON THIS MAP  ·  " + diff_text(summary.difficulty) + "  W" + str(int(a.get("best_wave", 0)))
    if a.get("fastest") is not None:
        best += "  ·  FASTEST " + fmt_time(a["fastest"])
    return best + tail, (Cyber.YELLOW if ach else Cyber.MUTED)


def star(cx, cy, r, col, line=None):
    """A filled five-point star centred on (cx, cy) (the bundled fonts have no star glyph)."""
    p = GPolygon()
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        p.add_vertex(cx + math.cos(a) * rr, cy + math.sin(a) * rr)
    p.set_filled(True)
    p.set_fill_color(col)
    p.set_color(col if line is None else line)
    return p


def add_records_line(into, summary, report, cx, y):
    """The records line centred on cx at baseline y, led by a solid NEW BEST! tag when the run broke a record."""
    text, col = records_line(summary, report)
    if not text:
        return
    f = Cyber.body(Font.BOLD, 14)
    lbl = Ui.label(text, 0, y, f, col)
    best = report is not None and report.new_bests
    tag = Ui.label("NEW BEST", 0, y, Cyber.body(Font.BOLD, 12), Color(0x1a1405)) if best else None
    tw = (tag.get_width() + 16) if tag is not None else 0
    x = cx - (lbl.get_width() + (tw + 10 if tag is not None else 0)) / 2
    if tag is not None:
        into.add(Cyber.Chamfer(x, y - 15, tw, 21, 3).fill(Cyber.YELLOW).border(None))
        tag.set_location(x + 8, y)
        into.add(tag)
        x += tw + 10
    lbl.set_location(x, y)
    into.add(lbl)


def _card(into, x, y, w, h, label, value, accent, tag=None):
    into.add(Cyber.Chamfer(x, y, w, h, 4).fill(Cyber.SURFACE_2))
    into.add(Ui.label(label[0:1].upper() + label[1:], x + 12, y + 19, Cyber.body(Font.PLAIN, 12), Cyber.MUTED))
    into.add(Ui.label(value, x + 12, y + h - 11, Cyber.mono(Font.BOLD, 18), Cyber.TEXT))
    if tag:
        f = Cyber.body(Font.BOLD, 11)
        t = Ui.label(tag, 0, 0, f, Color(0x1a1405))
        tw = t.get_width() + 12
        into.add(Ui.rect(x + w - tw - 6, y + 6, tw, 15, Cyber.YELLOW, Cyber.YELLOW))
        t.set_location(x + w - tw, y + 17)
        into.add(t)


def _short(text, f, max_w):
    """text, cut with an ellipsis to fit max_w."""
    probe = Ui.label(text, 0, 0, f, Cyber.TEXT)
    if probe.get_width() <= max_w:
        return text
    while len(text) > 1:
        text = text[:-1]
        probe.set_label(text.rstrip() + "…")
        if probe.get_width() <= max_w:
            return text.rstrip() + "…"
    return text


def build_page(into, game, summary, report, px, py, pw, ph, col, title):
    """The REPORT page inside the end panel (px, py, pw, ph); content stops 96 px above the panel bottom (buttons)."""
    cx = px + pw / 2.0
    x0 = px + 36
    w = pw - 72
    mode = summary.reverse_level if summary.reverse else summary.difficulty
    head = Ui.label(title + "   ·   " + summary.map_name.upper() + "   ·   " + diff_text(mode),
                    0, py + 76, Cyber.display(Font.BOLD, 18), Cyber.lerp(col, Color.WHITE, 0.25))
    head.set_location(cx - head.get_width() / 2, py + 76)
    into.add(head)
    # ---- stat strip
    y = py + 92
    cw = (w - 3 * 10) / 4.0
    best = report.after if report is not None else {}
    tag = "NEW BEST" if (report is not None and report.new_bests) else None
    if summary.reverse:
        rec_label, rec_value, tag = "defender ai", game.get_reverse().get_profile().display_name.upper(), None
    elif report is None or not report.counted:
        rec_label, rec_value = "map record", "NOT RECORDED" if report is not None else "-"
    else:
        rec_label, rec_value = "map best  " + diff_text(summary.difficulty), "W" + str(int(best.get("best_wave", 0)))
        if best.get("fastest") is not None:
            rec_value += "  " + fmt_time(best["fastest"])
    lost = max(0, summary.max_lives - summary.lives)
    cells = [("leaks", "%d  (-%d HP)" % (summary.leaks, lost) if (lost > 0 and not summary.reverse) else str(summary.leaks), Cyber.RED),
             ("game time", fmt_time(summary.time), Cyber.CYAN),
             ("bosses down", str(len(summary.bosses)), Cyber.MAGENTA),
             (rec_label, rec_value, Cyber.YELLOW)]
    for i, (lbl, val, acc) in enumerate(cells):
        _card(into, x0 + i * (cw + 10), y, cw, 50, lbl, val, acc, tag if i == 3 else None)
    # ---- MVP table
    y = py + 168
    built = len(summary.towers)
    sold = sum(1 for t in summary.towers if t.sold)
    into.add(Ui.label(("Defender AI towers" if summary.reverse else "Top towers") + " by damage", x0, y,
                      Cyber.body(Font.BOLD, 14), Cyber.MUTED))
    note = Ui.label("%d built  ·  %d sold" % (built, sold), 0, y, Cyber.body(Font.PLAIN, 13), Cyber.MUTED)
    note.set_location(x0 + w - note.get_width(), y)
    into.add(note)
    cols = [("#", 0), ("Tower", 28), ("Tier", 300), ("Damage", 360), ("Kills", 500), ("Cost", 590)]
    hy = y + 20
    for name, dx in cols:
        into.add(Ui.label(name, x0 + dx, hy, Cyber.body(Font.PLAIN, 11), Cyber.DIM))
    into.add(Ui.rect(x0, hy + 6, w, 1, Cyber.EDGE, Cyber.EDGE))
    rows = summary.mvp(rec.MVP_ROWS)
    top = rows[0].damage if rows and rows[0].damage > 0 else 1.0
    ry = hy + 12
    rh = 26.0
    if not rows:
        into.add(Ui.label("No towers were deployed this run.", x0 + 28, ry + 18, Cyber.body(Font.PLAIN, 14), Cyber.MUTED))
    for i, t in enumerate(rows):
        yy = ry + i * rh
        if i % 2 == 0:
            into.add(Ui.rect(x0, yy, w, rh - 2, Color(255, 255, 255, 7), Color(255, 255, 255, 0)))
        base = yy + 18
        rank_col = Cyber.YELLOW if i == 0 else Cyber.MUTED
        into.add(Ui.label(str(i + 1), x0 + 8, base, Cyber.mono(Font.BOLD, 13), rank_col))
        nf = Cyber.body(Font.BOLD, 15)
        name = Ui.label(_short(t.name, nf, 150), x0 + 28, base, nf, Cyber.TEXT)
        into.add(name)
        sub = t.tier_label + ("   SOLD" if t.sold else "")
        sf = Cyber.body(Font.PLAIN, 12)
        into.add(Ui.label(_short(sub, sf, 262 - name.get_width() - 10), x0 + 38 + name.get_width(), base, sf,
                          Cyber.alpha(Cyber.RED, 220) if t.sold else Cyber.MUTED))
        tier = "HERO" if t.hero and t.max_tier == 0 else "T%d/%d" % (t.tier, t.max_tier)
        into.add(Ui.label(tier, x0 + 300, base, Cyber.mono(Font.BOLD, 12), Cyber.MUTED))
        bar_w = 70.0
        into.add(Ui.rect(x0 + 360, yy + 10, bar_w, 4, Color(255, 255, 255, 22), Color(255, 255, 255, 22)))
        into.add(Ui.rect(x0 + 360, yy + 10, max(2.0, bar_w * t.damage / top), 4, Cyber.alpha(col, 230), Cyber.alpha(col, 230)))
        into.add(Ui.label(Cyber.abbrev(t.damage), x0 + 436, base, Cyber.mono(Font.BOLD, 13), Cyber.TEXT))
        into.add(Ui.label(Cyber.commas(t.kills), x0 + 500, base, Cyber.mono(Font.BOLD, 13), Cyber.TEXT))
        into.add(Ui.label(Ui.money(t.cost), x0 + 590, base, Cyber.mono(Font.BOLD, 13), Cyber.YELLOW))
    # ---- achievements
    y = ry + rec.MVP_ROWS * rh + 22
    unlocked = report.unlocked if report is not None else []
    into.add(Ui.label("Achievements unlocked", x0, y, Cyber.body(Font.BOLD, 14), Cyber.MUTED))
    if not unlocked:
        why = report.excluded if report is not None else None
        msg = ("Achievements are off for this run." if why in ("tutorial", "admin")
               else "None this run. See RECORDS on the main menu for what is left.")
        into.add(Ui.label(msg, x0 + 190, y, Cyber.body(Font.PLAIN, 13), Cyber.MUTED))
        return
    f = Cyber.mono(Font.BOLD, 11)
    x = x0
    cy = y + 10
    limit = y + 10 + 2 * 28
    for i, a in enumerate(unlocked):
        lbl = Ui.label(a.title.upper(), 0, 0, f, Cyber.TEXT)
        cwid = lbl.get_width() + 34
        if x + cwid > x0 + w and x > x0:
            x = x0
            cy += 28
        if cy + 22 > limit or (cy + 28 >= limit and i < len(unlocked) - 1 and x + cwid + 70 > x0 + w):
            more = Ui.label("+%d MORE" % (len(unlocked) - i), x + 4, cy + 15, f, Cyber.YELLOW)
            into.add(more)
            break
        into.add(Cyber.Chamfer(x, cy, cwid, 22, 3).fill(Cyber.alpha(Cyber.YELLOW, 26)).border(None))
        into.add(star(x + 13, cy + 11, 6.5, Cyber.YELLOW))
        lbl.set_location(x + 24, cy + 15)
        into.add(lbl)
        x += cwid + 8
