"""The campaign story on screen (the text is sim/campaign_story.py):

* StoryView: a scene played over the campaign screen - the prologue on the first visit, a level's dialogue before it
  starts (once), or a codex replay. A comms log: one line at a time, each with the speaker's portrait (tower art, hero
  figure, boss sprite; Palantir's lines are intercepted transmissions, the code font on a red edge). Click / Enter /
  Space: next line; Esc or SKIP: skip the rest.
* StoryCodex: the STORY button's codex - the scenes in four acts, the ones unlocked replayable.
* story_card / story_block: the briefing's story card and the LEVEL COMPLETE / DEFEAT panel's story rows.
* StoryChatter: in-level radio chatter - a small portrait bubble at the playfield's lower left when a scripted wave
  starts. It only reads the game (wave number, state), never changes it; hovering it makes it see-through.
* CampaignEnding: the finale's ending, in place of the classic epilogue for campaign runs (then CAMPAIGN COMPLETE).

Drawn flat (Chamfer panels with one fill and one 1 px border) with cyberpunk accents: the code font for system and
intercepted lines, thin accent bars. Fades and slides respect REDUCED MOTION; Palantir's colour is Cyber.bad() (COLOUR-
BLIND SAFE). Layout is the 1600 x 1000 logical space."""
from lindefense.sim import campaign
from lindefense.sim import campaign_story as story
from lindefense.ui import display_settings
from lindefense.ui.acm import GCompound
from lindefense.ui.cyber import Cyber
from lindefense.ui.jawt import AlphaComposite, Color, Font, KeyEvent, Rectangle2D
from lindefense.ui.ui import Ui

# ====================================================================== shared pieces
BOSS_FRAMING = {   # boss portrait: scale = size / (k * radius), then shifted by (dx, dy) * size
    "BELLARMINE_COLLEGE_PREP": (2.1, 0.0, -0.02),
    "SW_RESOURCE_CONSULTANT": (2.1, 0.0, 0.0),
    "THREE_COM": (2.1, 0.0, 0.0),
    "LOCKHEED_MARTIN": (2.8, 0.06, -0.08),
    "PALANTIR": (1.05, 0.0, 0.0),   # the eye
}


class Clip(GCompound):
    """A compound painted clipped to its w x h box (portraits crop the big boss sprites)."""

    def __init__(self, w, h):
        GCompound.__init__(self)
        self.cw = w
        self.ch = h

    def paint(self, g):
        g2 = g.create()
        try:
            g2.clip(Rectangle2D.Double(self.get_x(), self.get_y(), self.cw, self.ch))
            GCompound.paint(self, g2)
        finally:
            g2.dispose()


class Fader(GCompound):
    """A compound painted at an overall opacity (fade-ins, the see-through chatter bubble)."""

    def __init__(self):
        GCompound.__init__(self)
        self.opacity = 1.0

    def set_opacity(self, a):
        self.opacity = max(0.0, min(1.0, a))

    def paint(self, g):
        if self.opacity <= 0.004:
            return
        if self.opacity >= 0.996:
            GCompound.paint(self, g)
            return
        g2 = g.create()
        try:
            g2.set_composite(AlphaComposite.SrcOver.derive(float(self.opacity)))
            GCompound.paint(self, g2)
        finally:
            g2.dispose()


def flat(x, y, w, h, cut, fill, border, lw=1.0):
    """A flat panel: one fill and one thin border."""
    c = Cyber.Chamfer(x, y, w, h, cut).fill(fill).border(border).line_width(lw)
    if hasattr(c, "scan"):
        c.scan(False)
    return c


def accent(key):
    """A speaker's colour: Palantir's transmissions use the warning colour (orange with COLOUR-BLIND SAFE)."""
    sp = story.speaker(key)
    if sp.kind == "intercept":
        return Cyber.bad()
    return Ui.c(sp.rgb)


def name_of(key):
    return story.speaker(key).name


def role_of(key):
    """The caption next to a speaker's name: the hero's role, the tower's catalog subtitle, the boss's class."""
    sp = story.speaker(key)
    if sp.role:
        return sp.role
    if sp.kind == "tower":
        from lindefense.tower import catalog
        return catalog.get(sp.ref).subtitle
    if sp.kind == "boss":
        return "%s-class boss" % sp.ref.get_boss_class().label
    return ""


def _boss_sprite(t):
    """A boss's sprite from a throwaway Boss, whose id is handed back: the game's enemy ids (saved with the run) must
    not depend on what the story drew."""
    from lindefense.enemy.boss import Boss
    from lindefense.enemy.enemy import Enemy
    from lindefense.jenum import EnumSet
    from lindefense.map.path import Path
    from lindefense.ui.sprites.sprite_factory import SpriteFactory
    saved = Enemy._next_id
    try:
        p = Path("story", -1, -1, 1, -1, 1, 1, -1, 1, -1, -1)
        e = Boss(t, EnumSet.none_of(), p, 0, 0, 1.0, 1.0) if t.is_boss() else Enemy(t, EnumSet.none_of(), p, 0, 0, 1.0, 1.0)
        s = SpriteFactory.create(e)
        s.sync(e, 0)
    finally:
        Enemy._next_id = saved
    return s


