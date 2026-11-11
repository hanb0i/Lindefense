"""The bottom strip's next-wave preview (right-aligned block) and its hover card. Pure view: it is handed a WavePreview
and its threats (lindefense.ui.intel) and rebuilds its labels only when they change."""
import math

from lindefense.ui import jrt as _j
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.enemy.types import Modifier
from lindefense.ui import display_settings
from lindefense.ui.cyber import Cyber
from lindefense.ui.intel import MODIFIER_ORDER, MODIFIER_TAGS, Threat

MODIFIER_SHORT_TAGS = {Modifier.CAMO: "CAMO", Modifier.FORTIFIED: "FORT", Modifier.REGROW: "REGROW", Modifier.INJECTION: "INJECT"}


def modifier_color(m):
    """Same palette as the attacker's modifier buttons (AttackPanel)."""
    if m is Modifier.CAMO:
        return Cyber.lerp(Cyber.CYAN, Color.WHITE, 0.2)
    if m is Modifier.REGROW:
        return Cyber.GREEN
    if m is Modifier.INJECTION:
        return Cyber.MAGENTA
    return Cyber.YELLOW


class EnemyIconImage(GObject):
    """A static enemy sprite pre-rendered into a bitmap (cached per type, size and pixel scale), centred on its location.
Building the sprite needs a throwaway Enemy; the global enemy id counter is restored so the game never sees it."""
    CACHE = {}

    def __init__(self, type_, size):
        GObject.__init__(self)
        self.type = type_
        self.size = float(size)
        self.img = None
        self.img_scale = 0

    @staticmethod
    def bitmap(type_, size, ss):
        key = (type_, size, ss)
        b = EnemyIconImage.CACHE.get(key)
        if b is None:
            from lindefense.enemy.enemy import Enemy
            from lindefense.ui.catalog_screen import CatalogScreen
            px = _j.to_int(float(math.ceil(size * ss)))
            b = BufferedImage(px, px, BufferedImage.TYPE_INT_ARGB)
            saved = Enemy._next_id
            g = b.create_graphics()
            try:
                art = CatalogScreen.build_enemy_icon(type_, size)
                Cyber.quality(g)
                g.translate(px / 2.0, px / 2.0)
                g.scale(ss, ss)
                art.paint(g)
            finally:
                g.dispose()
                Enemy._next_id = saved
            EnemyIconImage.CACHE[key] = b
        return b

    def get_bounds(self):
        return GRectangle(self.get_x() - self.size / 2, self.get_y() - self.size / 2, self.size, self.size)

    def paint(self, g):
        from lindefense.ui.graphics_settings import GraphicsSettings
        g2 = g.create()
        try:
            q = GraphicsSettings.get().quality()
            ss = q.icon_scale(math.sqrt(abs(g2.get_transform().get_determinant())))
            if self.img is None or ss != self.img_scale:
                self.img = EnemyIconImage.bitmap(self.type, self.size, ss)
                self.img_scale = ss
            g2.set_rendering_hint(RenderingHints.KEY_INTERPOLATION, q.interpolation())
            at = AffineTransform()
            at.translate(self.get_x() - self.size / 2, self.get_y() - self.size / 2)
            at.scale(self.size / self.img.get_width(), self.size / self.img.get_height())
            g2.draw_image(self.img, at, None)
        finally:
            g2.dispose()


