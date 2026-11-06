"""Lindefense desktop app: a native pygame-ce window rendered with Skia (replaces the Java LindefenseProgram).

Rendering: the whole UI is one ScaledLayer laid out in a fixed 1600x1000 logical space. Every frame it is painted by
Skia straight into the window's OpenGL framebuffer at the display's native (Retina) pixel resolution, anti-aliased,
so text and vector art stay razor sharp at any window size. Without OpenGL the same picture is rasterised on the
CPU into the window surface.

Frame loop: the cap (30 / 60 / 120 fps, SETTINGS > DISPLAY) comes from GraphicsSettings; each frame advances the
active screen by the real elapsed time (capped at 0.1 s), runs the window grab, then paints once. Input arrives as
pygame events and is translated to the Java-style calls the ported screens expect (logical coordinates, KeyEvent
virtual-key codes).
"""
import ctypes
import glob
import os
import sys
import time

import pygame
import skia

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
    lib.SDL_GL_SwapWindow.argtypes = [ctypes.c_void_p]
    lib.SDL_GL_GetDrawableSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    lib.SDL_GL_SetSwapInterval.argtypes = [ctypes.c_int]
    lib.SDL_GL_SetAttribute.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.SDL_GetWindowFlags.restype = ctypes.c_uint32
    lib.SDL_GetWindowFlags.argtypes = [ctypes.c_void_p]
    lib.SDL_GetWindowDisplayIndex.argtypes = [ctypes.c_void_p]
    lib.SDL_GetDisplayUsableBounds.argtypes = [ctypes.c_int, ctypes.c_void_p]
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
        w = self.app.window
        w.position = (r.x, r.y)
        w.size = (max(MIN_W, r.width), max(MIN_H, r.height))

    def is_showing(self):
        return True

    def is_maximized_or_full_screen(self):
        flags = self.app.sdl.SDL_GetWindowFlags(self.app.win_ptr) if self.app.sdl else 0
        return bool(flags & (0x1 | 0x80 | 0x40 | 0x1000))   # fullscreen | maximized | minimized | fullscreen desktop

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

    def __init__(self, demo_dir=None):
        from lindefense.ui.scaled_layer import ScaledLayer
        pygame.init()
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
        self.running = True
        self._dragging = False
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
        use_gl = os.environ.get("LINDEFENSE_RENDERER", "gpu").lower() != "cpu"
        if use_gl:
            try:
                self.sdl = _sdl()
                # GL 3.2 core, 8-bit stencil, 4x MSAA on the default framebuffer
                for attr, val in ((17, 3), (18, 2), (21, 1), (7, 8), (13, 1), (14, 4)):
                    self.sdl.SDL_GL_SetAttribute(attr, val)
                self.window = pygame.Window(TITLE, (w, h), resizable=True, opengl=True, allow_high_dpi=True,
                                            hidden=bool(os.environ.get("LINDEFENSE_HIDDEN")))
                self.win_ptr = ctypes.c_void_p(self.sdl.SDL_GetWindowFromID(self.window.id))
                self.gl_ctx = self.sdl.SDL_GL_CreateContext(self.win_ptr)
                if not self.gl_ctx:
                    raise RuntimeError("no GL context")
                self.sdl.SDL_GL_MakeCurrent(self.win_ptr, ctypes.c_void_p(self.gl_ctx))
                self.sdl.SDL_GL_SetSwapInterval(0 if os.environ.get("LINDEFENSE_VSYNC") == "0" else 1)
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
            self.window = pygame.Window(TITLE, (w, h), resizable=True, allow_high_dpi=True,
                                        hidden=bool(os.environ.get("LINDEFENSE_HIDDEN")))
            if self.sdl is None:
                try:
                    self.sdl = _sdl()
                except Exception:
                    self.sdl = None
            if self.sdl is not None:
                self.win_ptr = ctypes.c_void_p(self.sdl.SDL_GetWindowFromID(self.window.id))
        self.window.minimum_size = (MIN_W, MIN_H)
        self._install_icon()
        self._resize_surface()

    def _drawable_size(self):
        if self.gr is not None and self.sdl is not None:
            dw, dh = ctypes.c_int(), ctypes.c_int()
            self.sdl.SDL_GL_GetDrawableSize(self.win_ptr, ctypes.byref(dw), ctypes.byref(dh))
            return dw.value, dh.value
        surf = self.window.get_surface()
        return surf.get_width(), surf.get_height()

    def _resize_surface(self):
        pw, ph = self._drawable_size()
        self.px_w, self.px_h = max(1, pw), max(1, ph)
        ww, wh = self.window.size
        self.dpr = self.px_w / float(max(1, ww))
        if self.gr is not None:
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
        self.root.remove_all()
        self.game_screen = self.map_select = self.menu = None

    def show_menu(self):
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.ui.menu_screen import MenuScreen
        self._clear_screens()
        self.menu = MenuScreen(self)
        self.root.add(self.menu)
        AudioManager.menu_music()

    def show_map_select(self):
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.ui.map_select_screen import MapSelectScreen
        self._clear_screens()
        self.map_select = MapSelectScreen(self)
        self.root.add(self.map_select)
        AudioManager.menu_music()

    @staticmethod
    def variance_for_players():
        v = os.environ.get("LINDEFENSE_VARIANCE")
        return v is None or v.lower() not in ("off", "false")

    def start_game(self, map_or_game, tutorial=False):
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.audio.sfx import Sfx
        from lindefense.sim.game import Game
        if isinstance(map_or_game, Game):
            self._start(map_or_game, tutorial)
            return
        from lindefense.map import maps
        from lindefense.sim.difficulty import Difficulty
        from lindefense.sim.misc import AdminMode, AdminOption, HeroCollection
        from lindefense.variance import variance
        AudioManager.sfx(Sfx.UI_SELECT)
        g = Game(maps.create(map_or_game), variance.seed_next(), Difficulty.get_selected())
        g.set_hero_collection(HeroCollection.persistent())
        g.set_admin(AdminMode.is_on(AdminOption.UNLOCK_HEROES), AdminMode.is_on(AdminOption.INFINITE_MONEY),
                    AdminMode.is_on(AdminOption.INFINITE_HEALTH))
        if self.variance_for_players():
            g.get_variance().enable()
        self._start(g, False)

    def replay_seed(self):
        from lindefense.sim.game import Game
        if self.game_screen is None:
            return
        old = self.game_screen.get_game()
        self._start(Game.fresh_copy(old, old.get_seed()), False)

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
        self._start(ReverseMatch.restart(old) if old.is_reverse() else Game.fresh_copy(old), False)

    def quit_level(self):
        self.show_map_select()

    def _start(self, game, tutorial):
        from lindefense.ui.game_screen import GameScreen
        self._clear_screens()
        self.game_screen = GameScreen(self, game, tutorial)
        self.root.add(self.game_screen)

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
        if self.game_screen is None and self.menu is not None and self.menu.is_typing():
            self.menu.key_pressed(e)
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
            self.running = False
        elif t in (pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED, pygame.WINDOWDISPLAYCHANGED):
            self._resize_surface()
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

    # ---------------------------------------------------------------- frame loop
    def frame(self, dt):
        if (abs(self.root.get_scale() - min(self.px_w / 1600.0, self.px_h / 1000.0)) > 1e-6):
            self.root.fit(self.px_w, self.px_h)
        if self.game_screen is not None:
            self.game_screen.frame(dt)
        elif self.menu is not None and self.menu.is_visible():
            self.menu.frame(dt)
        elif self.map_select is not None:
            self.map_select.frame(dt)
        if self.demo is not None:
            self.demo.frame(dt)
        if self.window_grab is not None:
            self.window_grab.frame(dt, self.get_game())

    def paint(self):
        cv = self.surface.getCanvas()
        reset_canvas_state(cv)
        cv.clear(0xFF05070F)
        g = Graphics2D(cv)
        self.root.paint(g)
        reset_canvas_state(cv)
        if self.gr is not None:
            self.surface.flushAndSubmit()
            self.sdl.SDL_GL_SwapWindow(self.win_ptr)
        else:
            img = self.surface.makeImageSnapshot().toarray(colorType=skia.kBGRA_8888_ColorType)
            win = self.window.get_surface()
            pygame.image.frombuffer(img.tobytes(), (self.px_w, self.px_h), "BGRA")
            win.blit(pygame.image.frombuffer(img.tobytes(), (self.px_w, self.px_h), "BGRA"), (0, 0))
            self.window.flip()

    def run(self):
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.ui.graphics_settings import GraphicsSettings
        from lindefense.ui.window_grab import WindowGrab
        AudioManager.install()
        self.show_menu()
        if os.environ.get("LINDEFENSE_START"):   # dev shortcut: jump straight into a match on map N
            self.start_game(int(os.environ["LINDEFENSE_START"]))
            gs = self.game_screen
            if os.environ.get("LINDEFENSE_START_WAVES"):
                g = gs.get_game()
                g.add_cash(20000, None)
                g.get_wave_manager().set_auto_start(True)
                g.start_next_wave()
        demo_dir = os.environ.get("LINDEFENSE_DEMO")
        if demo_dir:
            from lindefense.ui.demo_driver import DemoDriver
            self.demo = DemoDriver(self, demo_dir)
        self.window_grab = WindowGrab.create(_WindowAdapter(self), self.demo is not None)
        last = time.perf_counter()
        smoke = os.environ.get("LINDEFENSE_SMOKE")   # "<seconds>[:<screenshot.png>]": run, screenshot, quit
        smoke_end = smoke_png = None
        frames = 0
        if smoke:
            sec, _, smoke_png = smoke.partition(":")
            smoke_end = time.perf_counter() + float(sec)
        while self.running:
            if smoke_end is not None and time.perf_counter() >= smoke_end:
                if smoke_png:
                    self.surface.makeImageSnapshot().save(smoke_png, skia.kPNG)
                print("[smoke] %d frames, %.1f fps, %dx%d px (dpr %.1f), renderer %s" % (
                    frames, frames / float(smoke.partition(":")[0]), self.px_w, self.px_h, self.dpr,
                    "gpu" if self.gr is not None else "cpu"))
                break
            frames += 1
            for ev in pygame.event.get():
                self._handle(ev)
                if not self.running:
                    break
            if not self.running:
                break
            now = time.perf_counter()
            dt = min(0.1, now - last)
            last = now
            self.frame(dt)
            self.paint()
            delay = GraphicsSettings.get().frame_delay_ms() / 1000.0
            spare = delay - (time.perf_counter() - now)
            if spare > 0.001:
                time.sleep(spare)   # SETTINGS > DISPLAY > MAX FPS (vsync additionally aligns the GPU path)
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


def to_key_event(ev):
    k = ev.key
    code = None
    if pygame.K_a <= k <= pygame.K_z:
        code = 65 + (k - pygame.K_a)
    elif pygame.K_0 <= k <= pygame.K_9:
        code = 48 + (k - pygame.K_0)
    elif pygame.K_KP0 <= k <= pygame.K_KP9:
        code = 96 + (k - pygame.K_KP0)
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
