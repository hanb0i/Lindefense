"""Lindefense DemoDriver (ported from src/lindefense/ui/DemoDriver.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.enemy.types import EnemyType
from lindefense.sim.game import Game
from lindefense.sim.misc import HeroCollection
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType
from lindefense.variance.variance import RunVariance
import sys


class DemoDriver:
    """Optional scripted walkthrough used for automated UI verification. Enabled
with LINDEFENSE_DEMO=<output dir>; it drives the real screens
through the program's own mouse handlers (pixel coordinates mapped through
the scaled layer), resizes the window, verifies click-to-place lands on the
cursor at each size, writes PNG snapshots of the canvas, and exits.
Not used in normal play."""
    def __init__(self, app, dir_):
        self.app = None
        self.out = None
        self.t = 0.0
        self.next = 0
        self.steps = _j.ArrayList()
        self.results = _j.ArrayList()
        self.app = app
        self.out = _j.File(dir_)
        self.out.mkdirs()
        # the walkthrough keeps its records and saved run to itself: nothing it plays reaches the player's RECORDS or
        # CONTINUE (records in memory, the save slot in the output folder; the menu is rebuilt without a CONTINUE)
        Records._shared = Records.in_memory()
        CampaignProgress._shared = CampaignProgress.in_memory()   # campaign stars / BOOT CAMP stay with the walkthrough
        from lindefense.sim import campaign_story
        campaign_story.StoryLog._shared = campaign_story.StoryLog.in_memory(campaign_story.scene_keys())   # no scenes
        savegame._default = savegame.SaveSlot(_j.File(self.out, 'demo_run_save.bin').get_path())
        savegame.slot().delete()
        if app.get_menu() is not None:
            app.show_menu()
        times = ([0.0] * 51)
        sched = [[0, 2.6], [1, 2.8], [2, 3.8], [3, 4.0], [4, 10.0], [5, 11.5], [6, 13.0], [7, 13.5], [8, 15.0], [9, 15.5], [10, 17.0], [11, 19.5], [12, 32.0], [13, 10.2], [14, 10.4], [15, 0.5], [16, 1.6], [17, 1.9], [18, 2.2], [19, 2.5], [20, 10.5], [21, 10.7], [22, 10.9], [23, 11.1], [24, 11.3], [25, 19.7], [26, 20.0], [27, 20.1], [28, 20.4], [29, 20.7], [30, 20.8], [31, 23.4], [32, 23.6], [33, 23.7], [34, 25.8], [35, 11.35], [36, 26.0], [37, 26.2], [38, 26.5], [39, 26.9], [40, 27.3], [41, 27.6], [42, 27.9], [43, 28.3], [44, 28.7], [45, 29.1], [46, 29.6], [47, 31.0], [48, 23.5], [49, 31.3], [50, 31.6]]
        for sc in sched:
            times[_j.to_int(sc[0])] = sc[1]
        for i in range(len(times)):
            _j_add(self.steps, [times[i], i])
        _j.sort(self.steps, _j.Fn(lambda a, b: _j.compare(a[0], b[0])))
    def frame(self, dt):
        self.t += dt
        while (self.next < len(self.steps)) and (self.t >= self.steps[self.next][0]):
            idx = _j.to_int(self.steps[self.next][1])
            self.next += 1
            try:
                self.run(idx)
            except Exception as e:
                _j_add(self.results, _j.cat('FAIL step ', idx, ': ', e))
                _j.print_stack_trace(e)
    def run(self, idx):
        canvas = self.app.get_g_canvas()
        _sw1 = idx
        if _sw1 == 0:
            self.snap('01_menu')
        elif _sw1 == 1:
            self.click_logical(*self.menu_button_point('CLASSIC', 571))
        elif _sw1 == 2:
            self.snap('02_mapselect')
            for k in range(3):
                self.press_key(KeyEvent.VK_ESCAPE)
            on_menu = ((self.app.get_menu() is not None) and (self.app.get_map_select() is None))
            self.click_logical(*self.menu_button_point('CLASSIC', 571))
            reopened = ((self.app.get_map_select() is not None) and (self.app.get_menu() is None))
            _j_add(self.results, _j.cat(('PASS' if (on_menu and reopened) else 'FAIL'), ' Esc to the menu keeps its buttons working (menu ', on_menu, ', CLASSIC reopened map select ', reopened, ')'))
            self.click_logical(90, 49)
            on_menu2 = ((self.app.get_menu() is not None) and (self.app.get_map_select() is None))
            self.click_logical(*self.menu_button_point('CLASSIC', 571))
            reopened2 = ((self.app.get_map_select() is not None) and (self.app.get_menu() is None))
            _j_add(self.results, _j.cat(('PASS' if (on_menu2 and reopened2) else 'FAIL'), ' BACK button click to the menu keeps its buttons working (menu ', on_menu2, ', CLASSIC reopened map select ', reopened2, ')'))
            pass  # break
        elif _sw1 == 3:
            dc = MapSelectScreen.deploy_center(0)
            self.click_logical(dc[0], dc[1])
            ms = self.app.get_map_select()
            popup = ((((self.app.get_game() is None) and (ms is not None)) and ms.is_briefing_open()) and (ms.get_briefing_map() == 0))
            self.press_key(KeyEvent.VK_ESCAPE)
            closed = (((self.app.get_map_select() is ms) and (ms is not None)) and (not ms.is_briefing_open()))
            self.click_logical(dc[0], dc[1])
            if ms is not None:
                ms.frame(0.05)
            self.snap('02b_briefing')
            bc = MapSelectScreen.briefing_deploy_center()
            self.click_logical(bc[0], bc[1])
            started = (self.app.get_game() is not None)
            _j_add(self.results, _j.cat(('PASS' if ((popup and closed) and started) else 'FAIL'), ' DEPLOY opens the map briefing, Esc closes it, its DEPLOY starts the match (popup ', popup, ', closed ', closed, ', started ', started, ')'))
            g = self.app.get_game()
            gd = self.app.get_game_screen()
            gd.frame(0.05)
            draft = (((g.get_variance().is_enabled() and g.get_variance().is_draft_pending()) and gd.is_draft_open()) and (not g.get_wave_manager().can_start_next_wave()))
            self.snap('02c_patch_notes_draft')
            second = (g.get_variance().get_offer()[1] if (len(g.get_variance().get_offer()) > 1) else None)
            self.press_key(KeyEvent.VK_2)
            gd.frame(0.05)
            shipped = ((((second is not None) and (len(g.get_variance().get_active()) == 1)) and (g.get_variance().get_active()[0] is second)) and (not gd.is_draft_open()))
            _j_add(self.results, _j.cat(('PASS' if (draft and shipped) else 'FAIL'), ' launch patch-notes draft blocks wave 1 and key 2 ships the second card (draft ', draft, ', shipped ', shipped, ')'))
            self.auto_pick()
            g.add_cash(5000, None)
            g.set_hero_collection(HeroCollection.in_memory())
            for h in TowerType.heroes():
                g.get_hero_collection().unlock(h)
            self.place_via_click(TowerType.GPT, Vec(380, 300))
            self.place_via_click(TowerType.CLAUDE, Vec(700, 250))
            self.place_via_click(TowerType.PERPLEXITY, Vec(460, 520))
            self.place_via_click(TowerType.LOBBER_LUIS, Vec(560, 480))
            self.place_via_click(TowerType.SUNO, Vec(820, 660))
            gs = self.app.get_game_screen()
            gs.begin_placing(TowerType.GPT)
            self.press_key(KeyEvent.VK_ESCAPE)
            cancelled = ((not gs.is_menu_open()) and (gs.get_placing() is None))
            _j_add(self.results, _j.cat(('PASS' if cancelled else 'FAIL'), ' Esc first cancels a tower placement (menu stays closed)'))
            self.press_key(KeyEvent.VK_ESCAPE)
            opened = (gs.is_menu_open() and (gs.get_placing() is None))
            self.press_key(KeyEvent.VK_ESCAPE)
            resumed = (not gs.is_menu_open())
            self.press_key(KeyEvent.VK_ESCAPE)
            again = gs.is_menu_open()
            self.press_key(KeyEvent.VK_ESCAPE)
            _j_add(self.results, _j.cat(('PASS' if (((opened and resumed) and again) and (not gs.is_menu_open())) else 'FAIL'), ' Esc toggles the in-game menu (opened ', opened, ', resumed ', resumed, ', reopened ', again, ')'))
            self.app.get_game_screen().key_pressed(KeyEvent(canvas, 0, 0, 0, KeyEvent.VK_SPACE, ' '))
            self.app.get_game_screen().set_speed(3)
            for k in range(12):
                g.get_wave_manager().start_next_wave()
            pass  # break
        elif _sw1 == 4:
            for tw in self.app.get_game().get_tower_manager().get_towers():
                if tw.get_type() is TowerType.LOBBER_LUIS:
                    self.app.get_game_screen().select_tower(tw)
            self.app.get_game_screen().frame(0.01)
            self.snap('03_game_default')
            self.app.get_game_screen().set_speed(1)
            pass  # break
        elif _sw1 == 5:
            self.resize(900, 600)
            pass  # break
        elif _sw1 == 6:
            self.snap('04_game_small_900x600')
            self.verify_click('small')
            pass  # break
        elif _sw1 == 7:
            self.resize(2400, 1400)
            pass  # break
        elif _sw1 == 8:
            self.snap('05_game_large_2400x1400')
            self.verify_click('large')
            pass  # break
        elif _sw1 == 9:
            self.resize(1500, 950)
            g = self.app.get_game()
            while g.get_wave() < 99:
                g.get_wave_manager().start_next_wave()
                g.get_wave_manager().end_wave()
            g.get_enemy_manager().clear()
            g.start_next_wave()
            g.get_enemy_manager().spawn(EnemyType.BELLARMINE_COLLEGE_PREP, None, 1, 400)
            g.add_cash(20000, None)
            for tw in _j.ArrayList(g.get_tower_manager().get_towers()):
                for u in range(3):
                    g.upgrade_tower(tw)
            g.set_speed(3)
            pass  # break
        elif _sw1 == 10:
            g = self.app.get_game()
            if g.get_palantir() is not None:
                g.get_palantir().begin_surveillance(g)
            pass  # break
        elif _sw1 == 11:
            g = self.app.get_game()
            ok = (((g.get_wave() == 100) and (g.get_palantir() is not None)) and g.get_palantir().is_alive())
            _j_add(self.results, _j.cat(('PASS' if ok else 'FAIL'), ' finale fights Palantir on wave 100 (wave ', g.get_wave(), ', palantir ', (g.get_palantir() is not None), ')'))
            self.snap('06_palantir')
            pass  # break
        elif _sw1 == 13:
            self.app.get_game_screen().toggle_shop_all()
            for k in range(4):
                self.app.get_game_screen().frame(0.01)
            last_cell = (len(ShopLayout.all_cells()) - 1)
            want = ShopLayout.all_cells()[last_cell].type
            btns = self.app.get_game_screen().get_side_panel().get_buttons()
            card = btns[((len(ShopLayout.shop_factions()) + 2) + last_cell)]
            mv = self.pixel_event((card.get_x() + 5), (card.get_y() + 5))
            self.app.mouse_moved(mv)
            self.app.get_game_screen().frame(0.01)
            self.snap('03b_shop_all')
            self.app.mouse_pressed(mv)
            ok = ((self.app.get_game_screen().get_placing() is want) and self.app.get_game_screen().get_side_panel().is_all_mode())
            _j_add(self.results, _j.cat(('PASS' if ok else 'FAIL'), ' ALL-view cell click starts placement of ', want, ' (got ', self.app.get_game_screen().get_placing(), ')'))
            self.app.get_game_screen().begin_placing(None)
            side = self.app.get_game_screen().get_side_panel()
            side.toggle_shop_collapsed()
            self.app.get_game_screen().frame(0.01)
            self.snap('03i_shop_collapsed')
            collapsed = side.is_shop_collapsed()
            side.toggle_shop_collapsed()
            self.app.get_game_screen().frame(0.01)
            restored = (not side.is_shop_collapsed())
            _j_add(self.results, _j.cat(('PASS' if (collapsed and restored) else 'FAIL'), ' COLLAPSE SHOP hides the card grid and EXPAND SHOP restores it (collapsed ', collapsed, ', restored ', restored, ')'))
            pass  # break
        elif _sw1 == 14:
            self.app.get_game_screen().toggle_shop_all()
            pass  # break
        elif _sw1 == 15:
            self.snap('00_menu_intro')
        elif _sw1 == 16:
            self.resize(900, 600)
            pass  # break
        elif _sw1 == 17:
            self.snap('00b_menu_small')
            self.resize(2400, 1400)
            pass  # break
        elif _sw1 == 18:
            self.snap('00c_menu_large')
            self.resize(1600, 1028)
            pass  # break
        elif _sw1 == 19:
            self.menu_settings_audio_flow()
            self.app.mouse_moved(self.pixel_event((Ui.W / 2.0), 528))
            pass  # break
        elif _sw1 == 20:
            g = self.app.get_game()
            ts = [EnemyType.PRIMITIVE_VARIABLE, EnemyType.STATIC_ARRAY, EnemyType.DYNAMIC_ARRAY, EnemyType.BUBBLE_SORT, EnemyType.MERGE_SORT, EnemyType.QUICK_SORT, EnemyType.HEAP_SORT, EnemyType.SHELL_SORT, EnemyType.TIMSORT, EnemyType.RADIX_SORT]
            routes = len(g.get_map().get_routes())
            for i in range(100):
                e = g.get_enemy_manager().spawn(ts[_j.imod(i, len(ts))], None, _j.imod(i, routes), (40 + (i * 9)))
                if (e is not None) and (_j.imod(i, 3) != 0):
                    e.take_damage((e.get_max_hp() * (0.12 + ((0.75 * _j.imod((i * 37), 100)) / 100.0))), g.get_time())
            pass  # break
        elif _sw1 == 21:
            self.snap('03c_busy_wave')
        elif _sw1 == 22:
            self.app.get_game_screen().begin_placing(TowerType.CLAUDE)
            wp = self.app.get_game().get_map().get_routes()[0].get_waypoints()[2]
            self.app.mouse_moved(self.world_event(wp))
            self.app.get_game_screen().frame(0.01)
            self.snap('03d_placing_invalid')
            pass  # break
        elif _sw1 == 23:
            g = self.app.get_game()
            try:
                for yy in range(100, 800, 20):
                    for xx in range(100, 1100, 20):
                        v = Vec(xx, yy)
                        if g.get_tower_manager().placement_problem(TowerType.CLAUDE, v) is None:
                            self.app.mouse_moved(self.world_event(v))
                            raise _j.Break('outer')
            except _j.Break as _brk:
                if _brk.label != 'outer':
                    raise
            self.app.get_game_screen().frame(0.01)
            self.snap('03e_placing_valid')
            self.app.get_game_screen().begin_placing(None)
            self.app.get_game_screen().select_tower(None)
            self.app.mouse_moved(self.world_event(Vec(700, 250)))
            pass  # break
        elif _sw1 == 24:
            self.snap('03f_hover_nameplate')
            self.app.mouse_moved(self.pixel_event(5, 5))
        elif _sw1 == 25:
            g = self.app.get_game()
            bs = [EnemyType.BELLARMINE_COLLEGE_PREP, EnemyType.SW_RESOURCE_CONSULTANT, EnemyType.THREE_COM, EnemyType.LOCKHEED_MARTIN]
            for i in range(len(bs)):
                e = g.get_enemy_manager().spawn(bs[i], None, 0, (250 + (i * 160)))
                if e is not None:
                    e.take_damage((e.get_max_hp() * (0.1 + (0.15 * i))), g.get_time())
            if g.get_palantir() is not None:
                g.get_palantir().take_damage((g.get_palantir().get_max_hp() * 0.3), g.get_time())
            pass  # break
        elif _sw1 == 26:
            self.snap('06b_multi_boss')
        elif _sw1 == 27:
            self.app.get_game().set_paused(True)
        elif _sw1 == 28:
            self.snap('07_paused')
            g = self.app.get_game()
            g.set_paused(False)
            if g.get_palantir() is not None:
                g.lose_lives(max(0, (g.get_lives() - 18)), g.get_palantir())
            pass  # break
        elif _sw1 == 29:
            self.snap('06c_low_lives')
        elif _sw1 == 30:
            g = self.app.get_game()
            if g.get_palantir() is not None:
                g.get_palantir().take_damage(1e12, g.get_time())
            g.set_speed(3)
            pass  # break
        elif _sw1 == 31:
            ok = (self.app.get_game().get_state() is Game.State.VICTORY)
            _j_add(self.results, _j.cat(('PASS' if ok else 'FAIL'), ' victory screen reached (state ', self.app.get_game().get_state(), ')'))
            self.snap('08_victory')
            pass  # break
        elif _sw1 == 32:
            self.app.start_game(0)
            self.auto_pick()
        elif _sw1 == 33:
            g = self.app.get_game()
            e = g.get_enemy_manager().spawn(EnemyType.STATIC_ARRAY, None, 0, 100)
            g.lose_lives(g.get_lives(), e)
            g.set_speed(3)
            pass  # break
        elif _sw1 == 34:
            self.snap('09_defeat')
        elif _sw1 == 35:
            gs = self.app.get_game_screen()
            gs.toggle_shop_all()
            gs.frame(0.01)
            gs.frame(0.01)
            self.snap('03g_shop_all_idle')
            gs.toggle_shop_all()
            gs.toggle_help()
            gs.frame(0.01)
            self.snap('03h_help_overlay')
            gs.toggle_help()
            pass  # break
        elif _sw1 == 36:
            self.menu_restart_flow()
        elif _sw1 == 37:
            self.resize(900, 600)
        elif _sw1 == 38:
            gs = self.app.get_game_screen()
            gs.open_menu()
            gs.frame(0.01)
            self.snap('10d_pause_menu_small')
            self.resize(2400, 1400)
            pass  # break
        elif _sw1 == 39:
            self.snap('10e_pause_menu_large')
            self.resize(1600, 1028)
            pass  # break
        elif _sw1 == 40:
            self.menu_quit_flow()
        elif _sw1 == 41:
            self.reverse_flow()
        elif _sw1 == 42:
            self.records_flow()
        elif _sw1 == 43:
            self.settings_rows_flow()
        elif _sw1 == 44:
            self.daily_and_seed_flow()
        elif _sw1 == 45:
            self.continue_flow()
        elif _sw1 == 46:
            self.lose_continued_run()
        elif _sw1 == 47:
            self.end_report_flow()
        elif _sw1 == 48:
            self.victory_report_flow()
        elif _sw1 == 49:
            self.campaign_flow()
        elif _sw1 == 50:
            self.tutorial_flow()
        elif _sw1 == 12:
            for r in self.results:
                print(_j.s(r))
            print(_j.s('DEMO DONE'))
            sys.exit(0)
            pass  # break
        else:
            pass
    def check(self, ok, what):
        _j_add(self.results, _j.cat(('PASS ' if ok else 'FAIL '), what))
    def auto_pick(self):
        """PATCH NOTES: the scripted run jumps waves, so the current match answers its drafts itself (first card)."""
        g = self.app.get_game()
        if g is not None:
            g.get_variance().set_picker(RunVariance.Picker.FIRST)
    def menu_restart_flow(self):
        """MENU -> RESTART -> confirm: a fresh game on the same map and difficulty (wave, cash, lives, towers reset)."""
        self.app.start_game(0)
        self.auto_pick()
        gs = self.app.get_game_screen()
        g0 = self.app.get_game()
        g0.add_cash(3000, None)
        self.place_via_click(TowerType.GPT, Vec(380, 300))
        g0.start_next_wave()
        g0.run(300)
        progressed = ((g0.get_wave() > 0) and (not (len(g0.get_tower_manager().get_towers()) == 0)))
        gs.open_menu()
        gs.frame(0.01)
        self.check((gs.is_menu_open() and g0.is_paused()), 'MENU button path opens the pause menu and pauses the game')
        self.snap('10_pause_menu')
        self.pause_audio_flow(gs)
        self.click_logical(600, 489)
        self.check(((gs.get_pending_confirm() == 1) and (self.app.get_game() is g0)), 'RESTART asks for confirmation first')
        gs.frame(0.01)
        self.snap('10b_restart_confirm')
        self.click_logical(735, 595)
        self.check((((gs.get_pending_confirm() == 0) and (self.app.get_game() is g0)) and gs.is_menu_open()), 'NO keeps the current game and returns to the menu')
        self.click_logical(600, 489)
        self.click_logical(465, 595)
        g1 = self.app.get_game()
        # cash: at least the starting credits (the auto-picked launch Patch Notes card can be Venture Capital, +$3,400)
        self.check(((((((((progressed and (g1 is not g0)) and (g1.get_wave() == 0)) and (g1.get_lives() == g1.get_difficulty().start_lives(Game.START_LIVES))) and (g1.get_cash() >= g1.get_difficulty().start_cash(Game.START_CASH))) and (len(g1.get_tower_manager().get_towers()) == 0)) and (g1.get_map().get_name() == g0.get_map().get_name())) and (g1.get_difficulty() is g0.get_difficulty())) and (not g1.is_paused())), _j.cat('RESTART YES gives a fresh game on the same map and difficulty (wave ', g1.get_wave(), ', cash ', _j.to_int(g1.get_cash()), ', lives ', g1.get_lives(), ')'))
        self.check((self.app.get_game_screen() is not gs), 'old game screen was replaced')
    def menu_quit_flow(self):
        """MENU -> QUIT LEVEL -> confirm: back on the map select screen."""
        gs = self.app.get_game_screen()
        gs.open_menu()
        gs.frame(0.01)
        self.click_logical(600, 657)
        self.check(((gs.get_pending_confirm() == 2) and (self.app.get_game() is not None)), 'QUIT LEVEL asks for confirmation first')
        self.click_logical(465, 595)
        self.check(((self.app.get_game() is None) and (self.app.get_game_screen() is None)), 'QUIT LEVEL YES leaves the game (map select shown)')
        self.snap('10c_quit_to_mapselect')
    @staticmethod
    def find_sliders(o, into):
        """Every Slider under c, in paint order."""
        if isinstance(o, Slider):
            _j_add(into, o)
        elif isinstance(o, GCompound):
            c = o
            i = 0
            while i < c.get_element_count():
                DemoDriver.find_sliders(c.get_element(i), into)
                i += 1
        return into
    def drag_slider(self, s, from_, to):
        """Presses a slider's track at from (0-1) and drags to to through the program's real mouse handlers."""
        a = self.pixel_event((s.get_track_left() + (s.get_track_width() * from_)), s.get_center_y())
        self.app.mouse_moved(a)
        self.app.mouse_pressed(a)
        b = self.pixel_event((s.get_track_left() + (s.get_track_width() * to)), (s.get_center_y() + 30))
        self.app.mouse_dragged(b)
        s.animate(0.3)
        return b
    def menu_settings_audio_flow(self):
        """Main menu SETTINGS > AUDIO: open the panel, drag the MUSIC slider, snapshot, release, close."""
        am = AudioManager.get()
        self.click_logical(*self.menu_button_point('SETTINGS', 745))
        sl = DemoDriver.find_sliders(self.app.get_root(), _j.ArrayList())
        self.check(((len(sl) == 2) and (am is not None)), _j.cat('SETTINGS has a SOUND and a MUSIC volume slider (', len(sl), ')'))
        if (len(sl) != 2) or (am is None):
            return
        before = am.get_music_volume()
        up = self.drag_slider(sl[1], 1.0, 0.35)
        self.check(((abs((am.get_music_volume() - 35)) <= 1) and sl[1].is_dragging()), _j.cat('SETTINGS music slider drag sets the level live (', am.get_music_volume(), ')'))
        self.snap('01b_menu_settings_audio')
        self.app.mouse_released(up)
        self.check((((not sl[1].is_dragging()) and am.is_music_enabled()) and (am.get_sound_volume() == sl[0].get_value())), 'release ends the drag; music stays on; sound untouched')
        am.set_music_volume(before)
        self.app.key_pressed(KeyEvent(self.app.get_g_canvas(), 0, 0, 0, KeyEvent.VK_ESCAPE, _j.to_char(27)))
    def pause_audio_flow(self, gs):
        """Pause menu: drag the SOUND slider, mute MUSIC with its toggle (level kept, slider greyed), unmute with M."""
        am = AudioManager.get()
        sl = DemoDriver.find_sliders(gs, _j.ArrayList())
        self.check(((len(sl) == 2) and (am is not None)), _j.cat('pause menu has a SOUND and a MUSIC volume slider (', len(sl), ')'))
        if (len(sl) != 2) or (am is None):
            return
        snd = sl[0]
        mus = sl[1]
        s_before = am.get_sound_volume()
        m_before = am.get_music_volume()
        up = self.drag_slider(snd, (snd.get_value() / 100.0), 0.45)
        self.check((abs((am.get_sound_volume() - 45)) <= 1), _j.cat('pause SOUND slider drag sets the effects level (', am.get_sound_volume(), ')'))
        self.snap('10f_pause_volume_drag')
        self.app.mouse_released(up)
        self.click_logical((mus.get_x() - 100), mus.get_center_y())
        gs.frame(0.01)
        self.check(((((not am.is_music_enabled()) and (am.get_music_volume() == m_before)) and mus.is_inactive()) and (mus.get_value() == m_before)), _j.cat('MUSIC toggle mutes without touching the level; slider greyed (', mus.get_value(), ')'))
        self.snap('10g_pause_music_muted')
        self.app.key_pressed(KeyEvent(self.app.get_g_canvas(), 0, 0, 0, KeyEvent.VK_M, 'm'))
        gs.frame(0.01)
        self.check(((am.is_music_enabled() and (am.get_music_volume() == m_before)) and (not mus.is_inactive())), 'M unmutes music at its kept level')
        am.set_sound_volume(s_before)
        self.app.mouse_moved(self.pixel_event(5, 5))
    def resize(self, w, h):
        self.app.resize_window(w, h)
    def pixel_event(self, lx, ly):
        root = self.app.get_root()
        px = _j.to_int(_j.jround(((lx * root.get_scale()) + ((self.app.get_g_canvas().get_width() - (Ui.W * root.get_scale())) / 2))))
        py = _j.to_int(_j.jround(((ly * root.get_scale()) + ((self.app.get_g_canvas().get_height() - (Ui.H * root.get_scale())) / 2))))
        return MouseEvent(self.app.get_g_canvas(), MouseEvent.MOUSE_PRESSED, _j.current_time_millis(), 0, px, py, 1, False, MouseEvent.BUTTON1)
    def world_event(self, w):
        """A mouse event at the pixel where world point w is drawn."""
        l = self.app.get_game_screen().world_to_logical(w)
        return self.pixel_event(l[0], l[1])
    def reverse_flow(self):
        """Adversarial Training through the real UI: from map select (where QUIT LEVEL left us), DEPLOY opens the briefing,