class NextWavePanel(GCompound):
    """Right-hand block of the bottom status strip: what the next wave brings (enemy icons with counts, modifier tags,
boss chip, camo / Lead warnings, FORECAST marker) and, while hovered, a card above the strip with the full breakdown,
the warnings spelled out and the wave note."""
    ICON = 24.0
    LEVELS = ((2, 4), (1, 4), (0, 4), (0, 3), (0, 2), (0, 1))   # (modifier tags: 2 full / 1 short / 0 none, enemy groups)
    CARD_W = 440.0

    def __init__(self, right, top, card_bottom):
        GCompound.__init__(self)
        self.right = float(right)
        self.top = float(top)
        self.card_bottom = float(card_bottom)
        self.block = GCompound()
        self.card = GCompound()
        self.add(self.block)
        self.add(self.card)
        self.card.set_visible(False)
        self.left = self.right
        self.block_key = None
        self.card_key = None
        self.preview = None
        self.threats = []
        self.label = ''
        self.warn_frames = []
        self.time = 0.0

    # ------------------------------------------------------------------ state
    def show(self, preview, threats, label, min_left=0.0):
        """Shows a preview (None hides the block); label is the small heading ("Next: wave 41"). The block is kept
right of min_left: when the full block would cross it, modifier tags get shorter, then are left to the coloured marks
under the counts, and fewer enemy groups are listed (the hover card always has everything). Returns the block's left x."""
        self.preview = preview
        self.threats = threats
        self.label = label
        key = (None if preview is None else preview.key(), label, tuple(t.chip for t in threats), _j.to_int(min_left))
        if key != self.block_key:
            self.block_key = key
            for level in range(len(NextWavePanel.LEVELS)):
                self.build_block(level)
                if self.left >= min_left:
                    break
        return self.left

    def animate(self, dt, mx, my):
        self.time += dt
        a = display_settings.calm(0.5 + 0.5 * math.sin(self.time * 5), 1.0)   # reduced motion: steady warning frames
        for f, col in self.warn_frames:
            f.border(Cyber.lerp(Cyber.alpha(col, 60), Cyber.alpha(col, 220), a))
        hover = self.preview is not None and self.is_over(mx, my)
        if hover:
            key = (self.block_key, )
            if key != self.card_key:
                self.card_key = key
                self.build_card()
        self.card.set_visible(hover)

    def is_over(self, mx, my):
        return (self.left - 10) <= mx <= self.right + 18 and self.top <= my <= self.top + 52

    def is_card_visible(self):
        return self.card.is_visible()

    # ------------------------------------------------------------------ strip block
    def build_block(self, level=0):
        tags, max_types = NextWavePanel.LEVELS[level]
        self.block.remove_all()
        self.warn_frames = []
        pv = self.preview
        if pv is None:
            self.left = self.right
            return
        by = self.top
        micro_f = Cyber.body(Font.PLAIN, 12)
        tag_f = Cyber.body(Font.BOLD, 11)
        # row 1: warnings, modifier tags, "Next: wave n", Forecast / News
        row1 = []
        for th in self.threats:
            if th.kind is Threat.BOSS:
                continue
            row1.append(('warn', th))
        for m in MODIFIER_ORDER:
            c = pv.modifier_count(m)
            if (c > 0) and (tags > 0):
                row1.append(('tag', m, c))
        x = self.right
        heads = []   # left to right, ending at the right edge with the "Next: wave n" heading
        if pv.news is not None:
            heads.append(Ui.label(_j.cat('News: ', pv.news.title), 0, by + 18, micro_f, Cyber.MAGENTA))
        if pv.forecast:
            heads.append(Ui.label('Forecast', 0, by + 18, micro_f, Cyber.YELLOW))
        heads.append(Ui.label(self.label, 0, by + 18, micro_f, Cyber.MUTED))
        widths = sum(l.get_width() for l in heads) + 10 * (len(heads) - 1)
        hx = x - widths
        for l in heads:
            l.set_location(hx, by + 18)
            self.block.add(l)
            hx += l.get_width() + 10
        x -= widths + 16
        left1 = x
        items = []
        for it in row1:
            if it[0] == 'tag':
                m, c = it[1], it[2]
                l = Ui.label(_j.cat((MODIFIER_TAGS[m] if (tags > 1) else MODIFIER_SHORT_TAGS[m]), ' ', c), 0, by + 18, tag_f, modifier_color(m))
                items.append((l, None, l.get_width(), 10))
            else:
                th = it[1]
                col = Cyber.YELLOW
                l = Ui.label(_j.cat('! ', th.chip), 0, by + 17, tag_f, col)
                w = l.get_width() + 14
                f = Cyber.Chamfer(0, by + 5, w, 17, 3).fill(Cyber.alpha(col, 26)).border(Cyber.alpha(col, 220))
                items.append((l, f, w, 8))
                self.warn_frames.append((f, col))
        for l, f, w, gap in reversed(items):
            x -= w
            if f is not None:
                f.set_location(x, by + 5)
                self.block.add(f)
                l.set_location(x + 7, by + 17)
            else:
                l.set_location(x, by + 18)
            self.block.add(l)
            left1 = x
            x -= gap + 6
        # row 2: boss chip, the biggest enemy groups (icon, count, modifier marks), total
        total = Ui.label(_j.cat(pv.total, (' unit' if pv.total == 1 else ' units')), 0, by + 40,
                         Cyber.display(Font.BOLD, 17), Cyber.TEXT)
        x = self.right - total.get_width()
        total.set_location(x, by + 40)
        self.block.add(total)
        x -= 18
        normal = [gr for gr in pv.groups if not gr.type.is_boss()]
        shown = normal[:max_types]
        hidden = len(normal) - len(shown)
        count_f = Cyber.mono(Font.BOLD, 14)
        if hidden > 0:
            more = Ui.label(_j.cat('+', hidden), 0, by + 40, count_f, Cyber.MUTED)
            x -= more.get_width()
            more.set_location(x, by + 40)
            self.block.add(more)
            x -= 10
        for gr in reversed(shown):
            cl = Ui.label(_j.cat('×', gr.count), 0, by + 40, count_f, Cyber.TEXT)
            mods = gr.modifiers()
            w = self.ICON + 3 + max(cl.get_width(), len(mods) * 6)
            x -= w
            icon = EnemyIconImage(gr.type, self.ICON)
            icon.set_location(x + self.ICON / 2, by + 34)
            self.block.add(icon)
            cl.set_location(x + self.ICON + 3, by + 40)
            self.block.add(cl)
            for i, m in enumerate(mods):
                c = modifier_color(m)
                self.block.add(Ui.rect(x + self.ICON + 4 + i * 6, by + 44, 4, 3, c, c))
            x -= 12
        boss = next((th for th in self.threats if th.kind is Threat.BOSS), None)
        if boss is not None:
            bl = Ui.label(boss.chip, 0, by + 39, Cyber.mono(Font.BOLD, 11), Cyber.RED)
            bw = bl.get_width() + 16
            x -= bw - 6
            self.block.add(Cyber.Chamfer(x, by + 25, bw, 20, 3).fill(Cyber.alpha(Cyber.RED, 40)).border(Cyber.alpha(Cyber.RED, 200)))
            bl.set_location(x + 8, by + 39)
            self.block.add(bl)
        self.left = min(left1, x)

    # ------------------------------------------------------------------ hover card
    def build_card(self):
        self.card.remove_all()
        pv = self.preview
        if pv is None:
            return
        W = self.CARD_W
        pad = 16.0
        tw = W - 2 * pad
        body = Cyber.body(Font.PLAIN, 12)
        content = GCompound()
        y = 24.0
        boss_wave = bool(pv.bosses)
        accent = Cyber.RED if boss_wave else Cyber.CYAN
        content.add(Ui.label(_j.cat(self.label.split(':')[0], ' wave'), pad, y - 8, Cyber.body(Font.PLAIN, 12), Cyber.MUTED))
        y += 14
        content.add(Ui.label(_j.cat('WAVE ', pv.number), pad, y, Cyber.display(Font.BOLD, 20), Cyber.TEXT))
        tot = Ui.label(_j.cat(pv.total, ' units', ('  ·  forecast' if pv.forecast else '')), 0, y - 2,
                       Cyber.body(Font.PLAIN, 13), (Cyber.YELLOW if pv.forecast else Cyber.MUTED))
        tot.set_location(W - pad - tot.get_width(), y - 2)
        content.add(tot)
        y += 10
        ln = GLine(pad, y + 0.5, W - pad, y + 0.5)
        ln.set_color(Cyber.alpha(accent, 110) if boss_wave else Cyber.EDGE)
        content.add(ln)
        y += 4
        for gr in pv.groups:
            cy = y + 15
            if gr.type.is_boss():
                sk = Cyber.Icon(Cyber.Kind.SKULL, 20, Cyber.RED)
                sk.set_location(pad + 2, cy - 10)
                content.add(sk)
            else:
                icon = EnemyIconImage(gr.type, 26)
                icon.set_location(pad + 12, cy)
                content.add(icon)
            content.add(Ui.label(_j.cat('×', gr.count), pad + 32, cy + 5, Cyber.mono(Font.BOLD, 14),
                                 (Cyber.RED if gr.type.is_boss() else Cyber.TEXT)))
            name = gr.type.display_name + ((' (' + gr.type.get_boss_class().label + ')') if gr.type.is_boss() else '')
            nl = Ui.label(name, pad + 80, cy + 5, Cyber.body(Font.BOLD, 14), (Cyber.lerp(Cyber.RED, Color.WHITE, 0.25) if gr.type.is_boss() else Cyber.TEXT))
            content.add(nl)
            tx = W - pad
            for m in reversed(gr.modifiers()):
                c = gr.mods[m]
                txt = _j.cat(MODIFIER_TAGS[m] if m is not Modifier.INJECTION else 'INJECT', (_j.cat(' ', c) if c != gr.count else ''))
                tl = Ui.label(txt, 0, cy + 4, Cyber.body(Font.BOLD, 11), modifier_color(m))
                tx -= tl.get_width()
                tl.set_location(tx, cy + 4)
                content.add(tl)
                tx -= 8
            y += 28
        lines = []
        for gr in pv.groups:   # what each incoming corporate boss does (boss_abilities, from the live numbers)
            text = boss_abilities.describe(gr.type) if gr.type.is_boss() else ''
            if text:
                head, _, body_text = text.partition(': ')
                lines.append((_j.cat(gr.type.display_name.upper(), ':  ', head), body_text or text, Cyber.RED))
        for th in self.threats:
            if th.kind is Threat.BOSS:
                continue
            lines.append((_j.cat('! ', th.chip), th.detail, Cyber.YELLOW))
        if pv.news is not None:
            lines.append(('BREAKING NEWS', pv.news.headline(pv.number), Cyber.MAGENTA))
        if pv.forecast:
            lines.append(('FORECAST', _j.cat('Wave ', pv.number, '’s Breaking News is announced when wave ', pv.number - 1,
                                              ' ends and can still change it.'), Cyber.YELLOW))
        if pv.note is not None and len(pv.note) > 0:
            lines.append(('NOTE', pv.note, Cyber.MUTED))
        for head, text, col in lines:
            y += 8
            content.add(Ui.label(head, pad, y + 9, Cyber.body(Font.BOLD, 12), col))
            y += 12
            for l in Ui.wrap(text, body, tw)[:4]:
                y += 15
                content.add(Ui.label(l, pad, y, body, (Cyber.TEXT if col is not Cyber.MUTED else Cyber.MUTED)))
        h = y + 14
        frame = Cyber.Chamfer(0, 0, W, h, 4).fill(Color(9, 14, 28, 250)).border(Cyber.EDGE_HI)
        self.card.add(frame)
        self.card.add(content)
        self.card.set_location(self.right - W, self.card_bottom - h)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.enemy import boss_abilities  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402