def portrait(key, size):
    """The speaker's portrait art cropped to a size x size box with its top-left at (0, 0) (None for narration)."""
    from lindefense.enemy.types import EnemyType
    sp = story.speaker(key)
    if sp.kind == "system":
        return None
    box = Clip(size, size)
    box.add(Ui.rect(0, 0, size, size, Color(8, 13, 28), Color(8, 13, 28)))
    if sp.kind in ("hero", "tower"):
        from lindefense.ui.sprites.towers.tower_icons import TowerIcons
        box.add(TowerIcons.create(sp.ref, 0, size * 0.94), size / 2, size / 2)
        return box
    t = sp.ref if sp.ref is not None else EnemyType.PALANTIR
    k, dx, dy = BOSS_FRAMING.get(t.name, (2.1, 0.0, 0.0))
    sprite = _boss_sprite(t)
    if t is EnemyType.PALANTIR:   # a close-up of the eye: its hull logo keeps a legible size and would poke in
        for o in list(sprite):
            if isinstance(o, GCompound) and any(getattr(l, "get_label", lambda: None)() == "PALANTIR" for l in o):
                o.set_visible(False)
    holder = GCompound()
    holder.add(sprite)
    holder.scale(size / (k * t.radius))
    box.add(holder, size / 2 + dx * size, size / 2 + dy * size)
    if key == "unknown":   # the sender before the reveal: the eye, dimmed, under a redaction bar
        box.add(Ui.rect(0, 0, size, size, Color(4, 6, 14, 170), Color(4, 6, 14, 170)))
        box.add(Ui.rect(0, size * 0.36, size, size * 0.28, Color(2, 3, 8), Color(2, 3, 8)))
        q = Ui.label("REDACTED", 0, 0, Cyber.mono(Font.BOLD, max(7, int(size * 0.13))), Cyber.alpha(Cyber.bad(), 220))
        q.set_location((size - q.get_width()) / 2, size * 0.5 + max(7, int(size * 0.13)) * 0.36)
        box.add(q)
    return box


def portrait_tile(key, x, y, size, border=None):
    """A portrait in a flat frame at (x, y) (a compound placed in absolute coordinates)."""
    g = GCompound()
    art = portrait(key, size - 4)
    g.add(flat(0, 0, size, size, 6, Color(8, 13, 28), border or Cyber.alpha(accent(key), 170), 1.0))
    if art is not None:
        g.add(art, 2, 2)
    g.set_location(x, y)
    return g


def _fonts(key, size):
    """(text font, line height) for a line: the code font for system lines and intercepted transmissions."""
    kind = story.speaker(key).kind
    if kind in ("system", "intercept"):
        f = Cyber.mono(Font.PLAIN if kind == "system" else Font.BOLD, size - 2)
        return f, size + 3
    return Cyber.body(Font.PLAIN, size), size + 5


def _wrap(text, f, w, max_lines=None):
    lines = list(Ui.wrap(text, f, w))
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;:") + "…"
    return lines


def log_for(screen):
    """The StoryLog a screen uses: its own (tests inject one as screen.story_log), else the saved one."""
    log = getattr(screen, "story_log", None)
    return log if log is not None else story.StoryLog.persistent()


