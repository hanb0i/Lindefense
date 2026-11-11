"""Lindefense MenuScreen (ported from src/lindefense/ui/MenuScreen.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense import savegame
from lindefense import version
from lindefense.sim.misc import AdminMode
from lindefense.ui.logo_emblem import LogoEmblem


class MenuScreen(GCompound):
    """The title screen: a quiet backdrop (a faint grid and a soft light behind the logo), the emblem and the
LINDEFENSE wordmark, the button stack and the audio chips. Built once in the constructor (ACM primitives only); the
only motion is a short letter-by-letter reveal of the wordmark that any input skips (none with REDUCED MOTION)."""
    def __init__(self, app):
        self.audio_toggles = None
        self.help_shown = False
        self.settings_shown = False
        self.catalog = None
        self.catalog_shown = False
        self.stats = None
        self.stats_shown = False
        self.code_label = None
        self.admin_status = None
        self.code_feedback = None
        self.f_disable_admin = None
        self.option_buttons = None
        self.option_labels = None
        self.settings_toggles = None
        self.settings_sliders = None
        self.window_chip = None
        self.quality_chip = None
        self.fps_chip = None
        self.display_hint = None
        self.fullscreen_chip = None      # SETTINGS > DISPLAY / ACCESSIBILITY (display_settings.DisplaySettings)
        self.fps_counter_chip = None
        self.motion_chip = None
        self.colour_chip = None
        self.access_hint = None
        self.display_state = None
        self.settings_mouse = (-1.0, -1.0)
        self.app = app
        self.feedback_time = 0.0
        self.t = 0.0
        self.intro_t = 0.0
        self.intro_done = False
        self.main = None
        self.emblem = None
        self.subtitle = None
        self.tagline = None
        self.ver_label = None
        self.saved_run = None
        self.continue_button = None
        self.notice = None
        self.notice_time = 0.0
        GCompound.__init__(self)
        self.app = app
        self.buttons = _j.ArrayList()
        self.chips = _j.ArrayList()
        self.help = GCompound()
        self.settings = GCompound()
        self.code_input = _j.StringBuilder()
        self.settings_chips = _j.ArrayList()
        self.add(Ui.rect(0, 0, Ui.W, Ui.H, MenuScreen.BG, MenuScreen.BG))
        self.add(Cyber.Grid(0, 0, Ui.W, Ui.H, 40, Ui.with_alpha(MenuScreen.CYAN, 7)))
        self.add(Cyber.Light(0, 0, Ui.W, Ui.H, 800, (MenuScreen.LOGO_Y - 30), 640, 0.62, Ui.with_alpha(MenuScreen.CYAN, 20)))
        self.main = LogoWordmark(104.0, Color(0xeafcff), None, True)
        self.main.set_location(800, MenuScreen.LOGO_Y)
        self.add(self.main)
        self.emblem = LogoEmblem(120)
        self.emblem.set_location(800, 158)
        self.add(self.emblem)
        self.subtitle = Ui.label('THE LAST LINE OF CODE', 0, 0, MenuScreen.menu_font(Font.BOLD, 22), MenuScreen.CYAN)
        self.subtitle.set_location(((Ui.W - self.subtitle.get_width()) / 2), 426)
        self.add(self.subtitle)
        self.tagline = Ui.label('Deploy. Upgrade. Defend.', 0, 0, Cyber.body(Font.PLAIN, 15), Cyber.MUTED)
        self.tagline.set_location(((Ui.W - self.tagline.get_width()) / 2), 452)
        self.add(self.tagline)
        bf = MenuScreen.menu_font(Font.BOLD, 22)
        self.saved_run, notice = savegame.menu_entry()
        # the button stack: (y of the first row, row pitch, button height); a saved run adds CONTINUE on top
        y, step, bh = (MenuScreen.STACK_Y, 58, 50) if self.saved_run is None else (MenuScreen.STACK_Y - 6, 52, 46)
        if self.saved_run is not None:
            self.continue_button = self.build_continue(app, self.saved_run, y)
            _j_add(self.buttons, self.continue_button)
            self.add(self.continue_button)
            y += MenuScreen.CONTINUE_H + (step - bh)
        # CAMPAIGN leads; CLASSIC (the 100-wave game on any map: map select, daily run, seeds, challenges) and TUTORIAL
        # share the second row, so the stack keeps its six rows
        play = NeonButton(((Ui.W / 2.0) - 150), y, 300, bh, 'CAMPAIGN', bf, MenuScreen.CYAN, _j.Fn(lambda: app.show_campaign()))
        play.set_primary(self.saved_run is None)
        classic = NeonButton(((Ui.W / 2.0) - 150), (y + step), 146, bh, 'CLASSIC', bf, MenuScreen.CYAN, _j.Fn(app.show_map_select))
        tut = NeonButton(((Ui.W / 2.0) + 4), (y + step), 146, bh, 'TUTORIAL', bf, MenuScreen.CYAN, _j.Fn(app.start_tutorial))
        cat = NeonButton(((Ui.W / 2.0) - 150), (y + (2 * step)), 146, bh, 'CATALOG', bf, MenuScreen.CYAN, _j.Fn(self.toggle_catalog))
        stats = NeonButton(((Ui.W / 2.0) + 4), (y + (2 * step)), 146, bh, 'RECORDS', bf, MenuScreen.CYAN, _j.Fn(self.toggle_stats))
        how = NeonButton(((Ui.W / 2.0) - 150), (y + (3 * step)), 300, bh, 'HOW TO PLAY', bf, MenuScreen.CYAN, _j.Fn(self.toggle_help))
        set_ = NeonButton(((Ui.W / 2.0) - 150), (y + (4 * step)), 300, bh, 'SETTINGS', bf, MenuScreen.CYAN, _j.Fn(self.toggle_settings))
        quit = NeonButton(((Ui.W / 2.0) - 150), (y + (5 * step)), 300, bh, 'QUIT', bf, Cyber.MUTED, _j.Fn(app.quit))
        for b in [play, classic, tut, cat, stats, how, set_, quit]:
            _j_add(self.buttons, b)
            self.add(b)
        chips_y = ((y + (5 * step)) + bh) + 14
        self.audio_toggles = AudioToggle.pair(((Ui.W / 2.0) - 150), chips_y, 145, 38, 10, 'SOUND', 'MUSIC', self.chips)
        for c in self.chips:
            self.add(c)
        small = Cyber.mono(Font.BOLD, 13)
        self.ver_label = Ui.label(version.LABEL, 0, 44, small, Cyber.DIM)
        self.ver_label.set_location(((Ui.W - 40) - self.ver_label.get_width()), 44)
        self.add(self.ver_label)
        foot = Ui.label('Resize the window freely  ·  F11: full screen', 0, 0, Cyber.body(Font.PLAIN, 13), Cyber.DIM)
        foot.set_location(((Ui.W - foot.get_width()) / 2), (Ui.H - 22))
        self.add(foot)
        self.notice = Ui.label('', 0, (chips_y + 66), Cyber.mono(Font.BOLD, 14), Cyber.RED)
        self.add(self.notice)
        if notice is not None:
            self.show_notice(notice)
        self.build_help()
        self.help.set_visible(False)
        self.add(self.help)
        self.build_settings()
        self.settings.set_visible(False)
        self.add(self.settings)
        self.catalog = CatalogScreen(_j.Fn(self.toggle_catalog))
        self.catalog.set_visible(False)
        self.add(self.catalog)
        for i in range(self.main.get_letter_count()):
            self.main.set_letter_visible(i, False)
    def build_continue(self, app, info, y):
        """CONTINUE (only with a valid saved run): the run's map, difficulty and wave under the title."""
        w = 380.0
        b = NeonButton(((Ui.W - w) / 2), y, w, MenuScreen.CONTINUE_H, 'CONTINUE', MenuScreen.menu_font(Font.BOLD, 22), MenuScreen.ORANGE, _j.Fn(lambda: app.continue_run()))
        b.set_primary(True)
        b.text.set_location(((w - b.text.get_width()) / 2), 27)
        f = Cyber.mono(Font.BOLD, 13)
        d = info.get_difficulty()
        detail = Cyber.Text(info.label(None if d is None else DifficultySelector.display(d, f)))
        detail.set_font(f)
        size = 13
        while (detail.get_width() > (w - 28)) and (size > 10):
            size -= 1
            detail.set_font(Cyber.mono(Font.BOLD, size))
        detail.set_color(Color(0x2a1a06))
        detail.set_location(((w - detail.get_width()) / 2), 47)
        b.add(detail)
        return b
    def show_notice(self, text):
        """A one-off line under the buttons (a saved run that could not be loaded); fades after a few seconds."""
        self.notice.set_label(text)
        self.notice.set_location(((Ui.W - self.notice.get_width()) / 2), self.notice.get_y())
        self.notice_time = 6.0
    @staticmethod
    def menu_font(style, size):
        """Font fallback chain for small text."""
        return Cyber.display(style, size)
    def build_help(self):
        self.help.add(Ui.rect(0, 0, Ui.W, Ui.H, Cyber.SCRIM, Ui.with_alpha(Cyber.SCRIM, 0)))
        self.help.add(Cyber.Chamfer(((Ui.W / 2.0) - 440), 106, 880, 790, 6))
        y = 132.0
        x = ((Ui.W / 2.0) - 410)
        sections = [['GOAL', 'CAMPAIGN: 15 levels, each win unlocks new towers, up to the Palantir finale. CLASSIC: survive 100 waves, then Palantir.'], ['BUILDING', 'Pick a faction tab (or press B for all towers), click a tower, then click a free spot beside the track. Each tower has three upgrades named after its model lineup (Zethos has four) and several targeting priorities. Once a tower has every upgrade (Zethos: all four), buy its overpowered ability for $15,000 (U or the side panel).'], ['HERO STORE', 'Press HEROES (or K) in game. Buy a hero once to unlock it for good: 18 heroes, up to Mr. Lindemann, the strongest. Unlocked heroes cost a bit of cash to deploy, once per match, at most 3 per game, and level up with three upgrades. New here? Try TUTORIAL; look anything up in CATALOG.'], ['ECONOMY', 'Enemies pay cash when destroyed; every wave pays a bonus. Perplexity earns research income. Selling refunds 70% of everything spent on a tower.'], ['ENEMIES', 'Data structures and sorting algorithms, each with a mechanic: Bubble Sort swaps places, Heap Sort shields allies and is Lead-type (Sharp damage cannot hurt it), Merge/Quick/Counting/TimSort split, Bucket Sort stores weaker enemies, Radix Sort turns Lead-type in its armoured phases, Shell Sort gap-jumps.'], ['MODIFIERS', 'Camo needs detection (Grok, Perplexity and its radius, Gemini / Llama U2). Regrow heals. Fortified has double HP. Prompt Injection hijacks nearby towers; Claude, Copilot, DeepSeek, Perplexity and Mr. Lindemann are immune.'], ['BOSSES', 'Bellarmine College Prep (MOAB, wave 40: Crest Shield at half health), SW Resource Consultant (BFB, 60: outsources Quick Sorts), 3Com (ZOMG, 80: a hub that shields nearby enemies), Lockheed Martin (DDT, 90: afterburner) and Palantir (BAD, 100): Predictive Surveillance, a trick per phase - Panopticon sweep, Prompt Broadcast with decoys, a System Takeover that grabs your window - and escort squadrons whose Swarm Uplink shields it.'], ['CONTROLS', 'Space: next wave.  O: auto waves.  1/2/3: speed.  P: pause (you can still build, upgrade and sell).  Esc: cancel / deselect, else pause menu.  Right-click: cancel.  B: all towers.  Shift+1-9: place the Nth shop card.  Tab / Shift+Tab: next / previous tower.  U: upgrade / buy ability.  S: sell.  A: ability.  T / Shift+T: targeting.  K: Hero Store.  H: help.  M / N: music / sound.  F11 (Mac: Cmd+Ctrl+F): full screen.']]
        hf = MenuScreen.menu_font(Font.BOLD, 16)
        bf = Cyber.body(Font.PLAIN, 14)
        for s in sections:
            y += 26
            self.help.add(Ui.label(s[0], x, y, hf, MenuScreen.CYAN))
            for l in Ui.wrap(s[1], bf, 820):
                y += 20
                self.help.add(Ui.label(l, x, y, bf, Cyber.lerp(Ui.TEXT, Cyber.MUTED, 0.25)))
            y += 6
        close = NeonButton(((Ui.W / 2.0) - 100), 826, 200, 46, 'CLOSE', MenuScreen.menu_font(Font.BOLD, 20), MenuScreen.CYAN, _j.Fn(self.toggle_help))
        self.help.add(close)
        _j_add(self.buttons, close)
    def toggle_help(self):
        self.help_shown = (not self.help_shown)
        self.help.set_visible(self.help_shown)
    def skip_intro(self):
        """Any click or key ends the boot-up intro immediately."""
        if self.intro_done:
            return
        self.intro_done = True
        for i in range(self.main.get_letter_count()):
            self.main.set_letter_visible(i, True)
    def toggle_catalog(self):
        """CATALOG button: opens / closes the catalog as a pop-up panel over the menu (never a separate screen)."""
        self.catalog_shown = (not self.catalog_shown)
        if self.catalog_shown:
            self.help_shown = False
            self.help.set_visible(False)
            self.settings_shown = False
            self.settings.set_visible(False)
        self.catalog.set_visible(self.catalog_shown)
    def toggle_stats(self):
        """RECORDS button: opens / closes career stats, map records, achievements and run history over the menu
(rebuilt on every open, so it always shows the latest runs)."""
        self.stats_shown = (not self.stats_shown)
        if self.stats is not None:
            self.remove(self.stats)
            self.stats = None
        if self.stats_shown:
            self.help_shown = False
            self.help.set_visible(False)
            self.settings_shown = False
            self.settings.set_visible(False)
            replay = getattr(self.app, 'replay_run', None)
            self.stats = StatsScreen(_j.Fn(self.toggle_stats), replay)
            self.add(self.stats)
    def mouse_pressed(self, lx, ly):
        self.skip_intro()
        if self.stats_shown:
            self.stats.mouse_pressed(lx, ly)
            return
        if self.catalog_shown:
            self.catalog.mouse_pressed(lx, ly)
            return
        if self.settings_shown:
            if Slider.press_any(lx, ly, self.settings_sliders):
                return
            for c in self.settings_chips:
                if c.hit(lx, ly):
                    c.click()
                    return
            for b in self.buttons:
                if ((b.get_parent() is self.settings) and b.is_visible()) and b.hit(lx, ly):
                    b.click()
                    return
            return
        if not self.help_shown:
            for c in self.chips:
                if c.hit(lx, ly):
                    c.click()
                    return
        for b in self.buttons:
            # the HELP panel is modal too: while it is open only its own CLOSE responds (the menu buttons hidden
            # behind it, QUIT included, must not fire through the panel)
            if ((b.hit(lx, ly) and b.is_visible()) and (b.get_parent() is not self.settings)) and ((b.get_parent() is self.help) == self.help_shown):
                b.click()
                return
    def build_settings(self):
        w = 1000.0
        h = 920.0
        x = ((Ui.W - w) / 2)
        y = 40.0
        self.settings.add(Ui.rect(0, 0, Ui.W, Ui.H, Cyber.SCRIM, Ui.with_alpha(Cyber.SCRIM, 0)))
        self.settings.add(Cyber.Chamfer(x, y, w, h, 6))
        title = Ui.label('SETTINGS', (x + 40), (y + 56), MenuScreen.menu_font(Font.BOLD, 30), Cyber.TEXT)
        self.settings.add(title)
        lx = (x + 40)
        ty = (y + 100)
        ty = self.build_audio_settings(lx, ty, (w - 80))
        ty = self.build_display_settings(lx, ty, (w - 80))
        ty = self.build_accessibility_settings(lx, ty, (w - 80))
        self.settings.add(Ui.label('ADMIN CODE', lx, ty, MenuScreen.SECTION_FONT, Cyber.TEXT))
        body = Cyber.body(Font.PLAIN, 14)
        for l in Ui.wrap('Enter the admin code to unlock the cheat checklist. Each option can be switched on and off on its own and applies to matches started from CLASSIC.', body, (w - 80)):
            ty += 20
            self.settings.add(Ui.label(l, lx, ty, body, Cyber.MUTED))
        by = (ty + 22)
        self.settings.add(Cyber.Chamfer(lx, by, 380, 48, 4).fill(Color(4, 7, 16, 240)).border(Cyber.EDGE_HI))
        self.code_label = Ui.label('', (lx + 16), (by + 32), Cyber.mono(Font.BOLD, 20), Cyber.TEXT)
        self.settings.add(self.code_label)
        submit = NeonButton((lx + 400), by, 200, 48, 'ENTER', MenuScreen.menu_font(Font.BOLD, 20), MenuScreen.CYAN, _j.Fn(self.submit_code))
        self.settings.add(submit)
        _j_add(self.buttons, submit)
        self.admin_status = Ui.label('', lx, (by + 76), Cyber.mono(Font.BOLD, 15), Cyber.DIM)
        self.settings.add(self.admin_status)
        self.code_feedback = Ui.label('', lx, (by + 96), Cyber.mono(Font.PLAIN, 13), Cyber.RED)
        self.settings.add(self.code_feedback)
        opts = AdminMode.Option.values()
        self.option_buttons = ([None] * len(opts))
        self.option_labels = ([None] * len(opts))
        oy = (by + 112)
        for i in range(len(opts)):
            o = opts[i]
            t = NeonButton(lx, oy, 360, 40, o.label, MenuScreen.menu_font(Font.BOLD, 17), MenuScreen.CYAN, _j.Fn(lambda o=o: self.toggle_option(o)))
            self.settings.add(t)
            _j_add(self.buttons, t)
            self.option_buttons[i] = t
            desc = Ui.label(o.description, (lx + 374), (oy + 25), Cyber.body(Font.PLAIN, 12), Cyber.MUTED)
            self.settings.add(desc)
            self.option_labels[i] = desc
            oy += 46
        self.f_disable_admin = NeonButton(lx, (oy + 6), 360, 40, 'LOCK ADMIN (CODE AGAIN)', MenuScreen.menu_font(Font.BOLD, 15), Cyber.RED, _j.Fn(self.disable_admin))
        self.settings.add(self.f_disable_admin)
        _j_add(self.buttons, self.f_disable_admin)
        close = NeonButton(((Ui.W - 200) / 2.0), ((y + h) - 70), 200, 46, 'CLOSE', MenuScreen.menu_font(Font.BOLD, 20), MenuScreen.CYAN, _j.Fn(self.toggle_settings))
        self.settings.add(close)
        _j_add(self.buttons, close)
        self.refresh_settings()
    def build_audio_settings(self, lx, ty, cw):
        """SETTINGS > AUDIO: per channel an on/off chip and a volume slider, the two channels side by side. Returns the
baseline y of the next section."""
        self.settings.add(Ui.label('AUDIO', lx, ty, MenuScreen.SECTION_FONT, Cyber.TEXT))
        body = Cyber.body(Font.PLAIN, 14)
        for l in Ui.wrap('Levels are saved. Switching a channel off keeps its level. Outside SETTINGS, M toggles music and N sound.', body, cw):
            ty += 20
            self.settings.add(Ui.label(l, lx, ty, body, Cyber.MUTED))
        ry = (ty + 16)
        rh = 40.0
        chip_w = 150.0
        gap = 10.0
        half = ((cw - 20) / 2)
        sw = ((half - chip_w) - gap)
        mx = ((lx + half) + 20)
        self.settings_toggles = [AudioToggle.sound(lx, ry, chip_w, rh, 'SOUND'), AudioToggle.music(mx, ry, chip_w, rh, 'MUSIC')]
        for a in self.settings_toggles:
            self.settings.add(a.get_button())
            _j_add(self.settings_chips, a.get_button())
        self.settings_sliders = [AudioToggle.sound_volume(((lx + chip_w) + gap), ry, sw, rh, 'VOLUME'), AudioToggle.music_volume(((mx + chip_w) + gap), ry, sw, rh, 'VOLUME')]
        for sl in self.settings_sliders:
            self.settings.add(sl)
        div_y = ((ry + rh) + 22)
        self.settings.add(Ui.rect(lx, div_y, cw, 1, Cyber.EDGE, Ui.with_alpha(Cyber.EDGE, 0)))
        return div_y + 40
    def chip_row(self, lx, cy, cw, actions):
        """A row of equal SETTINGS chips (12 px apart) across cw, one per action; returns the chips."""
        ch = 38.0
        gap = 12.0
        n = len(actions)
        chip_w = ((cw - ((n - 1) * gap)) / n)
        row = []
        for i in range(n):
            b = UIButton((lx + (i * (chip_w + gap))), cy, chip_w, ch, '', Cyber.mono(Font.BOLD, 13), _j.Fn(actions[i]))
            self.settings.add(b)
            _j_add(self.settings_chips, b)
            row.append(b)
        return row
    def build_display_settings(self, lx, ty, cw):
        """SETTINGS > DISPLAY: one row of chips (graphics quality preset, frame-rate cap, full screen, FPS counter) and a
hint line: the chosen preset, or what the hovered chip does. Each chip cycles its value on click. Returns the baseline y
of the next section."""
        self.settings.add(Ui.label('DISPLAY', lx, ty, MenuScreen.SECTION_FONT, Cyber.TEXT))
        cy = (ty + 14)
        ch = 38.0
        self.quality_chip, self.fps_chip, self.fullscreen_chip, self.fps_counter_chip = self.chip_row(lx, cy, cw, [self.cycle_quality, self.cycle_fps, self.toggle_fullscreen, self.toggle_fps_counter])
        self.display_hint = Ui.label('', lx, ((cy + ch) + 24), Cyber.body(Font.PLAIN, 14), Cyber.MUTED)
        self.settings.add(self.display_hint)
        div_y = ((cy + ch) + 42)
        self.settings.add(Ui.rect(lx, div_y, cw, 1, Cyber.EDGE, Ui.with_alpha(Cyber.EDGE, 0)))
        return div_y + 40
    def build_accessibility_settings(self, lx, ty, cw):
        """SETTINGS > ACCESSIBILITY: reduced motion, the colour-blind-safe palette and Palantir's window effects, with a
hint line for the hovered chip. Returns the baseline y of the next section."""
        self.settings.add(Ui.label('ACCESSIBILITY', lx, ty, MenuScreen.SECTION_FONT, Cyber.TEXT))
        cy = (ty + 14)
        ch = 38.0
        self.motion_chip, self.colour_chip, self.window_chip = self.chip_row(lx, cy, cw, [self.toggle_reduced_motion, self.toggle_colour_blind, self.toggle_window_effects])
        self.access_hint = Ui.label('', lx, ((cy + ch) + 24), Cyber.body(Font.PLAIN, 14), Cyber.MUTED)
        self.settings.add(self.access_hint)
        self.sync_window_chip()
        self.sync_display_chips()
        div_y = ((cy + ch) + 42)
        self.settings.add(Ui.rect(lx, div_y, cw, 1, Cyber.EDGE, Ui.with_alpha(Cyber.EDGE, 0)))
        return div_y + 40
    def cycle_quality(self):
        """QUALITY chip: LOW -> MEDIUM -> HIGH -> LOW; takes effect on the next frame."""
        gs = GraphicsSettings.get()
        gs.set_quality(gs.quality().next())
        AudioManager.sfx(Sfx.UI_SELECT)
        self.sync_display_chips()
    def cycle_fps(self):
        """MAX FPS chip: 30 -> 60 -> 120 -> 30; the frame timer picks it up on its next tick."""
        gs = GraphicsSettings.get()
        gs.set_max_fps(gs.next_fps())
        AudioManager.sfx(Sfx.UI_SELECT)
        self.sync_display_chips()
    def sync_display_chips(self):
        gs = GraphicsSettings.get()
        ds = DisplaySettings.get()
        self.display_state = self.display_state_key()
        for chip, label, on, accent in ((self.fullscreen_chip, 'FULLSCREEN', ds.fullscreen, MenuScreen.CYAN), (self.fps_counter_chip, 'FPS COUNTER', ds.show_fps, MenuScreen.CYAN), (self.motion_chip, 'REDUCED MOTION', ds.reduced_motion, MenuScreen.CYAN), (self.colour_chip, 'COLOUR-BLIND SAFE', ds.colour_blind, MenuScreen.CYAN)):
            if chip is not None:
                chip.set_text(_j.cat(label, (': ON' if on else ': OFF')))
                chip.set_selected(on)
                chip.set_accent((accent if on else Cyber.DIM))
        q = gs.quality()
        self.quality_chip.set_text(_j.cat('QUALITY: ', q.label.upper()))
        self.quality_chip.set_selected((q is GraphicsSettings.Quality.HIGH))
        self.quality_chip.set_accent((MenuScreen.CYAN if (q is not GraphicsSettings.Quality.LOW) else Cyber.DIM))
        self.fps_chip.set_text(_j.cat('MAX FPS: ', gs.get_max_fps()))
        self.fps_chip.set_selected((gs.get_max_fps() > GraphicsSettings.DEFAULT_FPS))
        self.fps_chip.set_accent((MenuScreen.CYAN if (gs.get_max_fps() >= GraphicsSettings.DEFAULT_FPS) else Cyber.DIM))
        self.refresh_settings_hints()
    def quality_hint(self):
        q = GraphicsSettings.get().quality()
        return 'High: sharpest on 4K / 5K screens, with glow, vignette and screen shake.' if (q is GraphicsSettings.Quality.HIGH) else ('Medium: the original look, with automatic detail in big fights.' if (q is GraphicsSettings.Quality.MEDIUM) else 'Low: fastest. Lighter bitmaps and reduced detail everywhere.')
    def settings_hint_rows(self):
        """(chip, hint line, text) for every DISPLAY / ACCESSIBILITY chip: the text the hint line shows while it is hovered."""
        return [(self.quality_chip, self.display_hint, self.quality_hint()), (self.fps_chip, self.display_hint, 'Max FPS: the frame-rate cap (30 / 60 / 120). A lower cap saves battery.'), (self.fullscreen_chip, self.display_hint, 'Full screen: F11 (Mac: Cmd+Ctrl+F) switches it anywhere, in menus and in matches.'), (self.fps_counter_chip, self.display_hint, 'FPS counter: a small frame-rate readout in the bottom-right corner.'), (self.motion_chip, self.access_hint, 'Reduced motion: no screen shake, glitch bursts, big flashes or strobes. Warnings stay, as steady highlights.'), (self.colour_chip, self.access_hint, 'Colour-blind safe: blue / orange instead of green / red for HP, prices, buffs, placement and surveillance.'), (self.window_chip, self.access_hint, "Window effects: Palantir's final phase grabs and shrinks this window (never in full screen); drag it back.")]
    def refresh_settings_hints(self):
        """Hint lines under DISPLAY and ACCESSIBILITY: the hovered chip's explanation, else the quality preset / a general line."""
        if (self.display_hint is None) or (self.access_hint is None):
            return
        texts = {id(self.display_hint): self.quality_hint(), id(self.access_hint): 'Hover a setting to see what it does. Every change applies at once and is saved.'}
        mx, my = self.settings_mouse
        for chip, line, text in self.settings_hint_rows():
            if (chip is not None) and self.settings_shown and chip.hit(mx, my):
                texts[id(line)] = text
        for line in (self.display_hint, self.access_hint):
            if not (line.get_label() == texts[id(line)]):
                line.set_label(texts[id(line)])
    def display_state_key(self):
        ds = DisplaySettings.get()
        return (ds.fullscreen, ds.show_fps, ds.reduced_motion, ds.colour_blind)
    def toggle_fullscreen(self):
        """FULLSCREEN chip: the same switch as F11 (the app switches the real window and saves the choice)."""
        fn = getattr(self.app, 'toggle_fullscreen', None)
        ds = DisplaySettings.get()
        if callable(fn):
            fn()
        else:
            ds.set_fullscreen((not ds.fullscreen))
        AudioManager.sfx((Sfx.UI_SELECT if ds.fullscreen else Sfx.UI_CLICK))
        self.sync_display_chips()
    def toggle_fps_counter(self):
        on = DisplaySettings.get().toggle_show_fps()
        AudioManager.sfx((Sfx.UI_SELECT if on else Sfx.UI_CLICK))
        self.sync_display_chips()
    def toggle_reduced_motion(self):
        on = DisplaySettings.get().toggle_reduced_motion()
        AudioManager.sfx((Sfx.UI_SELECT if on else Sfx.UI_CLICK))
        self.sync_display_chips()
    def toggle_colour_blind(self):
        on = DisplaySettings.get().toggle_colour_blind()
        AudioManager.sfx((Sfx.UI_SELECT if on else Sfx.UI_CLICK))
        self.sync_display_chips()
    def toggle_window_effects(self):
        on = WindowEffects.toggle()
        AudioManager.sfx((Sfx.UI_SELECT if on else Sfx.UI_CLICK))
        self.sync_window_chip()
    def sync_window_chip(self):
        on = WindowEffects.is_enabled()
        self.window_chip.set_text(_j.cat('WINDOW EFFECTS: ', ('ON' if on else 'OFF')))
        self.window_chip.set_selected(on)
        self.window_chip.set_accent((MenuScreen.CYAN if on else Cyber.DIM))
    def toggle_settings(self):
        self.settings_shown = (not self.settings_shown)
        if self.settings_shown:
            self.help_shown = False
            self.help.set_visible(False)
            self.code_input.set_length(0)
            self.code_feedback.set_label('')
        self.settings.set_visible(self.settings_shown)
        self.refresh_settings()
    def submit_code(self):
        if AdminMode.try_code(self.code_input.to_string()):
            AudioManager.sfx(Sfx.UI_SELECT)
            self.code_feedback.set_label('Code accepted. Pick the cheats you want below.')
            self.code_feedback.set_color(Cyber.GREEN)
        else:
            AudioManager.sfx(Sfx.INVALID)
            self.code_feedback.set_label(('Type the code first.' if (self.code_input.length() == 0) else 'Invalid code.'))
            self.code_feedback.set_color(Cyber.RED)
        self.code_input.set_length(0)
        self.feedback_time = 4.0
        self.refresh_settings()
    def toggle_option(self, o):
        on = AdminMode.toggle(o)
        AudioManager.sfx((Sfx.UI_SELECT if on else Sfx.UI_CLICK))
        self.code_feedback.set_label(_j.cat(o.label, (': ON' if on else ': OFF')))
        self.code_feedback.set_color((Cyber.GREEN if on else Cyber.MUTED))
        self.feedback_time = 3.0
        self.refresh_settings()
    def disable_admin(self):
        AdminMode.disable_all()
        self.code_feedback.set_label('Admin cheats off. Enter the code again to re-open the checklist.')
        self.code_feedback.set_color(Cyber.MUTED)
        self.feedback_time = 4.0
        self.refresh_settings()
    def refresh_settings(self):
        unlocked = AdminMode.is_unlocked()
        self.admin_status.set_label((('ADMIN: UNLOCKED  //  CHEATS ACTIVE' if AdminMode.any_on() else 'ADMIN: UNLOCKED  //  NO CHEATS ON') if unlocked else 'ADMIN: LOCKED'))
        self.admin_status.set_color(((Cyber.GREEN if AdminMode.any_on() else Cyber.YELLOW) if unlocked else Cyber.DIM))
        opts = AdminMode.Option.values()
        for i in range(len(opts)):
            on = AdminMode.is_on(opts[i])
            self.option_buttons[i].set_visible(unlocked)
            self.option_labels[i].set_visible(unlocked)
            self.option_buttons[i].set_text(_j.cat(('[X]  ' if on else '[  ]  '), opts[i].label))
            self.option_buttons[i].set_selected(on)
        self.f_disable_admin.set_visible(unlocked)
        self.update_code_label()
    def update_code_label(self):
        sb = _j.StringBuilder()
        i = 0
        while i < self.code_input.length():
            sb.append('*')
            i += 1
        caret = (self.settings_shown and (_j.imod(_j.to_int((self.t * 2.2)), 2) == 0))
        if (self.code_input.length() == 0) and (not caret):
            self.code_label.set_label('enter code')
        else:
            self.code_label.set_label(_j.cat(sb, ('_' if caret else '')))
        self.code_label.set_color((Cyber.DIM if ((self.code_input.length() == 0) and (not caret)) else Cyber.TEXT))
    def is_typing(self):
        """True while the settings panel is open and capturing typed text."""
        return self.settings_shown
    def key_pressed(self, e):
        """Keys on the main menu. Any key ends the intro and Esc closes the HELP panel. While the settings panel is open
keys type the code: Enter submits, Backspace deletes, Esc closes."""
        self.skip_intro()
        if self.stats_shown:
            self.stats.key_pressed(e)
            return
        if self.catalog_shown:
            self.catalog.key_pressed(e)
            return
        k = e.get_key_code()
        if not self.settings_shown:
            if (k == KeyEvent.VK_ESCAPE) and self.help_shown:
                self.toggle_help()
            return
        if k == KeyEvent.VK_ESCAPE:
            self.toggle_settings()
            return
        if k == KeyEvent.VK_ENTER:
            self.submit_code()
            return
        if k == KeyEvent.VK_BACK_SPACE:
            if self.code_input.length() > 0:
                self.code_input.set_length((self.code_input.length() - 1))
            self.update_code_label()
            return
        c = e.get_key_char() or ''
        typed = False
        for ch in c:   # Java: c != CHAR_UNDEFINED && !Character.isISOControl(c)
            cp = ord(ch)
            if ch != KeyEvent.CHAR_UNDEFINED and not (cp <= 0x1f or 0x7f <= cp <= 0x9f) and self.code_input.length() < 24:
                self.code_input.append(ch)
                typed = True
        if typed:
            self.update_code_label()
    def mouse_moved(self, lx, ly):
        if self.stats_shown:
            self.stats.mouse_moved(lx, ly)
            return
        if self.catalog_shown:
            self.catalog.mouse_moved(lx, ly)
            return
        for b in self.buttons:
            b.set_hover(b.hit(lx, ly))
        for c in self.chips:
            c.set_hover(c.hit(lx, ly))
        for c in self.settings_chips:
            c.set_hover((self.settings_shown and c.hit(lx, ly)))
        if self.settings_shown:
            Slider.hover_all(lx, ly, self.settings_sliders)
            self.settings_mouse = (lx, ly)
            self.refresh_settings_hints()
    def mouse_dragged(self, lx, ly):
        """Mouse drag (logical coordinates): moves a grabbed SETTINGS volume slider."""
        if self.settings_shown:
            Slider.drag_all(lx, ly, self.settings_sliders)
    def mouse_released(self):
        """Mouse release: ends a SETTINGS volume-slider drag (the level is saved)."""
        Slider.release_all(self.settings_sliders)
    def frame(self, dt):
        self.t += dt
        if self.stats_shown:
            self.stats.frame(dt)
        if self.notice_time > 0:
            self.notice_time -= dt
            self.notice.set_color(Ui.with_alpha(Cyber.RED, _j.to_int((255 * _j.dmin(1, _j.dmax(0, self.notice_time))))))
            if self.notice_time <= 0:
                self.notice.set_label('')
        if self.catalog_shown:
            self.catalog.frame(dt)
        if self.settings_shown:
            self.update_code_label()
            if self.feedback_time > 0:
                self.feedback_time -= dt
                if self.feedback_time <= 0:
                    self.code_feedback.set_label('')
            AudioToggle.sync_all(self.settings_toggles)
            if self.display_state_key() != self.display_state:
                self.sync_display_chips()   # F11 / the system's full-screen control while SETTINGS is open
            for c in self.settings_chips:
                c.animate(dt)
            Slider.frame_all(dt, self.settings_sliders)
        self.animate_intro(dt)
        for b in self.buttons:
            b.animate(dt)
        AudioToggle.sync_all(self.audio_toggles)
        for c in self.chips:
            c.animate(dt)
    def animate_intro(self, dt):
        """The wordmark's letters appear one after another over INTRO_TIME (skipped with REDUCED MOTION or any input)."""
        if self.intro_done:
            return
        if display_settings.reduced_motion():
            self.skip_intro()
            return
        self.intro_t += dt
        n = self.main.get_letter_count()
        shown = _j.to_int(_j.dmin(n, float(math.floor(((self.intro_t / MenuScreen.INTRO_TIME) * (n + 1))))))
        for i in range(n):
            self.main.set_letter_visible(i, (i < shown))
        if self.intro_t >= (MenuScreen.INTRO_TIME + 0.05):
            self.skip_intro()


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.audio.audio_manager import AudioManager  # noqa: E402
from lindefense.audio.sfx import Sfx  # noqa: E402
from lindefense.ui.audio_toggle import AudioToggle  # noqa: E402
from lindefense.ui.catalog_screen import CatalogScreen  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.difficulty_selector import DifficultySelector  # noqa: E402
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.display_settings import DisplaySettings  # noqa: E402
from lindefense.ui.graphics_settings import GraphicsSettings  # noqa: E402
from lindefense.ui.logo_wordmark import LogoWordmark  # noqa: E402
from lindefense.ui.neon_button import NeonButton  # noqa: E402
from lindefense.ui.slider import Slider  # noqa: E402
from lindefense.ui.stats_screen import StatsScreen  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402
from lindefense.ui.ui_button import UIButton  # noqa: E402
from lindefense.ui.window_effects import WindowEffects  # noqa: E402

MenuScreen.serial_version_uid = 1
MenuScreen.BG = Color(0x05070f)
MenuScreen.CYAN = LogoEmblem.CYAN
MenuScreen.MAGENTA = LogoEmblem.MAGENTA
MenuScreen.YELLOW = LogoEmblem.YELLOW
MenuScreen.ORANGE = Color(0xffb347)
MenuScreen.STACK_Y = 488.0
MenuScreen.CONTINUE_H = 58.0
MenuScreen.INTRO_TIME = 0.9
MenuScreen.LOGO_Y = 330.0
MenuScreen.SECTION_FONT = Cyber.display(Font.BOLD, 18)
