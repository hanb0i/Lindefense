"""Lindefense desktop app: a native pygame-ce window rendered with Skia (replaces the Java LindefenseProgram).

Rendering: the whole UI is one ScaledLayer laid out in a fixed 1600x1000 logical space. Every frame it is painted by
Skia straight into the window's OpenGL framebuffer at the display's native (Retina) pixel resolution, anti-aliased,
so text and vector art stay razor sharp at any window size. Without OpenGL the same picture is rasterised on the
CPU into the window surface.

Frame loop: the cap (30 / 60 / 120 fps, SETTINGS > DISPLAY) comes from GraphicsSettings; each frame advances the
active screen by the real elapsed time (capped at 0.1 s), runs the window grab, then paints once. Input arrives as
pygame events and is translated to the Java-style calls the ported screens expect (logical coordinates, KeyEvent
virtual-key codes).

Window: F11 (and Cmd+Ctrl+F on macOS) toggles desktop full screen on every screen, as does SETTINGS > DISPLAY >
FULLSCREEN; the choice is saved and re-applied at launch. The windowed size, position and maximised state are saved a
moment after every change and on quit (prefs node 'window') and restored at launch, moved onto a display that is still
connected. Hidden, demo and smoke runs neither restore nor save any of it.
"""
import ctypes
import gc
import glob
import os
import sys
import time

import pygame
import skia

from lindefense.ui.acm import PaintCache
from lindefense.ui.display_settings import DisplaySettings, WindowMemory, place_on_displays
from lindefense.ui.jawt import Graphics2D, KeyEvent, reset_canvas_state

TITLE = "Lindefense - The Last Line of Code"
MIN_W, MIN_H = 640, 420


# ====================================================================== SDL access (HiDPI GL context, window bounds)
def _sdl():
    libs = glob.glob(os.path.join(os.path.dirname(pygame.__file__), ".dylibs", "libSDL2-2.0*.dylib")) \
        + glob.glob(os.path.join(os.path.dirname(pygame.__file__), "libSDL2*.so*")) \
        + glob.glob(os.path.join(os.path.dirname(pygame.__file__), "SDL2.dll"))
    lib = ctypes.CDLL(libs[0]) if libs else ctypes.CDLL(ctypes.util.find_library("SDL2"))
    lib.SDL_GetWindowFromID.restype = ctypes.c_void_p
    lib.SDL_GetWindowFromID.argtypes = [ctypes.c_uint32]
    lib.SDL_GL_CreateContext.restype = ctypes.c_void_p
    lib.SDL_GL_CreateContext.argtypes = [ctypes.c_void_p]
    lib.SDL_GL_MakeCurrent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.SDL_GL_GetCurrentContext.restype = ctypes.c_void_p
    lib.SDL_GL_GetCurrentContext.argtypes = []
    lib.SDL_GL_SwapWindow.argtypes = [ctypes.c_void_p]
    lib.SDL_GL_GetDrawableSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    lib.SDL_GL_SetSwapInterval.argtypes = [ctypes.c_int]
    lib.SDL_GL_SetAttribute.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.SDL_GetWindowFlags.restype = ctypes.c_uint32
    lib.SDL_GetWindowFlags.argtypes = [ctypes.c_void_p]
    lib.SDL_GetWindowDisplayIndex.argtypes = [ctypes.c_void_p]
    lib.SDL_GetDisplayUsableBounds.argtypes = [ctypes.c_int, ctypes.c_void_p]
    lib.SDL_GetDisplayBounds.argtypes = [ctypes.c_int, ctypes.c_void_p]
    lib.SDL_GetNumVideoDisplays.restype = ctypes.c_int
    lib.SDL_GetNumVideoDisplays.argtypes = []
    return lib


class _SDLRect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int), ("w", ctypes.c_int), ("h", ctypes.c_int)]


# ====================================================================== window adapter for Palantir's window grab
class _WindowAdapter:
    def __init__(self, app):
        self.app = app

    def get_bounds(self):
        from lindefense.ui.window_grab import Rect
        w = self.app.window
        x, y = w.position
        ww, hh = w.size
        return Rect(x, y, ww, hh)

    def set_bounds(self, r):
        if self.is_full_screen():   # never move or resize a full-screen window (see window_grab: the grab is blocked)
            return
        w = self.app.window
        self.app._self_moved_at = time.perf_counter()   # our own move: not a reason to auto-pause (see _focus_lost)
        w.position = (r.x, r.y)
        w.size = (max(MIN_W, r.width), max(MIN_H, r.height))

    def is_full_screen(self):
        f = getattr(self.app, "is_fullscreen", None)
        return bool(f()) if f is not None else bool(self._flags() & 0x1)

    def _flags(self):
        return self.app.sdl.SDL_GetWindowFlags(self.app.win_ptr) if self.app.sdl else 0

    def is_showing(self):
        """False while the window is hidden or minimized: there is nothing on screen to grab, and the player
        would never see a "blocked" banner."""
        return not (self._flags() & (0x8 | 0x40))   # hidden | minimized

    def is_maximized_or_full_screen(self):
        return bool(self._flags() & (0x1 | 0x80 | 0x1000)) or self.is_full_screen()   # fullscreen | maximized | desktop

    def min_size(self):
        return (MIN_W, MIN_H)

    def usable_screen(self):
        from lindefense.ui.window_grab import Rect
        sdl = self.app.sdl
        if sdl is not None:
            idx = sdl.SDL_GetWindowDisplayIndex(self.app.win_ptr)
            r = _SDLRect()
            if idx >= 0 and sdl.SDL_GetDisplayUsableBounds(idx, ctypes.byref(r)) == 0:
                return Rect(r.x, r.y, r.w, r.h)
        dw, dh = pygame.display.get_desktop_sizes()[0]
        return Rect(0, 25, dw, dh - 25)


class _CanvasStub:
    """What the ported screens expect from the ACM GCanvas (focus / repaint / size)."""

    def __init__(self, app):
        self.app = app

    def request_focus_in_window(self):
        pass

    def repaint(self):
        pass

    def get_width(self):
        return self.app.px_w

    def get_height(self):
        return self.app.px_h

    def set_background(self, c):
        pass

    def paint(self, g):
        """Paints the whole UI into g at canvas pixel scale (DemoDriver snapshots)."""
        from lindefense.ui.ui import Ui
        g.set_color(Ui.BG)
        g.fill_rect(0, 0, self.app.px_w, self.app.px_h)
        self.app.root.paint(g)