# ====================================================================== one line as a row (scenes, panels)
class Row(Fader):
    """One story line: portrait, name and caption, the wrapped text. Built for a width; height() says how tall."""
    PORTRAIT = 84.0

    def __init__(self, line, w, text_size=18, portrait_size=None, name_size=21):
        Fader.__init__(self)
        self.line = line
        key = line.speaker
        sp = story.speaker(key)
        self.labels = []
        ps = Row.PORTRAIT if portrait_size is None else portrait_size
        acc = accent(key)
        if sp.kind == "system":
            f, lh = _fonts(key, text_size)
            prompt = Ui.label(">", 0, lh - 4, Cyber.mono(Font.BOLD, text_size - 2), Cyber.alpha(Cyber.CYAN, 220))
            self.add(prompt)
            tx = prompt.get_width() + 10
            y = lh - 4
            for s in _wrap(line.text, f, w - tx):
                lab = Ui.label(s, tx, y, f, Cyber.alpha(Cyber.CYAN, 235))
                self.add(lab)
                self.labels.append(lab)
                y += lh
            self.h = y - lh + 10
            return
        intercept = sp.kind == "intercept"
        tx = ps + 18
        f, lh = _fonts(key, text_size)
        lines = _wrap(line.text, f, w - tx - (14 if intercept else 0))
        th = name_size + 12 + len(lines) * lh
        self.h = max(ps, th)
        if intercept:   # a transmission: a faint warning-tinted strip behind the text, tagged on the right
            self.add(flat(tx - 8, -4, w - tx + 8, self.h + 8, 6, Cyber.alpha(acc, 18), Cyber.alpha(acc, 110)))
            tag = Ui.label("INTERCEPTED", 0, 0, Cyber.mono(Font.BOLD, max(10, text_size - 7)), Cyber.alpha(acc, 210))
            tag.set_location(w - 12 - tag.get_width(), name_size - 2)
            self.add(tag)
        self.add(portrait_tile(key, 0, 0, ps))
        nx = tx + (6 if intercept else 0)
        name = Ui.label(name_of(key), nx, name_size, Cyber.display(Font.BOLD, name_size), acc)
        self.add(name)
        self.labels.append(name)
        role = role_of(key)
        if role:
            rf = Cyber.body(Font.PLAIN, max(11, text_size - 5))
            r = Ui.label(role, nx + name.get_width() + 12, name_size - 1, rf, Cyber.MUTED)
            self.add(r)
        y = name_size + 10 + lh - 4
        for s in lines:
            lab = Ui.label(s, nx, y, f, Cyber.TEXT if not intercept else Cyber.lerp(acc, Color.WHITE, 0.55))
            self.add(lab)
            self.labels.append(lab)
            y += lh

    def height(self):
        return self.h

    def texts(self):
        return [l.get_label() for l in self.labels]


