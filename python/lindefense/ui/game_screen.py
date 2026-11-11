"""Lindefense GameScreen (ported from src/lindefense/ui/GameScreen.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense import savegame
from lindefense.combat.visual_event import VisualEvent
from lindefense.enemy.types import EnemyType
from lindefense.jenum import JEnum
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game
from lindefense.sim.vec import Vec
from lindefense.tower import catalog
from lindefense.tower import shop
from lindefense.tower.manager import TowerManager
from lindefense.tower.tower_type import TowerType
from lindefense.wave import waves


class GameScreen(GCompound):
    """The in-game screen: composes the world view, HUD and side panel, routes
mouse/keyboard input (in logical coordinates) to game actions, and shows the
pause / victory / defeat overlays."""
    class Confirm(JEnum):
        """Pending in-overlay confirmation of the pause menu (RESTART / QUIT LEVEL / MAIN MENU / closing the window)."""
        NONE = ()
        RESTART = ()
        QUIT = ()
        MAIN_MENU = ()
        CLOSE = ()
    def _init_0(self, app, game):
        self.app = None
        self.game = None
        self.world = None
        self.hud = None
        self.side = None
        self.attack = None
        self.dock = None
        self.abilities = None
        self.strip = None
        self.draft_seen = False
        self.draft_open = False
        self.targeting_tower = None
        self.overlay_title = None
        self.dock_shown = 0.0
        self.help_shown = False
        self.hero_store_shown = False
        self.hero_store_cash = None
        self.hero_store_cash_right = 0.0
        self.hero_store_need_button = None
        self.hero_store_need_price = 0
        self.hero_store_notice = None
        self.placing = None
        self.selected_tower = None
        self.selected_enemy = None
        self.mouse_world = None
        self.mouse_lx = 0.0
        self.mouse_ly = 0.0
        self.pause_shown = False
        self.fx_timer = 0.0
        self.music_timer = 0.0
        self.pause_toggles = None
        self.pause_sliders = None
        self.tutorial = None
        self.shown_music_state = None
        self._init_1(app, game, False)
    def _init_1(self, app, game, tutorial):
        self.app = None
        self.game = None
        self.world = None
        self.hud = None
        self.side = None
        self.attack = None
        self.dock = None
        self.abilities = None
        self.strip = None
        self.draft_seen = False
        self.draft_open = False
        self.targeting_tower = None
        self.overlay_title = None
        self.dock_shown = 0.0
        self.help_shown = False
        self.hero_store_shown = False
        self.hero_store_cash = None
        self.hero_store_cash_right = 0.0
        self.hero_store_need_button = None
        self.hero_store_need_price = 0
        self.hero_store_notice = None
        self.placing = None
        self.selected_tower = None
        self.selected_enemy = None
        self.mouse_world = None
        self.mouse_lx = 0.0
        self.mouse_ly = 0.0
        self.pause_shown = False
        self.fx_timer = 0.0
        self.music_timer = 0.0
        self.pause_toggles = None
        self.pause_sliders = None
        self.tutorial = None
        self.shown_music_state = None
        self.menu_shown = False          # the pause menu is open (a pause without it is the tactical pause)
        self.menu_was_paused = False     # tactically paused when the menu opened: Esc returns there
        self.dismiss_tower = None        # hero waiting for the DISMISS confirmation
        self.pause_banner = None
        GCompound.__init__(self)
        self.overlay = GCompound()
        self.overlay_buttons = _j.ArrayList()
        self.hero_store_key = ''
        self.hero_store_selection = TowerType.heroes()[0]
        self.shown_state = Game.State.PLAYING
        self.music_director = MusicDirector()
        self.menu_confirm = GameScreen.Confirm.NONE
        self.session = None          # RunSession: records / achievements of this run (set by the app; None in tests)
        self.end_page = 0            # end panel tab: 0 SUMMARY, 1 REPORT
        self.toasts = []             # achievements waiting for a free HUD toast
        self.epilogue = None
        self.epilogue_done = False
        self.fx_rng = _j.Random(7)
        self.app = app
        self.game = game
        self.add(Ui.rect(0, 0, Ui.W, Ui.H, Ui.BG, Ui.BG))
        self.build_backdrop()
        self.world = WorldView(self)
        self.dock = BossDock(game)
        self.hud = HudPanel(self)
        self.side = SidePanel(self)
        self.attack = (AttackPanel(self) if game.is_reverse() else None)
        self.abilities = AbilityBar(self)
        self.strip = RunStrip(self)
        self.add(self.world)
        self.add(self.dock)
        self.chatter = StoryView.StoryChatter.create(self)   # campaign levels: the story's radio chatter (ui/story_view)
        if self.chatter is not None:
            self.add(self.chatter)
        self.add(self.hud)
        self.add(self.abilities)
        self.add((self.attack if (self.attack is not None) else self.side))
        self.add(self.strip)
        self.add(self.overlay)
        if tutorial:   # above the overlays: it points into the Hero Store and hides itself behind the others
            self.tutorial = TutorialGuide(TutorialScript(game, self), self)
            self.add(self.tutorial)
    def __init__(self, *a):
        if len(a) == 2:
            return self._init_0(*a)
        elif len(a) == 3:
            return self._init_1(*a)
        raise TypeError('no overload for %d args' % len(a))
    def set_run_session(self, session):
        """Attaches the run's records session (the app does this for every match it starts)."""
        self.session = session
    def get_run_report(self):
        return None if self.session is None else self.session.report
    def end_run(self):
        """Records the run if it has not been recorded yet: abandoned at its wave when the player leaves mid-run."""
        if self.session is not None:
            return self.session.finish()
        return None
    def set_end_page(self, page):
        """Victory / defeat panel tab: 0 SUMMARY, 1 REPORT."""
        if page != self.end_page:
            self.end_page = page
            if self.game.get_state() is not Game.State.PLAYING:
                self.build_overlay()
    def run_summary(self):
        if self.session is not None:
            return self.session.summary()
        return RunSummary.of(self.game, None, (self.tutorial is not None))
    def update_records(self, real_dt):
        """Live achievement toasts (queued until the HUD toast is free and nothing covers the map, so one earned in the
Hero Store or behind the pause menu is not played out of sight) and the run's play time."""
        if self.session is None:
            return
        st = self.game.get_state()
        for a in self.session.tick(real_dt, ((st is Game.State.PLAYING) and (not self.game.is_paused()))):
            self.toasts.append(a)
        if self.toasts and (self.game.get_banner() is None) and (self.hud.banner_time <= 0) and (not self.gameplay_keys_blocked()):
            a = self.toasts.pop(0)
            self.hud.flash_banner(_j.cat('ACHIEVEMENT: ', a.title.upper()), Cyber.YELLOW, 3.2)
            AudioManager.sfx(Sfx.CASH)
    def get_tutorial(self):
        """The running tutorial's script, or null outside the tutorial."""
        return None if (self.tutorial is None) else self.tutorial.get_script()
    def build_backdrop(self):
        """Faint grid behind the (possibly shrunken) playfield, visible in the margins while the boss dock is open."""
        self.add(Cyber.Grid(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, (Ui.BOTTOM_Y - Ui.WORLD_Y), 40, Cyber.alpha(Cyber.CYAN, 12)))
    def get_game(self):
        return self.game
    def get_placing(self):
        return self.placing
    def get_selected_tower(self):
        return self.selected_tower
    def get_selected_enemy(self):
        return self.selected_enemy
    def get_mouse_world(self):
        return self.mouse_world
    def get_targeting_tower(self):
        """Tower whose targeted ability is waiting for a map click (targeting mode), or null."""
        return self.targeting_tower
    def get_mouse_logical(self):
        """Last mouse position in logical coordinates {x, y}."""
        return [self.mouse_lx, self.mouse_ly]
    def get_side_panel(self):
        return self.side
    def toggle_shop_all(self):
        """B key / ALL button: switch the shop between one faction and all towers."""
        if not self.game.is_reverse():
            self.side.toggle_all()
    def begin_placing(self, t):
        if (t is not None) and self.game.is_reverse():
            return
        locked = (None if (t is None) else self.game.tower_lock_problem(t))   # campaign: towers not unlocked yet
        if locked is not None:
            self.abilities.show_hint(locked, Cyber.RED, 2.5)
            AudioManager.sfx(Sfx.INVALID)
            return
        self.placing = t
        if t is not None:
            self.selected_tower = None
            self.selected_enemy = None
            self.targeting_tower = None
        self.side.request_rebuild()
    def select_tower(self, t):
        self.selected_tower = t
        if t is not None:
            self.placing = None
            self.selected_enemy = None
        self.side.request_rebuild()
    def select_enemy(self, e):
        self.selected_enemy = e
        if e is not None:
            self.placing = None
            self.selected_tower = None
        self.side.request_rebuild()
    def start_wave(self):
        if self.game.is_reverse() or ((self.tutorial is not None) and (not self.tutorial.allow_wave_start())):
            return
        self.game.start_next_wave()
    def set_speed(self, s):
        self.game.set_speed(s)
        self.game.set_paused(False)
    def toggle_pause(self):
        """P / the HUD pause button: the tactical pause. The game stops but the map stays usable (place, upgrade, sell,
select, target); everything done meanwhile applies at once. With the pause menu open it resumes the game instead."""
        if self.is_menu_open():
            self.resume_game()
            return
        self.game.toggle_pause()
        if self.game.get_state() is Game.State.PLAYING:
            self.build_overlay()
    def is_tactically_paused(self):
        """True while the game is paused without the pause menu (the map stays usable)."""
        return (self.game.get_state() is Game.State.PLAYING) and self.game.is_paused() and (not self.menu_shown)
    def toggle_auto(self):
        if (self.tutorial is not None) and (not self.tutorial.allow_auto()):
            return
        if not self.game.is_reverse():
            self.game.get_wave_manager().set_auto_start((not self.game.get_wave_manager().is_auto_start()))
    def back_to_menu(self):
        self.app.show_menu()
    def escape_pressed(self):
        """Esc closes or cancels the innermost thing first: HELP, a pause-menu confirmation (back to the menu), the pause
menu (back to how the game was), the Hero Store, a DISMISS confirmation, an ability aim, a tower placement, the
selection; with none of them, it opens the pause menu. On the victory screen it only skips the epilogue."""
        if self.epilogue is not None:
            self.skip_epilogue()
            return
        if self.game.get_state() is not Game.State.PLAYING:
            return
        if self.help_shown:
            self.toggle_help()
        elif self.is_menu_open():
            if self.menu_confirm is not GameScreen.Confirm.NONE:
                self.set_confirm(GameScreen.Confirm.NONE)
            else:
                self.close_menu()
        elif self.hero_store_shown:
            self.toggle_hero_store()
        elif self.dismiss_tower is not None:
            self.cancel_dismiss()
        elif self.targeting_tower is not None:
            self.cancel_targeting()
        elif self.placing is not None:
            self.begin_placing(None)
        elif (self.selected_tower is not None) or (self.selected_enemy is not None):
            self.select_tower(None)
            self.select_enemy(None)
        else:
            self.open_menu()
    def open_menu(self):
        """MENU button / Esc: pauses the game and opens the pause menu (resume, restart, sound, music, quit level, main menu).
A half-finished tower placement or ability aim is dropped so nothing is still armed when the game resumes."""
        if self.game.get_state() is not Game.State.PLAYING:
            return
        if self.placing is not None:
            self.begin_placing(None)
        self.cancel_targeting()
        self.help_shown = False
        self.dismiss_tower = None
        self.menu_confirm = GameScreen.Confirm.NONE
        if not self.is_menu_open():
            self.menu_was_paused = self.game.is_paused()
        self.menu_shown = True
        self.game.set_paused(True)
        self.build_overlay()
    def is_menu_open(self):
        """True while the pause menu overlay is showing."""
        return self.menu_shown and (self.game.get_state() is Game.State.PLAYING) and self.game.is_paused()
    def get_pending_confirm(self):
        """Logic of the confirmation step, exposed for tests: 0 none, 1 restart, 2 quit, 3 main menu, 4 close window."""
        return self.menu_confirm.ordinal
    def set_confirm(self, c):
        self.menu_confirm = c
        self.build_overlay()
    def resume_game(self):
        """RESUME / P in the pause menu: closes it and runs the game."""
        self.menu_confirm = GameScreen.Confirm.NONE
        self.menu_shown = False
        self.game.set_paused(False)
        self.build_overlay()
    def close_menu(self):
        """Esc in the pause menu: closes it and returns to how the game was (running, or the tactical pause)."""
        self.menu_confirm = GameScreen.Confirm.NONE
        self.menu_shown = False
        self.game.set_paused(self.menu_was_paused)
        self.build_overlay()
    def toggle_help(self):
        """Opens / closes the full controls and modifier reference overlay (H key or the HELP button)."""
        self.help_shown = (not self.help_shown)
        if self.help_shown:
            self.hero_store_shown = False
        self.build_overlay()
    def toggle_hero_store(self):
        """Opens / closes the Hero Store overlay (HEROES button or K). The game keeps running underneath."""
        if (self.game.get_state() is not Game.State.PLAYING) or self.game.is_reverse():
            return
        c = self.game.get_campaign()
        if (c is not None) and (not c.heroes) and (not self.hero_store_shown):
            self.abilities.show_hint(c.lock_problem(TowerType.heroes()[0]), Cyber.RED, 2.5)   # opens after level N
            AudioManager.sfx(Sfx.INVALID)
            return
        self.hero_store_shown = (not self.hero_store_shown)
        if self.hero_store_shown:
            self.help_shown = False
            self.dismiss_tower = None
            self.hero_store_notice = None
        self.hero_store_key = ''
        self.build_overlay()
    def is_hero_store_open(self):
        return self.hero_store_shown
    def buy_hero(self, t):
        """Hero Store BUY button: spends the unlock price and shows the confirmation."""
        if self.game.purchase_hero(t):
            self.hero_store_notice = _j.cat(t.display_name, ' unlocked permanently! Press DEPLOY to place on the map.')
            self.hud.flash_banner(_j.cat(t.display_name.upper(), ' UNLOCKED'), Ui.c(t.primary_rgb), 2.5)
        else:
            why = self.game.hero_purchase_problem(t)
            self.hero_store_notice = _j.cat(t.display_name, ': ', ('purchase failed' if (why is None) else why.lower()))
        self.hero_store_key = ''
        self.build_overlay()
    def deploy_hero(self, t):
        """Hero Store DEPLOY button: closes the store and enters placement mode for the hero."""
        if self.game.get_tower_manager().hero_problem(t) is not None:
            return
        self.hero_store_shown = False
        self.build_overlay()
        self.begin_placing(t)
    def hero_store_state_key(self):
        """Changes whenever a card's button or badge would change (cash crossing a price, unlock, deploy)."""
        sb = _j.StringBuilder()
        for t in TowerType.heroes():
            sb.append(('U' if self.game.is_hero_unlocked(t) else ('A' if (self.game.get_cash() >= shop.unlock_price_of(t)) else 'L')))
            sb.append(('D' if self.game.is_hero_deployed(t) else '-'))
        return sb.append(self.hero_store_selection).to_string()
    def hero_store_cash_text(self):
        return _j.cat('CREDITS  ', ('ADMIN ∞' if self.game.is_admin() else Ui.money(self.game.get_cash())))
    def refresh_hero_store_live(self):
        """Updates the open Hero Store's credits readout and NEED-MORE button text without rebuilding it."""
        if self.hero_store_cash is not None:
            txt = self.hero_store_cash_text()
            if not (txt == self.hero_store_cash.get_label()):
                self.hero_store_cash.set_label(txt)
                self.hero_store_cash.set_location((self.hero_store_cash_right - self.hero_store_cash.get_width()), self.hero_store_cash.get_y())
        if self.hero_store_need_button is not None:
            txt = _j.cat('NEED ', Ui.money(_j.dmax(0, (self.hero_store_need_price - self.game.get_cash()))), ' MORE')
            if not (txt == self.hero_store_need_button.get_text()):
                self.hero_store_need_button.set_text(txt)
    def upgrade_selected(self):
        """U / the upgrade button: buys the next upgrade; on a maxed tower with a locked ability it buys the ability."""
        if (self.selected_tower is None) or self.game.is_reverse():
            return
        if self.selected_tower.can_upgrade():
            self.game.upgrade_tower(self.selected_tower)
        elif self.selected_tower.is_ability_locked():
            self.unlock_ability_selected()
        self.side.request_rebuild()
    def unlock_ability_selected(self):
        """UNLOCK ABILITY button: buys the selected maxed tower's ability ($15,000); it is ready at once."""
        t = self.selected_tower
        if ((t is None) or (not t.is_ability_locked())) or self.game.is_reverse():
            return
        name = t.get_ability_def().name
        locked = self.game.ability_lock_problem()
        if locked is not None:
            self.abilities.show_hint(locked, Cyber.RED, 2.5)
            return
        if self.game.unlock_ability(t):
            self.abilities.show_hint(_j.cat(name, ' UNLOCKED  -  press A or click it in the ability bar'), Cyber.GREEN, 3)
        elif not t.can_unlock_ability():
            self.abilities.show_hint(_j.cat(name, ': buy every upgrade first'), Cyber.RED, 2.5)
        else:
            self.abilities.show_hint(_j.cat(name, ': needs ', Ui.money(shop.ability_unlock_cost(self.game))), Cyber.RED, 2.5)
        self.side.request_rebuild()
    def sell_selected(self):
        """S / SELL: sells the selected tower. A hero asks first (DISMISS confirmation): it cannot be deployed again
this match."""
        if (self.selected_tower is not None) and (not self.game.is_reverse()):
            why = self.game.get_tower_manager().sell_problem(self.selected_tower)
            if why is not None:
                AudioManager.sfx(Sfx.INVALID)
                self.abilities.show_hint(why.upper(), Cyber.RED, 2.5)
                return
            if self.selected_tower.get_type().is_hero() and self.selected_tower.is_alive():
                self.request_dismiss(self.selected_tower)
                return
            self.game.sell_tower(self.selected_tower)
            self.selected_tower = None
            self.side.request_rebuild()
    def ability_selected(self):
        if self.selected_tower is not None:
            self.fire_ability(self.selected_tower)
    def fire_ability(self, t):
        """Fires a tower's ability; a targeted one enters targeting mode instead. Refusals are shown above the ability bar."""
        if ((t is None) or (not t.is_alive())) or (t.get_ability() is None):
            return
        if self.game.get_state() is not Game.State.PLAYING:
            return
        if self.game.is_reverse():
            self.abilities.show_hint('The defender AI fires its own abilities', Cyber.MAGENTA, 2)
            return
        why = self.ability_refusal(t)
        if why is not None:
            self.abilities.show_hint(_j.cat(t.get_ability().name, ': ', why), Cyber.RED, 2.5)
            return
        if t.get_ability().needs_target:
            self.targeting_tower = t
            self.placing = None
            self.abilities.clear_hint()
            self.side.request_rebuild()
            return
        if self.game.activate_ability(t):
            self.abilities.show_hint(_j.cat(t.get_ability().name, '!'), Cyber.GREEN, 1.2)
        else:
            self.abilities.show_hint(_j.cat(t.get_ability().name, ': no enemy in range'), Cyber.RED, 2.5)
        self.side.request_rebuild()
    def ability_refusal(self, t):
        """Why the ability cannot be used right now (null if it can be tried)."""
        if t.is_surveilled():
            return 'offline (surveillance)'
        if t.is_offline():
            return _j.cat('offline (', ('hijacked' if t.is_hijacked() else ('blinded' if t.get_intrusion().is_blinded() else 'disabled')), ')')
        if not t.is_ability_ready():
            return _j.format('recharging (%.0fs)', float(math.ceil(t.get_ability_cooldown_remaining())))
        return None
    def cast_targeted(self, w):
        """Casts the armed targeted ability at a world point; stays armed (with a message) if the sim refuses."""
        t = self.targeting_tower
        if t is None:
            return
        if not t.is_alive():
            self.cancel_targeting()
            return
        if self.game.activate_ability(t, w):
            self.abilities.show_hint(_j.cat(t.get_ability().name, '!'), Cyber.GREEN, 1.2)
            self.targeting_tower = None
            self.side.request_rebuild()
        else:
            why = self.ability_refusal(t)
            self.abilities.show_hint(_j.cat(t.get_ability().name, ': ', (why if (why is not None) else 'no valid track point there')), Cyber.RED, 2.5)
            if why is not None:
                self.cancel_targeting()
    def cancel_targeting(self):
        if self.targeting_tower is None:
            return
        self.targeting_tower = None
        self.abilities.clear_hint()
        self.side.request_rebuild()
    def cycle_targeting(self, dir_):
        if (self.selected_tower is None) or self.game.is_reverse():
            return
        self.selected_tower.cycle_targeting(dir_)
        self.side.request_rebuild()
    def flash_banner(self, text, col, seconds):
        self.hud.flash_banner(text, col, seconds)
    def is_draft_open(self):
        """True while the patch-notes draft overlay is showing (the next wave waits for a pick)."""
        return self.draft_open
    def pick_patch_note(self, index):
        """Ships offered card index (draft overlay click, or keys 1-3)."""
        v = self.game.get_variance()
        offer = v.get_offer()
        if (index < 0) or (index >= len(offer)):
            return
        p = offer[index]
        if not v.pick(index):
            return
        self.hud.flash_banner(_j.cat('PATCH ', v.get_version(), ' SHIPPED: ', p.title.upper()), PatchNotesView.accent(p.category), 2.6)
        self.build_overlay()
        self.side.request_rebuild()
    def all_buttons(self):
        all_ = _j.ArrayList(self.overlay_buttons)
        if self.tutorial is not None:
            all_.extend(self.tutorial.get_buttons())
        all_.extend(self.hud.get_buttons())
        all_.extend((self.attack.get_buttons() if (self.attack is not None) else self.side.get_buttons()))
        all_.extend(self.abilities.get_buttons())
        return all_
    def mouse_pressed(self, lx, ly, right_button):
        self.mouse_moved(lx, ly)
        if self.epilogue is not None:
            self.skip_epilogue()
            return
        if (not right_button) and Slider.press_any(lx, ly, self.pause_sliders):
            return
        if (not right_button) and (self.tutorial is not None) and self.tutorial.press(lx, ly):
            return
        if not (len(self.overlay_buttons) == 0):
            for b in self.overlay_buttons:
                if b.hit(lx, ly):
                    b.click()
                    return
            if (((((self.game.get_state() is not Game.State.PLAYING) or self.help_shown) or self.hero_store_shown) or self.is_menu_open()) or self.draft_open) or (self.dismiss_tower is not None):
                return
        if right_button:
            if self.targeting_tower is not None:
                self.cancel_targeting()
                return
            if self.placing is not None:
                self.begin_placing(None)
            else:
                self.select_tower(None)
                self.select_enemy(None)
            return
        for b in self.all_buttons():
            if b.hit(lx, ly):
                if b.click():
                    return
        if lx >= Ui.PANEL_X:
            return
        if (self.tutorial is not None) and self.tutorial.covers(lx, ly):
            return
        w = self.to_world(lx, ly)
        if w is None:
            return
        if self.targeting_tower is not None:
            self.cast_targeted(w)
            return
        if self.placing is not None:
            t = self.game.place_tower(self.placing, w)
            if t is not None:
                # keep placing the same tower while affordable; a hero deploys once per match, so its placement ends
                if t.get_type().is_hero() or (self.game.get_cash() < shop.price_of(t.get_type(), self.game)):
                    self.placing = None
                    self.select_tower(t)
                self.side.request_rebuild()
            return
        t = self.game.get_tower_manager().tower_at(w)
        if t is not None:
            self.select_tower(t)
            return
        e = self.world.pick_enemy(w)
        if e is not None:
            self.select_enemy(e)
            return
        self.select_tower(None)
        self.select_enemy(None)
    def mouse_moved(self, lx, ly):
        self.mouse_lx = lx
        self.mouse_ly = ly
        self.mouse_world = self.to_world(lx, ly)
        for b in self.all_buttons():
            b.set_hover(b.hit(lx, ly))
        Slider.hover_all(lx, ly, self.pause_sliders)
    def mouse_dragged(self, lx, ly):
        """Mouse drag (logical coordinates): moves a grabbed pause-menu volume slider."""
        Slider.drag_all(lx, ly, self.pause_sliders)
    def mouse_released(self):
        """Mouse release: ends a volume-slider drag (the level is saved)."""
        Slider.release_all(self.pause_sliders)
    def to_world(self, lx, ly):
        return self.world.to_world(lx, ly)
    def world_to_logical(self, w):
        """Logical point {x, y} where world point w is drawn (tools and the scripted demo click through it)."""
        return self.world.to_logical(w)
    def refresh_hover(self):
        """Re-applies hover to every button for the last mouse position (after panels rebuild)."""
        for b in self.all_buttons():
            b.set_hover(b.hit(self.mouse_lx, self.mouse_ly))
    def key_pressed(self, e):
        """Keys. P, H, K and Esc always work (M / N are handled by the app); the gameplay keys only act on the map, so
they do nothing behind the pause menu, HELP, the Hero Store, a confirmation, the patch-notes draft or the end screen.
The tactical pause (P) leaves them working. While the victory epilogue plays, Esc / Enter / Space skip it."""
        if self.epilogue is not None:
            if e.get_key_code() in (KeyEvent.VK_ESCAPE, KeyEvent.VK_ENTER, KeyEvent.VK_SPACE):
                self.skip_epilogue()
            return
        k = e.get_key_code()
        if self.draft_open:
            if (k >= KeyEvent.VK_1) and (k <= KeyEvent.VK_9):
                self.pick_patch_note((k - KeyEvent.VK_1))
                return
            if ((k != KeyEvent.VK_ESCAPE) and (k != KeyEvent.VK_H)) and (k != KeyEvent.VK_P):
                return
        if (k == KeyEvent.VK_ENTER) and self.confirm_default():
            return
        if (k == KeyEvent.VK_ENTER) and (self.tutorial is not None) and self.tutorial.enter_pressed():
            return
        if (((self.attack is not None) and (self.game.get_state() is Game.State.PLAYING)) and (not self.gameplay_keys_blocked())) and self.attack.key_pressed(e):
            return
        shift = e.is_shift_down()
        if k == KeyEvent.VK_P:
            self.toggle_pause()
        elif k == KeyEvent.VK_H:
            self.toggle_help()
        elif k == KeyEvent.VK_K:
            self.toggle_hero_store()
        elif k == KeyEvent.VK_ESCAPE:
            self.escape_pressed()
        elif (k == KeyEvent.VK_TAB) and (self.game.get_state() is not Game.State.PLAYING) and (not self.is_menu_open()):
            self.set_end_page((1 - self.end_page))
        elif self.gameplay_keys_blocked():
            return
        elif shift and (KeyEvent.VK_1 <= k <= KeyEvent.VK_9):
            self.pick_shop_card((k - KeyEvent.VK_1))
        elif k == KeyEvent.VK_SPACE:
            self.start_wave()
        elif k == KeyEvent.VK_1:
            self.set_speed(1)
        elif k == KeyEvent.VK_2:
            self.set_speed(2)
        elif k == KeyEvent.VK_3:
            self.set_speed(3)
        elif k == KeyEvent.VK_U:
            self.upgrade_selected()
        elif k == KeyEvent.VK_S:
            self.sell_selected()
        elif k == KeyEvent.VK_A:
            self.ability_selected()
        elif k == KeyEvent.VK_T:
            self.cycle_targeting(((-1) if shift else 1))
        elif k == KeyEvent.VK_B:
            self.toggle_shop_all()
        elif k == KeyEvent.VK_TAB:
            self.cycle_selection(((-1) if shift else 1))
        elif k == KeyEvent.VK_O:
            self.toggle_auto_key()
    def frame(self, real_dt):
        """One rendered frame: advances the simulation (fixed steps, capped by #MAX_SIM_STEPS_PER_FRAME, the
remainder of a step carried over by Game#advance) and then updates every view from the new state."""
        self.game.advance(_j.dmin(real_dt, ((GameScreen.MAX_SIM_STEPS_PER_FRAME * Game.DT) / max(1, self.game.get_speed()))))
        if (self.selected_tower is not None) and (not self.selected_tower.is_alive()):
            self.select_tower(None)
        if (self.selected_enemy is not None) and ((not self.selected_enemy.is_alive()) and ((self.game.get_time() - self.selected_enemy.get_last_hit_time()) > 3)):
            self.select_enemy(None)
        self.dock.update(real_dt)
        target = self.dock.get_height()
        self.dock_shown += ((target - self.dock_shown) * _j.dmin(1, (real_dt * 9)))
        if abs((target - self.dock_shown)) < 0.3:
            self.dock_shown = target
        strip_h = self.strip.height()
        self.dock.set_location(0, (Ui.WORLD_Y + strip_h))
        self.world.set_dock((self.dock_shown + strip_h))
        self.mouse_world = self.to_world(self.mouse_lx, self.mouse_ly)
        self.world.update(real_dt)
        self.hud.update(real_dt)
        self.strip.update(real_dt)
        if self.attack is not None:
            self.attack.update(real_dt)
        else:
            self.side.update(real_dt)
        if (self.targeting_tower is not None) and (not self.targeting_tower.is_alive()):
            self.cancel_targeting()
        if (self.dismiss_tower is not None) and (not self.dismiss_tower.is_alive()):
            self.cancel_dismiss()
        if self.pause_banner is not None:
            self.pause_banner.set_visible(((self.mouse_ly < (AbilityBar.Y - 8)) or (self.mouse_lx >= Ui.WORLD_W)))   # ability tooltips show there
        self.abilities.update(real_dt)
        if self.tutorial is not None:
            self.tutorial.update(real_dt)
        for b in self.all_buttons():
            b.animate(real_dt)
        if self.game.is_victory_sequence_active():
            self.victory_fireworks(real_dt)
        if self.epilogue is not None:
            self.epilogue.update(real_dt)
        self.update_music(real_dt)
        self.update_records(real_dt)
        if self.chatter is not None:
            self.chatter.update(real_dt)
        if self.pause_toggles is not None:
            AudioToggle.sync_all(self.pause_toggles)
        Slider.frame_all(real_dt, self.pause_sliders)
        DailyRecords.get().note(self.game)   # a daily run's best wave is saved as soon as it is beaten
        st = self.game.get_state()
        if st is not self.shown_state:
            self.shown_state = st
            if st is not Game.State.PLAYING:
                self.end_run()
            self.build_overlay()
            if self.game.is_reverse():
                AudioManager.sfx((Sfx.VICTORY if self.game.get_reverse().attacker_won() else Sfx.DEFEAT))
            elif st is Game.State.VICTORY:
                AudioManager.sfx(Sfx.VICTORY)
            elif st is Game.State.DEFEAT:
                AudioManager.sfx(Sfx.DEFEAT)
        elif (st is Game.State.PLAYING) and (self.game.is_paused() != self.pause_shown):
            self.build_overlay()
        elif (st is Game.State.PLAYING) and (self.game.get_variance().is_draft_pending() != self.draft_seen):
            self.build_overlay()
        elif self.hero_store_shown and (not (self.hero_store_state_key() == self.hero_store_key)):
            self.build_overlay()
        if self.hero_store_shown:
            self.refresh_hero_store_live()
    def update_music(self, dt):
        """AUDIO HOOK: picks the music track from the game situation about 4 times a second."""
        am = AudioManager.get()
        if am is None:
            return
        self.music_timer -= dt
        st = self.game.get_state()
        if (self.music_timer > 0) and (st is self.shown_music_state):
            return
        self.music_timer = 0.25
        self.shown_music_state = st
        palantir = False
        boss = False
        for e in self.game.get_enemy_manager().get_enemies():
            if (not e.get_type().is_boss()) or (not e.is_alive()):
                continue
            if e.get_type() is EnemyType.PALANTIR:
                palantir = True
            else:
                boss = True
        won = (st is Game.State.VICTORY)
        lost = (st is Game.State.DEFEAT)
        wave = self.game.get_era_wave()   # a campaign level's music follows the war's wave it plays
        if self.game.is_reverse():
            won = lost
            lost = (st is Game.State.VICTORY)
            wave = self.game.get_reverse().equivalent_wave()
        am.set_music(self.music_director.choose(won, lost, wave, (self.game.get_difficulty() is Difficulty.ONN), palantir, boss, self.game.get_time()))
    def victory_fireworks(self, dt):
        self.fx_timer -= dt
        if self.fx_timer > 0:
            return
        self.fx_timer = 0.12
        c = (self.game.get_palantir().get_position() if (self.game.get_palantir() is not None) else Vec(600, 450))
        r = self.fx_rng
        ang = r.next_double() * (math.pi * 2)
        d = 20 + r.next_double() * 240
        p = Vec((c.x + (math.cos(ang) * d)), (c.y + (math.sin(ang) * d)))
        cols = [0xffe94a, 0xff3b4e, 0x3bff8a, 0x00f0ff, 0xff2bd6]
        radius = 30 + r.next_double() * 60
        rgb = cols[r.next_int(len(cols))]
        if not display_settings.reduced_motion():   # same numbers drawn either way: the effect stream stays in step
            _j_add(self.game.get_events(), VisualEvent.explosion(p, radius, rgb))
    def build_overlay(self):
        self.overlay.remove_all()
        self.epilogue = None
        self.hero_store_cash = None
        self.hero_store_need_button = None
        self.overlay_buttons.clear()
        self.overlay_title = None
        self.pause_toggles = None
        Slider.release_all(self.pause_sliders)
        self.pause_sliders = None
        self.pause_banner = None
        self.pause_shown = self.game.is_paused()
        self.draft_seen = self.game.get_variance().is_draft_pending()
        self.draft_open = False
        st = self.game.get_state()
        if (st is not Game.State.PLAYING) or (not self.game.is_paused()):
            self.menu_shown = False
        if st is not Game.State.PLAYING:
            self.hero_store_shown = False
            self.dismiss_tower = None
            self.help_shown = False   # H on the end screen must not leave HELP armed for CONTINUE - FREEPLAY
        menu = self.is_menu_open()
        if self.help_shown and (st is Game.State.PLAYING):
            self.build_help_overlay()
            return
        if (self.draft_seen and (st is Game.State.PLAYING)) and (not menu):
            self.build_draft_overlay()
            return
        if (self.hero_store_shown and (st is Game.State.PLAYING)) and (not menu):
            self.build_hero_store_overlay()
            return
        if ((self.dismiss_tower is not None) and (st is Game.State.PLAYING)) and (not menu):
            self.build_dismiss_overlay()
            return
        if (st is Game.State.PLAYING) and (not menu):
            self.menu_confirm = GameScreen.Confirm.NONE
            if self.game.is_paused():
                self.build_pause_banner()
            return
        if st is Game.State.PLAYING:
            self.build_menu_overlay()
            return
        if (st is Game.State.VICTORY) and self.wants_epilogue():
            self.build_epilogue_overlay()
            return
        if self.game.get_campaign() is not None:   # campaign levels: LEVEL COMPLETE (stars, reward) or DEFEAT
            CampaignEndView.build(self)
            self.refresh_hover()
            return
        ended = (st is not Game.State.PLAYING)
        self.overlay.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, (200 if ended else 140)), Ui.c(0x000000, 0)))
        cx = (Ui.WORLD_X + (Ui.WORLD_W / 2.0))
        cy = (Ui.WORLD_Y + (Ui.WORLD_H / 2.0))
        if st is Game.State.VICTORY:
            title = 'VICTORY'
            col = Cyber.YELLOW
            sub = _j.cat('Palantir has fallen. All ', waves.WAVE_COUNT, ' waves survived on ', self.game.get_map().get_name(), '.')
            if self.game.is_freeplay():
                sub = _j.cat('VICTORY - reached wave ', self.game.get_wave(), ' in freeplay on ', self.game.get_map().get_name(), '. Palantir fell at wave ', waves.WAVE_COUNT, '.')
        elif st is Game.State.DEFEAT:
            title = 'DEFEAT'
            col = Cyber.RED
            sub = _j.cat('Your defenses were breached on wave ', self.game.get_wave(), '.')
        else:
            return
        if self.game.is_reverse():
            rt = AttackPanel.end_texts(self.game)
            title = rt[0]
            sub = rt[1]
            col = (Cyber.YELLOW if ('win' == rt[2]) else Cyber.RED)
        notes = (ended and self.game.get_variance().is_enabled())
        freeplay = (ended and self.freeplay_offered())
        pw = (760.0 if ended else 720.0)
        rules_h = (RunSetupView.end_rows_height(self.game, (pw - 80)) if ended else 0)
        replay_ok = (ended and (not self.game.is_reverse()))   # every defense run has a seed to replay
        rounds_h = (AttackPanel.END_ROUNDS_H if (ended and self.game.is_reverse()) else 0)   # reverse: the round strip
        ph = ((((482 + rules_h) + (62 if freeplay else 0)) + rounds_h) if ended else 270)
        px = (cx - (pw / 2))
        py = (cy - (ph / 2))
        self.overlay.add(Cyber.Chamfer(px, py, pw, ph, 6))
        report_page = (ended and (self.end_page == 1))
        summary = None
        if ended:
            summary = self.run_summary()
            report = self.get_run_report()
            for b in RunReportView.tab_buttons(px, py, pw, self.end_page, self.set_end_page):
                self.overlay.add(b)
                _j_add(self.overlay_buttons, b)
        if report_page:
            RunReportView.build_page(self.overlay, self.game, summary, report, px, py, pw, ph, col, title)
        t = Ui.label(title, 0, 0, Cyber.display(Font.BOLD, 68), Cyber.lerp(col, Color.WHITE, 0.15))
        t.set_location((cx - (t.get_width() / 2)), (py + 128))
        if not report_page:
            self.overlay.add(t)
            self.overlay_title = t
        sy = (py + 168)
        for line in ([] if report_page else Ui.wrap(sub, Cyber.body(Font.PLAIN, 16), (pw - 100))):
            s = Ui.label(line, 0, sy, Cyber.body(Font.PLAIN, 16), Cyber.MUTED)
            s.set_location((cx - (s.get_width() / 2)), sy)
            self.overlay.add(s)
            sy += 22
        if ended and (not report_page):
            stats = [['Waves cleared', _j.s(self.game.get_last_completed_wave()), ''], ['Hostiles purged', Cyber.commas(self.game.get_enemy_manager().get_total_killed()), ''], ['Credits earned', Ui.money(summary.cash_earned), 'y'], ['Integrity left', _j.s(self.game.get_lives()), 'r']]
            if self.game.is_reverse():
                stats = AttackPanel.end_stats(self.game)
            cw = 166.0
            gap = 12.0
            sx = (cx - (((4 * cw) + (3 * gap)) / 2))
            cyy = (py + 214)
            for i in range(4):
                x = (sx + (i * (cw + gap)))
                vc = (Cyber.YELLOW if (stats[i][2] == 'y') else Cyber.TEXT)
                self.overlay.add(Cyber.Chamfer(x, cyy, cw, 58, 4).fill(Cyber.SURFACE_2))
                self.overlay.add(Ui.label(GameScreen.sentence(stats[i][0]), (x + 12), (cyy + 20), Cyber.body(Font.PLAIN, 12), Cyber.MUTED))
                self.overlay.add(Ui.label(stats[i][1], (x + 12), (cyy + 45), Cyber.mono(Font.BOLD, 20), vc))
            if rounds_h > 0:
                AttackPanel.end_rounds(self.overlay, self.game, cx, (cyy + 86), (pw - 60))
                cyy += rounds_h
            mode_font = Cyber.body(Font.PLAIN, 14)
            mode = Ui.label(_j.cat(DifficultySelector.display(self.game.get_difficulty(), mode_font), '  ', self.game.get_difficulty().subtitle, '   ·   ', PatchNotesView.seed_text(self.game)), 0, (cyy + 86), mode_font, Cyber.MUTED)
            if self.game.is_reverse():
                mode.set_label(_j.cat('Adversarial training   ·   AI ', DifficultySelector.display(self.game.get_reverse().get_level(), mode_font), '  ', self.game.get_reverse().get_profile().display_name, '   ·   ', self.game.get_reverse().get_doctrine().display_name, ' doctrine'))
            mode.set_location((cx - (mode.get_width() / 2)), (cyy + 86))
            self.overlay.add(mode)
            ry = (cyy + 112)
            if rules_h > 0:
                ry = (RunSetupView.chip_rows(self.overlay, RunSetupView.rule_chips(self.game, True), cx, (cyy + 102), (pw - 80)) + 18)
            if notes:
                ry = (PatchNotesView.chip_rows(self.overlay, self.game.get_variance().get_active(), cx, ((cyy + 102) + rules_h), (pw - 80)) + 18)
            RunReportView.add_records_line(self.overlay, summary, report, cx, ry)
        if ended:
            # RETRY (same map and difficulty, new seed), REPLAY SEED (same seed), MAP SELECT, MAIN MENU; after the first
            # Palantir victory CONTINUE - FREEPLAY sits on its own row above them
            labels = [['RETRY', Cyber.YELLOW, (lambda : self.app.restart_level())]]
            if replay_ok:
                _j_add(labels, ['REPLAY SEED', Cyber.CYAN, (lambda : self.app.replay_seed())])
            _j_add(labels, ['MAP SELECT', Cyber.CYAN, (lambda : self.app.show_map_select())])
            _j_add(labels, ['MAIN MENU', Cyber.CYAN, (lambda : self.app.show_menu())])
            gap = 12.0
            bw = (((pw - 64) - (gap * (len(labels) - 1))) / len(labels))
            bx = (cx - ((pw - 64) / 2))
            for i in range(len(labels)):
                b = UIButton((bx + (i * (bw + gap))), ((py + ph) - 76), bw, 50, labels[i][0], Cyber.display(Font.BOLD, 20), _j.Fn(labels[i][2]))
                b.set_accent(labels[i][1])
                b.set_primary(((i == 0) and (not freeplay)))
                self.overlay.add(b)
                _j_add(self.overlay_buttons, b)
            if freeplay:
                fp = UIButton((cx - 250), ((py + ph) - 138), 500, 50, 'CONTINUE - FREEPLAY', Cyber.display(Font.BOLD, 22), _j.Fn(self.continue_freeplay))
                fp.set_icon(Cyber.Kind.PLAY)
                fp.set_accent(Cyber.YELLOW)
                fp.set_primary(True)
                self.overlay.add(fp)
                _j_add(self.overlay_buttons, fp)
        self.refresh_hover()
    def wants_epilogue(self):
        """The epilogue / credits play once, after the first Palantir victory of a run (not after Freeplay, Reverse
mode or the tutorial)."""
        c = self.game.get_campaign()
        if (c is not None) and (not c.finale):
            return False   # campaign: only the finale (Palantir) plays the epilogue
        if (c is not None) and (not StoryView.wants_ending(self)):
            return False   # ... the campaign's own ending, once (the campaign's STORY codex replays it)
        return ((((not self.epilogue_done) and (self.tutorial is None)) and (not self.game.is_reverse())) and (not self.game.is_freeplay())) and (self.game.get_state() is Game.State.VICTORY)
    def build_epilogue_overlay(self):
        if self.game.get_campaign() is not None:   # a won campaign finale: the campaign's ending
            self.epilogue = StoryView.ending_for(self)
        else:
            self.epilogue = VictoryEpilogue(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H)
        self.overlay.add(self.epilogue)
    def is_epilogue_open(self):
        return self.epilogue is not None
    def skip_epilogue(self):
        """Click / Esc on the epilogue: on to the victory stats (and CONTINUE - FREEPLAY)."""
        self.epilogue_done = True
        self.build_overlay()
    def freeplay_offered(self):
        return (self.tutorial is None) and self.game.can_continue_freeplay()
    def continue_freeplay(self):
        """CONTINUE - FREEPLAY: the same board keeps going with endless generated waves from wave 101."""
        if (self.tutorial is not None) or (not self.game.continue_freeplay()):
            return
        if self.session is not None:
            self.session.reopen()   # the victory stays recorded; freeplay extends that run when it ends
        if hasattr(self.app, 'on_freeplay'):
            self.app.on_freeplay()  # the victory deleted the save: freeplay autosaves again
        self.end_page = 0
        self.epilogue_done = True
        self.shown_state = self.game.get_state()
        self.build_overlay()
        self.side.request_rebuild()
    @staticmethod
    def sentence(s):
        """'waves cleared' -> 'Waves cleared' (small captions are sentence case, not spaced capitals)."""
        return (s[0:1].upper() + s[1:]) if s else s
    def menu_button(self, x, y, w, h, text, icon, accent, r):
        b = UIButton(x, y, w, h, text, Cyber.display(Font.BOLD, 20), r)
        if icon is not None:
            b.set_icon(icon)
        if accent is not None:
            b.set_accent(accent)
        self.overlay.add(b)
        _j_add(self.overlay_buttons, b)
        return b
    def build_draft_overlay(self):
        """PATCH NOTES draft: three cards over the playfield; the next wave waits until one is shipped."""
        if self.placing is not None:
            self.begin_placing(None)
        self.cancel_targeting()
        self.hero_store_shown = False
        self.draft_open = True
        self.overlay_title = PatchNotesView.build_draft(self.overlay, self.overlay_buttons, self.game, _j.Fn(self.pick_patch_note))
        self.refresh_hover()
    def build_menu_overlay(self):
        """The pause menu: RESUME, RESTART, SOUND EFFECTS and MUSIC (each toggle with its volume slider), QUIT LEVEL, MAIN MENU (or a Yes / No confirmation)."""
        self.overlay.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, 150), Ui.c(0x000000, 0)))
        cx = (Ui.WORLD_X + (Ui.WORLD_W / 2.0))
        cy = (Ui.WORLD_Y + (Ui.WORLD_H / 2.0))
        confirm = (self.menu_confirm is not GameScreen.Confirm.NONE)
        col = (Cyber.RED if confirm else Cyber.CYAN)
        pw = 600.0
        ph = (320 if confirm else 520)
        px = (cx - (pw / 2))
        py = (cy - (ph / 2))
        self.overlay.add(Cyber.Chamfer(px, py, pw, ph, 6))
        C = GameScreen.Confirm
        texts = {C.RESTART: ('RESTART?', 'Restart level? Progress will be lost.'), C.QUIT: ('QUIT LEVEL?', 'Quit level? Progress will be lost.'), C.MAIN_MENU: ('MAIN MENU?', 'Leave for the main menu? Progress will be lost.'), C.CLOSE: ('QUIT GAME?', 'Quit Lindefense? This run will be lost.')}
        title = (texts[self.menu_confirm][0] if confirm else 'PAUSED')
        t = Ui.label(title, 0, 0, Cyber.display(Font.BOLD, (44 if confirm else 52)), (Cyber.lerp(col, Color.WHITE, 0.25) if confirm else Cyber.TEXT))
        t.set_location((cx - (t.get_width() / 2)), (py + (104 if confirm else 108)))
        self.overlay.add(t)
        self.overlay_title = t
        if confirm:
            q = texts[self.menu_confirm][1]
            if (self.menu_confirm in (C.QUIT, C.MAIN_MENU, C.CLOSE)) and savegame.can_save(self.game, (self.tutorial is not None)) and savegame.has_progress(self.game):
                q = {C.QUIT: 'Quit level? Your run is saved: CONTINUE it from the main menu.', C.MAIN_MENU: 'Leave for the main menu? Your run is saved: CONTINUE it there.', C.CLOSE: 'Quit Lindefense? Your run is saved: CONTINUE it next time.'}[self.menu_confirm]
            s = Ui.label(q, 0, (py + 156), Cyber.body(Font.PLAIN, 17), Cyber.TEXT)
            s.set_location((cx - (s.get_width() / 2)), (py + 156))
            self.overlay.add(s)
            k = Ui.label('Enter = yes   ·   Esc = no', 0, (py + 186), Cyber.body(Font.PLAIN, 13), Cyber.DIM)
            k.set_location((cx - (k.get_width() / 2)), (py + 190))
            self.overlay.add(k)
            yes = _j.Fn(self.confirm_yes)
            y = self.menu_button((cx - 260), ((py + ph) - 90), 250, 54, 'YES', Cyber.Kind.CHECK, Cyber.RED, yes)
            y.set_primary(True)
            n = self.menu_button((cx + 10), ((py + ph) - 90), 250, 54, 'NO', None, Cyber.CYAN, _j.Fn(lambda : self.set_confirm(GameScreen.Confirm.NONE)))
            self.refresh_hover()
            return
        seed = _j.cat('   ·   ', PatchNotesView.seed_text(self.game), (_j.cat('   ·   Patch ', self.game.get_variance().get_version()) if self.game.get_variance().is_enabled() else ''))
        hint = Ui.label(_j.cat(('P to resume, Esc stays paused' if self.menu_was_paused else 'P or Esc to resume'), seed), 0, (py + 142), Cyber.body(Font.PLAIN, 14), Cyber.MUTED)
        hint.set_location((cx - (hint.get_width() / 2)), (py + 142))
        self.overlay.add(hint)
        bw = 500.0
        bx = (cx - (bw / 2))
        by = (py + 172)
        bh = 46.0
        gap = 10.0
        tw = 200.0
        resume = self.menu_button(bx, by, bw, bh, 'RESUME', Cyber.Kind.PLAY, None, _j.Fn(self.resume_game))
        resume.set_primary(True)
        self.menu_button(bx, (by + (bh + gap)), bw, bh, 'RESTART', Cyber.Kind.AUTO, None, _j.Fn(lambda : self.set_confirm(GameScreen.Confirm.RESTART)))
        snd = AudioToggle.sound(bx, (by + (2 * (bh + gap))), tw, bh, 'SOUND EFFECTS:')
        mus = AudioToggle.music(bx, (by + (3 * (bh + gap))), tw, bh, 'MUSIC:')
        self.pause_toggles = [snd, mus]
        for at in self.pause_toggles:
            self.overlay.add(at.get_button())
            _j_add(self.overlay_buttons, at.get_button())
        self.pause_sliders = [AudioToggle.sound_volume(((bx + tw) + gap), (by + (2 * (bh + gap))), ((bw - tw) - gap), bh, 'VOL'), AudioToggle.music_volume(((bx + tw) + gap), (by + (3 * (bh + gap))), ((bw - tw) - gap), bh, 'VOL')]
        for sl in self.pause_sliders:
            self.overlay.add(sl)
        self.menu_button(bx, (by + (4 * (bh + gap))), bw, bh, 'QUIT LEVEL', Cyber.Kind.SKULL, Cyber.RED, _j.Fn(lambda : self.set_confirm(GameScreen.Confirm.QUIT)))
        self.menu_button(bx, (by + (5 * (bh + gap))), bw, bh, 'MAIN MENU', Cyber.Kind.MENU, None, _j.Fn(lambda : self.set_confirm(GameScreen.Confirm.MAIN_MENU)))
        AudioToggle.sync_all(self.pause_toggles)
        self.refresh_hover()
    def build_hero_store_overlay(self):
        """The Hero Store: a grid of all 17 heroes (sprite, name, price, lock status) beside a detail panel for the
selected one showing its role, base ability, current statistics and all three purchasable upgrades with their
names, prices and exactly what each changes. Buying only unlocks a hero; deploying is a separate action."""
        self.hero_store_key = self.hero_store_state_key()
        self.overlay.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, 200), Ui.c(0x000000, 0)))
        pw = 1180.0
        ph = 870.0
        px = (Ui.WORLD_X + ((Ui.WORLD_W - pw) / 2))
        py = (Ui.WORLD_Y + ((Ui.WORLD_H - ph) / 2))
        self.overlay.add(Cyber.Chamfer(px, py, pw, ph, 6))
        self.overlay.add(Ui.label('HERO STORE', (px + 30), (py + 66), Cyber.display(Font.BOLD, 32), Cyber.TEXT))
        cash = Ui.label(self.hero_store_cash_text(), 0, (py + 62), Cyber.mono(Font.BOLD, 18), Cyber.YELLOW)
        self.hero_store_cash_right = ((((px + pw) - 30) - 130) - 20)
        cash.set_location((self.hero_store_cash_right - cash.get_width()), (py + 62))
        self.overlay.add(cash)
        self.hero_store_cash = cash
        self.hero_store_need_button = None
        close = UIButton((((px + pw) - 30) - 130), (py + 38), 130, 36, 'CLOSE  [K]', Cyber.display(Font.BOLD, 16), _j.Fn(self.toggle_hero_store))
        self.overlay.add(close)
        _j_add(self.overlay_buttons, close)
        sub = (self.hero_store_notice if (self.hero_store_notice is not None) else _j.cat('Buy a hero once to unlock it forever. Unlocked heroes cost a bit of cash to deploy, once per match (up to ', TowerManager.MAX_HEROES_PER_GAME, ' heroes per game), then level up with three upgrades bought in game.'))
        self.overlay.add(Ui.label(sub, (px + 30), (py + 92), Cyber.body(Font.PLAIN, 14), (Cyber.GREEN if (self.hero_store_notice is not None) else Cyber.MUTED)))
        heroes = TowerType.heroes()
        cols = 5
        gx = (px + 22)
        gy = (py + 108)
        gap = 8.0
        tw = 118.0
        th = 104.0
        for i in range(len(heroes)):
            self.hero_tile(heroes[i], (gx + (_j.imod(i, cols) * (tw + gap))), (gy + (_j.idiv(i, cols) * (th + gap))), tw, th)
        grid_w = ((cols * tw) + ((cols - 1) * gap))
        self.hero_detail(self.hero_store_selection, ((gx + grid_w) + 18), gy, ((pw - grid_w) - 58), ((ph - 108) - 22))
        self.refresh_hover()
    def hero_tile(self, t, x, y, w, h):
        """One tile in the roster grid: sprite, name, price and lock state; clicking it opens that hero's details."""
        unlocked = self.game.is_hero_unlocked(t)
        deployed = self.game.is_hero_deployed(t)
        selected = (t is self.hero_store_selection)
        price = catalog.get(t).unlock_cost
        accent = Ui.c(t.primary_rgb)
        border = (Cyber.CYAN if selected else Cyber.EDGE)
        def _lam1(*, t=t):
            self.hero_store_selection = t
            self.hero_store_key = ''
        pick = UIButton(x, y, w, h, '', Cyber.mono(Font.BOLD, 1), _j.Fn(_lam1))
        pick.set_flat(True)
        pick.set_accent(border)
        self.overlay.add(pick)
        _j_add(self.overlay_buttons, pick)
        self.overlay.add(Cyber.Chamfer(x, y, w, h, 4).fill((Color(16, 28, 50, 245) if selected else Cyber.SURFACE_2)).border(border))
        icon = TowerIcons.create(t, 0, 54)
        icon.set_location((x + (w / 2)), (y + 34))
        self.overlay.add(icon)
        if not unlocked:
            self.overlay.add(Cyber.Ring(((x + (w / 2)) - 28), ((y + 34) - 28), 56, 56, Color(5, 9, 22, 130), None))
        nm = Ui.label(t.display_name, 0, 0, Cyber.display(Font.BOLD, 13), (Cyber.TEXT if (selected or unlocked) else Cyber.MUTED))
        sz = 13
        while (nm.get_width() > (w - 10)) and (sz > 8):
            nm.set_font(Cyber.display_compact(Font.BOLD, sz))
            sz -= 1
        nm.set_location((x + ((w - nm.get_width()) / 2)), ((y + h) - 26))
        self.overlay.add(nm)
        tag = ('DEPLOYED' if deployed else ('READY' if unlocked else Ui.money(price)))
        tc = (Cyber.DIM if deployed else (Cyber.GREEN if unlocked else (Cyber.YELLOW if (self.game.get_cash() >= price) else Cyber.RED)))
        pl = Ui.label(tag, 0, 0, Cyber.mono(Font.BOLD, 10), tc)
        pl.set_location((x + ((w - pl.get_width()) / 2)), ((y + h) - 9))
        self.overlay.add(pl)
    def hero_detail(self, t, x, y, w, h):
        """The selected hero's full card: role, base ability, live statistics, the three upgrades and the action button."""
        d = catalog.get(t)
        unlocked = self.game.is_hero_unlocked(t)
        deployed = self.game.is_hero_deployed(t)
        price = d.unlock_cost
        afford = (self.game.get_cash() >= price)
        accent = Ui.c(t.primary_rgb)
        self.overlay.add(Cyber.Chamfer(x, y, w, h, 4).fill(Cyber.SURFACE_2))
        icon = TowerIcons.create(t, 0, 86)
        icon.set_location((x + 60), (y + 60))
        self.overlay.add(icon)
        tx = (x + 116)
        tw = (w - 130)
        self.overlay.add(Ui.label(t.display_name, tx, (y + 36), Cyber.display(Font.BOLD, 26), Cyber.TEXT))
        self.overlay.add(Ui.label(HeroStatText.role(t), tx, (y + 56), Cyber.body(Font.PLAIN, 13), Cyber.MUTED))
        status = ('DEPLOYED THIS MATCH' if deployed else ('UNLOCKED' if unlocked else 'LOCKED'))
        sc = (Cyber.DIM if deployed else (Cyber.GREEN if unlocked else Cyber.RED))
        sl = Ui.label(status, 0, 0, Cyber.mono(Font.BOLD, 11), sc)
        self.overlay.add(Cyber.Chamfer(tx, (y + 66), (sl.get_width() + 16), 18, 3).fill(Cyber.alpha(sc, 30)).border(None))
        sl.set_location((tx + 8), (y + 79))
        self.overlay.add(sl)
        pr = Ui.label(('owned' if unlocked else Ui.money(price)), 0, 0, Cyber.mono(Font.BOLD, 18), (Cyber.DIM if unlocked else (Cyber.YELLOW if afford else Cyber.RED)))
        pr.set_location((((x + w) - 16) - pr.get_width()), (y + 40))
        self.overlay.add(pr)
        yy = (y + 104)
        for l in Ui.wrap(d.description, Cyber.body(Font.PLAIN, 12), (w - 32)):
            self.overlay.add(Ui.label(l, (x + 16), yy, Cyber.body(Font.PLAIN, 12), Cyber.MUTED))
            yy += 15
        yy += 10
        self.overlay.add(Ui.label(_j.cat('Level 1  ·  ', d.tier_labels[0]), (x + 16), yy, Cyber.body(Font.BOLD, 13), Cyber.TEXT))
        for l in HeroStatText.attack_lines(t, 0):
            yy += 16
            self.overlay.add(Ui.label(l, (x + 16), yy, Cyber.mono(Font.BOLD, 11), Cyber.TEXT))
        for i in range(len(d.upgrades)):
            up = d.upgrades[i]
            yy += 20
            self.overlay.add(Ui.label(_j.cat('Level ', (i + 2), '  ·  ', up.name), (x + 16), yy, Cyber.body(Font.BOLD, 13), Cyber.TEXT))
            uc = Ui.label(Ui.money(up.cost), 0, yy, Cyber.mono(Font.BOLD, 11), Cyber.YELLOW)
            uc.set_location((((x + w) - 16) - uc.get_width()), yy)
            self.overlay.add(uc)
            lines = 0
            for l in Ui.wrap(up.description, Cyber.body(Font.PLAIN, 12), (w - 32)):
                if (lines := lines + 1) > 3:
                    break
                yy += 15
                self.overlay.add(Ui.label(l, (x + 16), yy, Cyber.body(Font.PLAIN, 12), Cyber.MUTED))
        yy += 20
        self.overlay.add(Ui.label(_j.cat('Fully upgraded: ', Ui.money(d.total_cost()), ' of in-match credits on top of the unlock'), (x + 16), yy, Cyber.body(Font.PLAIN, 12), Cyber.DIM))
        by = ((y + h) - 54)
        if not unlocked:
            b = UIButton((x + 16), by, (w - 32), 40, (_j.cat('BUY  ', Ui.money(price)) if afford else _j.cat('NEED ', Ui.money((price - self.game.get_cash())), ' MORE')), Cyber.display(Font.BOLD, 17), _j.Fn(lambda *, t=t: self.buy_hero(t)))
            if not afford:
                self.hero_store_need_button = b
                self.hero_store_need_price = price
            b.set_enabled(afford)
            b.set_accent(Cyber.YELLOW)
            if afford:
                b.set_primary(True)
        elif (not deployed) and (self.game.get_tower_manager().heroes_deployed_this_match() >= self.game.get_hero_limit()):
            b = UIButton((x + 16), by, (w - 32), 40, _j.cat('HERO LIMIT  ', self.game.get_hero_limit(), ' PER GAME'), Cyber.display(Font.BOLD, 16), None)
            b.set_enabled(False)
        elif not deployed:
            b = UIButton((x + 16), by, (w - 32), 40, _j.cat('DEPLOY (FREE)  ', self.game.get_tower_manager().heroes_deployed_this_match(), ' / ', self.game.get_hero_limit(), ' USED'), Cyber.display(Font.BOLD, 17), _j.Fn(lambda *, t=t: self.deploy_hero(t)))
            b.set_accent(Cyber.GREEN)
            b.set_primary(True)
        else:
            b = UIButton((x + 16), by, (w - 32), 40, 'ALREADY DEPLOYED THIS MATCH', Cyber.display(Font.BOLD, 16), None)
            b.set_enabled(False)
        self.overlay.add(b)
        _j_add(self.overlay_buttons, b)
    def build_help_overlay(self):
        """Full controls / modifiers / economy reference, opened from the side panel."""
        self.overlay.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, 205), Ui.c(0x000000, 0)))
        cx = (Ui.WORLD_X + (Ui.WORLD_W / 2.0))
        cy = (Ui.WORLD_Y + (Ui.WORLD_H / 2.0))
        pw = 860.0
        ph = 640.0
        px = (cx - (pw / 2))
        py = (cy - (ph / 2))
        self.overlay.add(Cyber.Chamfer(px, py, pw, ph, 6))
        self.overlay.add(Ui.label('HELP', (px + 34), (py + 70), Cyber.display(Font.BOLD, 34), Cyber.TEXT))
        keys = [['SPACE', 'start next wave'], ['O', 'auto-start waves on / off'], ['1  2  3', 'game speed'], ['P', 'pause / resume (you can still build)'], ['ESC', 'cancel / deselect, else pause menu'], ['B', 'all towers / faction tabs'], ['SHIFT 1-9', 'place the Nth card of the shop'], ['TAB', 'select next tower (Shift: previous)'], ['U', 'upgrade selected tower'], ['S', 'sell selected tower'], ['A', "fire selected tower's ability"], ['T', 'cycle targeting (Shift: backwards)'], ['K', 'Hero Store'], ['M', 'music on / off'], ['N', 'sound on / off'], ['H', 'toggle this help']]
        if self.game.is_reverse():
            keys = AttackPanel.HELP_KEYS
        keys = (keys + [['F11', 'full screen (Mac: Cmd+Ctrl+F)']])
        ky = (py + 126)
        self.overlay.add(Ui.label('Controls', (px + 34), ky, Cyber.body(Font.BOLD, 14), Cyber.TEXT))
        for k in keys:
            ky += 24
            self.overlay.add(Ui.label(k[0], (px + 34), ky, Cyber.mono(Font.BOLD, 14), Cyber.CYAN))
            self.overlay.add(Ui.label(k[1], (px + 130), ky, Cyber.body(Font.PLAIN, 15), Cyber.TEXT))
        rx = (px + 470)
        ry = (py + 126)
        rw = ((pw - 470) - 34)
        notes = [['enemy modifiers', 'Camo enemies need detection (Perplexity, Grok, or Gemini / Llama after their second upgrade). Regrow enemies heal over time. Fortified enemies carry double HP. Prompt Injection enemies (wave 30+) hijack nearby towers; Claude, Copilot (and its radius), DeepSeek, Perplexity and Mr. Lindemann are immune.'], ['hero store', 'Open with HEROES or K. Buy a hero once to unlock it permanently, then deploy it for a deploy cost, once per match. Heroes are not in the tower shop.'], ['economy', 'Enemies pay cash when destroyed and every wave pays a bonus. Selling refunds most of what you spent on a tower.'], ['bosses', _j.cat('Boss health and abilities show in the dock under the top bar; every boss has a signature move. Palantir (wave ', waves.WAVE_COUNT, ') disrupts your best towers with Predictive Surveillance (Perplexity protects) and its escorts shield it: kill them.')]]
        if self.game.is_reverse():
            notes = AttackPanel.HELP_NOTES
        for n in notes:
            self.overlay.add(Ui.label(GameScreen.sentence(n[0]), rx, ry, Cyber.body(Font.BOLD, 14), Cyber.TEXT))
            for l in Ui.wrap(n[1], Cyber.body(Font.PLAIN, 14), rw):
                ry += 20
                self.overlay.add(Ui.label(l, rx, ry, Cyber.body(Font.PLAIN, 14), Cyber.MUTED))
            ry += 34
        close = UIButton((cx - 100), ((py + ph) - 70), 200, 46, 'CLOSE', Cyber.display(Font.BOLD, 20), _j.Fn(self.toggle_help))
        close.set_primary(True)
        self.overlay.add(close)
        _j_add(self.overlay_buttons, close)
        self.refresh_hover()

    # ---------------------------------------------------------------- match safety: confirmations, key gating, pauses, hotkeys
    def gameplay_keys_blocked(self):
        """True while something covers the map (pause menu, HELP, Hero Store, a confirmation, the patch-notes draft) or the
match is over: the gameplay keys must not act on the hidden map. The tactical pause blocks nothing."""
        return ((((((self.game.get_state() is not Game.State.PLAYING) or self.help_shown) or self.is_menu_open()) or self.hero_store_shown) or (self.dismiss_tower is not None)) or self.draft_open)
    def confirm_default(self):
        """Enter answers YES in the confirmation showing (pause menu or DISMISS). True if a confirmation took the key."""
        if self.help_shown or (self.game.get_state() is not Game.State.PLAYING):
            return False
        if self.is_menu_open():
            if self.menu_confirm is GameScreen.Confirm.NONE:
                return False
            self.confirm_yes()
            return True
        if (self.dismiss_tower is not None) and (not self.hero_store_shown):
            self.confirm_dismiss()
            return True
        return False
    def confirm_yes(self):
        """YES in the pause menu's confirmation step."""
        C = GameScreen.Confirm
        c = self.menu_confirm
        if c is C.RESTART:
            self.app.restart_level()
        elif c is C.QUIT:
            self.app.quit_level()
        elif c is C.MAIN_MENU:
            self.back_to_menu()
        elif c is C.CLOSE:
            self.app.quit()
    def request_window_close(self):
        """The window's close button (or Cmd+Q) during a match. True if the QUIT GAME? confirmation now shows and the app
keeps running; False when the app should simply quit: no live match, or that confirmation was already showing (a
second close request quits)."""
        if self.game.get_state() is not Game.State.PLAYING:
            return False
        if self.is_menu_open() and (self.menu_confirm is GameScreen.Confirm.CLOSE):
            return False
        self.open_menu()
        self.set_confirm(GameScreen.Confirm.CLOSE)
        return True
    def auto_pause(self):
        """The window lost focus or was minimised: opens the pause menu if the match is running (not already paused,
tactically or in the menu, and not over). True if it paused."""
        if (self.game.get_state() is not Game.State.PLAYING) or self.game.is_paused():
            return False
        self.open_menu()
        return True
    def get_pending_dismiss(self):
        """Hero waiting for the DISMISS confirmation, or null."""
        return self.dismiss_tower
    def request_dismiss(self, t):
        self.dismiss_tower = t
        self.build_overlay()
    def cancel_dismiss(self):
        if self.dismiss_tower is None:
            return
        self.dismiss_tower = None
        self.build_overlay()
    def confirm_dismiss(self):
        """DISMISS confirmed: sells the hero (it stays used up for this match)."""
        t = self.dismiss_tower
        self.dismiss_tower = None
        if ((t is not None) and t.is_alive()) and (not self.game.is_reverse()):
            self.game.sell_tower(t)
            if self.selected_tower is t:
                self.selected_tower = None
            self.side.request_rebuild()
        self.build_overlay()
    def cycle_selection(self, dir_):
        """Tab / Shift+Tab: selects the next / previous placed tower in placement order (the view does not move)."""
        towers = self.game.get_tower_manager().get_player_towers()
        if len(towers) == 0:
            return
        i = next((j for j, t in enumerate(towers) if t is self.selected_tower), (-1))
        if i < 0:
            t = (towers[0] if (dir_ > 0) else towers[(-1)])
        else:
            t = towers[((i + dir_) % len(towers))]
        self.cancel_targeting()
        self.select_tower(t)
    def pick_shop_card(self, index):
        """Shift+1-9: arms placement of the shop card at that position in the shop as shown (the open faction tab, or ALL)."""
        if self.game.is_reverse():
            return
        cells = (ShopLayout.all_cells() if self.side.is_all_mode() else ShopLayout.faction_cells(self.side.get_tab()))
        if (index < 0) or (index >= len(cells)):
            return
        t = cells[index].type
        if (self.game.tower_lock_problem(t) is None) and (not ShopLayout.affordable(self.game, t)):   # a locked tower: begin_placing says which level unlocks it
            self.abilities.show_hint(_j.cat(t.display_name, ': needs ', Ui.money(ShopLayout.shortfall(self.game, t)), ' more'), Cyber.RED, 2)
            return
        self.cancel_targeting()
        self.begin_placing(t)
    def toggle_auto_key(self):
        """O: the AUTO button (each next wave starts by itself)."""
        if self.game.is_reverse():
            return
        self.toggle_auto()
        on = self.game.get_wave_manager().is_auto_start()
        self.hud.flash_banner(('AUTO WAVES ON' if on else 'AUTO WAVES OFF'), Cyber.MAGENTA, 1.4)
    def build_pause_banner(self):
        """The tactical pause: a banner above the ability bar and a frame around the playfield. It has no buttons, so the
map underneath stays usable."""
        f = Cyber.Chamfer(Ui.WORLD_X + 1, Ui.WORLD_Y + 1, Ui.WORLD_W - 2, Ui.WORLD_H - 2, 0).fill(None).border(Cyber.alpha(Cyber.YELLOW, 90))
        self.overlay.add(f)
        h = 52.0
        b = GCompound()
        frame = Cyber.Chamfer(0, 0, 400, h, 4)
        b.add(frame)
        b.add(Ui.rect(0, 0, 3, h, Cyber.YELLOW, Cyber.YELLOW))
        title = Ui.label('PAUSED', 22, 35, Cyber.display(Font.BOLD, 24), Cyber.lerp(Cyber.YELLOW, Color.WHITE, 0.3))
        b.add(title)
        tx = ((22 + title.get_width()) + 24)
        b.add(Ui.rect((tx - 12), 12, 1, (h - 24), Cyber.EDGE, Cyber.EDGE))
        a = Ui.label('Press P to resume', tx, 23, Cyber.body(Font.BOLD, 14), Cyber.TEXT)
        c = Ui.label(('you can still send units and inspect towers' if self.game.is_reverse() else ('you can still build, upgrade and target' if self.game.is_selling_locked() else 'you can still build, upgrade, sell and target')), tx, 41, Cyber.body(Font.PLAIN, 12), Cyber.MUTED)
        b.add(a)
        b.add(c)
        w = ((tx + _j.dmax(a.get_width(), c.get_width())) + 26)
        frame.size(w, h)
        b.set_location((Ui.WORLD_X + ((Ui.WORLD_W - w) / 2)), (((AbilityBar.Y - 34) - 12) - h))
        self.overlay.add(b)
        self.pause_banner = b
    def build_dismiss_overlay(self):
        """DISMISS confirmation for a hero (S or the DISMISS button): it cannot be deployed again this match."""
        t = self.dismiss_tower
        name = t.get_type().display_name
        self.overlay.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, 140), Ui.c(0x000000, 0)))
        cx = (Ui.WORLD_X + (Ui.WORLD_W / 2.0))
        cy = (Ui.WORLD_Y + (Ui.WORLD_H / 2.0))
        pw = 600.0
        ph = 330.0
        px = (cx - (pw / 2))
        py = (cy - (ph / 2))
        self.overlay.add(Cyber.Chamfer(px, py, pw, ph, 6))
        title = Ui.label('DISMISS HERO?', 0, 0, Cyber.display(Font.BOLD, 44), Cyber.lerp(Cyber.RED, Color.WHITE, 0.25))
        title.set_location((cx - (title.get_width() / 2)), (py + 104))
        self.overlay.add(title)
        self.overlay_title = title
        sy = (py + 150)
        lines = [_j.cat('Dismiss ', name, ' for a refund of ', Ui.money(shop.sell_value(t, self.game)), '?'), _j.cat(name, ' cannot be deployed again this match.')]
        for line in lines:
            s = Ui.label(line, 0, sy, Cyber.body(Font.PLAIN, 17), Cyber.TEXT)
            s.set_location((cx - (s.get_width() / 2)), sy)
            self.overlay.add(s)
            sy += 24
        k = Ui.label('Enter = dismiss   ·   Esc = keep', 0, (sy + 6), Cyber.body(Font.PLAIN, 13), Cyber.DIM)
        k.set_location((cx - (k.get_width() / 2)), (sy + 6))
        self.overlay.add(k)
        yes = self.menu_button((cx - 260), ((py + ph) - 90), 250, 54, 'DISMISS', Cyber.Kind.CHECK, Cyber.RED, _j.Fn(self.confirm_dismiss))
        yes.set_primary(True)
        self.menu_button((cx + 10), ((py + ph) - 90), 250, 54, 'KEEP', None, Cyber.CYAN, _j.Fn(self.cancel_dismiss))
        self.refresh_hover()


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.audio.audio_manager import AudioManager  # noqa: E402
from lindefense.audio.music_director import MusicDirector  # noqa: E402
from lindefense.audio.sfx import Sfx  # noqa: E402
from lindefense.ui.ability_bar import AbilityBar  # noqa: E402
from lindefense.ui.attack_panel import AttackPanel  # noqa: E402
from lindefense.ui.audio_toggle import AudioToggle  # noqa: E402
from lindefense.ui.boss_dock import BossDock  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.difficulty_selector import DifficultySelector  # noqa: E402
from lindefense.ui.hero_stat_text import HeroStatText  # noqa: E402
from lindefense.ui.hud_panel import HudPanel  # noqa: E402
from lindefense.ui.patch_notes_view import PatchNotesView  # noqa: E402
from lindefense.ui import run_report_view as RunReportView  # noqa: E402
from lindefense.sim.records import RunSummary  # noqa: E402
from lindefense.ui import campaign_end_view as CampaignEndView  # noqa: E402
from lindefense.ui.run_strip import RunStrip  # noqa: E402
from lindefense.ui.shop_layout import ShopLayout  # noqa: E402
from lindefense.ui import run_setup_view as RunSetupView  # noqa: E402
from lindefense.sim.run_setup import DailyRecords  # noqa: E402
from lindefense.ui.side_panel import SidePanel  # noqa: E402
from lindefense.ui.slider import Slider  # noqa: E402
from lindefense.ui.sprites.towers.tower_icons import TowerIcons  # noqa: E402
from lindefense.ui.tutorial_guide import TutorialGuide  # noqa: E402
from lindefense.ui.tutorial_script import TutorialScript  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402
from lindefense.ui.ui_button import UIButton  # noqa: E402
from lindefense.ui.victory_epilogue import VictoryEpilogue  # noqa: E402
from lindefense.ui import story_view as StoryView  # noqa: E402
from lindefense.ui.world_view import WorldView  # noqa: E402

GameScreen.serial_version_uid = 1
GameScreen.MAX_SIM_STEPS_PER_FRAME = 8