# ====================================================================== the app
class LindefenseApp:
    VARIANCE_PROPERTY = "lindefense.variance"

    def __init__(self, demo_dir=None, window_memory=None):
        from lindefense.ui.scaled_layer import ScaledLayer
        pygame.init()
        pygame.key.set_repeat(400, 35)   # held keys repeat, as the OS-repeated key presses Java/Swing receives
        self.sdl = None
        self.win_ptr = None
        self.gl_ctx = None
        self.gr = None
        self.surface = None
        self.cpu_buf = None
        self.root = ScaledLayer()
        self.menu = self.map_select = self.game_screen = None
        self.demo = None
        self.window_grab = None
        self.autosave = None       # savegame.Autosave of the match on screen (Save & Continue)
        self.running = True
        self._dragging = False
        self._pumping = False      # True while the main loop is inside pygame.event.get()
        self._live_busy = False
        self._live_watch = None
        self._last_tick = time.perf_counter()
        self._errors = {}          # traceback text -> times seen (see _guarded)
        self._init_match_safety()
        self._init_display(window_memory)
        self._make_window()
        self.canvas = _CanvasStub(self)

    # ---------------------------------------------------------------- window + surfaces
    def _initial_size(self):
        try:
            dw, dh = pygame.display.get_desktop_sizes()[0]
        except Exception:
            dw, dh = 1600, 1028
        w = int(min(1600, dw * 0.92))
        h = int(min(1000 + 28, dh * 0.92))
        if w / 1.6 > h:
            w = int(h * 1.6)
        else:
            h = int(w / 1.6)
        return max(MIN_W, w), max(MIN_H, h)

    def _make_window(self):
        w, h = self._initial_size()
        pos, maximized = pygame.WINDOWPOS_UNDEFINED, False
        restored = self._restored_geometry()
        if restored is not None:
            x, y, w, h, maximized = restored
            pos = (x, y)
            self._win_rect, self._win_maximized = (x, y, w, h), maximized
        use_gl = os.environ.get("LINDEFENSE_RENDERER", "gpu").lower() != "cpu"
        if use_gl:
            try:
                self.sdl = _sdl()
                # GL 3.2 core, 8-bit stencil, 4x MSAA on the default framebuffer
                for attr, val in ((17, 3), (18, 2), (21, 1), (7, 8), (13, 1), (14, 4)):
                    self.sdl.SDL_GL_SetAttribute(attr, val)
                self.window = pygame.Window(TITLE, (w, h), pos, resizable=True, opengl=True, allow_high_dpi=True,
                                            hidden=bool(os.environ.get("LINDEFENSE_HIDDEN")), maximized=maximized)
                self.win_ptr = ctypes.c_void_p(self.sdl.SDL_GetWindowFromID(self.window.id))
                # pygame-ce creates its own GL context for an opengl Window and makes it current again whenever the
                # window is resized. Render with that context: with a second context of our own, every frame after
                # the first resize was drawn into a context that was no longer current and the window went blank.
                self.gl_ctx = self.sdl.SDL_GL_GetCurrentContext() or self.sdl.SDL_GL_CreateContext(self.win_ptr)
                if not self.gl_ctx:
                    raise RuntimeError("no GL context")
                self.sdl.SDL_GL_MakeCurrent(self.win_ptr, ctypes.c_void_p(self.gl_ctx))
                # no vsync for hidden (automation) windows: SDL's macOS vsync waits on the display link and can
                # block forever in SDL_GL_SwapWindow for a window that is never shown
                self.sdl.SDL_GL_SetSwapInterval(0 if os.environ.get("LINDEFENSE_VSYNC") == "0"
                                                or os.environ.get("LINDEFENSE_HIDDEN") else 1)
                self.gr = skia.GrDirectContext.MakeGL()
                if self.gr is None:
                    raise RuntimeError("Skia GL context failed")
            except Exception as e:
                print("[render] GPU unavailable (%s); using the CPU renderer" % e, file=sys.stderr)
                self.gr = None
                self.gl_ctx = None
                try:
                    self.window.destroy()
                except Exception:
                    pass
        if self.gr is None:
            self.window = pygame.Window(TITLE, (w, h), pos, resizable=True, allow_high_dpi=True,
                                        hidden=bool(os.environ.get("LINDEFENSE_HIDDEN")), maximized=maximized)
            if self.sdl is None:
                try:
                    self.sdl = _sdl()
                except Exception:
                    self.sdl = None
            if self.sdl is not None:
                self.win_ptr = ctypes.c_void_p(self.sdl.SDL_GetWindowFromID(self.window.id))
        self.window.minimum_size = (MIN_W, MIN_H)
        self._install_icon()
        if DisplaySettings.get().fullscreen and not self._is_automation():
            self.set_fullscreen(True, save=False)   # SETTINGS > DISPLAY > FULLSCREEN, saved from the last session
        self._resize_surface()

    def _drawable_size(self):
        if self.gr is not None and self.sdl is not None:
            dw, dh = ctypes.c_int(), ctypes.c_int()
            self.sdl.SDL_GL_GetDrawableSize(self.win_ptr, ctypes.byref(dw), ctypes.byref(dh))
            return dw.value, dh.value
        surf = self.window.get_surface()
        return surf.get_width(), surf.get_height()

    def _ensure_gl_current(self, force_reset=False):
        """Makes the render context current again if anything switched contexts (pygame-ce does on resize) and
        tells Skia to forget the GL state it cached, which may no longer match."""
        if self.sdl.SDL_GL_GetCurrentContext() != self.gl_ctx:
            self.sdl.SDL_GL_MakeCurrent(self.win_ptr, ctypes.c_void_p(self.gl_ctx))
            force_reset = True
        if force_reset:
            self.gr.resetContext()

    def _resize_surface(self):
        if self.gr is not None:
            self._ensure_gl_current(force_reset=True)   # pygame's own resize handling may have touched GL state
        pw, ph = self._drawable_size()
        self.px_w, self.px_h = max(1, pw), max(1, ph)
        ww, wh = self.window.size
        self.dpr = self.px_w / float(max(1, ww))
        if self.gr is not None:
            self.surface = None   # release the old framebuffer wrapper before wrapping the resized one
            fb = skia.GrGLFramebufferInfo(0, 0x8058)   # GL_RGBA8
            target = skia.GrBackendRenderTarget(self.px_w, self.px_h, 4, 8, fb)
            self.surface = skia.Surface.MakeFromBackendRenderTarget(
                self.gr, target, skia.kBottomLeft_GrSurfaceOrigin, skia.kRGBA_8888_ColorType, skia.ColorSpace.MakeSRGB())
            if self.surface is None:   # no MSAA available
                target = skia.GrBackendRenderTarget(self.px_w, self.px_h, 0, 8, fb)
                self.surface = skia.Surface.MakeFromBackendRenderTarget(
                    self.gr, target, skia.kBottomLeft_GrSurfaceOrigin, skia.kRGBA_8888_ColorType, skia.ColorSpace.MakeSRGB())
        else:
            win_surf = self.window.get_surface()
            self.px_w, self.px_h = win_surf.get_size()
            self.surface = skia.Surface.MakeRasterN32Premul(self.px_w, self.px_h)
        self.root.fit(self.px_w, self.px_h)

    def _install_icon(self):
        try:
            from lindefense.ui.logo_emblem import LogoEmblem
            n = 256
            surf = skia.Surface.MakeRasterN32Premul(n, n)
            cv = surf.getCanvas()
            cv.clear(0)
            reset_canvas_state(cv)
            g = Graphics2D(cv)
            g.translate(n / 2.0, n / 2.0)
            e = LogoEmblem(n * 0.9)
            e.animate(0.4)
            e.paint(g)
            reset_canvas_state(cv)
            img = surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
            icon = pygame.image.frombuffer(img.tobytes(), (n, n), "RGBA")
            self.window.set_icon(icon)
        except Exception as e:
            print("[app] icon: %s" % e, file=sys.stderr)

    # ---------------------------------------------------------------- screens
    def _clear_screens(self):
        saved = self._leave_game()
        self._end_run(saved)
        self.root.remove_all()
        self.game_screen = self.map_select = self.menu = None

    def show_menu(self):
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.ui.menu_screen import MenuScreen
        self._clear_screens()
        self.menu = MenuScreen(self)
        self.root.add(self.menu)
        AudioManager.menu_music()
        self._settle_heap()

    def show_map_select(self):
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.ui.map_select_screen import MapSelectScreen
        self._clear_screens()
        self.map_select = MapSelectScreen(self)
        self.root.add(self.map_select)
        AudioManager.menu_music()
        self._settle_heap()

    @staticmethod
    def variance_for_players():
        """Patch Notes / Breaking News for new runs: the briefing's PATCH NOTES switch (saved), unless
        LINDEFENSE_VARIANCE=off forces them off."""
        from lindefense.sim.run_setup import RunOptions
        return RunOptions.get().patch_notes_on()

    def start_game(self, map_or_game, tutorial=False):
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.audio.sfx import Sfx
        from lindefense.sim.game import Game
        if isinstance(map_or_game, Game):
            self._start(map_or_game, tutorial)
            return
        from lindefense.sim.difficulty import Difficulty
        from lindefense.sim.run_setup import RunSetup
        self.start_run(RunSetup(map_or_game, Difficulty.get_selected(), None, (), self.variance_for_players()))

    def start_run(self, setup):
        """Starts a defense run from a briefing's RunSetup (map, difficulty, optional seed, challenge rules, Patch Notes,
        daily date) with the saved Hero Store collection."""
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.audio.sfx import Sfx
        from lindefense.sim.misc import AdminMode, AdminOption, HeroCollection
        AudioManager.sfx(Sfx.UI_SELECT)
        g = setup.create_game(HeroCollection.persistent(),
                              (AdminMode.is_on(AdminOption.UNLOCK_HEROES), AdminMode.is_on(AdminOption.INFINITE_MONEY),
                               AdminMode.is_on(AdminOption.INFINITE_HEALTH)))
        self._start(g, False)

    def replay_seed(self):
        from lindefense.sim.game import Game
        if self.game_screen is None:
            return
        old = self.game_screen.get_game()
        self._start(Game.fresh_copy(old, old.get_seed()), self._in_tutorial())

    def start_reverse(self, map_index):
        from lindefense.ai.reverse_match import ReverseMatch
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.audio.sfx import Sfx
        from lindefense.sim.difficulty import Difficulty
        from lindefense.sim.misc import AdminMode, AdminOption
        AudioManager.sfx(Sfx.UI_SELECT)
        g = ReverseMatch.create(map_index, time.perf_counter_ns(), Difficulty.get_selected())
        g.get_reverse().set_unlimited_credits(AdminMode.is_on(AdminOption.INFINITE_MONEY))
        self._start(g, False)

    def start_tutorial(self):
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.audio.sfx import Sfx
        from lindefense.map import maps
        from lindefense.sim.difficulty import Difficulty
        from lindefense.sim.game import Game
        from lindefense.variance import variance
        AudioManager.sfx(Sfx.UI_SELECT)
        self._start(Game(maps.create(0), variance.seed_next(), Difficulty.O1), True)

    def restart_level(self):
        from lindefense.ai.reverse_match import ReverseMatch
        from lindefense.sim.game import Game
        if self.game_screen is None:
            return
        old = self.game_screen.get_game()
        self._start(ReverseMatch.restart(old) if old.is_reverse() else Game.fresh_copy(old), self._in_tutorial())

    def _in_tutorial(self):
        """RESTART / RETRY / REPLAY SEED in the tutorial start the tutorial again: a plain match would be recorded and
        saved, replacing the player's saved run, while still using the tutorial's in-memory Hero Store."""
        return self.game_screen is not None and self.game_screen.get_tutorial() is not None

    def quit_level(self):
        self.show_map_select()

    def replay_run(self, map_index, difficulty, seed, notes=True, challenges=()):
        """REPLAY SEED from the run history: a fresh match on that map, difficulty and seed with that run's challenge
        rules and Patch Notes as then (only LINDEFENSE_VARIANCE=off overrides them), like REPLAY SEED on the end screen:
        the seed counts as chosen ("custom-seed"), so RESTART keeps it."""
        from lindefense.sim.run_setup import RunOptions, RunSetup
        self.start_run(RunSetup(map_index, difficulty, seed, challenges, notes and RunOptions.env_allows_patch_notes()))

    def _end_run(self, saved=False):
        """Leaving a match (menu, map select, restart, retry, closing the window) records it if it is still running.
        A run kept in the save slot is not recorded now: it is recorded when it is continued and finished."""
        gs = self.game_screen
        if gs is None:
            return
        if saved and gs.session is not None:
            gs.session.cancel()
        else:
            gs.end_run()

    def continue_run(self):
        """CONTINUE (main menu): restores the saved run exactly and opens it. A run saved mid-wave opens paused (the
        tactical pause: P resumes). A save that cannot be loaded is deleted and reported once on the main menu; nothing
        is raised."""
        from lindefense import savegame
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.audio.sfx import Sfx
        from lindefense.ui.cyber import Cyber
        slot = savegame.slot()
        try:
            game = slot.load()
            AudioManager.sfx(Sfx.UI_SELECT)
            game.set_paused(game.get_wave_manager().is_wave_active())
            self._start(game, False, restored=True)
        except Exception as e:
            print("[save] could not continue the saved run: %s: %s" % (type(e).__name__, e), file=sys.stderr)
            self.autosave = None   # never re-save a run that failed to come up
            slot.delete()
            self.show_menu()
            self.menu.show_notice(savegame.LOAD_FAILED_TEXT)
            return
        self.game_screen.flash_banner("RUN RESTORED  -  WAVE %d" % max(1, game.get_wave()), Cyber.CYAN, 3.0)

    @staticmethod
    def _record_replaced_save():
        """A new run replaces the saved one: the saved run was never finished, so it goes into the records now (as
        abandoned at its wave; a saved Freeplay run extends its campaign victory)."""
        from lindefense import savegame
        from lindefense.sim.records import Records, RunSession
        s = savegame.slot()
        if not s.exists():
            return
        try:
            old = s.load()
        except Exception:
            return   # unreadable: nothing to record
        RunSession(Records.persistent(), old).finish()

    def on_freeplay(self):
        """CONTINUE - FREEPLAY: the won run goes on, so it can be saved again (the victory deleted its save)."""
        from lindefense import savegame
        if self.game_screen is not None and getattr(self, "demo", None) is None:
            self.autosave = savegame.Autosave(self.game_screen.get_game(), False)

    def _start(self, game, tutorial, restored=False):
        from lindefense import savegame
        from lindefense.sim.records import Records, RunSession
        from lindefense.ui.game_screen import GameScreen
        self._clear_screens()
        demo = getattr(self, "demo", None) is not None   # the scripted demo leaves the player's saved run alone
        if not restored and not demo and savegame.can_save(game, tutorial):
            self._guarded("records", self._record_replaced_save)
            savegame.slot().delete()   # a new run on any map replaces the saved one
        self.game_screen = GameScreen(self, game, tutorial)
        self.game_screen.set_run_session(RunSession(Records.persistent(), game, tutorial))
        self.autosave = None if demo else savegame.Autosave(game, tutorial)
        self.root.add(self.game_screen)
        self._settle_heap()

    def _leave_game(self):
        """The game screen is going away (menu, map select, another match, closing the window): autosave the run.
        Returns True when the run is in the save slot afterwards."""
        a, self.autosave = getattr(self, "autosave", None), None
        if a is None:
            return False
        out = [False]
        self._guarded("autosave", lambda: out.__setitem__(0, bool(a.leave())))
        return out[0]   # True: the run waits in the save slot for CONTINUE

    @staticmethod
    def _settle_heap():
        """At a screen change: free the previous screen's garbage, then move everything still alive (the new screen,
        map art, fonts, sounds) out of the cyclic garbage collector's reach. During play Python's full collections
        otherwise re-walk those ~100k long-lived objects every so often, a 20-30 ms hitch each. Reference counting
        still frees frozen objects as usual; the next screen change unfreezes and collects what is left."""
        gc.unfreeze()
        gc.collect()
        gc.freeze()

    def quit(self):
        self.running = False

    # ---------------------------------------------------------------- accessors used by the screens / demo
    def get_root(self):
        return self.root

    def get_game_screen(self):
        return self.game_screen

    def get_map_select(self):
        return self.map_select

    def get_menu(self):
        return self.menu

    def get_game(self):
        return None if self.game_screen is None else self.game_screen.get_game()

    def get_g_canvas(self):
        return self.canvas

    def get_background_color(self):
        from lindefense.ui.ui import Ui
        return Ui.BG

    # ---------------------------------------------------------------- input
    def _logical(self, pos):
        x, y = pos
        return self.root.to_logical_x(x * self.dpr), self.root.to_logical_y(y * self.dpr)

    def _ev(self, ev):
        """Java-style MouseEvent (canvas pixel coordinates, DemoDriver) -> logical coordinates."""
        return self.root.to_logical_x(ev.get_x()), self.root.to_logical_y(ev.get_y())

    def resize_window(self, w, h):
        """Resizes the window to w x h canvas pixels (DemoDriver)."""
        self._self_moved_at = time.perf_counter()
        self.window.size = (max(MIN_W, int(round(w / self.dpr))), max(MIN_H, int(round(h / self.dpr))))
        self._resize_surface()

    def mouse_pressed(self, lx, ly=None, right=False):
        if ly is None:
            right = lx.get_button() == 3
            lx, ly = self._ev(lx)
        if self.game_screen is not None:
            self.game_screen.mouse_pressed(lx, ly, right)
        elif self.map_select is not None:
            self.map_select.mouse_pressed(lx, ly)
        elif self.menu is not None:
            self.menu.mouse_pressed(lx, ly)

    def mouse_moved(self, lx, ly=None):
        if ly is None:
            lx, ly = self._ev(lx)
        if self.game_screen is not None:
            self.game_screen.mouse_moved(lx, ly)
        elif self.map_select is not None:
            self.map_select.mouse_moved(lx, ly)
        elif self.menu is not None:
            self.menu.mouse_moved(lx, ly)

    def mouse_dragged(self, lx, ly=None):
        if ly is None:
            lx, ly = self._ev(lx)
        self.mouse_moved(lx, ly)
        if self.game_screen is not None:
            self.game_screen.mouse_dragged(lx, ly)
        elif self.map_select is None and self.menu is not None:
            self.menu.mouse_dragged(lx, ly)

    def mouse_released(self, *a):
        if self.game_screen is not None:
            self.game_screen.mouse_released()
        elif self.map_select is None and self.menu is not None:
            self.menu.mouse_released()

    def key_pressed(self, e):
        from lindefense.audio.audio_manager import AudioManager
        if self.is_fullscreen_key(e):   # works on every screen, even while SETTINGS takes typed text
            self.toggle_fullscreen()
            return
        if self.game_screen is None and self.menu is not None and self.menu.is_typing():
            self.menu.key_pressed(e)
            return
        if self.game_screen is None and self.map_select is not None and self.map_select.is_typing():
            self.map_select.key_pressed(e)   # the briefing's SEED field: M / N are letters there
            return
        am = AudioManager.get()
        if am is not None and e.get_key_code() in (KeyEvent.VK_M, KeyEvent.VK_N):
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

    def _handle(self, ev):
        t = ev.type
        if t == pygame.QUIT or (t == pygame.WINDOWCLOSE):
            self._close_requested()
        elif t == pygame.WINDOWFOCUSLOST:
            self._focus_lost(minimized=False)
        elif t == pygame.WINDOWMINIMIZED:
            self._focus_lost(minimized=True)
        elif t == pygame.WINDOWFOCUSGAINED:
            self._focus_recheck = False
        elif t in (pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED, pygame.WINDOWDISPLAYCHANGED):
            self._resize_surface()
            self._note_window_change()
        elif t in (pygame.WINDOWMOVED, pygame.WINDOWMAXIMIZED, pygame.WINDOWRESTORED):
            self._note_window_change()
        elif t == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
            lx, ly = self._logical(ev.pos)
            mods = pygame.key.get_mods()
            right = ev.button == 3 or bool(mods & pygame.KMOD_CTRL)
            self._dragging = True
            self.mouse_pressed(lx, ly, right)
        elif t == pygame.MOUSEBUTTONUP and ev.button in (1, 3):
            self._dragging = False
            self.mouse_released()
        elif t == pygame.MOUSEMOTION:
            lx, ly = self._logical(ev.pos)
            if self._dragging and ev.buttons and ev.buttons[0]:
                self.mouse_dragged(lx, ly)
            else:
                self.mouse_moved(lx, ly)
        elif t == pygame.KEYDOWN:
            ke = to_key_event(ev)
            if ke is not None:
                self.key_pressed(ke)

    # ---------------------------------------------------------------- match safety: window close, auto-pause
    CLOSE_DEDUP_SECONDS = 0.5   # one click on the close button sends WINDOWCLOSE and then QUIT
    FOCUS_GRACE_SECONDS = 1.0   # after the game moved / resized its own window (Palantir's System Takeover)

    def _init_match_safety(self):
        self._last_close_request = -1e9
        self._self_moved_at = -1e9
        self._focus_recheck = False

    @staticmethod
    def _is_automation():
        """Hidden, scripted-demo and smoke runs never wait for a player: they quit at once and never auto-pause."""
        return any(os.environ.get(k) for k in ("LINDEFENSE_HIDDEN", "LINDEFENSE_DEMO", "LINDEFENSE_SMOKE"))

    def _close_requested(self):
        """Window close button / Cmd+Q. During a live match the game shows a QUIT GAME? confirmation instead of quitting;
        a second close request while it shows, or closing anywhere else, quits."""
        now = time.perf_counter()
        repeat = now - self._last_close_request < self.CLOSE_DEDUP_SECONDS
        self._last_close_request = now
        if repeat:
            return
        if self._is_automation() or self.game_screen is None or not self.game_screen.request_window_close():
            self.running = False

    def _has_input_focus(self):
        try:
            if self.sdl is not None and self.win_ptr is not None:
                return bool(self.sdl.SDL_GetWindowFlags(self.win_ptr) & 0x200)   # SDL_WINDOW_INPUT_FOCUS
            return bool(pygame.key.get_focused())
        except Exception:
            return False

    def _moved_recently(self):
        return time.perf_counter() - self._self_moved_at < self.FOCUS_GRACE_SECONDS

    def _focus_lost(self, minimized):
        """The window lost focus or was minimised: pause a running match (the pause menu opens). A focus loss already undone
        is ignored, and one that arrives while the game itself is moving its window (Palantir's System Takeover) is only
        acted on if the window still lacks focus once the move has settled."""
        if self._is_automation() or self.game_screen is None:
            return
        if not minimized:
            if self._has_input_focus():
                return
            if self._moved_recently():
                self._focus_recheck = True
                return
        self.game_screen.auto_pause()

    def _check_deferred_focus(self):
        if not self._focus_recheck or self._moved_recently():
            return
        self._focus_recheck = False
        if self.game_screen is not None and not self._is_automation() and not self._has_input_focus():
            self.game_screen.auto_pause()

    # ---------------------------------------------------------------- display: full screen, window memory, FPS counter
    GEOMETRY_SAVE_DELAY = 0.75   # seconds after the last move / resize before the window geometry is written

    def _init_display(self, window_memory=None):
        from lindefense.ui.fps_counter import FpsCounter
        if window_memory is None:
            window_memory = WindowMemory.in_memory() if self._is_automation() else WindowMemory.persistent()
        self.window_memory = window_memory
        self.fps_counter = FpsCounter()
        self._win_rect = None        # last windowed (not full screen / maximised / minimised) bounds, screen points
        self._win_maximized = False
        self._geometry_dirty_at = None

    def _display_bounds(self, usable=True):
        """(x, y, w, h) of every connected display in screen points (the usable area without menu bar / dock / taskbar
        by default); the first is the main display."""
        out = []
        try:
            sdl = self.sdl if self.sdl is not None else _sdl()
            get = sdl.SDL_GetDisplayUsableBounds if usable else sdl.SDL_GetDisplayBounds
            for i in range(max(0, sdl.SDL_GetNumVideoDisplays())):
                r = _SDLRect()
                if get(i, ctypes.byref(r)) == 0 and r.w > 0 and r.h > 0:
                    out.append((r.x, r.y, r.w, r.h))
        except Exception:
            out = []
        if not out:
            try:
                dw, dh = pygame.display.get_desktop_sizes()[0]
                out = [(0, 0, dw, dh)]
            except Exception:
                pass
        return out

    def _restored_geometry(self):
        """(x, y, w, h, maximized) of the saved window moved onto a connected display, or None (first launch, automation)."""
        saved = self.window_memory.load() if self.window_memory is not None else None
        if saved is None:
            return None
        r = place_on_displays((saved["x"], saved["y"], saved["w"], saved["h"]), self._display_bounds(), (MIN_W, MIN_H))
        return None if r is None else r + (saved["maximized"],)

    def _window_flags(self):
        try:
            if self.sdl is not None and self.win_ptr is not None:
                return self.sdl.SDL_GetWindowFlags(self.win_ptr)
        except Exception:
            pass
        return 0

    def _fills_display(self):
        """The window covers its whole display: the system's own full screen (macOS green button or Window menu), which
        SDL does not flag."""
        try:
            idx = self.sdl.SDL_GetWindowDisplayIndex(self.win_ptr)
            r = _SDLRect()
            if idx < 0 or self.sdl.SDL_GetDisplayBounds(idx, ctypes.byref(r)) != 0:
                return False
            w, h = self.window.size
            return w >= r.w and h >= r.h
        except Exception:
            return False

    def is_fullscreen(self):
        if getattr(self, "window", None) is None:
            return False
        return bool(self._window_flags() & 0x1) or self._fills_display()   # SDL_WINDOW_FULLSCREEN(_DESKTOP)

    @staticmethod
    def is_fullscreen_key(e):
        """F11, or Cmd+Ctrl+F (the macOS full-screen shortcut)."""
        k = e.get_key_code()
        return k == KeyEvent.VK_F11 or (k == KeyEvent.VK_F and e.is_meta_down() and e.is_control_down())

    def toggle_fullscreen(self):
        """F11 / Cmd+Ctrl+F / SETTINGS > DISPLAY > FULLSCREEN. Returns the new state."""
        return self.set_fullscreen(not self.is_fullscreen())

    def set_fullscreen(self, on, save=True):
        """Desktop full screen (the display keeps its resolution) on or off. The drawing surface follows the new size at
        once (and again on the resize events that follow); Palantir's window grab leaves a full-screen window alone. The
        choice is saved for the next launch unless this is a hidden / demo / smoke run."""
        if getattr(self, "window", None) is None:
            return False
        on = bool(on)
        if on != self.is_fullscreen():
            self._note_window_change(follow=False)      # keep the windowed bounds to come back to (and to save)
            self._self_moved_at = time.perf_counter()   # our own switch: focus blips during it must not auto-pause
            try:
                if on:
                    self.window.set_fullscreen(desktop=True)
                else:
                    if not (self._window_flags() & 0x1):
                        self.window.set_fullscreen(desktop=True)   # the system's own full screen: adopt it to leave it
                    self.window.set_windowed()
            except Exception as ex:
                print("[app] full screen: %s" % ex, file=sys.stderr)
            self._self_moved_at = time.perf_counter()
            self._resize_surface()
        actual = self.is_fullscreen()
        ds = DisplaySettings.get()
        if save and not self._is_automation():
            ds.set_fullscreen(actual)
        else:
            ds.fullscreen = actual
        return actual

    def _note_window_change(self, follow=True):
        """The window moved / resized / was maximised or restored: remember its windowed geometry, saved a moment later
        (_flush_geometry) and on quit. Full screen and minimised windows keep the bounds from before; moves the game
        makes itself (Palantir's System Takeover, the scripted demo) are not remembered. With follow, a full screen
        entered or left with the system's own controls (macOS green button) updates the FULLSCREEN setting."""
        if getattr(self, "window_memory", None) is None or getattr(self, "window", None) is None:
            return
        flags = self._window_flags()
        if flags & 0x40:   # minimised
            return
        full = self.is_fullscreen()
        ds = DisplaySettings.get()
        if follow and ds.fullscreen != full and not self._is_automation() and not self._moved_recently():
            ds.set_fullscreen(full)
        if full or (self.window_grab is not None and self.window_grab.is_holding()) or self._moved_recently():
            return
        self._win_maximized = bool(flags & 0x80)
        if not self._win_maximized:
            x, y = self.window.position
            w, h = self.window.size
            self._win_rect = (int(x), int(y), int(w), int(h))
        self._geometry_dirty_at = time.perf_counter()

    def _flush_geometry(self, force=False):
        """Writes the remembered window geometry once it has been still for GEOMETRY_SAVE_DELAY (at once with force)."""
        if getattr(self, "window_memory", None) is None:
            return
        if not force and (self._geometry_dirty_at is None
                          or time.perf_counter() - self._geometry_dirty_at < self.GEOMETRY_SAVE_DELAY):
            return
        self._geometry_dirty_at = None
        if self._win_rect is not None:
            x, y, w, h = self._win_rect
            self.window_memory.save(x, y, w, h, self._win_maximized)

    # ---------------------------------------------------------------- frame loop
    def frame(self, dt):
        if (abs(self.root.get_scale() - min(self.px_w / 1600.0, self.px_h / 1000.0)) > 1e-6):
            self.root.fit(self.px_w, self.px_h)
        if self.game_screen is not None:
            self.game_screen.frame(dt)
            if self.autosave is not None:
                self.autosave.frame()
        elif self.menu is not None and self.menu.is_visible():
            self.menu.frame(dt)
        elif self.map_select is not None:
            self.map_select.frame(dt)
        if self.demo is not None:
            self.demo.frame(dt)
        if self.window_grab is not None:
            self.window_grab.frame(dt, self.get_game())

    def paint(self, present=True):
        """Draws the UI into the window's back buffer and shows it. present=False leaves the frame unpresented so
        it can be read back (a GL back buffer's contents are undefined after the swap)."""
        if self.gr is not None:
            self._ensure_gl_current()
        cv = self.surface.getCanvas()
        reset_canvas_state(cv)
        cv.clear(0xFF05070F)
        g = Graphics2D(cv)
        self.root.paint(g)
        if DisplaySettings.get().show_fps:
            self.fps_counter.paint(g, self.root)   # SETTINGS > DISPLAY > FPS COUNTER, over every screen
        reset_canvas_state(cv)
        PaintCache.next_frame()
        if self.gr is not None:
            self.surface.flushAndSubmit()
            if present:
                self.sdl.SDL_GL_SwapWindow(self.win_ptr)
        elif present:
            self._present_cpu()

    def _present_cpu(self):
        """CPU renderer: copies the finished frame into the window surface and flips it. When the window surface is
        32-bit xRGB (BGRA in memory, the usual case) the pixels are read straight into it, about 25x cheaper than
        converting through a numpy array, a bytes copy and an alpha-blended blit (which cost ~12 ms a Retina frame)."""
        win = self.window.get_surface()
        if (sys.byteorder == "little" and win.get_size() == (self.px_w, self.px_h) and win.get_bytesize() == 4
                and win.get_masks()[:3] == (0xFF0000, 0xFF00, 0xFF)):
            info = skia.ImageInfo.Make(self.px_w, self.px_h, skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)
            view = win.get_view("1")   # locks the surface until the view is released
            try:
                ok = self.surface.readPixels(info, view, win.get_pitch(), 0, 0)
            finally:
                del view
            if ok:
                self.window.flip()
                return
        img = self.surface.makeImageSnapshot().toarray(colorType=skia.kBGRA_8888_ColorType)
        win.blit(pygame.image.frombuffer(img, (self.px_w, self.px_h), "BGRA"), (0, 0))
        self.window.flip()

    # ---------------------------------------------------------------- live resize
    _SDL_WINDOWEVENT = 0x200
    _WINDOWEVENT_EXPOSED, _WINDOWEVENT_SIZE_CHANGED = 3, 6
    _EventWatch = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)

    def _install_live_resize(self):
        """While the player drags a window edge, macOS (and Windows) keep the app inside pygame.event.get() until
        the mouse is released, so the loop can't run and the window shows a stretched copy of the last frame. An SDL
        event watch still sees every resize during the drag: use it to keep the game running and redraw."""
        if self.sdl is None or self._live_watch is not None:
            return
        try:
            self.sdl.SDL_AddEventWatch.argtypes = [self._EventWatch, ctypes.c_void_p]
            self.sdl.SDL_DelEventWatch.argtypes = [self._EventWatch, ctypes.c_void_p]
            self._live_watch = self._EventWatch(self._on_sdl_event)   # keep a reference: SDL holds a raw pointer
            self.sdl.SDL_AddEventWatch(self._live_watch, None)
        except Exception as e:
            self._live_watch = None
            print("[app] live resize unavailable: %s" % e, file=sys.stderr)

    def _remove_live_resize(self):
        if self._live_watch is not None:
            try:
                self.sdl.SDL_DelEventWatch(self._live_watch, None)
            except Exception:
                pass
            self._live_watch = None

    def _on_sdl_event(self, _userdata, event):
        # Only act while the main loop is blocked in pygame.event.get(): resizes the game makes itself (the scripted
        # demo, Palantir's window grab) happen inside frame() and must not re-enter it.
        if not self._pumping or self._live_busy or not self.running or not event:
            return 1
        try:
            if ctypes.cast(event, ctypes.POINTER(ctypes.c_uint32))[0] != self._SDL_WINDOWEVENT:
                return 1
            kind = ctypes.cast(event, ctypes.POINTER(ctypes.c_uint8))[12]   # SDL_WindowEvent.event
            if kind not in (self._WINDOWEVENT_SIZE_CHANGED, self._WINDOWEVENT_EXPOSED):
                return 1
            self._live_busy = True
            if kind == self._WINDOWEVENT_SIZE_CHANGED:
                self._resize_surface()
            self._tick()
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            self._live_busy = False
        return 1

    def _tick(self):
        """Advances the game by the real time since the last frame (capped at 0.1 s) and paints once."""
        now = time.perf_counter()
        self.fps_counter.tick(now - self._last_tick)
        dt = min(0.1, now - self._last_tick)
        self._last_tick = now
        self._guarded("frame", self.frame, dt)
        self._guarded("paint", self.paint)
        return now

    def _guarded(self, what, fn, *args):
        """Runs one input / frame / paint step. An exception is reported and the game keeps running, as an exception
        on Java's event-dispatch thread was, instead of closing the window. Repeats of the same error are counted,
        not reprinted every frame."""
        try:
            fn(*args)
        except Exception:
            import traceback
            tb = traceback.format_exc()
            n = self._errors.get(tb, 0) + 1
            if n == 1 and len(self._errors) >= 200:
                self._errors.clear()
            self._errors[tb] = n
            if n == 1:
                print("[app] exception in %s (the game keeps running):\n%s" % (what, tb), file=sys.stderr)
            elif n in (10, 100, 1000) or n % 10000 == 0:
                print("[app] the same exception in %s again (%d times so far)" % (what, n), file=sys.stderr)

    def run(self):
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.ui.graphics_settings import GraphicsSettings
        from lindefense.ui.window_grab import WindowGrab
        from lindefense.sim import records
        AudioManager.install()
        records.restore_difficulty()
        self.show_menu()
        if os.environ.get("LINDEFENSE_START"):   # dev shortcut: jump straight into a match on map N
            self.start_game(int(os.environ["LINDEFENSE_START"]))
            gs = self.game_screen
            if os.environ.get("LINDEFENSE_START_WAVES"):
                g = gs.get_game()
                g.add_cash(20000, None)
                g.get_wave_manager().set_auto_start(True)
                g.start_next_wave()
        if os.environ.get("LINDEFENSE_CONTINUE"):   # dev shortcut: CONTINUE the saved run at once
            self.continue_run()
        demo_dir = os.environ.get("LINDEFENSE_DEMO")
        if demo_dir:
            from lindefense.ui.demo_driver import DemoDriver
            self.demo = DemoDriver(self, demo_dir)
        self.window_grab = WindowGrab.create(_WindowAdapter(self), self.demo is not None)
        self._last_tick = time.perf_counter()
        self._install_live_resize()
        smoke = os.environ.get("LINDEFENSE_SMOKE")   # "<seconds>[:<screenshot.png>]": run, screenshot, quit
        smoke_end = smoke_png = None
        frames = 0
        if smoke:
            sec, _, smoke_png = smoke.partition(":")
            smoke_end = time.perf_counter() + float(sec)
        while self.running:
            if smoke_end is not None and time.perf_counter() >= smoke_end:
                if smoke_png:
                    self.paint(present=False)   # read back a fresh frame, not a presented (undefined) back buffer
                    self.surface.makeImageSnapshot().save(smoke_png, skia.kPNG)
                print("[smoke] %d frames, %.1f fps, %dx%d px (dpr %.1f), renderer %s" % (
                    frames, frames / float(smoke.partition(":")[0]), self.px_w, self.px_h, self.dpr,
                    "gpu" if self.gr is not None else "cpu"))
                break
            frames += 1
            self._pumping = True
            try:
                events = pygame.event.get()
            finally:
                self._pumping = False
            for ev in events:
                self._guarded("input", self._handle, ev)
                if not self.running:
                    break
            if not self.running:
                break
            self._guarded("focus", self._check_deferred_focus)
            self._guarded("geometry", self._flush_geometry)
            # the pixel size can change without a resize event (the window dragged to a display with another scale,
            # the display's scaling changed): keep the canvas at the drawable's real size
            pw, ph = self._drawable_size()
            if (max(1, pw), max(1, ph)) != (self.px_w, self.px_h):
                self._guarded("resize", self._resize_surface)
            now = self._tick()
            delay = GraphicsSettings.get().frame_delay_ms() / 1000.0
            spare = delay - (time.perf_counter() - now)
            if spare > 0.001:
                time.sleep(spare)   # SETTINGS > DISPLAY > MAX FPS (vsync additionally aligns the GPU path)
        self._remove_live_resize()
        saved = self._leave_game()
        self._guarded("records", self._end_run, saved)
        self._guarded("geometry", self._flush_geometry, True)
        AudioManager.get() and AudioManager.get().save_settings()
        pygame.quit()