# ====================================================================== a scene
class StoryView(GCompound):
    """A scene over the whole screen (see the module docstring). on_done(skipped) runs once, when the last line is
    passed, SKIP is pressed or Esc."""
    PW = 1160.0
    PAD = 36.0
    HEAD = 104.0
    FOOT = 86.0
    GAP = 18.0
    MAX_H = 940.0
    FADE = 0.35
    SLIDE = 10.0

    def __init__(self, lines, kicker, title, done_label="CONTINUE", on_done=None):
        from lindefense.ui.campaign_screen import button
        GCompound.__init__(self)
        self.lines = list(lines)
        self.on_done = on_done
        self.done = False
        self.skipped = False
        self.index = 0          # rows shown: 1..len(lines)
        self.age = 0.0          # seconds since the newest row appeared
        self.done_label = done_label
        self.add(Ui.rect(0, 0, Ui.W, Ui.H, Ui.c(0x02040a, 232), Ui.c(0x000000, 0)))
        pw = StoryView.PW
        px = (Ui.W - pw) / 2
        rw = pw - 2 * StoryView.PAD
        self.rows = [Row(l, rw) for l in self.lines]
        body = sum(r.height() for r in self.rows) + StoryView.GAP * max(0, len(self.rows) - 1)
        avail = StoryView.MAX_H - StoryView.HEAD - StoryView.FOOT
        self.body_h = min(body, avail)
        ph = StoryView.HEAD + self.body_h + StoryView.FOOT + 8
        py = (Ui.H - ph) / 2
        self.px, self.py, self.pw, self.ph = px, py, pw, ph
        self.add(flat(px, py, pw, ph, 6, Color(7, 11, 24, 250), Cyber.alpha(Cyber.CYAN, 150), 1.2))
        # header: an accent bar, the kicker and title; the channel on the right
        self.add(Ui.rect(px + StoryView.PAD, py + 30, 3, 50, Cyber.MAGENTA, Cyber.MAGENTA))
        self.add(Ui.label(kicker, px + StoryView.PAD + 16, py + 44, Cyber.body(Font.BOLD, 14),
                          Cyber.alpha(Cyber.MAGENTA, 235)))
        tf = Cyber.display(Font.BOLD, 30)
        from lindefense.ui.catalog_screen import CatalogScreen
        tf = CatalogScreen.fit_font(title, tf, pw - 2 * StoryView.PAD - 360, 16)
        self.add(Ui.label(title, px + StoryView.PAD + 16, py + 78, tf, Cyber.TEXT))
        ch = Ui.label("SECURE CHANNEL  //  LINDEFENSE OPS", 0, 0, Cyber.mono(Font.BOLD, 12),
                      Cyber.alpha(Cyber.CYAN, 200))
        ch.set_location(px + pw - StoryView.PAD - ch.get_width(), py + 44)
        self.add(ch)
        self.progress = Ui.label("", 0, 0, Cyber.mono(Font.PLAIN, 12), Cyber.MUTED)
        self.add(self.progress)
        self.add(Ui.rect(px + StoryView.PAD, py + StoryView.HEAD - 8, rw, 1, Cyber.EDGE, Cyber.EDGE))
        self.body_x = px + StoryView.PAD
        self.body_y = py + StoryView.HEAD + 10
        for r in self.rows:
            r.set_visible(False)
            self.add(r)
        # footer
        fy = py + ph - StoryView.FOOT + 14
        self.add(Ui.rect(px + StoryView.PAD, fy - 4, rw, 1, Cyber.EDGE, Cyber.EDGE))
        self.add(Ui.label("Click, Enter or Space: next   ·   Esc: skip", px + StoryView.PAD, fy + 36,
                          Cyber.body(Font.PLAIN, 14), Cyber.MUTED))
        bx = px + pw - StoryView.PAD
        self.next_button = button(bx - 230, fy + 8, 230, 48, "NEXT", 20, Cyber.YELLOW, self.advance, True)
        self.skip_button = button(bx - 230 - 12 - 140, fy + 8, 140, 48, "SKIP", 18, Cyber.CYAN, self.skip)
        self.buttons = [self.skip_button, self.next_button]
        self.add(self.skip_button)
        self.add(self.next_button)
        self.advance()

    # ---- flow
    def advance(self):
        """Next line (the one fading in snaps into place); after the last one, done."""
        if self.done:
            return
        if self.index > 0 and self.age < StoryView.FADE:
            self.age = StoryView.FADE
            self._apply()
        if self.index >= len(self.rows):
            self._finish(False)
            return
        self.index += 1
        self.age = 0.0
        self._layout()
        self._apply()

    def skip(self):
        if not self.done:
            self._finish(True)

    def _finish(self, skipped):
        self.done = True
        self.skipped = skipped
        if self.on_done is not None:
            self.on_done(skipped)

    def is_done(self):
        return self.done

    def _layout(self):
        """Rows 0..index-1 stacked from the top; the oldest scroll out when they no longer fit."""
        shown = self.rows[:self.index]
        lo = 0
        total = sum(r.height() for r in shown) + StoryView.GAP * (len(shown) - 1)
        while total > self.body_h + 0.5 and lo < len(shown) - 1:
            total -= shown[lo].height() + StoryView.GAP
            lo += 1
        y = self.body_y
        for i, r in enumerate(self.rows):
            vis = lo <= i < self.index
            r.set_visible(vis)
            if vis:
                r.set_location(self.body_x, y)
                r.base_y = y
                y += r.height() + StoryView.GAP
        self.next_button.set_text(self.done_label if self.index >= len(self.rows) else "NEXT")
        self.progress.set_label("%d / %d" % (self.index, len(self.rows)))
        self.progress.set_location(self.px + self.pw - StoryView.PAD - self.progress.get_width(), self.py + 72)

    def _apply(self):
        if self.index <= 0:
            return
        r = self.rows[self.index - 1]
        a = 1.0 if display_settings.reduced_motion() else max(0.0, min(1.0, self.age / StoryView.FADE))
        r.set_opacity(a)
        dy = 0.0 if display_settings.reduced_motion() else (1 - a) * StoryView.SLIDE
        r.set_location(self.body_x, r.base_y + dy)

    # ---- input / frame
    def frame(self, dt):
        if self.age < StoryView.FADE:
            self.age += dt
            self._apply()
        for b in self.buttons:
            b.animate(dt)

    def mouse_pressed(self, lx, ly):
        for b in self.buttons:
            if b.hit(lx, ly):
                b.click()
                return
        self.advance()

    def mouse_moved(self, lx, ly):
        for b in self.buttons:
            b.set_hover(b.hit(lx, ly))

    def key_pressed(self, e):
        k = e.get_key_code()
        if k == KeyEvent.VK_ESCAPE:
            self.skip()
        elif k in (KeyEvent.VK_ENTER, KeyEvent.VK_SPACE, KeyEvent.VK_RIGHT):
            self.advance()

    def texts(self):
        """The text of every row shown so far (tests)."""
        out = []
        for r in self.rows[:self.index]:
            out.extend(r.texts())
        return out

    def bounds(self):
        return (self.px, self.py, self.pw, self.ph)


def scene_header(key):
    """(kicker, title) of a scene."""
    lv = story.scene_level(key)
    if lv is None:
        if key == story.ENDING_KEY:
            return "Act IV  ·  Epilogue", story.ENDING_TITLE.title()
        return "Prologue", "The Last Line of Code"
    n, _t = story.act_of(lv)
    return "Act %s  ·  Level %d of %d" % (n, lv.index, len(campaign.LEVELS)), lv.title