ATTACK INSTEAD switches it to the reverse briefing, ATTACK starts the match, a unit card click queues a unit, and
Esc still toggles the pause menu."""
        if self.app.get_map_select() is None:
            _j_add(self.results, 'FAIL reverse mode: map select not showing after QUIT LEVEL')
            return
        dc = MapSelectScreen.deploy_center(0)
        self.click_logical(dc[0], dc[1])
        mc = MapSelectScreen.briefing_mode_center()
        self.click_logical(mc[0], mc[1])
        reverse_briefing = ((self.app.get_map_select() is not None) and self.app.get_map_select().is_reverse_briefing())
        self.app.get_map_select().frame(0.05)
        self.snap('11_reverse_briefing')
        bc = MapSelectScreen.briefing_deploy_center()
        self.click_logical(bc[0], bc[1])
        g = self.app.get_game()
        started = ((g is not None) and g.is_reverse())
        sent = False
        if started:
            for i in range(3):
                self.app.get_game_screen().frame(0.02)
            before = g.get_reverse().get_queued()
            cc = AttackPanel.card_center(0)
            self.click_logical(cc[0], cc[1])
            sent = (g.get_reverse().get_queued() > before)
            for i in range(3):
                self.app.get_game_screen().frame(0.02)
            self.snap('11b_reverse_match')
        _j_add(self.results, _j.cat(('PASS' if ((reverse_briefing and started) and sent) else 'FAIL'), ' Adversarial Training: ATTACK INSTEAD briefing, ATTACK starts a reverse match, a card click queues a unit (briefing ', reverse_briefing, ', started ', started, ', sent ', sent, ')'))
        if not started:
            return
        self.press_key(KeyEvent.VK_ESCAPE)
        open_ = self.app.get_game_screen().is_menu_open()
        self.press_key(KeyEvent.VK_ESCAPE)
        _j_add(self.results, _j.cat(('PASS' if (open_ and (not self.app.get_game_screen().is_menu_open())) else 'FAIL'), ' Esc toggles the pause menu in reverse mode'))
    # ---------------------------------------------------------------- final-beta screens
    def type_key(self, code, ch):
        """Sends a typed key (code and character) through the program's real key routing."""
        self.app.key_pressed(KeyEvent(self.app.get_g_canvas(), KeyEvent.KEY_PRESSED, 0, 0, code, ch))
    @staticmethod
    def center_of(b):
        return [(b.get_x() + (b.w / 2.0)), (b.get_y() + (b.h / 2.0))]
    def overlay_button(self, text):
        gs = self.app.get_game_screen()
        for b in (gs.overlay_buttons if (gs is not None) else ()):
            if b.get_text() == text:
                return b
        return None
    def leave_to_menu(self):
        """Pause menu -> MAIN MENU -> Enter, through the real UI (Esc first drops a selection)."""
        gs = self.app.get_game_screen()
        for k in range(3):
            if gs.is_menu_open():
                break
            self.press_key(KeyEvent.VK_ESCAPE)
        b = self.overlay_button('MAIN MENU')
        if b is not None:
            self.click_logical(*self.center_of(b))
            self.press_key(KeyEvent.VK_ENTER)
        return self.app.get_menu() is not None
    def records_flow(self):
        """Main menu RECORDS: every tab by click (the history holds this walkthrough's runs), a resize while it is open
keeps clicks mapped, Esc closes it."""
        on_menu = self.leave_to_menu()
        self.check(on_menu, 'MAIN MENU (pause menu, Enter) leaves the reverse match for the main menu')
        if not on_menu:
            return
        self.click_logical(*self.menu_button_point('RECORDS', 629))
        m = self.app.get_menu()
        st = m.stats
        self.check((m.stats_shown and (st is not None)), 'RECORDS opens the records screen')
        if st is None:
            return
        tabs = StatsScreen.Tab.values()
        for t in tabs:
            self.click_logical(*self.center_of(st.tabs[t.ordinal]))
            st.frame(0.05)
            self.snap(_j.cat('12_records_', t.label.lower()))
            self.check((st.get_tab() is t), _j.cat('RECORDS tab ', t.label, ' opens by click'))
        rec = Records.persistent()
        results = [h.get('result') for h in rec.history()]
        self.check((('victory' in results) and ('defeat' in results) and (len(st.replay_buttons) == len(results))), _j.cat('HISTORY lists the walkthrough runs with a REPLAY SEED each (', results, ')'))
        self.check((rec.unlocked_count() >= 1), _j.cat('the walkthrough victory unlocked achievements (', rec.unlocked_count(), ')'))
        self.resize(900, 600)
        self.click_logical(*self.center_of(st.tabs[0]))
        small = (st.get_tab() is tabs[0])
        self.resize(1600, 1028)
        self.click_logical(*self.center_of(st.tabs[2]))
        self.check((small and (st.get_tab() is tabs[2])), 'RECORDS tabs still click right after resizing the window')
        self.press_key(KeyEvent.VK_ESCAPE)
        self.check(((not m.stats_shown) and (m.stats is None) and (self.app.get_menu() is m)), 'Esc closes RECORDS back to the menu')
    def settings_rows_flow(self):
        """SETTINGS > DISPLAY / ACCESSIBILITY rows: each chip switches its setting by click and back, the hovered chip
explains itself in the hint line, Esc closes the panel."""
        self.click_logical(*self.menu_button_point('SETTINGS', 745))
        m = self.app.get_menu()
        ds = DisplaySettings.get()
        self.check(m.settings_shown, 'SETTINGS opens')
        rows = [(m.motion_chip, 'REDUCED MOTION', 'reduced_motion'), (m.colour_chip, 'COLOUR-BLIND SAFE', 'colour_blind'), (m.fps_counter_chip, 'FPS COUNTER', 'show_fps')]
        for chip, label, attr in rows:
            before = getattr(ds, attr)
            self.click_logical(*self.center_of(chip))
            on = getattr(ds, attr)
            text = chip.get_text()
            if attr == 'colour_blind':
                self.snap('13_settings_rows_on')
            self.click_logical(*self.center_of(chip))
            self.check((((on != before) and (text == _j.cat(label, (': ON' if on else ': OFF')))) and (getattr(ds, attr) == before)), _j.cat('SETTINGS ', label, ' switches by click and back (', text, ')'))
        self.app.mouse_moved(self.pixel_event(*self.center_of(m.motion_chip)))
        self.check(m.access_hint.get_label().startswith('Reduced motion:'), _j.cat('hovering a row explains it (', m.access_hint.get_label(), ')'))
        self.press_key(KeyEvent.VK_ESCAPE)
        self.check((not m.settings_shown), 'Esc closes SETTINGS')
    def daily_and_seed_flow(self):
        """CLASSIC -> the DAILY RUN card's briefing (locked seed and rule) -> Esc; a map's briefing: click the SEED field,
type a run code (M types a letter instead of toggling music), switch NO SELLING on, Enter deploys that seed and rule."""
        self.click_logical(*self.menu_button_point('CLASSIC', 571))
        ms = self.app.get_map_select()
        if ms is None:
            self.check(False, 'CLASSIC opens map select')
            return
        daily_btn = None
        for b in ms.buttons:
            if (getattr(b, 'text', None) is not None) and (b.text.get_label() in ('PLAY DAILY', 'DAILY RUN')):
                daily_btn = b
        if daily_btn is not None:
            self.click_logical(*self.center_of(daily_btn))
        day = DailyRun.today()
        rs = ms.get_run_setup()
        ok = (ms.is_daily_briefing() and (rs is not None))
        if ok:
            self.click_logical(*self.center_of(rs.field))
            ms.frame(0.05)
            self.snap('14_daily_briefing')
            ok = ((((rs.field.text == day.seed_text()) and rs.field.locked) and (not ms.is_typing())) and (rs.challenges() == day.challenges))
        self.check(ok, _j.cat('PLAY DAILY opens the daily briefing: seed ', day.seed_text(), ' and rule ', day.rule.chip, ' locked'))
        self.press_key(KeyEvent.VK_ESCAPE)
        self.check((not ms.is_briefing_open()), 'Esc closes the daily briefing')
        dc = MapSelectScreen.deploy_center(0)
        self.click_logical(dc[0], dc[1])
        rs = ms.get_run_setup()
        self.click_logical(*self.center_of(rs.field))
        typing = ms.is_typing()
        am = AudioManager.get()
        music = ((am is not None) and am.is_music_enabled())
        for ch in 'demo42':
            self.type_key(ord(ch.upper()), ch)
        kept = ((am is None) or (am.is_music_enabled() == music))
        rule = None
        for c, b in rs.toggles:
            if c is Challenge.NO_SELLING:
                rule = b
        self.click_logical(*self.center_of(rule))
        ms.frame(0.05)
        self.snap('14b_seed_typed')
        self.check(((((typing and kept) and (rs.field.text == 'demo42')) and (rs.status_head.get_label() == 'RUN CODE DEMO42')) and (RunOptions.get().challenges == (Challenge.NO_SELLING,))), _j.cat('SEED field takes typed text (M is a letter there) and NO SELLING switches on (', rs.field.text, ')'))
        self.click_logical(*self.center_of(rs.field))
        self.press_key(KeyEvent.VK_ENTER)
        g = self.app.get_game()
        RunOptions.get().set_challenges(())   # the session's rules go back to none for the rest of the walkthrough
        self.check(((((g is not None) and (g.get_seed() == seed_parse('DEMO42'))) and (g.get_challenges() == (Challenge.NO_SELLING,))) and ('custom-seed' in g.run_tags)), _j.cat('Enter in the SEED field deploys that seed and rule (', (g.run_tags if (g is not None) else None), ')'))
        self.auto_pick()
    def continue_flow(self):
        """Save & Continue through the UI: build, start wave 1, QUIT LEVEL (the confirmation says the run is saved) ->
map select -> Esc -> the main menu offers CONTINUE -> it restores the run exactly (paused mid-wave)."""
        g = self.app.get_game()
        if g is None:
            self.check(False, 'a run to save')
            return
        self.app.autosave = savegame.Autosave(g)   # the walkthrough's own slot (see __init__)
        g.add_cash(1000, None)
        self.place_via_click(TowerType.GPT, Vec(380, 300))
        self.press_key(KeyEvent.VK_SPACE)
        g.run(120)
        before = (g.get_seed(), g.get_tick(), g.get_cash(), g.get_lives(), len(g.get_tower_manager().get_towers()), g.get_challenges())
        gs = self.app.get_game_screen()
        for k in range(3):
            if gs.is_menu_open():
                break
            self.press_key(KeyEvent.VK_ESCAPE)
        b = self.overlay_button('QUIT LEVEL')
        if b is not None:
            self.click_logical(*self.center_of(b))
        gs.frame(0.01)
        promised = any(('Your run is saved' in t) for t in DemoDriver.labels_in(gs.overlay))
        self.press_key(KeyEvent.VK_ENTER)
        saved = ((self.app.get_map_select() is not None) and savegame.slot().exists())
        self.check((promised and saved), _j.cat('QUIT LEVEL says the run is saved, and it is (promised ', promised, ', saved ', saved, ')'))
        self.press_key(KeyEvent.VK_ESCAPE)
        m = self.app.get_menu()
        cont = (m.continue_button if (m is not None) else None)
        self.check((cont is not None), 'the main menu offers CONTINUE after a quit')
        if cont is None:
            return
        m.frame(0.05)
        self.snap('15_menu_continue')
        self.click_logical(*self.center_of(cont))
        h = self.app.get_game()
        after = (None if (h is None) else (h.get_seed(), h.get_tick(), h.get_cash(), h.get_lives(), len(h.get_tower_manager().get_towers()), h.get_challenges()))
        self.check((((after == before) and (h is not g)) and h.is_paused()), _j.cat('CONTINUE restores the run exactly, paused mid-wave (', after, ')'))
        self.app.get_game_screen().frame(0.05)
        self.snap('15b_continued')
        savegame.slot().delete()
        self.auto_pick()
    def lose_continued_run(self):
        g = self.app.get_game()
        if g is None:
            return
        self.press_key(KeyEvent.VK_P)
        g.set_speed(3)
        e = g.get_enemy_manager().spawn(EnemyType.STATIC_ARRAY, None, 0, 100)
        g.lose_lives(g.get_lives(), e)
    def end_report_flow(self):
        """The defeat panel of the continued run: its rule chip, then Tab to the REPORT page and back by click."""
        gs = self.app.get_game_screen()
        g = self.app.get_game()
        lost = ((g is not None) and (g.get_state() is Game.State.DEFEAT))
        self.check((lost and ('NO SELLING' in DemoDriver.labels_in(gs.overlay))), _j.cat('the continued run ends on the defeat panel with its rule chip (state ', (g.get_state() if (g is not None) else None), ')'))
        if not lost:
            return
        self.press_key(KeyEvent.VK_TAB)
        # the REPORT page's tower table ("Top towers by damage" since the minimalist restyle's sentence-case headings)
        report = ((gs.end_page == 1) and any(t.lower().startswith('top towers') for t in DemoDriver.labels_in(gs.overlay)))
        self.snap('16_end_report')
        summary_tab = self.overlay_button('SUMMARY')
        if summary_tab is not None:
            self.click_logical(*self.center_of(summary_tab))
        self.check((report and (gs.end_page == 0)), 'Tab opens the end screen REPORT page; the SUMMARY tab click goes back')
    def victory_report_flow(self):
        """The victory epilogue: Esc skips it to the victory panel (CONTINUE - FREEPLAY offered), Tab shows the REPORT."""
        gs = self.app.get_game_screen()
        epilogue = ((gs is not None) and gs.is_epilogue_open())
        self.press_key(KeyEvent.VK_ESCAPE)
        offered = ((gs is not None) and (not gs.is_epilogue_open()) and (self.overlay_button('CONTINUE - FREEPLAY') is not None))
        self.press_key(KeyEvent.VK_TAB)
        self.snap('08b_victory_report')
        report = ((gs is not None) and (gs.end_page == 1))
        self.press_key(KeyEvent.VK_TAB)
        self.check(((epilogue and offered) and report), _j.cat('victory: the epilogue, Esc to the stats with CONTINUE - FREEPLAY, Tab to the REPORT (epilogue ', epilogue, ', freeplay ', offered, ', report ', report, ')'))
    def campaign_flow(self):
        """CAMPAIGN through the real UI: from the defeat panel's MAIN MENU to the level path; a click on level 1 opens its
briefing; START plays the level (its own waves, cash and starter towers, no Patch Notes); a locked tower and the
Hero Store are refused; QUIT LEVEL after building saves the level and returns to the campaign; CONTINUE names and
restores the level."""
        b = self.overlay_button('MAIN MENU')
        if b is not None:
            self.click_logical(*self.center_of(b))
        on_menu = (self.app.get_menu() is not None)
        self.click_logical(*self.menu_button_point('CAMPAIGN', 513))
        cs = self.app.get_map_select()
        opened = isinstance(cs, CampaignScreen)
        self.check((on_menu and opened), _j.cat('MAIN MENU on the end panel, then CAMPAIGN opens the level path (menu ', on_menu, ', campaign ', opened, ')'))
        if not opened:
            return
        cs.frame(0.05)
        self.snap('17_campaign')
        x, y, w, h = campaign_slot_rect(1)
        self.click_logical((x + (w / 2)), (y + (h / 2)))
        brief = (cs.is_briefing_open() and (cs.get_briefing_level() is campaign.level(1)))
        cs.frame(0.05)
        self.snap('17b_campaign_briefing')
        go = next((b for b in cs.briefing_buttons if (b.get_text() == 'START')), None)
        if go is not None:
            self.click_logical(*self.center_of(go))
        g = self.app.get_game()
        c = (None if (g is None) else g.get_campaign())
        lv = campaign.level(1)
        started = ((c is not None) and (c.level_id == lv.id) and (g.get_wave_count() == lv.wave_count()) and (g.get_cash() == lv.start_cash) and (not g.get_variance().is_enabled()))
        self.check((brief and started), _j.cat('a click on level 1 opens its briefing and START plays it (briefing ', brief, ', level ', (c.level_id if (c is not None) else None), ')'))
        if not started:
            return
        self.app.autosave = savegame.Autosave(g)   # the walkthrough's own slot (see __init__)
        gs = self.app.get_game_screen()
        gs.begin_placing(TowerType.ZETHOS)
        self.press_key(KeyEvent.VK_K)
        refused = ((gs.get_placing() is None) and (not gs.is_hero_store_open()))
        self.place_via_click(TowerType.GPT, Vec(380, 300))
        built = (len(g.get_tower_manager().get_player_towers()) == 1)
        gs.frame(0.05)
        self.snap('17c_campaign_level')
        self.check((refused and built), _j.cat('level 1 refuses a locked tower and the Hero Store, builds a starter (refused ', refused, ', built ', built, ')'))
        for k in range(3):
            if gs.is_menu_open():
                break
            self.press_key(KeyEvent.VK_ESCAPE)
        q = self.overlay_button('QUIT LEVEL')
        if q is not None:
            self.click_logical(*self.center_of(q))
        self.press_key(KeyEvent.VK_ENTER)
        info = savegame.slot().peek()
        back = isinstance(self.app.get_map_select(), CampaignScreen)
        self.check((back and (info is not None) and info.label().startswith('Level 1: Hello, World')), _j.cat('QUIT LEVEL saves the level and returns to the campaign (', (info.label() if (info is not None) else None), ')'))
        self.press_key(KeyEvent.VK_ESCAPE)
        m = self.app.get_menu()
        cont = (m.continue_button if (m is not None) else None)
        if cont is not None:
            self.click_logical(*self.center_of(cont))
        h = self.app.get_game()
        restored = ((h is not None) and (h is not g) and (h.get_campaign() is not None) and (h.get_campaign().level_id == lv.id) and (len(h.get_tower_manager().get_player_towers()) == 1))
        self.check(restored, 'CONTINUE restores the campaign level with its tower')
        if restored:
            self.app.get_game_screen().frame(0.05)
            self.snap('17d_campaign_continued')
            self.app.quit_level()
        savegame.slot().delete()
    def tutorial_flow(self):
        """The tutorial's first steps from the campaign's BOOT CAMP node: the welcome card, NEXT, the build step's
spotlight (shop card, then the suggested spot) places the first tower and moves on to START WAVE; QUIT LEVEL goes back
to the campaign and nothing is saved."""
        cs = self.app.get_map_select()
        if not isinstance(cs, CampaignScreen):
            self.check(False, 'the campaign screen is showing for BOOT CAMP')
            return
        x, y, w, h = campaign_slot_rect(0)
        self.click_logical((x + (w / 2)), (y + (h / 2)))
        gs = self.app.get_game_screen()
        guide = (None if (gs is None) else gs.tutorial)
        if guide is None:
            self.check(False, 'BOOT CAMP starts the tutorial')
            return
        sc = guide.get_script()
        gs.frame(0.05)
        welcome = (guide.is_shown() and (sc.current().key == 'welcome') and (guide.get_card_rect() is not None))
        self.snap('18_tutorial_welcome')
        nxt = next((b for b in guide.get_buttons() if (b.get_text() == 'NEXT')), None)
        if nxt is not None:
            self.click_logical(*self.center_of(nxt))
        gs.frame(0.05)
        build = ((sc.current().key == 'build') and (guide.get_target_rect() is not None))
        self.snap('18b_tutorial_build')
        for k in range(4):
            if sc.current().key != 'build':
                break
            r = guide.resolve(sc.target())
            if r is not None:
                self.click_logical((r[0] + (r[2] / 2.0)), (r[1] + (r[3] / 2.0)))
            gs.frame(0.05)
        g = gs.get_game()
        placed = ((sc.current().key == 'start1') and (len(g.get_tower_manager().get_player_towers()) == 1))
        self.snap('18c_tutorial_built')
        self.check(((welcome and build) and placed), _j.cat('tutorial: welcome card, NEXT, the spotlit build step places a tower (welcome ', welcome, ', build ', build, ', now ', sc.current().key, ')'))
        for k in range(3):
            if gs.is_menu_open():
                break
            self.press_key(KeyEvent.VK_ESCAPE)
        q = self.overlay_button('QUIT LEVEL')
        if q is not None:
            self.click_logical(*self.center_of(q))
        lost = any(('Progress will be lost' in t) for t in DemoDriver.labels_in(gs.overlay))
        self.press_key(KeyEvent.VK_ENTER)
        back = isinstance(self.app.get_map_select(), CampaignScreen)
        self.check(((lost and back) and (not savegame.slot().exists())), _j.cat('tutorial QUIT LEVEL warns, returns to the campaign and saves nothing (warned ', lost, ', campaign ', back, ')'))
    @staticmethod
    def labels_in(c, out=None):
        """Every text label under compound c."""
        out = ([] if (out is None) else out)
        for i in range(c.get_element_count()):
            e = c.get_element(i)
            if isinstance(e, GLabel):
                out.append(e.get_label())
            elif isinstance(e, GCompound):
                DemoDriver.labels_in(e, out)
        return out
    def press_key(self, code):
        """Sends a key press through the program's real key routing."""
        self.app.key_pressed(KeyEvent(self.app.get_g_canvas(), KeyEvent.KEY_PRESSED, 0, 0, code, KeyEvent.CHAR_UNDEFINED))
    def menu_button_point(self, label, default_y):
        """Centre of a main menu button (the stack moves down when a saved run adds CONTINUE)."""
        m = self.app.get_menu()
        for b in (m.buttons if m is not None else ()):
            if (b.get_parent() is m) and (b.text.get_label() == label):
                return [(b.get_x() + (b.w / 2)), (b.get_y() + (b.h / 2))]
        return [(Ui.W / 2.0), default_y]
    def click_logical(self, lx, ly):
        """Sends a press through the real program mouse handler at the pixel position of a logical point."""
        ev = self.pixel_event(lx, ly)
        self.app.mouse_moved(ev)
        self.app.mouse_pressed(ev)
    def place_via_click(self, type_, world):
        self.app.get_game_screen().begin_placing(type_)
        l = self.app.get_game_screen().world_to_logical(world)
        self.click_logical(l[0], l[1])
        self.app.get_game_screen().begin_placing(None)
    def verify_click(self, label):
        g = self.app.get_game()
        g.add_cash(1000, None)
        target = Vec((150 if (label == 'small') else 320), 60)
        before = len(g.get_tower_manager().get_towers())
        self.place_via_click(TowerType.QWEN, target)
        placed = None
        for tw in g.get_tower_manager().get_towers():
            if (tw.get_type() is TowerType.QWEN) and (tw.get_position().dist(target) < 1.5):
                placed = tw
        ok = ((placed is not None) and (len(g.get_tower_manager().get_towers()) == (before + 1)))
        _j_add(self.results, _j.cat(('PASS' if ok else 'FAIL'), ' click-to-place after resize (', label, ', canvas ', self.app.get_g_canvas().get_width(), 'x', self.app.get_g_canvas().get_height(), ', scale ', _j.format('%.3f', self.app.get_root().get_scale()), ')', (_j.cat(' tower at ', placed.get_position()) if (placed is not None) else _j.cat(' no tower at ', target))))
    def snap(self, name):
        canvas = self.app.get_g_canvas()
        w = _j.dmax(1, canvas.get_width())
        h = _j.dmax(1, canvas.get_height())
        img = BufferedImage(w, h, BufferedImage.TYPE_INT_RGB)
        g2 = img.create_graphics()
        canvas.paint(g2)
        g2.dispose()
        try:
            ImageIO.write(img, 'png', _j.File(self.out, _j.cat(name, '.png')))
            _j_add(self.results, _j.cat('SNAP ', name, ' ', w, 'x', h))
        except Exception as e:
            _j_add(self.results, _j.cat('FAIL snapshot ', name, ': ', e))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense import savegame  # noqa: E402
from lindefense.audio.audio_manager import AudioManager  # noqa: E402
from lindefense.sim.challenges import Challenge  # noqa: E402
from lindefense.sim.records import Records  # noqa: E402
from lindefense.sim.run_setup import DailyRun, RunOptions  # noqa: E402
from lindefense.ui.display_settings import DisplaySettings  # noqa: E402
from lindefense.ui.stats_screen import StatsScreen  # noqa: E402
from lindefense.variance.variance import seed_parse  # noqa: E402
from lindefense.ui.attack_panel import AttackPanel  # noqa: E402
from lindefense.ui.map_select_screen import MapSelectScreen  # noqa: E402
from lindefense.ui.shop_layout import ShopLayout  # noqa: E402
from lindefense.ui.slider import Slider  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402
from lindefense.sim import campaign  # noqa: E402
from lindefense.sim.campaign import CampaignProgress  # noqa: E402
from lindefense.ui.campaign_screen import CampaignScreen, slot_rect as campaign_slot_rect  # noqa: E402
