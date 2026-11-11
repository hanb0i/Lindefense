"""The guided tutorial's view (the steps and their rules live in TutorialScript).

* A spotlight: everything is dimmed except the element being taught (a shop card or tab, START WAVE, the pause button,
  HEROES, the UPGRADE button with its preview, the targeting arrows, the next-wave preview, the boss dock, the Hero
  Store's BUY / DEPLOY, a tower or a suggested spot on the map), outlined, with an arrow from the card. The outline
  breathes unless REDUCED MOTION is on.
* A compact instruction card placed next to its target and never over it (nor over the boss dock, the tactical-pause
  banner or the next-wave hover card): the chapter, the goal, NEXT on info cards and SKIP TUTORIAL always.
* One-off contextual tips (TutorialScript.TIPS) in a small card that keeps clear of the instruction card.
* The completion card: what to do next (START CAMPAIGN when the app has a campaign, PLAY A MAP, MAIN MENU; RESUME
  TUTORIAL after a skip). Finishing the tutorial calls app.on_tutorial_complete() once, when the app has one.

It is drawn above the game screen's overlays so it can point into the Hero Store, and hides itself behind every other
overlay (pause menu, HELP, a confirmation, the end screen). Targets are resolved to the live widgets every frame, so
everything follows the side panel's rebuilds, the boss dock and window resizes (the layout is logical 1600x1000)."""
import math

from lindefense.ui import jrt as _j
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.sim.vec import Vec
from lindefense.ui.ui import Ui


def _hit(r, x, y):
    return r is not None and r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]


def _overlap(a, b, pad=0.0):
    return (a is not None and b is not None and a[0] < b[0] + b[2] + pad and b[0] < a[0] + a[2] + pad
            and a[1] < b[1] + b[3] + pad and b[1] < a[1] + a[3] + pad)


def _panel(x, y, w, h, cut, border, line=1.2):
    """A flat panel: the surface colour and one thin border, no scanlines or glow (the minimalist style; works with the
    Chamfer of either style API)."""
    c = Cyber.Chamfer(x, y, w, h, cut).fill(getattr(Cyber, "SURFACE", Color(6, 10, 24, 244))).border(border).line_width(line)
    if hasattr(c, "scan"):
        c.scan(False)
    return c


def _button_rect(b):
    return None if b is None or not b.is_visible() else (b.get_x(), b.get_y(), b.get_w(), b.get_h())


def _union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    return (x0, y0, max(a[0] + a[2], b[0] + b[2]) - x0, max(a[1] + a[3], b[1] + b[3]) - y0)


class Spotlight(GObject):
    """Dims the whole screen except a chamfered hole around the target, outlines the hole and draws the arrow from the
    card to it. Plain fields set every frame; one even-odd path, a stroke and a small arrowhead."""

    def __init__(self):
        GObject.__init__(self)
        self.hole = None
        self.dim = Color(2, 4, 10, 150)
        self.line = Cyber.YELLOW
        self.arrow = None

    def set(self, hole, dim_alpha, line, arrow):
        self.hole = hole
        self.dim = Color(2, 4, 10, max(0, min(255, int(dim_alpha))))
        self.line = line
        self.arrow = arrow

    def get_bounds(self):
        return GRectangle(0, 0, Ui.W, Ui.H)

    def paint(self, g):
        g2 = g.create()
        try:
            Cyber.quality(g2)
            if self.dim.get_alpha() > 0:
                p = Path2D.Double(Path2D.WIND_EVEN_ODD)
                p.append(Rectangle2D.Double(-4, -4, Ui.W + 8, Ui.H + 8), False)
                if self.hole is not None:
                    x, y, w, h = self.hole
                    p.append(Cyber.chamfer(x, y, w, h, 8), False)
                g2.set_color(self.dim)
                g2.fill(p)
            if self.hole is not None:
                x, y, w, h = self.hole
                g2.set_stroke(Cyber.stroke(2.0))
                g2.set_color(self.line)
                g2.draw(Cyber.chamfer(x, y, w, h, 8))
            if self.arrow is not None:
                x0, y0, x1, y1 = self.arrow
                g2.set_stroke(Cyber.stroke(1.6))
                g2.set_color(self.line)
                g2.draw(Line2D.Double(x0, y0, x1, y1))
                a = math.atan2(y1 - y0, x1 - x0)
                head = Path2D.Double()
                head.move_to(x1, y1)
                head.line_to(x1 - 10 * math.cos(a - 0.45), y1 - 10 * math.sin(a - 0.45))
                head.line_to(x1 - 10 * math.cos(a + 0.45), y1 - 10 * math.sin(a + 0.45))
                head.close_path()
                g2.fill(head)
        finally:
            g2.dispose()