def scene_view(key, progress=None, done_label="CONTINUE", on_done=None, replay=False):
    """A StoryView of a scene: the prologue, a level's pre-level dialogue, or (replay) a codex replay of either."""
    kicker, title = scene_header(key)
    if replay:
        lines = story.replay_lines(key, progress)
    elif key == story.INTRO_KEY:
        lines = list(story.INTRO)
    else:
        lines = list(story.story(story.scene_level(key)).dialogue)
    return StoryView(lines, kicker, title, done_label, on_done)


# ====================================================================== the briefing card and the panel rows
def story_card(into, lv, x, top, w, bottom):
    """The level's story line in its briefing: a flat card with the speaker's portrait, bottom-aligned to `bottom`
    (never above `top`). Returns its (x, y, w, h)."""
    line = story.story(lv).briefing
    acc = accent(line.speaker)
    ps = 56.0
    f = Cyber.body(Font.PLAIN, 15)
    tx = 12 + ps + 16
    lines = _wrap(line.text, f, w - tx - 14, 3)
    h = max(ps + 24, 38 + len(lines) * 20)
    y = max(top, bottom - h)
    into.add(flat(x, y, w, h, 6, Color(9, 15, 32, 235), Cyber.alpha(acc, 120)))
    into.add(Ui.rect(x, y + 10, 2, h - 20, acc, acc))
    into.add(portrait_tile(line.speaker, x + 12, y + (h - ps) / 2, ps))
    into.add(Ui.label(name_of(line.speaker), x + tx, y + 24, Cyber.body(Font.BOLD, 13), acc))
    yy = y + 45
    for s in lines:
        into.add(Ui.label(s, x + tx, yy, f, Cyber.TEXT))
        yy += 20
    return (x, y, w, h)


def story_block(lines, w):
    """Story lines as compact rows in a flat block w wide (LEVEL COMPLETE / DEFEAT): (a compound with its top-left at
    (0, 0), its height); (None, 0) without lines."""
    if not lines:
        return None, 0.0
    rows = [Row(l, w - 32, text_size=15, portrait_size=44, name_size=15) for l in lines]
    h = sum(r.height() for r in rows) + 12 * (len(rows) - 1) + 28
    g = GCompound()
    g.add(flat(0, 0, w, h, 6, Color(8, 13, 28, 235), Cyber.alpha(Cyber.CYAN, 70)))
    g.add(Ui.rect(0, 14, 2, h - 28, Cyber.alpha(Cyber.MAGENTA, 200), Cyber.alpha(Cyber.MAGENTA, 200)))
    yy = 14
    for r in rows:
        r.set_location(16, yy)
        g.add(r)
        yy += r.height() + 12
    g.rows = rows
    return g, h


def outcome_lines(lv, won, out):
    """The story lines of a finished level: won - its outcome, then the new towers' first lines (first clear only);
    lost - Mr. Lindemann's retry nudge."""
    if not won:
        return [story.defeat_line(lv)]
    lines = list(story.story(lv).outcome)
    if out is not None and out.first_clear:
        lines.extend(story.unlock_lines(lv))
    return lines