# ====================================================================== key translation
_SPECIAL = {
    pygame.K_RETURN: KeyEvent.VK_ENTER, pygame.K_KP_ENTER: KeyEvent.VK_ENTER, pygame.K_BACKSPACE: KeyEvent.VK_BACK_SPACE,
    pygame.K_TAB: KeyEvent.VK_TAB, pygame.K_ESCAPE: KeyEvent.VK_ESCAPE, pygame.K_SPACE: KeyEvent.VK_SPACE,
    pygame.K_LEFT: KeyEvent.VK_LEFT, pygame.K_RIGHT: KeyEvent.VK_RIGHT, pygame.K_UP: KeyEvent.VK_UP,
    pygame.K_DOWN: KeyEvent.VK_DOWN, pygame.K_DELETE: KeyEvent.VK_DELETE, pygame.K_HOME: KeyEvent.VK_HOME,
    pygame.K_END: KeyEvent.VK_END, pygame.K_PAGEUP: KeyEvent.VK_PAGE_UP, pygame.K_PAGEDOWN: KeyEvent.VK_PAGE_DOWN,
    pygame.K_MINUS: KeyEvent.VK_MINUS, pygame.K_EQUALS: KeyEvent.VK_EQUALS, pygame.K_COMMA: KeyEvent.VK_COMMA,
    pygame.K_PERIOD: KeyEvent.VK_PERIOD, pygame.K_SLASH: KeyEvent.VK_SLASH, pygame.K_SEMICOLON: KeyEvent.VK_SEMICOLON,
    pygame.K_QUOTE: KeyEvent.VK_QUOTE, pygame.K_LEFTBRACKET: KeyEvent.VK_OPEN_BRACKET,
    pygame.K_RIGHTBRACKET: KeyEvent.VK_CLOSE_BRACKET, pygame.K_BACKSLASH: KeyEvent.VK_BACK_SLASH,
    pygame.K_BACKQUOTE: KeyEvent.VK_BACK_QUOTE, pygame.K_LSHIFT: KeyEvent.VK_SHIFT, pygame.K_RSHIFT: KeyEvent.VK_SHIFT,
    pygame.K_LCTRL: KeyEvent.VK_CONTROL, pygame.K_RCTRL: KeyEvent.VK_CONTROL, pygame.K_LALT: KeyEvent.VK_ALT,
    pygame.K_RALT: KeyEvent.VK_ALT, pygame.K_LMETA: KeyEvent.VK_META, pygame.K_RMETA: KeyEvent.VK_META,
    pygame.K_KP_PLUS: KeyEvent.VK_ADD, pygame.K_KP_MINUS: KeyEvent.VK_SUBTRACT,
}
# keypad digits -> VK_NUMPAD0..9 (SDL's keypad codes are not contiguous: KP_1..KP_9 come before KP_0)
_SPECIAL.update({getattr(pygame, "K_KP%d" % i): 96 + i for i in range(10)})


def to_key_event(ev):
    k = ev.key
    code = None
    if pygame.K_a <= k <= pygame.K_z:
        code = 65 + (k - pygame.K_a)
    elif pygame.K_0 <= k <= pygame.K_9:
        code = 48 + (k - pygame.K_0)
    elif pygame.K_F1 <= k <= pygame.K_F12:
        code = 112 + (k - pygame.K_F1)
    else:
        code = _SPECIAL.get(k)
    if code is None:
        code = 0
    m = ev.mod
    mods = (1 if m & pygame.KMOD_SHIFT else 0) | (2 if m & pygame.KMOD_CTRL else 0) | (4 if m & pygame.KMOD_META else 0) \
        | (8 if m & pygame.KMOD_ALT else 0)
    ch = ev.unicode if getattr(ev, "unicode", "") else KeyEvent.CHAR_UNDEFINED
    return KeyEvent(None, KeyEvent.KEY_PRESSED, int(time.time() * 1000), mods, code, ch)


def main():
    app = LindefenseApp()
    app.run()


if __name__ == "__main__":
    main()