class TutorialGuide(GCompound):
    """See the module docstring. screen: the GameScreen (None in pure-script tests: no targets, no app)."""
    CARD_W = 384.0
    TIP_W = 330.0
    TIP_TIME = 9.0
    FINAL_W = 640.0
    GAP = 22.0
    PAD = 10.0             # a card keeps at least this far from its target

    def __init__(self, script, screen=None):
        GCompound.__init__(self)
        self.script = script
        self.screen = screen
        self.time = 0.0
        self.nudge_t = 0.0
        self.spot = Spotlight()
        self.card = GCompound()
        self.tip_box = GCompound()
        self.final = GCompound()
        self.add(self.spot)
        self.add(self.card)
        self.add(self.tip_box)
        self.add(self.final)
        self.card_buttons = []         # (button, dx, dy): placed relative to the card
        self.tip_buttons = []
        self.final_buttons = []
        self.card_key = None
        self.card_size = (TutorialGuide.CARD_W, 160.0)
        self.card_rect = None
        self.card_frame = None
        self.target_rect = None
        self.tip = None
        self.tip_age = 0.0
        self.tip_rect = None
        self.tip_size = (TutorialGuide.TIP_W, 100.0)
        self.tip_offsets = []
        self.final_key = None
        self.final_rect = None
        self.place_cache = {}
        self.reported = False
        self.shown = True
        self.update(0.0)

    # ------------------------------------------------------------------ public
    def get_script(self):
        return self.script

    def get_buttons(self):
        if not self.shown:
            return []
        if self.script.is_finished():
            return list(self.final_buttons)
        return [b for b, _, _ in self.card_buttons] + list(self.tip_buttons)

    def get_card_rect(self):
        return None if (not self.shown or self.script.is_finished()) else self.card_rect

    def get_target_rect(self):
        return None if (not self.shown or self.script.is_finished()) else self.target_rect

    def get_tip_rect(self):
        return None if (not self.shown or self.tip is None) else self.tip_rect

    def get_final_rect(self):
        return self.final_rect if (self.shown and self.script.is_finished()) else None

    def is_shown(self):
        return self.shown

    def covers(self, lx, ly):
        """True if the point is on the card, a tip or the completion card (clicks there never reach the map)."""
        return self.shown and (_hit(self.get_card_rect(), lx, ly) or _hit(self.get_tip_rect(), lx, ly)
                               or _hit(self.get_final_rect(), lx, ly))

    def press(self, lx, ly):
        """A left click: the guide's buttons first; a click elsewhere on its cards is swallowed. True if consumed."""
        if not self.shown:
            return False
        for b in self.get_buttons():
            if b.hit(lx, ly):
                b.click()
                return True
        return self.covers(lx, ly)

    def enter_pressed(self):
        """Enter is NEXT on an info card."""
        if self.shown and not self.script.is_finished() and self.script.current().kind == self.script.Step.INFO:
            self.script.next()
            return True
        return False

    def allow_wave_start(self):
        """START WAVE / SPACE: refused (with a nudge) while the current step is about something else."""
        if self.script.allows_wave_start():
            return True
        self.nudge("FINISH THIS STEP FIRST  -  OR SKIP TUTORIAL")
        return False

    def allow_auto(self):
        if self.script.allows_auto():
            return True
        self.nudge("AUTO WAVES ARE OFF DURING THE TUTORIAL")
        return False

    def nudge(self, text):
        self.nudge_t = 0.9
        if self.screen is not None and getattr(self.screen, "abilities", None) is not None:
            self.screen.abilities.show_hint(text, Cyber.YELLOW, 2.2)

    # ------------------------------------------------------------------ frame
    def blocked(self):
        """Hidden behind every overlay but the Hero Store (and behind that too unless the step works in the store)."""
        s = self.screen
        if s is None:
            return False
        g = s.get_game()
        if g.get_state() is not g.State.PLAYING:
            return True
        if s.help_shown or s.is_menu_open() or s.is_draft_open() or s.get_pending_dismiss() is not None \
                or s.is_epilogue_open():
            return True
        if s.is_hero_store_open() and (self.script.is_finished() or not self.script.current().store):
            return True
        return False

    def update(self, dt):
        self.time += dt
        self.nudge_t = max(0.0, self.nudge_t - dt)
        self.script.update(dt)
        if self.script.is_completed() and not self.reported:
            self.reported = True
            hook = getattr(self.app(), "on_tutorial_complete", None)
            if callable(hook):
                hook()   # e.g. the campaign marks its optional tutorial node done
        self.shown = not self.blocked()
        self.set_visible(self.shown)
        if not self.shown:
            return
        finished = self.script.is_finished()
        for b, _, _ in self.card_buttons:
            b.set_visible(not finished)
        if finished:
            self.spot.set(None, 150, Cyber.YELLOW, None)
            self.card.set_visible(False)
            self.target_rect = None
            self.show_final()
            return
        if self.final_buttons:
            for b in self.final_buttons:
                self.remove(b)
            self.final_buttons = []
        self.final.set_visible(False)
        self.final_key = None
        self.card.set_visible(True)
        self.update_card()
        self.update_tip(dt)

    # ------------------------------------------------------------------ targets
    def resolve(self, target):
        """The logical rectangle (x, y, w, h) of a symbolic target from TutorialScript, or None (a widget that is not
        there, or not where it used to be, only loses its spotlight: the card still shows)."""
        try:
            return self.find(target)
        except (AttributeError, IndexError, ValueError, TypeError):
            return None

    def find(self, target):
        s = self.screen
        if s is None or target is None:
            return None
        kind = target[0]
        hud, side = s.hud, s.side
        if kind == "chips":
            a, b = hud.cash_chip, hud.lives_chip
            return (a.get_x(), a.get_y(), b.get_x() + b.width - a.get_x(), hud.CHIP_H)
        if kind == "start":
            return _button_rect(hud.start_btn)
        if kind == "pause":
            return _button_rect(hud.pause_btn)
        if kind == "heroes":
            return _button_rect(hud.hero_btn)
        if kind == "speed":
            f = hud.speed_frame
            return (f.get_x(), f.get_y(), f.get_w(), f.get_h())
        if kind == "card":
            for c in side.cards:
                if c.cell.type is target[1] and side.card_layer.is_visible():
                    return _button_rect(c.button)
            return self.resolve(("tab", target[1].faction))
        if kind == "tab":
            from lindefense.ui.shop_layout import ShopLayout
            fs = list(ShopLayout.shop_factions())
            if side.is_shop_collapsed():
                return _button_rect(side.collapse_btn)
            return _button_rect(side.tab_buttons[fs.index(target[1])]) if target[1] in fs else None
        if kind == "expand":
            return _button_rect(side.collapse_btn)
        if kind == "upgrade":
            r = _button_rect(side.upgrade_btn)
            if r is None:
                return None
            below = [b for b in side.info_buttons if b.get_y() > r[1] + r[3]]
            bottom = min([b.get_y() for b in below] + [Ui.H - 12]) - 8
            return (r[0], r[1], r[2], max(r[3], bottom - r[1]))
        if kind == "targeting":
            arrows = [b for b in side.info_buttons if b.get_text() in ("<", ">")]
            if len(arrows) < 2:
                return None
            r = None
            for b in arrows:
                r = _union(r, _button_rect(b))
            return (side.x0 - 4, r[1], r[0] + r[2] - side.x0 + 4, r[3])
        if kind == "preview":
            nw = hud.next_wave
            if nw.preview is None or not nw.is_visible():
                return None
            return (nw.left - 10, nw.top + 3, nw.right - nw.left + 20, 48)
        if kind == "dock":
            h = s.dock.get_height()
            return None if h <= 0 else (s.dock.get_x(), s.dock.get_y(), Ui.WORLD_W, h)
        if kind in ("buy", "deploy"):
            want = ("BUY", "NEED") if kind == "buy" else ("DEPLOY",)
            for b in s.overlay_buttons:
                if b.get_text().startswith(want):
                    return _button_rect(b)
            return None
        if kind == "tower":
            t = target[1]
            if t is None or not t.is_alive():
                return None
            p = s.world_to_logical(t.get_position())
            r = t.get_radius() + 12
            return (p[0] - r, p[1] - r, 2 * r, 2 * r)
        if kind == "spot":
            if target[1] is None:
                return None
            p = s.world_to_logical(target[1])
            return (p[0] - 30, p[1] - 30, 60, 60)
        return None

    # ------------------------------------------------------------------ the instruction card
    def update_card(self):
        sc = self.script
        step = sc.current()
        title, text = sc.title(), sc.text()
        key = (sc.index(), title, text, step.kind)
        if key != self.card_key:
            self.card_key = key
            self.build_card(step, title, text)
        target = sc.target()
        tr = self.resolve(target)
        self.target_rect = tr
        w, h = self.card_size
        x, y = self.place(tr, w, h, None if target is None else target[0])
        if self.card_rect is None or (x, y) != (self.card_rect[0], self.card_rect[1]):
            self.card.set_location(x, y)
            for b, dx, dy in self.card_buttons:
                b.set_location(x + dx, y + dy)
        self.card_rect = (x, y, w, h)
        flash = self.nudge_t / 0.9
        self.card_frame.border(Cyber.lerp(Cyber.alpha(Cyber.YELLOW, 170), Cyber.bad(), flash))
        if tr is None:
            self.spot.set(None, 0, Cyber.YELLOW, None)
            return
        live = sc.wave_live() and not sc.game.is_paused()
        dim = 90 if step.store else (120 if live else 165)   # lighter while a wave runs, so the fight stays visible
        pulse = display_settings.calm(0.5 + 0.5 * math.sin(self.time * 4.0), 1.0)
        line = Cyber.alpha(Cyber.YELLOW, int(140 + 115 * pulse))
        hole = (tr[0] - 5, tr[1] - 5, tr[2] + 10, tr[3] + 10)
        self.spot.set(hole, dim, line, self.arrow(self.card_rect, hole))

    def build_card(self, step, title, text):
        sc = self.script
        for b, _, _ in self.card_buttons:
            self.remove(b)
        self.card_buttons = []
        self.card.remove_all()
        W = TutorialGuide.CARD_W
        body = Cyber.body(Font.PLAIN, 14)
        lines = Ui.wrap(text, body, W - 32)
        H = 72 + 19 * len(lines) + 52
        self.card_size = (W, H)
        self.card_frame = _panel(0, 0, W, H, 10, Cyber.alpha(Cyber.YELLOW, 170))
        self.card.add(self.card_frame)
        self.card.add(Ui.rect(16, 0, 44, 2, Cyber.YELLOW, Cyber.YELLOW))
        head = _j.cat('Wave ', step.chapter, ' of ', sc.chapter_count(), '  ·  ', sc.chapter_name())
        self.card.add(Ui.label(head, 16, 24, Cyber.mono(Font.BOLD, 10), Cyber.alpha(Cyber.YELLOW, 220)))
        tag, tag_col = {step.ACTION: ('Your move', Cyber.good()), step.WATCH: ('Watch', Cyber.CYAN)}.get(step.kind, ('Info', Cyber.MUTED))
        tl = Ui.label(tag, 0, 24, Cyber.mono(Font.BOLD, 10), tag_col)
        tl.set_location(W - 16 - tl.get_width(), 24)
        self.card.add(tl)
        self.card.add(Ui.label(title, 16, 52, Cyber.display(Font.BOLD, 20), Cyber.TEXT))
        y = 58.0
        for l in lines:
            y += 19
            self.card.add(Ui.label(l, 16, y, body, Cyber.lerp(Cyber.MUTED, Cyber.TEXT, 0.3)))
        track_w = W - 32
        self.card.add(Ui.rect(16, H - 9, track_w, 2, Color(255, 255, 255, 22), Color(255, 255, 255, 22)))
        self.card.add(Ui.rect(16, H - 9, max(2.0, track_w * sc.progress()), 2, Cyber.alpha(Cyber.YELLOW, 170), Cyber.alpha(Cyber.YELLOW, 170)))
        by = H - 44
        if step.kind == step.INFO:
            nxt = UIButton(0, 0, 104, 28, 'NEXT', Cyber.display(Font.BOLD, 14), _j.Fn(sc.next))
            nxt.set_primary(True)
            self.add_card_button(nxt, 16, by)
        skip = UIButton(0, 0, 132, 28, 'SKIP TUTORIAL', Cyber.mono(Font.BOLD, 10), _j.Fn(sc.skip_all))
        skip.set_flat(True)
        skip.set_accent(Cyber.MUTED)
        self.add_card_button(skip, W - 16 - 132, by)
        if self.card_rect is not None:
            x, y = self.card_rect[0], self.card_rect[1]
            for b, dx, dy in self.card_buttons:
                b.set_location(x + dx, y + dy)
        self.card_rect = None   # placed again this frame

    def add_card_button(self, b, dx, dy):
        self.card_buttons.append((b, dx, dy))
        self.add(b)

    # ------------------------------------------------------------------ placement
    @staticmethod
    def region(kind):
        """Where a card may go: the playfield above the ability bar, or the side panel while the Hero Store covers the
        playfield."""
        if kind in ("buy", "deploy"):
            return (Ui.PANEL_X + 6, Ui.TOP_H + 6, Ui.PANEL_W - 12, Ui.H - Ui.TOP_H - 12)
        return (6, Ui.WORLD_Y + 6, Ui.WORLD_W - 12, AbilityBar.Y - 6 - Ui.WORLD_Y - 6)

    def avoid_rects(self, kind):
        """Things a card or tip must not cover besides its target."""
        s = self.screen
        out = []
        if s is None:
            return out
        dh = s.dock.get_height()
        if dh > 0 and kind != "dock":
            out.append((s.dock.get_x(), s.dock.get_y(), Ui.WORLD_W, dh))
        pb = getattr(s, "pause_banner", None)
        if pb is not None:
            b = pb.get_bounds()
            out.append((b.get_x(), b.get_y(), b.get_width(), b.get_height()))
        if kind == "preview":
            nw = s.hud.next_wave
            out.append((nw.right - nw.CARD_W - 10, Ui.WORLD_Y + 200, nw.CARD_W + 30, Ui.H - Ui.WORLD_Y - 200))
        return out

    def candidates(self, tr, w, h, kind):
        G = TutorialGuide.GAP
        rx, ry, rw, rh = TutorialGuide.region(kind)
        if tr is None:
            return [(rx + rw - w - 8, ry + 6), (rx + 8, ry + 6), (rx + 8, ry + rh - h)]
        x, y, tw, th = tr
        cx, cy = x + tw / 2, y + th / 2
        below = [(cx - w / 2, y + th + G), (x, y + th + G), (x + tw - w, y + th + G)]
        above = [(cx - w / 2, y - G - h), (x, y - G - h), (x + tw - w, y - G - h)]
        left = [(x - G - w, cy - h / 2), (x - G - w, y), (x - G - w, y + th - h)]
        right = [(x + tw + G, cy - h / 2), (x + tw + G, y), (x + tw + G, y + th - h)]
        if kind in ("chips", "start", "pause", "heroes", "speed", "dock"):
            return below + left + right
        if kind in ("card", "tab", "expand", "upgrade", "targeting"):
            wx = rx + rw - w - 12     # in the playfield beside the side panel, arrow across
            return [(wx, cy - h / 2), (wx, y), (wx, y + th - h)] + below + above
        if kind == "preview":
            return [(rx + 8, ry + rh - h), (rx + 8, y - G - h)] + above + left
        if kind in ("buy", "deploy"):
            return [(rx + 2, cy - h / 2), (rx + 2, ry + rh - h), (rx + 2, ry)]
        G2 = 46
        return ([(x + tw + G2, cy - h / 2), (x - G2 - w, cy - h / 2), (cx - w / 2, y + th + G2), (cx - w / 2, y - G2 - h)]
                + [(rx + 8, ry + 6), (rx + rw - w - 8, ry + 6), (rx + 8, ry + rh - h), (rx + rw - w - 8, ry + rh - h)])

    @staticmethod
    def fits(r, tr, avoid, region):
        if r[0] < region[0] - 0.5 or r[1] < region[1] - 0.5 or r[0] + r[2] > region[0] + region[2] + 0.5 \
                or r[1] + r[3] > region[1] + region[3] + 0.5:
            return False
        if _overlap(r, tr, TutorialGuide.PAD):
            return False
        return not any(_overlap(r, a) for a in avoid)

    def clutter_points(self):
        """Logical points a card should rather not hide, with weights: the track (every 24 px, both lanes) and the
        player's towers."""
        s = self.screen
        if s is None:
            return []
        g = s.get_game()
        pts = []
        track = 1.0 if g.get_wave_manager().is_wave_active() else 0.15   # the track matters most while enemies walk it
        for r in g.get_map().get_routes():
            d = 0.0
            while d <= r.get_total_length():
                p = s.world_to_logical(r.position_at(d))
                pts.append((p[0], p[1], track))
                d += 24.0
        for t in g.get_tower_manager().get_player_towers():
            p = s.world_to_logical(t.get_position())
            pts.append((p[0], p[1], 3.0))
        return pts

    @staticmethod
    def clutter(r, pts, pad=18.0):
        x0, y0, x1, y1 = r[0] - pad, r[1] - pad, r[0] + r[2] + pad, r[1] + r[3] + pad
        return sum(wt for (x, y, wt) in pts if x0 <= x <= x1 and y0 <= y <= y1)

    def best_spot(self, w, h, cands, reg, tr, avoid, key):
        """The candidate (clamped to the region, preferred order first) that fits and hides the least track and
        towers, staying near the target; a coarse sweep of the region joins in when the preferred ones are cluttered.
        Cached per key: it only changes when the target, the card or the board does."""
        hit = self.place_cache.get(key)
        if hit is not None:
            return hit

        def clamp(x, y):
            return (max(reg[0], min(reg[0] + reg[2] - w, x)), max(reg[1], min(reg[1] + reg[3] - h, y)))
        pts = self.clutter_points()
        anchor = None if tr is None else (tr[0] + tr[2] / 2, tr[1] + tr[3] / 2)
        best, best_cost = None, None
        sweep = [(float(x), float(y)) for y in range(int(reg[1]), int(reg[1] + reg[3] - h) + 1, 32)
                 for x in range(int(reg[0]), int(reg[0] + reg[2] - w) + 1, 32)]
        for i, c in enumerate(list(cands) + sweep):
            x, y = clamp(*c)
            r = (x, y, w, h)
            if not TutorialGuide.fits(r, tr, avoid, reg):
                continue
            mess = TutorialGuide.clutter(r, pts)
            if i < len(cands) and mess == 0:
                best = (x, y)   # the first preferred spot that hides nothing
                break
            cost = 30.0 * mess + (i if i < len(cands) else 40)
            if anchor is not None:
                cost += 0.25 * math.hypot(x + w / 2 - anchor[0], y + h / 2 - anchor[1])
            if best_cost is None or cost < best_cost:
                best, best_cost = (x, y), cost
        if best is None:
            best = clamp(*cands[0])
        if len(self.place_cache) > 64:
            self.place_cache.clear()
        self.place_cache[key] = best
        return best

    def place(self, tr, w, h, kind):
        """Top-left corner for a w x h card next to target rect tr, inside its region, covering neither the target nor
        anything in avoid_rects, and hiding as little of the track and the player's towers as it can."""
        avoid = self.avoid_rects(kind)
        reg = TutorialGuide.region(kind)
        key = ("card", kind, None if tr is None else tuple(int(round(v)) for v in tr), int(w), int(h),
               tuple(tuple(int(round(v)) for v in a) for a in avoid), self.board_key())
        return self.best_spot(w, h, self.candidates(tr, w, h, kind), reg, tr, avoid, key)

    def board_key(self):
        s = self.screen
        if s is None:
            return None
        g = s.get_game()
        return (len(g.get_tower_manager().get_player_towers()), int(round(s.world_to_logical(Vec(0, 0))[1])),
                g.get_wave_manager().is_wave_active())

    @staticmethod
    def arrow(card, hole):
        """A short arrow from the card's edge facing the hole to just outside it (None when they nearly touch)."""
        cx0, cy0, cw, ch = card
        hx, hy, hw, hh = hole
        if hx > cx0 + cw:                          # target to the right
            y = max(cy0 + 16, min(cy0 + ch - 16, hy + hh / 2))
            a, b = (cx0 + cw + 4, y), (hx - 6, max(hy + 6, min(hy + hh - 6, y)))
        elif hx + hw < cx0:                        # to the left
            y = max(cy0 + 16, min(cy0 + ch - 16, hy + hh / 2))
            a, b = (cx0 - 4, y), (hx + hw + 6, max(hy + 6, min(hy + hh - 6, y)))
        elif hy + hh < cy0:                        # above
            x = max(cx0 + 16, min(cx0 + cw - 16, hx + hw / 2))
            a, b = (x, cy0 - 4), (max(hx + 6, min(hx + hw - 6, x)), hy + hh + 6)
        elif hy > cy0 + ch:                        # below
            x = max(cx0 + 16, min(cx0 + cw - 16, hx + hw / 2))
            a, b = (x, cy0 + ch + 4), (max(hx + 6, min(hx + hw - 6, x)), hy - 6)
        else:
            return None
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 14:
            return None
        return (a[0], a[1], b[0], b[1])

    # ------------------------------------------------------------------ tips
    def update_tip(self, dt):
        if self.tip is not None:
            self.tip_age += dt
            if self.tip_age >= TutorialGuide.TIP_TIME:
                self.close_tip()
        if self.tip is None:
            t = self.script.pop_tip()
            if t is not None:
                self.build_tip(t)
        if self.tip is None:
            self.tip_box.set_visible(False)
            return
        self.tip_box.set_visible(True)
        w, h = self.tip_size
        x, y = self.place_tip(w, h)
        if self.tip_rect is None or (x, y) != (self.tip_rect[0], self.tip_rect[1]):
            self.tip_box.set_location(x, y)
            for b, dx, dy in self.tip_offsets:
                b.set_location(x + dx, y + dy)
        self.tip_rect = (x, y, w, h)

    def place_tip(self, w, h):
        """A tip goes to a corner of the playfield, clear of the card, the target and the usual overlays."""
        avoid = self.avoid_rects("preview") + [r for r in (self.card_rect, self.target_rect) if r is not None]
        reg = TutorialGuide.region(None)
        bottom = reg[1] + reg[3] - h
        right = reg[0] + reg[2] - w
        cands = [(reg[0] + 8, bottom), (right - 8, bottom), (reg[0] + 8, reg[1] + 6), (right - 8, reg[1] + 6),
                 ((Ui.WORLD_W - w) / 2, bottom)]
        key = ("tip", int(w), int(h), tuple(tuple(int(round(v)) for v in a) for a in avoid), self.board_key())
        return self.best_spot(w, h, cands, reg, None, avoid, key)

    def build_tip(self, tip):
        self.tip = tip
        self.tip_age = 0.0
        self.tip_rect = None
        for b in self.tip_buttons:
            self.remove(b)
        self.tip_buttons = []
        self.tip_offsets = []
        self.tip_box.remove_all()
        W = TutorialGuide.TIP_W
        col = {"bad": Cyber.bad(), "warn": Cyber.YELLOW}.get(tip.tone, Cyber.CYAN)
        body = Cyber.body(Font.PLAIN, 13)
        lines = Ui.wrap(tip.text, body, W - 36)
        H = 50 + 17 * len(lines) + 34
        self.tip_size = (W, H)
        self.tip_box.add(_panel(0, 0, W, H, 8, Cyber.alpha(col, 160)))
        self.tip_box.add(Ui.rect(0, 10, 3, H - 20, col, col))
        self.tip_box.add(Ui.label('Tip', 18, 20, Cyber.mono(Font.BOLD, 10), Cyber.alpha(col, 230)))
        self.tip_box.add(Ui.label(tip.title, 18, 42, Cyber.display(Font.BOLD, 16), Cyber.TEXT))
        y = 46.0
        for l in lines:
            y += 17
            self.tip_box.add(Ui.label(l, 18, y, body, Cyber.lerp(Cyber.MUTED, Cyber.TEXT, 0.25)))
        ok = UIButton(0, 0, 84, 24, 'GOT IT', Cyber.mono(Font.BOLD, 10), _j.Fn(self.close_tip))
        ok.set_flat(True)
        ok.set_accent(col)
        self.tip_buttons.append(ok)
        self.tip_offsets.append((ok, W - 14 - 84, H - 32))
        self.add(ok)

    def close_tip(self):
        self.tip = None
        self.tip_rect = None
        for b in self.tip_buttons:
            self.remove(b)
        self.tip_buttons = []
        self.tip_offsets = []
        self.tip_box.remove_all()
        self.tip_box.set_visible(False)

    # ------------------------------------------------------------------ the completion card
    def app(self):
        return None if self.screen is None else self.screen.app

    def has_campaign(self):
        a = self.app()
        return a is not None and callable(getattr(a, "show_campaign", None))

    def go(self, what):
        a = self.app()
        if a is None:
            return
        if what == "campaign":
            a.show_campaign()
        elif what == "maps":
            a.show_map_select()
        else:
            a.show_menu()

    def show_final(self):
        sc = self.script
        key = (sc.is_completed(), sc.is_skipped(), self.has_campaign())
        if key == self.final_key:
            self.final.set_visible(True)
            return
        self.final_key = key
        if self.tip is not None:
            self.close_tip()
        for b in self.final_buttons:
            self.remove(b)
        self.final_buttons = []
        self.final.remove_all()
        g = sc.game
        done = sc.is_completed()
        W = TutorialGuide.FINAL_W
        body = Cyber.body(Font.PLAIN, 15)
        if done:
            micro, title, col = 'Tutorial complete', "You're ready", Cyber.good()
            lead = _j.cat('Seven waves cleared with ', g.get_lives(), ' integrity left. You built and upgraded towers, read '
                          'the next-wave preview, answered Lead and Camo, paused to build and brought down a boss.')
        else:
            micro, title, col = 'Tutorial skipped', 'Ready when you are', Cyber.MUTED
            lead = 'You can pick the tutorial up where you left it, or jump straight in.'
        nxt = ('The CAMPAIGN is the best next step: short levels that unlock new towers as you win. Or pick any map. '
               if self.has_campaign() else 'Pick a map and play a full run. ') + \
            'In game, H lists every control; the CATALOG on the main menu explains every enemy, tower and hero.'
        lead_lines = Ui.wrap(lead, body, W - 64)
        next_lines = Ui.wrap(nxt, Cyber.body(Font.PLAIN, 14), W - 64)
        H = 112 + 21 * len(lead_lines) + 40 + 19 * len(next_lines) + 92
        x0 = Ui.WORLD_X + (Ui.WORLD_W - W) / 2
        y0 = Ui.WORLD_Y + (Ui.WORLD_H - H) / 2
        self.final_rect = (x0, y0, W, H)
        self.final.add(_panel(x0, y0, W, H, 14, Cyber.alpha(col, 190), 1.4))
        self.final.add(Ui.rect(x0 + 32, y0, 64, 2, col, col))
        self.final.add(Ui.label(micro, x0 + 32, y0 + 36, Cyber.mono(Font.BOLD, 11), col))
        self.final.add(Ui.label(title, x0 + 32, y0 + 82, Cyber.display(Font.BOLD, 34), Cyber.TEXT))
        y = y0 + 96
        for l in lead_lines:
            y += 21
            self.final.add(Ui.label(l, x0 + 32, y, body, Cyber.lerp(Cyber.MUTED, Cyber.TEXT, 0.4)))
        y += 34
        self.final.add(Ui.label("What's next", x0 + 32, y, Cyber.mono(Font.BOLD, 11), Cyber.alpha(Cyber.YELLOW, 220)))
        for l in next_lines:
            y += 19
            self.final.add(Ui.label(l, x0 + 32, y, Cyber.body(Font.PLAIN, 14), Cyber.MUTED))
        specs = []
        if sc.is_skipped():
            specs.append(('RESUME TUTORIAL', Cyber.YELLOW, sc.resume))
        if self.has_campaign():
            specs.append(('START CAMPAIGN', Cyber.CYAN, lambda: self.go("campaign")))
        specs.append(('PLAY A MAP', Cyber.CYAN, lambda: self.go("maps")))
        specs.append(('MAIN MENU', Cyber.MAGENTA, lambda: self.go("menu")))
        gap = 10.0
        bw = (W - 64 - gap * (len(specs) - 1)) / len(specs)
        by = y0 + H - 32 - 44
        for i, (label, accent, fn) in enumerate(specs):
            b = UIButton(x0 + 32 + i * (bw + gap), by, bw, 44, label, Cyber.display(Font.BOLD, 16 if len(specs) < 4 else 14), _j.Fn(fn))
            b.set_accent(accent)
            b.set_primary(i == 0)
            self.final_buttons.append(b)
            self.add(b)
        self.final.set_visible(True)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.ability_bar import AbilityBar  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.ui_button import UIButton  # noqa: E402

TutorialGuide.serial_version_uid = 1