# ====================================================================== the codex (STORY)
class StoryCodex(GCompound):
    """The scenes in four acts; an unlocked one replays on click (on_play(key)); CLOSE / Esc: on_close()."""
    PX, PW = 50.0, 1500.0
    CARD_H = 112.0
    CARD_GAP = 14.0

    def __init__(self, log, progress, on_play, on_close):
        from lindefense.ui.campaign_screen import button
        from lindefense.ui.catalog_screen import CatalogScreen
        GCompound.__init__(self)
        self.log = log
        self.progress = progress
        self.on_play = on_play
        self.on_close = on_close
        self.cards = []         # (rect, key, frame, border, unlocked)
        self.hover = None
        self.add(Ui.rect(0, 0, Ui.W, Ui.H, Ui.c(0x02040a, 228), Ui.c(0x000000, 0)))
        ph = 118 + 40 + 5 * (StoryCodex.CARD_H + StoryCodex.CARD_GAP) + 22
        px, py, pw = StoryCodex.PX, (Ui.H - ph) / 2, StoryCodex.PW
        self.rect = (px, py, pw, ph)
        self.add(flat(px, py, pw, ph, 6, Color(7, 11, 24, 250), Cyber.alpha(Cyber.CYAN, 150), 1.2))
        self.add(Ui.rect(px + 34, py + 30, 3, 50, Cyber.MAGENTA, Cyber.MAGENTA))
        self.add(Ui.label("The Last Line of Code", px + 50, py + 44, Cyber.body(Font.BOLD, 14),
                          Cyber.alpha(Cyber.MAGENTA, 235)))
        self.add(Ui.label("Story", px + 50, py + 80, Cyber.display(Font.BOLD, 34), Cyber.CYAN))
        keys = story.scene_keys()
        n_open = sum(1 for k in keys if story.scene_unlocked(k, log, progress))
        self.add(Ui.label("Replay the scenes you have unlocked  ·  %d / %d" % (n_open, len(keys)),
                          px + 190, py + 78, Cyber.body(Font.PLAIN, 15), Cyber.MUTED))
        close = button(px + pw - 34 - 150, py + 32, 150, 46, "CLOSE", 18, Cyber.CYAN, self.close)
        self.buttons = [close]
        self.add(close)
        # four columns, one act each
        cols = (["intro"] + [story.level_key(lv) for lv in campaign.LEVELS[0:3]],
                [story.level_key(lv) for lv in campaign.LEVELS[3:8]],
                [story.level_key(lv) for lv in campaign.LEVELS[8:13]],
                [story.level_key(lv) for lv in campaign.LEVELS[13:15]] + ["ending"])
        gx, gap = px + 34, 22.0
        cw = (pw - 68 - 3 * gap) / 4
        top = py + 118
        for c, col_keys in enumerate(cols):
            x = gx + c * (cw + gap)
            n, title = story.ACTS[c]
            act = Ui.label("Act " + n, x, top + 14, Cyber.mono(Font.BOLD, 13), Cyber.alpha(Cyber.MAGENTA, 230))
            self.add(act)
            ax = x + act.get_width() + 12
            tf = CatalogScreen.fit_font(title, Cyber.display(Font.BOLD, 21), x + cw - ax, 13)
            self.add(Ui.label(title, ax, top + 15, tf, Cyber.TEXT))
            self.add(Ui.rect(x, top + 26, cw, 1, Cyber.EDGE, Cyber.EDGE))
            y = top + 40
            for key in col_keys:
                self._card(key, x, y, cw, StoryCodex.CARD_H)
                y += StoryCodex.CARD_H + StoryCodex.CARD_GAP

    def _card(self, key, x, y, w, h):
        from lindefense.ui.catalog_screen import CatalogScreen
        ok = story.scene_unlocked(key, self.log, self.progress)
        seen = self.log.is_seen(key)
        lv = story.scene_level(key)
        acc = Cyber.CYAN if ok else Cyber.DIM
        border = Cyber.alpha(acc, 150 if ok else 90)
        frame = flat(x, y, w, h, 6, Color(9, 14, 30) if ok else Color(7, 10, 20), border, 1.2)
        self.add(frame)
        ps = 72.0
        face = self._face(key)
        if ok:
            self.add(portrait_tile(face, x + 14, y + (h - ps) / 2, ps))
        else:
            self.add(flat(x + 14, y + (h - ps) / 2, ps, ps, 6, Color(6, 9, 18), Cyber.alpha(Cyber.DIM, 90)))
            lk = Ui.label("?", 0, 0, Cyber.mono(Font.BOLD, 26), Cyber.alpha(Cyber.DIM, 160))
            lk.set_location(x + 14 + (ps - lk.get_width()) / 2, y + h / 2 + 9)
            self.add(lk)
        tx = x + 14 + ps + 14
        tw = x + w - 12 - tx
        if lv is None:
            kick = "Prologue" if key == story.INTRO_KEY else "Epilogue"
            title = "The Last Line of Code" if key == story.INTRO_KEY else story.ENDING_TITLE.title()
        else:
            kick = "Level %d" % lv.index
            title = lv.title
        self.add(Ui.label(kick, tx, y + 32, Cyber.body(Font.BOLD, 13), Cyber.alpha(acc, 230)))
        tf = CatalogScreen.fit_font(title, Cyber.display(Font.BOLD, 20), tw, 12)
        self.add(Ui.label(title, tx, y + 58, tf, Cyber.TEXT if ok else Cyber.MUTED))
        if not ok:
            if lv is not None:
                status = "Play level %d to unlock" % lv.index
            else:
                status = "Defeat Palantir to unlock"
            col = Cyber.DIM
        elif not seen and key != story.INTRO_KEY:
            status, col = "Replay", Cyber.YELLOW
        else:
            status, col = "Replay", Cyber.alpha(Cyber.CYAN, 220)
        sf = CatalogScreen.fit_font(status, Cyber.body(Font.BOLD, 13), tw, 10)
        self.add(Ui.label(status, tx, y + h - 22, sf, col))
        self.cards.append(((x, y, w, h), key, frame, border, ok))

    @staticmethod
    def _face(key):
        """The scene's portrait: the first speaker who is not the narrator, Mr. Lindemann or Hanbo."""
        if key == story.ENDING_KEY:
            return "lindemann"
        if key == story.INTRO_KEY:
            return "unknown"
        lines = story.INTRO if key == story.INTRO_KEY else story.story(story.scene_level(key)).dialogue
        for l in lines:
            if l.speaker not in ("system", "lindemann", "hanbo"):
                return l.speaker
        return "lindemann"

    def close(self):
        if self.on_close is not None:
            self.on_close()

    def card_at(self, lx, ly):
        for (x, y, w, h), key, frame, border, ok in self.cards:
            if x <= lx <= x + w and y <= ly <= y + h:
                return key, ok
        return None, False

    def mouse_pressed(self, lx, ly):
        for b in self.buttons:
            if b.hit(lx, ly):
                b.click()
                return
        key, ok = self.card_at(lx, ly)
        if key is not None and ok and self.on_play is not None:
            self.on_play(key)

    def mouse_moved(self, lx, ly):
        for b in self.buttons:
            b.set_hover(b.hit(lx, ly))
        key, ok = self.card_at(lx, ly)
        hover = key if ok else None
        if hover != self.hover:
            self.hover = hover
            for _r, k, frame, border, _ok in self.cards:
                frame.border(Cyber.lerp(border, Color.WHITE, 0.45) if k == hover else border)

    def key_pressed(self, e):
        if e.get_key_code() == KeyEvent.VK_ESCAPE:
            self.close()

    def frame(self, dt):
        for b in self.buttons:
            b.animate(dt)

    def keys(self):
        return [k for _r, k, *_ in self.cards]


