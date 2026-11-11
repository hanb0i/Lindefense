"""Out-of-match screens: main menu (SETTINGS panel, admin code typing, HELP), catalog, patch-notes draft, display fonts and
the pygame -> KeyEvent key translation. Screens are built offscreen; nothing opens a window."""
import pygame
import pytest

from kit import new_game
from lindefense import prefs
from lindefense.sim.misc import AdminMode, AdminOption
from lindefense.ui.acm import GCompound
from lindefense.ui.catalog_screen import CatalogScreen
from lindefense.ui.cyber import Cyber
from lindefense.ui.jawt import Font, KeyEvent
from lindefense.ui.menu_screen import MenuScreen
from lindefense.ui.patch_notes_view import PatchNotesView
from lindefense.ui.ui import Ui


@pytest.fixture(autouse=True)
def _prefs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    prefs._nodes.clear()
    AdminMode._unlocked, AdminMode._options = None, {}
    yield
    prefs._nodes.clear()
    AdminMode._unlocked, AdminMode._options = None, {}


class _App:
    """The parts of LindefenseApp the menu screen calls."""

    def __init__(self):
        self.calls = []

    def show_map_select(self):
        self.calls.append("map_select")

    def show_campaign(self, briefing=None):
        self.calls.append("campaign")

    def start_tutorial(self):
        self.calls.append("tutorial")

    def quit(self):
        self.calls.append("quit")

    def continue_run(self):
        self.calls.append("continue")


def _key(code, ch=KeyEvent.CHAR_UNDEFINED, mods=0):
    return KeyEvent(None, KeyEvent.KEY_PRESSED, 0, mods, code, ch)


def _type(m, text):
    for ch in text:
        if ch.isupper():
            m.key_pressed(_key(KeyEvent.VK_SHIFT, mods=1))   # Shift's own key press carries no character
        m.key_pressed(_key(ord(ch.upper()), ch, 1 if ch.isupper() else 0))


def _center(b):
    return b.get_x() + b.get_width() / 2, b.get_y() + b.get_height() / 2


def test_settings_panel_frames_and_takes_the_typed_code(check):
    m = MenuScreen(_App())
    m.toggle_settings()
    check(m.is_typing(), "SETTINGS captures typed text")
    for _ in range(3):
        m.frame(0.05)   # used to raise NotImplementedError('assignment in expression') every frame
    _type(m, "Lindeveloper")
    check(m.code_input.to_string() == "Lindeveloper", "Shift + letters type the code (got %r)" % m.code_input.to_string())
    m.key_pressed(_key(KeyEvent.VK_LEFT))
    m.key_pressed(_key(KeyEvent.VK_BACK_SPACE, "\b"))
    check(m.code_input.to_string() == "Lindevelope", "keys without a character type nothing; Backspace deletes one")
    m.key_pressed(_key(KeyEvent.VK_R, "r"))
    m.key_pressed(_key(KeyEvent.VK_ENTER, "\r"))
    check(AdminMode.is_unlocked(), "Enter submits the code")
    check(m.code_feedback.get_label().startswith("Code accepted"), "accepted feedback shown")
    for _ in range(90):
        m.frame(0.05)
    check(m.code_feedback.get_label() == "", "the feedback line clears after its 4 s")
    m.key_pressed(_key(KeyEvent.VK_ESCAPE))
    check(not m.is_typing(), "Esc closes SETTINGS")


def test_admin_checklist_buttons_toggle_their_own_cheat(check):
    m = MenuScreen(_App())
    m.toggle_settings()
    check(AdminMode.try_code("lindeveloper"), "code accepted")
    m.refresh_settings()
    for i, o in enumerate(AdminOption):
        m.mouse_pressed(*_center(m.option_buttons[i]))
        on = {x for x in AdminOption if AdminMode.is_on(x)}
        check(on == set(list(AdminOption)[:i + 1]), "clicking %s switches on exactly that cheat (on: %s)" % (o.name, sorted(x.name for x in on)))
    m.mouse_pressed(*_center(m.f_disable_admin))
    check(not AdminMode.is_unlocked() and not AdminMode.any_on(), "LOCK ADMIN switches everything off")


