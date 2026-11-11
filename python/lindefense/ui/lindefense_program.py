"""Lindefense LindefenseProgram (ported from src/lindefense/ui/LindefenseProgram.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ai.reverse_match import ReverseMatch
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game
from lindefense.sim.misc import AdminMode
from lindefense.sim.misc import HeroCollection
from lindefense.sim.run_setup import RunOptions, RunSetup
from lindefense.variance import variance


class LindefenseProgram(GraphicsProgram):
    """The ACM GraphicsProgram that hosts Lindefense. Everything is drawn inside one
ScaledLayer laid out in a fixed 1600x1000 logical space, so the game
fills any window size (the window is resizable; the layer re-fits on every
resize and mouse coordinates are mapped back into logical space).

The simulation is advanced from a Swing timer on the event-dispatch thread,
which is also where ACM delivers mouse and key events, so no locking is needed.

Frame loop
The timer fires every 1000 / maxFps ms, where the cap (30, 60 or 120 frames per second, default 60) is set
in SETTINGS > DISPLAY (GraphicsSettings) and applied on the next tick. It coalesces:
if a frame is still being painted when the next tick is due, ticks are merged instead of queuing up, and the
mouse and key events waiting on the event thread are handled between frames. Each frame advances the simulation in
fixed lindefense.sim.Game#DT steps (capped per frame by GameScreen#MAX_SIM_STEPS_PER_FRAME),
updates the views and requests one repaint; Swing merges repaint requests, so each frame is painted once."""
    def __init__(self):
        self.menu = None
        self.map_select = None
        self.game_screen = None
        self.last_nanos = 0
        self.timer = None
        self.demo = None
        self.window_grab = None
        GraphicsProgram.__init__(self)
        self.root = ScaledLayer()
        pass
    def init(self):
        b = GraphicsEnvironment.get_local_graphics_environment().get_maximum_window_bounds()
        w = _j.to_int(_j.dmin(1600, (b.width * 0.92)))
        h = _j.to_int(_j.dmin((1000 + 28), (b.height * 0.92)))
        if (w / 1.6) > h:
            w = _j.to_int((h * 1.6))
        else:
            h = (_j.to_int((w / 1.6)) + 28)
        self.set_size(w, h)
        self.set_title('Lindefense - The Last Line of Code')
        self.set_background(Ui.BG)
    @staticmethod
    def configure_canvas(canvas):
        """Canvas settings shared by the game and the offscreen benchmark (tools.PerfBench):

  auto-repaint off: the frame loop repaints once per frame instead of on every GObject mutation;
  native arcs on: GOval / GArc are painted with Java2D's curve-based arcs instead of ACM's
      fallback ArcRenderer, which converts every oval into an integer polygon of about
      2 * PI * diameter vertices (190 for a 30 px enemy, 600+ for a range ring) that then has to be
      anti-aliased and stroked vertex by vertex. Profiling showed that fallback alone was about 70% of frame time
      in large fights."""
        canvas.set_auto_repaint_flag(False)
        canvas.set_native_arc_flag(True)
    def run(self):
        canvas = self.get_g_canvas()
        canvas.set_background(Ui.BG)
        LindefenseProgram.configure_canvas(canvas)
        win = SwingUtilities.get_window_ancestor(canvas)
        if isinstance(win, JFrame):
            f = win
            f.set_resizable(True)
            f.set_minimum_size(Dimension(640, 420))
            self.install_icon(f)
        self.add(self.root)
        self.root.fit(canvas.get_width(), canvas.get_height())
        _outer_self = self
        class _Anon1(object):
            def __init__(self_, *a):
                self_._outer = _outer_self
            def component_resized(self, e):
                self._outer.root.fit(canvas.get_width(), canvas.get_height())
                canvas.repaint()
        canvas.add_component_listener(_Anon1())
        self.add_mouse_listeners()
        self.add_key_listeners()
        AudioManager.install()
        self.show_menu()
        demo_dir = _j.get_property('lindefense.demo')
        if demo_dir is not None:
            self.demo = DemoDriver(self, demo_dir)
        self.window_grab = WindowGrab.create(win, (self.demo is not None))
        self.last_nanos = _j.nano_time()
        self.timer = Timer(GraphicsSettings.get().frame_delay_ms(), _j.Fn(lambda e: self.frame()))
        self.timer.set_coalesce(True)
        self.timer.start()
    def frame(self):
        delay = GraphicsSettings.get().frame_delay_ms()
        if (self.timer is not None) and (self.timer.get_delay() != delay):
            self.timer.set_delay(delay)
        now = _j.nano_time()
        dt = _j.dmin(0.1, ((now - self.last_nanos) / 1e9))
        self.last_nanos = now
        canvas = self.get_g_canvas()
        if (canvas.get_width() > 0) and (abs((self.root.get_scale() - _j.dmin((canvas.get_width() / float(Ui.W)), (canvas.get_height() / float(Ui.H))))) > 1e-6):
            self.root.fit(canvas.get_width(), canvas.get_height())
        if self.game_screen is not None:
            self.game_screen.frame(dt)
        elif (self.menu is not None) and self.menu.is_visible():
            self.menu.frame(dt)
        elif self.map_select is not None:
            self.map_select.frame(dt)
        if self.demo is not None:
            self.demo.frame(dt)
        if self.window_grab is not None:
            self.window_grab.frame(dt, self.get_game())
        canvas.repaint()
    def clear_screens(self):
        """Removes the current screen and forgets EVERY screen reference. Input is routed to the first non-null screen