# ====================================================================== in-level radio chatter
class StoryChatter(Fader):
    """Radio lines of a campaign level (campaign_story.chatter_schedule): each shows once (StoryLog), in a bubble at
    the playfield's lower left, when its wave starts. Waves already played before this screen opened (a continued
    level) are not replayed; the current wave's unseen lines still play while it runs. Reads the game only."""
    W = 372.0
    PS = 52.0
    FADE = 0.25

    def __init__(self, screen):
        Fader.__init__(self)
        self.screen = screen
        g = screen.get_game()
        self.level = g.get_campaign().level()
        self.schedule = story.chatter_schedule(self.level)
        self.last_wave = g.get_wave()
        # a continued level: the wave being played still brings its unheard lines (looked up at the first update, with
        # the log the screen uses by then); the waves before it are past
        self.catch_up = self.last_wave > 0 and g.get_wave_manager().is_wave_active()
        self.queue = []          # (wave, index, Chatter) waiting
        self.current = None      # (index, Chatter) on screen
        self.time = 0.0          # seconds the current line has been up
        self.duration = 0.0
        self.shown = []          # (wave, index) in the order shown (tests)
        self.fade = 0.0
        self.box = None
        self.rect = None
        self.set_visible(False)

    @staticmethod
    def create(screen):
        """The chatter of a campaign level's screen (None for every other game)."""
        g = screen.get_game()
        if g.get_campaign() is None or screen.get_tutorial() is not None:
            return None
        return StoryChatter(screen)

    def _log(self):
        return log_for(self.screen)

    def _enqueue(self, wave):
        log = self._log()
        for w, i, c in self.schedule:
            if w == wave and not log.is_seen(story.chatter_key(self.level, i)):
                self.queue.append((w, i, c))

    def _can_show(self):
        from lindefense.sim.game import Game
        s = self.screen
        g = s.get_game()
        return (g.get_state() is Game.State.PLAYING and not s.gameplay_keys_blocked() and not s.is_epilogue_open()
                and not g.is_paused())

    def update(self, dt):
        g = self.screen.get_game()
        if self.catch_up:
            self.catch_up = False
            self._enqueue(self.last_wave)
        w = g.get_wave()
        if w > self.last_wave:
            for n in range(self.last_wave + 1, w + 1):
                self._enqueue(n)
            self.last_wave = w
        ok = self._can_show()
        if self.current is None and self.queue and ok:
            self._show(self.queue.pop(0))
        if self.current is None:
            self.set_visible(False)
            return
        if ok:
            self.time += dt
            limit = self.duration if not self.queue else min(self.duration, max(3.0, self.duration * 0.7))
            if self.time >= limit:
                self.current = None
                self.fade = 0.0
                if self.queue and ok:
                    self._show(self.queue.pop(0))
                if self.current is None:
                    self.set_visible(False)
                    return
        self.set_visible(ok)
        if not ok:
            return
        self.fade = min(1.0, self.fade + dt / StoryChatter.FADE)
        a = 1.0 if display_settings.reduced_motion() else self.fade
        mx, my = self.screen.get_mouse_logical()
        x, y, bw, bh = self.rect
        if x <= mx <= x + bw and y <= my <= y + bh:
            a = min(a, 0.18)   # see-through while the pointer is on it
        self.set_opacity(a)
        dy = 0.0 if display_settings.reduced_motion() else (1 - self.fade) * 8
        self.box.set_location(0, dy)

    def _show(self, entry):
        w, i, c = entry
        self.current = entry
        self.time = 0.0
        self.fade = 0.0
        self.duration = max(4.0, min(8.5, 2.5 + 0.05 * len(c.text)))
        self._log().mark(story.chatter_key(self.level, i))
        self.shown.append((w, i))
        self._build(story.Line(c.speaker, c.text))

    def _build(self, line):
        from lindefense.ui.ability_bar import AbilityBar
        if self.box is not None:
            self.remove(self.box)
        key = line.speaker
        acc = accent(key)
        bw, ps = StoryChatter.W, StoryChatter.PS
        tx = 12 + ps + 12
        kind = story.speaker(key).kind
        f, lh = (Cyber.mono(Font.BOLD, 13), 17) if kind == "intercept" else (Cyber.body(Font.PLAIN, 14), 18)
        lines = _wrap(line.text, f, bw - tx - 12, 4)
        bh = max(ps + 24, 40 + len(lines) * lh)
        bottom = AbilityBar.Y - 42
        x, y = Ui.WORLD_X + 10, bottom - bh
        self.rect = (x, y, bw, bh)
        b = GCompound()
        b.add(flat(x, y, bw, bh, 6, Color(7, 11, 24, 236), Cyber.alpha(acc, 170), 1.0))
        b.add(Ui.rect(x, y + 10, 2, bh - 20, acc, acc))
        b.add(portrait_tile(key, x + 12, y + 12, ps))
        tag = "RADIO" if kind != "intercept" else "INTERCEPTED"
        tl = Ui.label(tag, 0, 0, Cyber.mono(Font.BOLD, 10), Cyber.alpha(acc, 200))
        tl.set_location(x + bw - 12 - tl.get_width(), y + 20)
        b.add(tl)
        nf = Cyber.body(Font.BOLD, 14)
        from lindefense.ui.catalog_screen import CatalogScreen
        nm = story.speaker(key).name
        b.add(Ui.label(nm, x + tx, y + 21, CatalogScreen.fit_font(nm, nf, bw - tx - 24 - tl.get_width(), 10), acc))
        self.labels = []
        yy = y + 40
        for s in lines:
            lab = Ui.label(s, x + tx, yy, f, Cyber.TEXT if kind != "intercept" else Cyber.lerp(acc, Color.WHITE, 0.55))
            b.add(lab)
            self.labels.append(lab)
            yy += lh
        self.box = b
        self.add(b)

    def get_current(self):
        """The Chatter on screen, or None."""
        return None if self.current is None else self.current[2]

    def get_rect(self):
        return self.rect

    def texts(self):
        return [l.get_label() for l in getattr(self, "labels", [])]