def test_help_panel_is_modal(check):
    app = _App()
    m = MenuScreen(app)
    m.skip_intro()
    quit_btn = next(b for b in m.buttons if b.get_parent() is m and b.text.get_label() == "QUIT")
    help_close = next(b for b in m.buttons if b.get_parent() is m.help)
    m.toggle_help()
    m.mouse_pressed(*_center(quit_btn))
    m.mouse_pressed(800, 513)   # CAMPAIGN, under the help text
    check(app.calls == [] and m.help_shown, "menu buttons under the HELP panel do not fire (calls %s)" % app.calls)
    m.mouse_pressed(*_center(help_close))
    check(not m.help_shown, "HELP's CLOSE closes it")
    m.mouse_pressed(*_center(quit_btn))
    check(app.calls == ["quit"], "QUIT works once HELP is closed")


def test_catalog_tabs_and_cards_open_their_own_entry(check):
    c = CatalogScreen(None)
    for i, t in enumerate(CatalogScreen.Tab):
        c.mouse_pressed(*_center(c.tabs[i]))
        check(c.get_tab() is t, "tab button %d opens %s (got %s)" % (i, t, c.get_tab()))
    c.set_tab(CatalogScreen.Tab.ENEMIES)
    for i in (0, 4, len(c.grid_buttons) - 1):
        c.mouse_pressed(*_center(c.grid_buttons[i]))
        check(c.detail_open and c.selected == i, "card %d opens entry %d (got %d)" % (i, i, c.selected))
        c.mouse_pressed(*_center(c.close_detail_btn))
        check(not c.detail_open, "X closes the detail card")


def test_patch_note_draft_cards_ship_their_own_card(check):
    g = new_game(0)
    g.get_variance().enable()
    check(g.get_variance().is_draft_pending() and len(g.get_variance().get_offer()) == 3, "launch draft offers three cards")
    picked = []
    buttons = []
    PatchNotesView.build_draft(GCompound(), buttons, g, lambda i: picked.append(i))
    for b in buttons:
        b.click()
    check(picked == [0, 0, 1, 1, 2, 2], "each card area and SHIP IT button picks its own card (got %s)" % picked)


def test_small_display_fonts_keep_their_size(check):
    for size in (8, 11, 12):
        f = Cyber.display(Font.BOLD, size)
        check(f.get_size2d() >= 9 and f.get_style() == Cyber.display(Font.BOLD, 24).get_style(),
              "display(BOLD, %d) is a readable font (size %s, style %s)" % (size, f.get_size2d(), f.get_style()))
    foot = Ui.label("PYTHON + SKIA GRAPHICS  •  RESIZE THE WINDOW FREELY", 0, 0, MenuScreen.menu_font(Font.PLAIN, 12), Cyber.TEXT)
    check(foot.get_width() > 250, "the menu footer is drawn at its size (width %.1f)" % foot.get_width())
    c = Cyber.display_compact(Font.BOLD, 9)
    check(c.get_size2d() >= 9, "display_compact keeps its 9 pt floor (size %s)" % c.get_size2d())


def test_key_translation(check):
    from lindefense.app import to_key_event

    def ev(k, uni="", mod=0):
        return to_key_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode=uni, scancode=0))

    for i in range(10):
        check(ev(getattr(pygame, "K_KP%d" % i), str(i)).get_key_code() == 96 + i, "keypad %d -> VK_NUMPAD%d" % (i, i))
        check(ev(getattr(pygame, "K_%d" % i), str(i)).get_key_code() == 48 + i, "digit %d -> VK_%d" % (i, i))
    a = ev(pygame.K_a, "A", pygame.KMOD_LSHIFT)
    check(a.get_key_code() == KeyEvent.VK_A and a.get_key_char() == "A" and a.is_shift_down(), "Shift+A")
    s = ev(pygame.K_LSHIFT, "", pygame.KMOD_LSHIFT)
    check(s.get_key_code() == KeyEvent.VK_SHIFT and s.get_key_char() == KeyEvent.CHAR_UNDEFINED, "Shift alone has no character")
    check(ev(pygame.K_BACKSPACE, "\b").get_key_code() == KeyEvent.VK_BACK_SPACE, "Backspace")
    check(ev(pygame.K_RETURN, "\r").get_key_code() == KeyEvent.VK_ENTER and ev(pygame.K_KP_ENTER, "\r").get_key_code() == KeyEvent.VK_ENTER, "Enter")
    check(ev(pygame.K_ESCAPE, "\x1b").get_key_code() == KeyEvent.VK_ESCAPE, "Escape")
    check(ev(pygame.K_F1).get_key_code() == KeyEvent.VK_F1 and ev(pygame.K_F12).get_key_code() == KeyEvent.VK_F12, "F keys")