(game, map select, menu; the catalog is a pop-up panel owned by the menu screen itself), so a stale reference
to a screen that is no longer showing would keep swallowing clicks and keys meant for the new one (Esc from
map select once left the menu's buttons dead)."""
        self.root.remove_all()
        self.game_screen = None
        self.map_select = None
        self.menu = None
    def show_menu(self):
        self.clear_screens()
        self.menu = MenuScreen(self)
        self.root.add(self.menu)
        AudioManager.menu_music()
        self.get_g_canvas().repaint()
    def show_map_select(self):
        self.clear_screens()
        self.map_select = MapSelectScreen(self)
        self.root.add(self.map_select)
        AudioManager.menu_music()
        self.get_g_canvas().repaint()
    def _start_game_0(self, map_index):
        self.start_run(RunSetup(map_index, Difficulty.get_selected(), None, (), LindefenseProgram.variance_for_players()))
    def start_run(self, setup):
        """Starts a defense run from a briefing's RunSetup (seed, challenge rules, Patch Notes, daily date)."""
        AudioManager.sfx(Sfx.UI_SELECT)
        g = setup.create_game(HeroCollection.persistent(), (AdminMode.is_on(AdminMode.Option.UNLOCK_HEROES), AdminMode.is_on(AdminMode.Option.INFINITE_MONEY), AdminMode.is_on(AdminMode.Option.INFINITE_HEALTH)))
        self.start_game(g)
    def _start_game_1(self, game):
        self.start_game(game, False)
    def _start_game_2(self, game, tutorial):
        self.clear_screens()
        self.game_screen = GameScreen(self, game, tutorial)
        self.root.add(self.game_screen)
        self.get_g_canvas().request_focus_in_window()
        self.get_g_canvas().repaint()
    def start_game(self, *a):
        if len(a) == 1:
            if (isinstance(a[0], int) and not isinstance(a[0], bool)):
                return self._start_game_0(*a)
            return self._start_game_1(*a)
        elif len(a) == 2:
            return self._start_game_2(*a)
        raise TypeError('no overload for %d args' % len(a))
    @staticmethod
    def variance_for_players():
        """Patch Notes and news for new runs: the briefing's PATCH NOTES switch (saved, on by default), unless
#VARIANCE_PROPERTY is "off" / "false"."""
        v = _j.get_property(LindefenseProgram.VARIANCE_PROPERTY)
        return ((v is None) or (v.lower() not in ('off', 'false'))) and RunOptions.get().patch_notes_on()
    def replay_seed(self):
        """REPLAY SEED (end screen): a fresh match on the same map, difficulty and seed (same patch-note offers and news)."""
        if self.game_screen is None:
            return
        old = self.game_screen.get_game()
        self.start_game(Game.fresh_copy(old, old.get_seed()))
    def start_reverse(self, map_index):
        """ATTACK (reverse mode, "Adversarial Training", from the mission briefing): the player sends the enemies and a
defender AI builds the towers on map mapIndex; the selected Difficulty Growth mode picks the AI. The AI's
Hero Store collection is in memory (saved unlocks are never used or changed); the admin "infinite money" cheat
gives the attacker unlimited compute credits instead."""
        AudioManager.sfx(Sfx.UI_SELECT)
        g = ReverseMatch.create(map_index, _j.nano_time(), Difficulty.get_selected())
        g.get_reverse().set_unlimited_credits(AdminMode.is_on(AdminMode.Option.INFINITE_MONEY))
        self.start_game(g)
    def start_tutorial(self):
        """TUTORIAL (main menu): a guided match on the first map at the default difficulty. It uses an in-memory hero
collection, so practice unlocks never touch the saved Hero Store progress."""
        AudioManager.sfx(Sfx.UI_SELECT)
        g = Game(maps.create(0), variance.seed_next(), Difficulty.O1)
        self.start_game(g, True)
    def restart_level(self):
        """RESTART: throws the running level away and starts a fresh game on the same map and difficulty."""
        if self.game_screen is None:
            return
        old = self.game_screen.get_game()
        self.start_game((ReverseMatch.restart(old) if old.is_reverse() else Game.fresh_copy(old)))
    def quit_level(self):
        """QUIT LEVEL: abandons the running level and returns to the map / difficulty select screen."""
        self.show_map_select()
    def install_icon(self, f):
        """Renders the emblem to an image and uses it as the window / dock icon (best effort)."""
        try:
            n = 128
            img = BufferedImage(n, n, BufferedImage.TYPE_INT_ARGB)
            g2 = img.create_graphics()
            Cyber.quality(g2)
            g2.translate((n / 2.0), (n / 2.0))
            e = LogoEmblem((n * 0.9))
            e.animate(0.4)
            e.paint(g2)
            g2.dispose()
            f.set_icon_image(img)
            if Taskbar.is_taskbar_supported() and Taskbar.get_taskbar().is_supported(Taskbar.Feature.ICON_IMAGE):
                Taskbar.get_taskbar().set_icon_image(img)
        except Exception as ignored:
            pass
    def quit(self):
        if self.timer is not None:
            self.timer.stop()
        self.exit()
    def mouse_pressed(self, e):
        self.get_g_canvas().request_focus_in_window()
        lx = self.root.to_logical_x(e.get_x())
        ly = self.root.to_logical_y(e.get_y())
        right = (SwingUtilities.is_right_mouse_button(e) or e.is_control_down())
        if self.game_screen is not None:
            self.game_screen.mouse_pressed(lx, ly, right)
        elif self.map_select is not None:
            self.map_select.mouse_pressed(lx, ly)
        elif self.menu is not None:
            self.menu.mouse_pressed(lx, ly)
        self.get_g_canvas().repaint()
    def mouse_moved(self, e):
        lx = self.root.to_logical_x(e.get_x())
        ly = self.root.to_logical_y(e.get_y())
        if self.game_screen is not None:
            self.game_screen.mouse_moved(lx, ly)
        elif self.map_select is not None:
            self.map_select.mouse_moved(lx, ly)
        elif self.menu is not None:
            self.menu.mouse_moved(lx, ly)
    def mouse_dragged(self, e):
        """A drag also moves the pointer (hover, placement ghost); it then drives a grabbed volume slider."""
        self.mouse_moved(e)
        lx = self.root.to_logical_x(e.get_x())
        ly = self.root.to_logical_y(e.get_y())
        if self.game_screen is not None:
            self.game_screen.mouse_dragged(lx, ly)
        elif (self.map_select is None) and (self.menu is not None):
            self.menu.mouse_dragged(lx, ly)
    def mouse_released(self, e):
        """Ends a volume-slider drag (the screens save the new level on release)."""
        if self.game_screen is not None:
            self.game_screen.mouse_released()
        elif (self.map_select is None) and (self.menu is not None):
            self.menu.mouse_released()
    def key_pressed(self, e):
        if ((self.game_screen is None) and (self.menu is not None)) and self.menu.is_typing():
            self.menu.key_pressed(e)
            return
        if ((self.game_screen is None) and (self.map_select is not None)) and self.map_select.is_typing():
            self.map_select.key_pressed(e)
            return
        am = AudioManager.get()
        if (am is not None) and ((e.get_key_code() == KeyEvent.VK_M) or (e.get_key_code() == KeyEvent.VK_N)):
            if e.get_key_code() == KeyEvent.VK_M:
                am.toggle_music()
            else:
                am.toggle_sound()
            return
        if self.game_screen is not None:
            self.game_screen.key_pressed(e)
        elif self.map_select is not None:
            self.map_select.key_pressed(e)
        elif self.menu is not None:
            self.menu.key_pressed(e)
    def get_root(self):
        """Exposed for tests / tooling."""
        return self.root
    def get_game_screen(self):
        return self.game_screen
    def get_map_select(self):
        return self.map_select
    def get_menu(self):
        return self.menu
    def get_game(self):
        return None if (self.game_screen is None) else self.game_screen.get_game()
    def get_background_color(self):
        return Ui.BG


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.audio.audio_manager import AudioManager  # noqa: E402
from lindefense.audio.sfx import Sfx  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.demo_driver import DemoDriver  # noqa: E402
from lindefense.ui.game_screen import GameScreen  # noqa: E402
from lindefense.ui.graphics_settings import GraphicsSettings  # noqa: E402
from lindefense.ui.logo_emblem import LogoEmblem  # noqa: E402
from lindefense.ui.map_select_screen import MapSelectScreen  # noqa: E402
from lindefense.ui.menu_screen import MenuScreen  # noqa: E402
from lindefense.ui.scaled_layer import ScaledLayer  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402
from lindefense.ui.window_grab import WindowGrab  # noqa: E402

LindefenseProgram.serial_version_uid = 1
LindefenseProgram.VARIANCE_PROPERTY = 'lindefense.variance'