# ====================================================================== the campaign ending
def _epilogue_base():
    from lindefense.ui.victory_epilogue import VictoryEpilogue
    return VictoryEpilogue


class CampaignEnding(_epilogue_base()):
    """The finale's ending for campaign runs (the classic epilogue's layout and credits, the campaign's story)."""
    TITLE = story.ENDING_TITLE
    STORY = story.ENDING

    def story_style(self, i, para):
        if para == story.CODE_LINE:   # the last line of code
            return Cyber.body(Font.BOLD, 60), Cyber.lerp(Cyber.CYAN, Color.WHITE, 0.3), 40
        return _epilogue_base().story_style(self, i, para)


class EndingReplay(GCompound):
    """The campaign ending replayed from the codex, over the whole screen: a click, Enter, Space or Esc closes it
    (on_done(skipped))."""

    def __init__(self, on_done):
        GCompound.__init__(self)
        self.on_done = on_done
        self.done = False
        self.ending = CampaignEnding(0, 0, Ui.W, Ui.H)
        self.add(self.ending)

    def _close(self):
        if not self.done:
            self.done = True
            if self.on_done is not None:
                self.on_done(not self.ending.is_finished())

    def mouse_pressed(self, lx, ly):
        self._close()

    def mouse_moved(self, lx, ly):
        pass

    def key_pressed(self, e):
        if e.get_key_code() in (KeyEvent.VK_ESCAPE, KeyEvent.VK_ENTER, KeyEvent.VK_SPACE):
            self._close()

    def frame(self, dt):
        self.ending.update(dt)

    def is_done(self):
        return self.done

    def texts(self):
        return self.ending.texts()


def wants_ending(screen):
    """A won finale shows the campaign ending once (StoryLog "ending"); the screen keeps showing it until skipped."""
    return getattr(screen, "_story_ending", False) or not log_for(screen).is_seen(story.ENDING_KEY)


def ending_for(screen):
    """The ending overlay of a won campaign finale (marks it seen)."""
    from lindefense.ui.ui import Ui as _Ui
    screen._story_ending = True
    log_for(screen).mark(story.ENDING_KEY)
    return CampaignEnding(_Ui.WORLD_X, _Ui.WORLD_Y, _Ui.WORLD_W, _Ui.WORLD_H)