STACK = ["CAMPAIGN", "CLASSIC", "TUTORIAL", "CATALOG", "RECORDS", "HOW TO PLAY", "SETTINGS", "QUIT"]


def _menu_buttons(m):
    return [b for b in m.buttons if b.get_parent() is m]


def test_continue_only_with_a_saved_run(check):
    from lindefense import savegame
    from lindefense.sim.difficulty import Difficulty
    from lindefense.sim.game import Game
    from lindefense.map import maps
    plain = MenuScreen(_App())
    check(plain.continue_button is None, "no saved run: no CONTINUE")
    labels = [b.text.get_label() for b in _menu_buttons(plain)]
    check(labels == STACK, "the usual stack (%s)" % labels)
    rows = [0, 1, 1, 2, 2, 3, 4, 5]   # CLASSIC + TUTORIAL and CATALOG + RECORDS share a row: still six rows
    check([b.get_y() for b in _menu_buttons(plain)] == [488 + 58 * r for r in rows], "at the usual positions")
    first = _menu_buttons(plain)[0]
    check(first.w == 300 and first.get_x() == 650, "CAMPAIGN is the full-width first button")
    pairs = _menu_buttons(plain)[1:3]
    check([b.get_x() for b in pairs] == [650, 804] and all(b.w == 146 for b in pairs), "CLASSIC | TUTORIAL")
    app0 = _App()
    m0 = MenuScreen(app0)
    m0.skip_intro()
    for b in _menu_buttons(m0)[:3]:
        m0.mouse_pressed(*_center(b))
    check(app0.calls == ["campaign", "map_select", "tutorial"], "CAMPAIGN, CLASSIC, TUTORIAL (%s)" % app0.calls)

    g = Game(maps.create(1), 3, Difficulty.ON2)
    g.get_wave_manager().start_next_wave()
    savegame.slot().save(g)
    app = _App()
    m = MenuScreen(app)
    m.skip_intro()
    m.frame(0.05)
    c = m.continue_button
    check(c is not None and c.text.get_label() == "CONTINUE", "a saved run adds CONTINUE")
    details = [o.get_label() for o in c if o is not c.text and hasattr(o, "get_label")]
    check(details == ["The Legacy Monolith, O(N²), wave 1"] or details == ["The Legacy Monolith, O(N^2), wave 1"],
          "labelled with map, difficulty and wave (%s)" % details)
    stack = _menu_buttons(m)
    check(stack[0] is c and [b.text.get_label() for b in stack[1:]] == STACK, "CONTINUE heads the stack")
    boxes = [(b.get_x(), b.get_y(), b.w, b.h) for b in stack] + [(ch.get_x(), ch.get_y(), ch.get_width(), ch.get_height()) for ch in m.chips]
    check(all(0 <= x and x + w <= 1600 and 470 <= y and y + h <= 940 for x, y, w, h in boxes), "all inside the layout (%s)" % boxes)
    overlap = [(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:]
               if a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]]
    check(not overlap, "no two buttons overlap (%s)" % overlap)
    m.mouse_pressed(*_center(c))
    check(app.calls == ["continue"], "clicking CONTINUE continues the run (%s)" % app.calls)
    m.mouse_pressed(*_center(stack[1]))
    check(app.calls == ["continue", "campaign"], "CAMPAIGN still works below it")
    m.mouse_pressed(*_center(stack[2]))
    check(app.calls[-1] == "map_select", "and CLASSIC")


def test_unloadable_save_shows_the_notice_once(check):
    from lindefense import savegame
    with open(savegame.slot().path(), "wb") as f:
        f.write(savegame.MAGIC + b'{"format": 0}\n')
    m = MenuScreen(_App())
    check(m.continue_button is None, "no CONTINUE for a save of another version")
    check(m.notice.get_label() == savegame.LOAD_FAILED_TEXT, "the notice says so (%r)" % m.notice.get_label())
    check(not savegame.slot().exists(), "the save is deleted")
    for _ in range(140):
        m.frame(0.05)
    check(m.notice.get_label() == "", "the notice fades out")
    check(MenuScreen(_App()).notice.get_label() == "", "and is not shown again")
