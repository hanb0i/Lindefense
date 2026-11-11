"""Campaign mode (sim/campaign.py and its UI): the level table (wave counts, determinism, threat coverage), tower
unlocks and the saved progress, shop / TowerManager gating, level victory and the Palantir finale, the HUD wave chip,
Save & Continue of a level, records and the campaign achievements, the campaign screen / briefing / level-complete
panel painted offscreen, and the classic game staying untouched. Every test uses temp folders."""
import pytest

from kit import DT, force_place, kill_outright, spawn_at
from lindefense import prefs, savegame
from lindefense.ai.defender_ai import EFFICIENT_PLAN, DefenderAI, Options
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.map import maps
from lindefense.sim import campaign
from lindefense.sim import records as R
from lindefense.sim.campaign import CampaignProgress, LEVELS, STARTER
from lindefense.sim.campaign_story import StoryLog, scene_keys
from lindefense.sim.game import Game, State
from lindefense.sim.misc import HeroCollection
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType as T
from lindefense.wave import waves

SHOP = T.shop_towers()


@pytest.fixture(autouse=True)
def _temp_prefs(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path / "prefs"))
    prefs._nodes.clear()
    shared = (CampaignProgress._shared, HeroCollection._shared, R.Records._shared, StoryLog._shared)
    CampaignProgress._shared = HeroCollection._shared = R.Records._shared = StoryLog._shared = None
    yield
    prefs._nodes.clear()
    CampaignProgress._shared, HeroCollection._shared, R.Records._shared, StoryLog._shared = shared


# ====================================================================== the level table
def test_levels_vary_and_span_the_war(check):
    n = len(LEVELS)
    counts = [lv.wave_count() for lv in LEVELS]
    check(14 <= n <= 16, "14-16 levels (%d)" % n)
    check(all(8 <= c <= 35 for c in counts), "every level has 8-35 waves (%s)" % counts)
    check(all(a != b for a, b in zip(counts, counts[1:])), "no two neighbouring levels have the same wave count (%s)" % counts)
    check(any(c <= 12 for c in counts) and any(c >= 24 for c in counts), "short skirmishes and long sieges")
    check(len(set(counts)) >= 10, "the wave counts really vary (%d distinct)" % len(set(counts)))
    check({lv.map_index for lv in LEVELS} == set(range(maps.MAP_COUNT)), "all seven maps are used")
    check(len({lv.id for lv in LEVELS}) == n and len({lv.title for lv in LEVELS}) == n, "unique ids and titles")
    check(all(lv.flavour and len(lv.flavour) < 140 and lv.title for lv in LEVELS), "a title and one line of flavour each")
    check([lv.index for lv in LEVELS] == list(range(1, n + 1)), "indices 1..n")
    for lv in LEVELS:
        b = lv.bases
        check(all(1 <= x <= waves.WAVE_COUNT for x in b) and all(x < y for x, y in zip(b, b[1:])),
              "%s plays base waves in order, each once (%s)" % (lv.id, b))
        check(lv.start_cash > 0 and lv.start_lives > 0, "%s has its own cash and lives" % lv.id)
        cap = campaign.FINALE_CASH_CAP if lv.is_finale() else campaign.CASH_CAP
        check(lv.start_cash <= cap, "%s starts with a manageable build ($%d <= $%d)" % (lv.id, lv.start_cash, cap))
        a, b = lv.hp_range()
        check(0 < a < b <= 8, "%s: enemy health multiplier %s-%s rises through the level" % (lv.id, a, b))
        check(lv.start_lives == 100, "%s: 100 integrity, no padding (%d)" % (lv.id, lv.start_lives))
    check(set(campaign.BALANCE) == {lv.id for lv in LEVELS}, "one BALANCE entry per level")
    check([lv.start_cash for lv in LEVELS[:4]] == sorted(lv.start_cash for lv in LEVELS[:4]), "early levels start small")
    early = [lv for lv in LEVELS if lv.bases[-1] <= 40]
    check(early and all(lv.hp_range()[0] > 1 for lv in early),
          "the early levels' easy waves are tougher than in CLASSIC (%s)" % [lv.hp_range() for lv in early])
    ends = [lv.bases[-1] for lv in LEVELS]
    check(ends[0] <= 15 and ends[-1] == waves.WAVE_COUNT, "from the first waves to wave 100 (%s)" % ends)
    check(sum(1 for a, b in zip(ends, ends[1:]) if b < a) <= 2, "the war mostly advances level by level (%s)" % ends)
    fin = campaign.finale()
    check(fin is LEVELS[-1] and fin.waves()[-1].contains(EnemyType.PALANTIR), "the finale's last wave is Palantir")
    check(not any(w.contains(EnemyType.PALANTIR) for lv in LEVELS[:-1] for w in lv.waves()), "Palantir only in the finale")
    bosses = {t for lv in LEVELS for _, t in lv.threats()["bosses"]}
    check(bosses == {e for e in EnemyType if e.is_boss()}, "every boss appears somewhere (%s)" % sorted(b.name for b in bosses))


def test_level_waves_are_deterministic_and_scaled_by_their_base_wave(check):
    for lv in LEVELS:
        ws = lv.waves()
        check(ws is lv.waves(), "%s: built once and shared" % lv.id)
        check([w.number for w in ws] == list(range(1, lv.wave_count() + 1)), "%s: local numbers 1..N" % lv.id)
        check(all(w.groups == waves.get(w.base).groups for w in ws), "%s: each wave plays its base wave's groups" % lv.id)
    a = campaign.new_game("campus_tour", 1)
    b = campaign.new_game("campus_tour", 999)
    check(a.get_campaign().waves is b.get_campaign().waves, "the same waves whatever the seed")
    g = campaign.new_game("network_effect", 5)
    c = g.get_campaign()
    check(g.get_wave_count() == c.wave_count() == 16 and g.get_era_wave() == 0, "16 waves, none played yet")
    g.start_next_wave()
    base = c.wave(1).base
    check(g.get_wave() == 1 and g.get_era_wave() == base, "wave 1 plays base wave %d" % base)
    hp0, hp1 = campaign.level("network_effect").hp_range()
    check(abs(g.get_wave_hp_scale() - waves.hp_scale(base) * hp0) < 1e-12, "HP scale of the base wave x the level's own")
    e = g.get_enemy_manager().spawn(c.wave(1).groups[0].type, None, 0, 0)
    check(abs(e.get_hp_scale() - waves.hp_scale(base) * hp0) < 1e-12, "spawned enemies carry it")
    check(abs(c.hp_at(16) - hp1) < 1e-12 and abs(c.hp_at(1) - hp0) < 1e-12, "the multiplier runs from the first to the last wave")
    check(all(c.hp_at(n) <= c.hp_at(n + 1) for n in range(1, 16)), "and never falls")
    t = 8 / 15.0
    check(hp1 > hp0 and abs(c.hp_at(9) - (hp0 + (hp1 - hp0) * t ** campaign.HP_RAMP)) < 1e-12 and c.hp_at(9) < (hp0 + hp1) / 2,
          "most of the rise comes in the second half (wave 9: %.3f)" % c.hp_at(9))
    check(abs(g.get_wave_speed_scale() - waves.speed_scale(base)) < 1e-12, "speed scale of the base wave")
    check(abs(g.get_reward_scale() - waves.reward_scale(base)) < 1e-12, "reward scale of the base wave")
    check(waves.for_game(g, 3) is c.wave(3) and waves.exists(g, 16) and not waves.exists(g, 17), "the level's waves only")
    check(not g.get_variance().is_enabled(), "no Patch Notes or Breaking News")
    check(g.get_difficulty().id == "O1", "Difficulty Growth O(1)")


def test_injection_is_explained_on_each_levels_first_injection_wave(check):
    for lv in LEVELS:
        first = next((w for w in lv.waves() if any(Modifier.INJECTION in g.modifiers for g in w.groups)), None)
        if first is not None:
            check("IGNORE PREVIOUS INSTRUCTIONS" in (first.note or ""), "%s explains Prompt Injection" % lv.id)


# ====================================================================== tower unlocks
def test_unlock_order_ends_with_every_tower(check):
    rewards = [t for lv in LEVELS for t in lv.reward]
    check(len(rewards) == len(set(rewards)) and set(rewards) | set(STARTER) == set(SHOP) and not set(rewards) & set(STARTER),
          "every shop tower is unlocked exactly once, after the starters")
    check(len(STARTER) == 3 and all(t.faction.label == "Primary" for t in STARTER), "three Primary starters")
    check(all(1 <= len(lv.reward) <= 2 for lv in LEVELS[:-1]) and not LEVELS[-1].reward, "1-2 towers per level")
    check(set(LEVELS[-1].towers()) == set(SHOP), "the finale has all 18 towers")
    check(campaign.unlock_level(T.ZETHOS).index >= len(LEVELS) - 2, "Zethos is late")
    check(LEVELS[0].towers() == tuple(t for t in SHOP if t in STARTER), "level 1: the starters only")
    for lv in LEVELS:
        prev = campaign.level(lv.index - 1)
        if prev is not None:
            check(set(lv.towers()) == set(prev.towers()) | set(prev.reward), "%s adds the previous reward" % lv.id)
    hl, al = campaign.heroes_level(), campaign.abilities_level()
    check(1 < hl.index < al.index < len(LEVELS), "the Hero Store opens mid-campaign, abilities later")
    check(not LEVELS[hl.index - 1].heroes_allowed() and LEVELS[hl.index].heroes_allowed(), "heroes from the next level")
    check(not LEVELS[al.index - 1].abilities_allowed() and LEVELS[al.index].abilities_allowed(), "abilities from the next level")


def test_every_levels_threats_have_an_unlocked_answer(check):
    cnt = campaign.counters()
    for lv in LEVELS:
        th = lv.threats()
        have = set(lv.towers())
        if th["camo"]:
            check(have & set(cnt["camo"]), "%s: camo detection is unlocked" % lv.id)
        if th["lead"]:
            check(have & set(cnt["lead"]), "%s: non-Sharp damage for Lead-type enemies" % lv.id)
        if th["injection"]:
            check(have & set(cnt["injection"]), "%s: an injection-immune tower" % lv.id)
        if th["bosses"]:
            check(have & set(cnt["boss"]), "%s: a boss killer (DeepSeek / Cohere)" % lv.id)
        if any(t is EnemyType.PALANTIR for _, t in th["bosses"]):
            check(have & set(cnt["palantir"]), "%s: Perplexity against Predictive Surveillance" % lv.id)
    first_camo = next(lv for lv in LEVELS if lv.threats()["camo"])
    check(T.PERPLEXITY in first_camo.towers(), "the dedicated detector arrives before the first camo level")


def _place_all(g, types):
    """Places one of each tower (fully upgraded) on free buildable spots."""
    placed = []
    g.add_cash(10_000_000, None)
    for t in types:
        done = None
        for y in range(40, 880, 30):
            for x in range(40, 1180, 30):
                if g.get_tower_manager().can_place(t, Vec(x, y)):
                    done = g.get_tower_manager().place(t, Vec(x, y))
                    break
            if done is not None:
                break
        if done is not None:
            while g.get_tower_manager().upgrade(done):
                pass
            placed.append(done)
    return placed


def test_intel_raises_no_camo_or_lead_alarm_with_the_levels_towers(check):
    """The HUD's own threat check (ui/intel.threats): with every tower the level allows built and fully upgraded,
    no wave of the level warns NO CAMO DETECTION or SHARP VS LEAD."""
    from lindefense.ui import intel
    for lv in LEVELS:
        g = campaign.new_game(lv, 3)
        placed = _place_all(g, lv.towers())
        check(len(placed) == len(lv.towers()), "%s: all %d towers built" % (lv.id, len(lv.towers())))
        bad = []
        for n in range(1, lv.wave_count() + 1):
            pv = intel.preview(g, n)
            kinds = {th.kind for th in intel.threats(g, pv)}
            if kinds & {intel.Threat.CAMO, intel.Threat.LEAD}:
                bad.append((n, sorted(kinds)))
        check(not bad, "%s: alarms on %s" % (lv.id, bad))


def test_star_thresholds_are_one_near_flawless_rule(check):
    """STAR_PERCENT is the one place the thresholds live: 3 stars only for a near-flawless win (at most 5% of the
    integrity lost), 2 for most of it kept; star_lives gives them in integrity, as the briefing shows them."""
    three, two = campaign.STAR_PERCENT
    check(three >= 95 and 50 <= two < three, "3 stars: lose at most 5%%; 2 stars below that (%s)" % (campaign.STAR_PERCENT,))
    check(campaign.star_lives(100) == (three, two), "in a 100-integrity level: %s" % (campaign.star_lives(100),))
    for n in (100, 80, 60, 33, 7):
        a, b = campaign.star_lives(n)
        check(campaign.stars_for(a, n) == 3 and campaign.stars_for(a - 1, n) == 2, "%d integrity: 3 stars from %d" % (n, a))
        check(campaign.stars_for(b, n) == 2 and campaign.stars_for(b - 1, n) <= 1, "%d integrity: 2 stars from %d" % (n, b))
        check(a * 100 >= three * n > (a - 1) * 100 and b * 100 >= two * n > (b - 1) * 100, "%d integrity: exact percentages" % n)
    for lv in LEVELS:
        check(lv.star_lives() == campaign.star_lives(lv.start_lives), "%s: its thresholds follow its integrity" % lv.id)
        check(lv.start_lives - lv.star_lives()[0] <= 0.05 * lv.start_lives, "%s: 3 stars are near-flawless" % lv.id)


def test_a_leaking_boss_costs_at_most_the_levels_cap(check):
    """Campaign rule (BALANCE boss_leak): one corporate boss that gets through costs at most the level's cap, so a
    single leak hurts without deciding the level. Palantir is never capped (it ends the finale), regular enemies pay
    their own cost, and CLASSIC games are untouched."""
    for lv in LEVELS:
        cap = lv.boss_leak()
        if lv.threats()["bosses"]:
            check(cap is not None and 10 <= cap <= 0.4 * lv.start_lives,
                  "%s: a boss leak costs at most %s of %d integrity" % (lv.id, cap, lv.start_lives))
    fin = campaign.finale()
    check(fin.start_lives <= EnemyType.PALANTIR.lives, "Palantir reaching the core still ends the finale")
    check(fin.balance().boss_leak is not None and
          campaign.CampaignRun(fin).leak_cost(EnemyType.PALANTIR, EnemyType.PALANTIR.lives) == EnemyType.PALANTIR.lives,
          "Palantir is never capped")

    lv = campaign.level("network_effect")
    cap = lv.boss_leak()
    g = campaign.new_game(lv, 3)
    end = g.get_map().get_routes()[0].get_total_length()
    spawn_at(g, EnemyType.THREE_COM, None, 0, end - 2)
    g.run(20)
    check(g.get_lives() == lv.start_lives - cap, "3Com (%d lives) costs %d here: %d left" % (EnemyType.THREE_COM.lives, cap, g.get_lives()))
    spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, end - 2)
    g.run(20)
    check(g.get_lives() == lv.start_lives - cap - min(cap, EnemyType.BELLARMINE_COLLEGE_PREP.lives), "a second boss too")
    before = g.get_lives()
    spawn_at(g, EnemyType.TIMSORT, None, 0, end - 2)
    g.run(10)
    check(g.get_lives() == before - EnemyType.TIMSORT.lives, "regular enemies pay their own cost")
    c = Game(maps.create(lv.map_index), 3)
    spawn_at(c, EnemyType.SW_RESOURCE_CONSULTANT, None, 0, c.get_map().get_routes()[0].get_total_length() - 2)
    c.run(20)
    check(c.get_lives() == c.get_max_lives() - EnemyType.SW_RESOURCE_CONSULTANT.lives, "CLASSIC: the full cost (%d)" % c.get_lives())

    # the enemy panel shows what a leak would cost here
    from lindefense.ui.acm import GLabel
    from lindefense.ui.game_screen import GameScreen
    for game, want in ((campaign.new_game(lv, 4), str(cap)), (Game(maps.create(lv.map_index), 4), str(EnemyType.THREE_COM.lives))):
        sc = GameScreen(None, game)
        game.start_next_wave()
        sc.select_enemy(spawn_at(game, EnemyType.THREE_COM, None, 0, 200))
        sc.frame(0.02)
        texts = [o.get_label() for o in sc.side.info if isinstance(o, GLabel)]
        i = texts.index("Lives cost") if "Lives cost" in texts else -1
        check(i >= 0 and texts[i + 1] == want, "the 3Com panel says lives cost %s (%s)" % (want, texts[i:i + 2]))


# ====================================================================== progress
def test_progress_unlocks_levels_and_towers(check):
    p = CampaignProgress.in_memory()
    check([p.state(lv) for lv in LEVELS[:3]] == ["available", "locked", "locked"], "only level 1 at first")
    check(p.unlocked_towers() == LEVELS[0].towers() and p.next_level() is LEVELS[0], "starters, level 1 next")
    out = p.record(1, False)
    check(not out.won and p.completed_count() == 0, "a defeat changes nothing")
    out = p.record(1, True, 85, 100)
    check(out.won and out.first_clear and out.stars == 2 and out.towers == (T.PERPLEXITY,), "first clear: 2 stars, Perplexity")
    check(p.state(1) == "completed" and p.state(2) == "available" and T.PERPLEXITY in p.unlocked_towers(), "level 2 opens")
    out = p.record(1, True, 100, 100)
    check(out.new_best and out.stars == 3 and not out.towers and not out.first_clear, "a replay can raise the stars")
    out = p.record(1, True, 10, 100)
    check(out.stars == 1 and out.best == 3 and p.best_stars(1) == 3, "the best is kept")
    check([campaign.stars_for(l, 100) for l in (100, 95, 94, 60, 59, 1)] == [3, 3, 2, 2, 1, 1], "stars by lives left")
    hl = campaign.heroes_level()
    for lv in LEVELS[:hl.index - 1]:
        p.record(lv, True, 100, 100)
    check(not p.heroes_unlocked(), "Hero Store still closed")
    out = p.record(hl, True, 100, 100)
    check(out.heroes and p.heroes_unlocked(), "the Hero Store opens with its level")
    for lv in LEVELS:
        p.record(lv, True, 100, 100)
    check(p.is_finished() and p.total_stars() == 3 * len(LEVELS) and set(p.unlocked_towers()) == set(SHOP), "all done")
    check(p.next_level() is None, "nothing left")


def test_progress_persists_in_its_own_node(check, tmp_path):
    p = CampaignProgress.persistent()
    p.record(1, True, 100, 100)
    p.record(2, True, 60, 100)
    check(not p.boot_camp_done(), "BOOT CAMP not done yet")
    p.mark_boot_camp()
    prefs._nodes.clear()
    CampaignProgress._shared = None
    q = CampaignProgress.persistent()
    check(q is not p and q.stars() == {"hello_world": 3, "garbage_collection": 2}, "read back (%s)" % q.stars())
    check(q.boot_camp_done(), "the finished tutorial is remembered (BOOT CAMP)")
    check((tmp_path / "prefs" / "lindefense_campaign.json").exists(), "saved as lindefense_campaign.json")
    node = prefs.node(campaign.NODE)
    check(T.MISTRAL.name in node.get("unlocked"), "the unlocked towers are stored too")
    node.put("stars", {"hello_world": "x", "nope": 3, "legacy_code": 7})
    prefs._nodes.clear()
    r = CampaignProgress(campaign._PrefsStorage())
    check(r.stars() == {"legacy_code": 3}, "bad entries are dropped, stars capped (%s)" % r.stars())
    mem = CampaignProgress.in_memory({"hello_world": 3})
    mem.record(2, True, 100, 100)
    check(mem._storage.saves == 1 and mem.stars() == {"hello_world": 3, "garbage_collection": 3}, "in-memory storage")


# ====================================================================== gating
def test_locked_towers_heroes_and_abilities_are_refused(check):
    g = campaign.new_game(1, 4)
    tm = g.get_tower_manager()
    p = Vec(300, 300)
    while not g.get_map().is_buildable(p, 30):
        p = Vec(p.x + 20, p.y)
    g.add_cash(100_000, None)
    check(tm.placement_problem(T.PERPLEXITY, p) == "Perplexity unlocks after level 1", "a locked tower is refused")
    check(tm.place(T.PERPLEXITY, p) is None and g.place_tower(T.ZETHOS, p) is None, "and never placed")
    check(tm.placement_problem(T.GEMINI, p) is None, "a starter is fine")
    g.get_hero_collection().unlock(T.LOBBER_LUIS)
    check(tm.hero_problem(T.LOBBER_LUIS) == "The Hero Store opens after level %d" % campaign.heroes_level().index,
          "heroes are locked (%s)" % tm.hero_problem(T.LOBBER_LUIS))
    check(not g.purchase_hero(T.SPEAR_HANBO) and "Hero Store" in g.hero_purchase_problem(T.SPEAR_HANBO), "no hero purchase")
    t = tm.place(T.GEMINI, p)
    while tm.upgrade(t):
        pass
    check(t.can_unlock_ability() and not g.unlock_ability(t) and t.is_ability_locked(), "abilities are locked")
    check(g.ability_lock_problem() == "Ability unlocks open after level %d" % campaign.abilities_level().index, "with a reason")
    late = campaign.new_game(campaign.abilities_level().index + 1, 4)
    t2 = _place_all(late, [T.GEMINI])[0]
    late.add_cash(20_000, None)
    check(late.unlock_ability(t2), "after the abilities level they unlock")
    late.get_hero_collection().unlock(T.LOBBER_LUIS)
    check(late.get_tower_manager().hero_problem(T.LOBBER_LUIS) is None, "and heroes deploy")
    classic = Game(maps.create(0), 4)
    check(classic.tower_lock_problem(T.ZETHOS) is None and classic.ability_lock_problem() is None, "classic: no locks")


def test_shop_shows_locked_towers_greyed(check):
    from lindefense.ui.game_screen import GameScreen
    g = campaign.new_game("legacy_code", 2)
    s = GameScreen(None, g)
    s.side.toggle_all()
    s.frame(0.02)
    cards = {c.cell.type: c for c in s.side.cards}
    allowed = set(g.get_campaign().allowed)
    check(set(cards) == set(SHOP), "the ALL view lists every shop tower")
    check(all(cards[t].locked == (t not in allowed) for t in SHOP), "the locked ones are marked")
    check(all(not cards[t].button.is_enabled() for t in SHOP if t not in allowed), "and cannot be clicked")
    check(cards[T.DEEPSEEK].price.get_label() == "AFTER L3", "their price slot names the level (%s)" % cards[T.DEEPSEEK].price.get_label())
    check(cards[T.GEMINI].button.is_enabled() and cards[T.GEMINI].price.get_label() == "$400", "unlocked ones as usual")
    s.begin_placing(T.ZETHOS)
    check(s.get_placing() is None, "placing a locked tower is refused")
    s.begin_placing(T.GEMINI)
    check(s.get_placing() is T.GEMINI, "an unlocked one arms placement")
    s.begin_placing(None)
    s.toggle_hero_store()
    check(not s.is_hero_store_open(), "the Hero Store stays shut before its level")


# ====================================================================== victory
def _clear_waves(g, last):
    """Starts waves up to `last` and kills everything as it spawns."""
    steps = 0
    while g.get_state() is State.PLAYING and steps < 200_000:
        if g.get_wave_manager().can_start_next_wave() and g.get_wave() < last:
            g.start_next_wave()
        for e in list(g.get_enemy_manager().get_enemies()):
            if e.is_alive() and e.get_type() is not EnemyType.PALANTIR:
                kill_outright(g, e)
        g.step(DT)
        g.get_events().clear()
        steps += 1
        if g.get_wave() >= last and not g.get_wave_manager().is_wave_active() and not g.is_campaign_won():
            break


def test_level_is_won_when_its_last_wave_is_cleared(check):
    g = campaign.new_game("hello_world", 8)
    n = g.get_wave_count()
    _clear_waves(g, n - 1)
    check(g.get_wave() == n - 1 and g.get_state() is State.PLAYING and not g.is_campaign_won(), "not over before the last wave")
    _clear_waves(g, n)
    for _ in range(120):
        g.step(DT)
    check(g.get_state() is State.VICTORY and g.get_last_completed_wave() == n, "won on wave %d of %d" % (g.get_wave(), n))
    check(not g.can_continue_freeplay() and not g.get_wave_manager().can_start_next_wave(), "no freeplay, no wave %d" % (n + 1))
    check(R.RunSummary.of(g).campaign_stars == 3 and R.RunSummary.result_of(g) == R.VICTORY, "a 3-star victory")


def test_finale_is_won_when_palantir_dies(check):
    g = campaign.new_game(campaign.finale(), 9)
    n = g.get_wave_count()
    g.get_wave_manager()._current_wave = n - 1   # jump to the Palantir wave
    g.start_next_wave()
    pal = None
    for _ in range(60 * 20):
        g.step(DT)
        pal = next((e for e in g.get_enemy_manager().get_enemies() if e.get_type() is EnemyType.PALANTIR), None)
        if pal is not None:
            break
    check(pal is not None, "Palantir arrives on the finale's last wave")
    kill_outright(g, pal)
    check(g.is_campaign_won() and g.get_state() is State.PLAYING, "the victory sequence starts")
    for _ in range(60 * 6):
        g.step(DT)
    check(g.get_state() is State.VICTORY and not g.can_continue_freeplay(), "won, and no freeplay")


# ====================================================================== HUD
def test_hud_shows_the_level_wave_count(check):
    from lindefense.ui.game_screen import GameScreen
    g = campaign.new_game("legacy_code", 2)
    s = GameScreen(None, g)
    s.frame(0.02)
    check(s.hud.wave_chip.value.get_label() == "W 0 / 12", "before the first wave (%s)" % s.hud.wave_chip.value.get_label())
    g.start_next_wave()
    s.frame(0.02)
    check(s.hud.wave_chip.value.get_label() == "W 1 / 12", "W 1 / 12 (%s)" % s.hud.wave_chip.value.get_label())
    c = Game(maps.create(0), 2)
    sc = GameScreen(None, c)
    c.start_next_wave()
    sc.frame(0.02)
    check(sc.hud.wave_chip.value.get_label() == "1 / 100", "classic keeps 1 / 100")


# ====================================================================== save & continue
def test_continued_level_is_bit_identical(check, tmp_path):
    from test_savegame import digest
    from lindefense.tools.auto_player import campaign_options, setup_phase
    last = 5

    def player(g):
        return DefenderAI(g, campaign_options(g))

    def tick(g, ai):
        if g.get_tick() % 15 == 0:
            ai.manage()
        if g.get_wave_manager().can_start_next_wave() and g.get_wave() < last:
            g.start_next_wave()
        g.step(DT)
        g.get_events().clear()

    def done(g):
        return g.get_state() is not State.PLAYING or (g.get_wave() >= last and not g.get_wave_manager().is_wave_active())

    g = campaign.new_game("backpropagation", 21)   # a level with its own enemy health multiplier
    ai = player(g)
    setup_phase(ai)
    trace, snaps, taken = {}, [], set()
    while not done(g):
        wm = g.get_wave_manager()
        key = g.get_last_completed_wave() if not wm.is_wave_active() else ("mid", g.get_wave())
        if key in (2, 3, ("mid", 4)) and key not in taken and (not wm.is_wave_active() or wm.get_wave_time() > 8):
            taken.add(key)
            snaps.append((g.get_tick(), savegame.dumps(g), (ai._tracked_wave, ai._lives_at_wave_start, ai._lives_prev_wave)))
        tick(g, ai)
        trace[g.get_tick()] = digest(g)
    check(len(snaps) == 3, "two boundary snapshots and one mid-wave (%d)" % len(snaps))
    end = (g.get_tick(), g.get_cash(), g.get_lives(), g.get_enemy_manager().get_total_killed())
    slot = savegame.SaveSlot(str(tmp_path / "slot.bin"))
    for i, (t0, payload, memory) in enumerate(snaps):
        if i == 0:
            slot.save(savegame.loads(payload))
            h = slot.load()
            info = slot.peek()
            check(info.label() == "Level 6: Backpropagation, wave 2 / 21", "the save names the level (%s)" % info.label())
        else:
            h = savegame.loads(payload)
        check(h.get_campaign() is not None and h.get_campaign().waves is campaign.level("backpropagation").waves(),
              "the level's waves come back as the shared ones")
        check((h.get_campaign().hp, h.get_campaign().hp_end) == campaign.level("backpropagation").hp_range(),
              "and its health multiplier")
        a2 = player(h)
        a2._tracked_wave, a2._lives_at_wave_start, a2._lives_prev_wave = memory
        bad = []
        while not done(h):
            tick(h, a2)
            if trace.get(h.get_tick()) != digest(h):
                bad.append(h.get_tick())
        check(not bad, "saved at tick %d: %d steps differ" % (t0, len(bad)))
        got = (h.get_tick(), h.get_cash(), h.get_lives(), h.get_enemy_manager().get_total_killed())
        check(got == end, "ends where the uninterrupted run did: %s vs %s" % (got, end))


def test_continue_button_names_the_level(check):
    from lindefense.ui.menu_screen import MenuScreen

    g = campaign.new_game("outsourced", 3)
    g.start_next_wave()
    savegame.slot().save(g)
    m = MenuScreen(_App())
    c = m.continue_button
    details = [o.get_label() for o in c if o is not c.text and hasattr(o, "get_label")]
    check(details == ["Level 7: Outsourced, wave 1 / 14"], "CONTINUE names the level (%s)" % details)


# ====================================================================== records and achievements
def _summary(**kw):
    base = dict(map_name="The Silicon Circuit", map_index=0, result=R.VICTORY, wave=10, waves_cleared=10, kills=500,
                lives=100, max_lives=100, time=600.0, play_time=600.0, cash_earned=9000.0)
    base.update(kw)
    return R.RunSummary(**base)


def test_campaign_runs_count_toward_career_only(check):
    rec = R.Records.in_memory()
    rep = rec.record(_summary(campaign_level="hello_world", campaign_stars=3, bosses=["BELLARMINE_COLLEGE_PREP"]))
    car = rec.career()
    check(rep.counted and car["runs"] == 1 and car["victories"] == 1 and car["waves_cleared"] == 10 and car["enemies_killed"] == 500,
          "career totals count it (%s)" % car)
    check(rec.map_record("The Silicon Circuit", "O1")["runs"] == 0 and not rec.history(), "no map record, no history")
    check(car["best_wave"] == 0, "a level's wave count is not a classic best wave")
    check(not rec.is_unlocked("first_win") and not rec.is_unlocked("win_the_silicon_circuit")
          and not rec.is_unlocked("flawless"), "classic-run achievements are not earned by a level")
    check(rec.is_unlocked("boss_bellarmine_college_prep"), "boss achievements are")
    rec.record(_summary(campaign_level=""))
    check(rec.map_record("The Silicon Circuit", "O1")["runs"] == 1 and rec.is_unlocked("first_win"), "classic runs unchanged")


def test_campaign_achievements(check):
    ids = {a.id for a in R.achievements()}
    check({"campaign_done", "campaign_stars", "campaign_starter"} <= ids, "three campaign achievements")
    rec = R.Records.in_memory()
    rec.record(_summary(campaign_level=campaign.finale().id, result=R.DEFEAT))
    check(not rec.is_unlocked("campaign_done"), "losing the finale is not finishing")
    rec.record(_summary(campaign_level=campaign.finale().id))
    check(rec.is_unlocked("campaign_done"), "winning the finale finishes the campaign")
    almost = {lv.id: 3 for lv in LEVELS}
    almost["legacy_code"] = 2
    rec.record(_summary(campaign_level="legacy_code", campaign_best=almost))
    check(not rec.is_unlocked("campaign_stars"), "3 stars everywhere needs every level")
    rec.record(_summary(campaign_level="legacy_code", campaign_best={lv.id: 3 for lv in LEVELS}))
    check(rec.is_unlocked("campaign_stars"), "State of the Art")
    line = lambda t, hero=False: R.TowerLine(t.name, t.display_name, 3, "x", 3, 1000, 10, 900, hero=hero)
    starters = [line(T.GEMINI), line(T.CLAUDE), line(T.GPT)]
    early = campaign.level(R.STARTER_ONLY_FROM - 1).id
    late = campaign.level(R.STARTER_ONLY_FROM).id
    rec.record(_summary(campaign_level=early, towers=starters))
    check(not rec.is_unlocked("campaign_starter"), "too early a level does not count")
    rec.record(_summary(campaign_level=late, towers=starters + [line(T.PERPLEXITY)]))
    check(not rec.is_unlocked("campaign_starter"), "a non-starter tower (even sold) disqualifies")
    rec.record(_summary(campaign_level=late, towers=starters))
    check(rec.is_unlocked("campaign_starter"), "Base Model")


def test_run_session_records_the_level_into_the_progress(check):
    p = CampaignProgress.in_memory()
    rec = R.Records.in_memory()
    g = campaign.new_game("hello_world", 1)
    _clear_waves(g, g.get_wave_count())
    for _ in range(120):
        g.step(DT)
    s = R.RunSession(rec, g, False, p)
    s.finish()
    out = s.campaign_outcome
    check(out is not None and out.won and out.first_clear and out.towers == (T.PERPLEXITY,), "the outcome is recorded")
    check(p.is_completed("hello_world") and s.report.counted, "progress and records both updated")
    s.finish()
    check(p._storage.saves == 1, "finish() records once")
    q = R.RunSession(rec, campaign.new_game("garbage_collection", 1), False, p)
    q.finish()
    check(q.campaign_outcome is not None and not q.campaign_outcome.won and p.completed_count() == 1, "an abandoned level is not a win")


# ====================================================================== screens
class _App:
    def __init__(self):
        self.calls = []

    def show_menu(self):
        self.calls.append("menu")

    def start_tutorial(self):
        self.calls.append("tutorial")

    def start_campaign_level(self, lid):
        self.calls.append("start:" + lid)

    def show_campaign(self, briefing=None):
        self.calls.append("campaign" + ("" if briefing is None else ":" + briefing))

    def restart_level(self):
        self.calls.append("retry")

    def show_map_select(self):
        self.calls.append("map_select")

    def continue_run(self):
        self.calls.append("continue")

    def quit(self):
        self.calls.append("quit")


def _paint(c):
    from lindefense.ui.cyber import Cyber
    from lindefense.ui.jawt import BufferedImage
    img = BufferedImage(1600, 1000, BufferedImage.TYPE_INT_ARGB)
    g2 = img.create_graphics()
    Cyber.quality(g2)
    c.paint(g2)
    g2.dispose()
    return img


def test_campaign_screen_states_and_clicks(check):
    from lindefense.ui.campaign_screen import BOOT_CAMP, CampaignScreen, slot_rect
    from lindefense.ui.jawt import KeyEvent
    app = _App()
    p = CampaignProgress.in_memory({"hello_world": 3, "garbage_collection": 1})
    s = CampaignScreen(app, p, story=StoryLog.in_memory(scene_keys()))   # every scene seen: no story in the way
    s.frame(0.05)
    _paint(s)
    nodes = [n for _r, n, *_ in s.cards]
    check(nodes == [BOOT_CAMP] + [lv.id for lv in LEVELS], "BOOT CAMP and every level, in path order")
    rects = [r for r, *_ in s.cards]
    check(all(0 <= x and x + w <= 1600 and 100 <= y and y + h <= 1000 for x, y, w, h in rects), "inside the layout")
    check(not [(a, b) for i, a in enumerate(rects) for b in rects[i + 1:]
               if a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]], "no overlaps")
    ok = {n: o for _r, n, _f, _b, o in s.cards}
    check(ok["hello_world"] and ok["legacy_code"] and not ok["campus_tour"], "completed / available / locked")

    def centre(i):
        x, y, w, h = slot_rect(i)
        return x + w / 2, y + h / 2
    s.mouse_pressed(*centre(4))   # campus_tour: locked
    check(not s.is_briefing_open(), "a locked level does not open")
    s.mouse_pressed(*centre(3))   # legacy_code
    check(s.is_briefing_open() and s.get_briefing_level().id == "legacy_code", "an available level opens its briefing")
    s.frame(0.05)
    _paint(s)
    go = next(b for b in s.briefing_buttons if b.get_text() == "START")
    s.mouse_pressed(go.get_x() + 10, go.get_y() + 10)
    check(app.calls == ["start:legacy_code"], "START plays it (%s)" % app.calls)
    s.key_pressed(KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, KeyEvent.VK_ESCAPE, KeyEvent.CHAR_UNDEFINED))
    check(not s.is_briefing_open(), "Esc closes the briefing")
    s.key_pressed(KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, KeyEvent.VK_ESCAPE, KeyEvent.CHAR_UNDEFINED))
    check(app.calls[-1] == "menu", "a second Esc goes back to the menu")
    s.mouse_pressed(*centre(0))
    check(app.calls[-1] == "tutorial", "BOOT CAMP starts the tutorial")
    texts = [o.get_label() for o in s if hasattr(o, "get_label")]
    check("Start the tutorial" in texts, "BOOT CAMP not done yet")
    done_screen = CampaignScreen(app, CampaignProgress.in_memory(boot_camp=True))
    check(any(hasattr(o, "get_label") and o.get_label().startswith("Done") for o in done_screen), "a finished BOOT CAMP says so")
    s.key_pressed(KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, KeyEvent.VK_ENTER, KeyEvent.CHAR_UNDEFINED))
    check(s.get_briefing_level() is campaign.level("legacy_code"), "Enter briefs the next level")
    done = CampaignScreen(app, CampaignProgress.in_memory({lv.id: 3 for lv in LEVELS}), "last_line_of_code")
    check(done.is_briefing_open(), "a briefing can open at once (NEXT LEVEL)")
    _paint(done)
    fresh = CampaignScreen(app, CampaignProgress.in_memory(), "outsourced")
    check(not fresh.is_briefing_open(), "never for a locked level")


def test_briefing_shows_the_star_thresholds_and_the_boss_leak_cap(check):
    """Every briefing has a Stars block (the integrity a win must keep for 3 and 2 stars) and, in a level with bosses,
    the boss leak cap (the finale adds that Palantir costs all of it), above the Best row and the buttons."""
    from lindefense.ui.campaign_screen import BRIEF_H, BRIEF_Y, CampaignScreen
    s = CampaignScreen(_App(), CampaignProgress.in_memory({lv.id: 2 for lv in LEVELS}))
    for lv in LEVELS:
        s.open_briefing(lv)
        texts = [o.get_label() for o in s.briefing if hasattr(o, "get_label")]
        three, two = lv.star_lives()
        check("Stars" in texts and "lose at most %d integrity" % (lv.start_lives - three) in texts
              and "at most %d" % (lv.start_lives - two) in texts and "any win" in texts, "%s: the star thresholds" % lv.id)
        cap = [t for t in texts if t.startswith("A boss that gets through")]
        if lv.threats()["bosses"]:
            check(len(cap) == 1 and ("at most %d integrity" % lv.boss_leak()) in cap[0], "%s: the boss leak cap (%s)" % (lv.id, cap))
            check(("Palantir costs all of it" in cap[0]) == lv.is_finale(), "%s: Palantir named in the finale only" % lv.id)
        else:
            check(not cap, "%s: no boss line without bosses" % lv.id)
        check(s.scoring_bottom <= BRIEF_Y + BRIEF_H - 118, "%s: above the Best row (%.0f)" % (lv.id, s.scoring_bottom))
        hp = [t for t in texts if t.startswith("Enemies have")]
        check(len(hp) == 1 and lv.hp_text() in hp[0], "%s: the enemy health line" % lv.id)
    _paint(s)


def test_level_complete_and_defeat_panels(check):
    from lindefense.ui.game_screen import GameScreen
    app = _App()
    g = campaign.new_game("outsourced", 5)
    s = GameScreen(app, g)
    g._state = State.VICTORY
    s.frame(0.02)
    _paint(s)
    labels = [b.get_text() for b in s.overlay_buttons]
    check(labels == ["NEXT LEVEL", "CAMPAIGN", "RETRY"], "won: NEXT LEVEL / CAMPAIGN / RETRY (%s)" % labels)
    texts = [o.get_label() for o in s.overlay if hasattr(o, "get_label")]
    check("LEVEL COMPLETE" in texts and texts.count("NEW TOWER UNLOCKED") == 2, "the title and two reward cards (%s)" % texts)
    s.overlay_buttons[0].click()
    check(app.calls == ["campaign:technical_debt"], "NEXT LEVEL briefs the next level (%s)" % app.calls)
    s.overlay_buttons[2].click()
    check(app.calls[-1] == "retry", "RETRY")
    g2 = campaign.new_game("outsourced", 5)
    s2 = GameScreen(app, g2)
    g2._lives = 0
    g2._state = State.DEFEAT
    s2.frame(0.02)
    _paint(s2)
    check([b.get_text() for b in s2.overlay_buttons] == ["RETRY", "CAMPAIGN"], "lost: RETRY / CAMPAIGN")
    g3 = campaign.new_game(campaign.finale(), 5)
    s3 = GameScreen(app, g3)
    g3._state = State.VICTORY
    s3.frame(0.02)
    check(s3.is_epilogue_open(), "the finale plays the epilogue first")
    s3.skip_epilogue()
    _paint(s3)
    check([b.get_text() for b in s3.overlay_buttons] == ["CAMPAIGN", "RETRY", "MAIN MENU"], "then CAMPAIGN COMPLETE")
    check("CAMPAIGN COMPLETE" in [o.get_label() for o in s3.overlay if hasattr(o, "get_label")], "titled so")


def test_retry_replays_the_same_level(check):
    g = campaign.new_game("event_horizon", 5)
    g.start_next_wave()
    h = Game.fresh_copy(g)
    check(h.get_campaign() is not None and h.get_campaign().level_id == "event_horizon" and h.get_wave() == 0, "same level, fresh")
    check(h.get_cash() == campaign.level("event_horizon").start_cash, "with its starting cash")


# ====================================================================== classic untouched
def test_classic_games_are_untouched(check):
    g = Game(maps.create(2), 77)
    check(g.get_campaign() is None and g.get_wave_count() == waves.WAVE_COUNT, "no campaign, 100 waves")
    g.start_next_wave()
    check(g.get_era_wave() == g.get_wave() == 1 and waves.for_game(g, 5) is waves.get(5), "the base waves")
    check("campaign" not in " ".join(g.get_tags()), "no campaign tag")
    ai = DefenderAI(g, Options())
    check(list(ai.get_plan()) == list(EFFICIENT_PLAN) and ai._overflow_list is None, "the bot without an allowlist is unchanged")


def test_bot_respects_the_allowlist(check):
    from lindefense.tools.auto_player import campaign_options, setup_phase
    g = campaign.new_game("legacy_code", 3)
    ai = DefenderAI(g, campaign_options(g))
    check(all(st.type in g.get_campaign().allowed for st in ai.get_plan()), "the plan keeps only allowed towers")
    setup_phase(ai)
    for _ in range(60 * 60 * 3):
        if g.get_tick() % 15 == 0:
            ai.manage()
        if g.get_wave_manager().can_start_next_wave() and g.get_wave() < 6:
            g.start_next_wave()
        g.step(DT)
        g.get_events().clear()
    built = {t.get_type() for t in g.get_tower_manager().get_player_towers()}
    check(built and built <= set(g.get_campaign().allowed), "it only built allowed towers (%s)" % sorted(t.name for t in built))


# ====================================================================== the real app flow
def _real_app():
    from lindefense.app import LindefenseApp
    from lindefense.ui.scaled_layer import ScaledLayer
    app = LindefenseApp.__new__(LindefenseApp)
    app.root = ScaledLayer()
    app.menu = app.map_select = app.game_screen = None
    app.demo = app.window_grab = app.autosave = None
    app._errors = {}
    app.running = True
    app.px_w, app.px_h = 1600, 1000
    app._settle_heap = lambda: None
    return app


def test_app_flow_campaign_to_level_and_back(check):
    from lindefense.ui.campaign_screen import CampaignScreen
    app = _real_app()
    app.show_campaign()
    check(isinstance(app.get_map_select(), CampaignScreen), "CAMPAIGN opens the level path")
    cs = app.get_map_select()
    check(cs.is_story_open(), "the first visit plays the prologue")
    cs.open_briefing(1)
    cs.start(1)
    check(cs.is_story_open() and app.get_game() is None, "the first START plays the level's dialogue")
    cs.story_overlay.skip()
    g = app.get_game()
    check(g is not None and g.get_campaign().level_id == "hello_world", "START plays level 1")
    check(g.get_hero_collection() is HeroCollection.persistent(), "with the saved Hero Store collection")
    g.start_next_wave()
    app.frame(1 / 60.0)
    app.quit_level()
    check(isinstance(app.get_map_select(), CampaignScreen), "QUIT LEVEL returns to the campaign")
    info = savegame.slot().peek()
    check(info is not None and info.label() == "Level 1: Hello, World, wave 1 / 10", "the level waits in the save slot")
    app.continue_run()
    g = app.get_game()
    check(g.get_campaign().level_id == "hello_world" and g.get_wave() == 1, "CONTINUE restores the level")
    _clear_waves(g, g.get_wave_count())
    for _ in range(90):
        app.frame(1 / 60.0)
    check(g.get_state() is State.VICTORY, "won")
    p = CampaignProgress.persistent()
    check(p.is_completed("hello_world") and T.PERPLEXITY in p.unlocked_towers(), "the progress is saved")
    check(not savegame.slot().exists(), "the finished level left the save slot")
    gs = app.get_game_screen()
    nxt = next(b for b in gs.overlay_buttons if b.get_text() == "NEXT LEVEL")
    nxt.click()
    cs = app.get_map_select()
    check(isinstance(cs, CampaignScreen) and cs.get_briefing_level() is campaign.level(2), "NEXT LEVEL briefs level 2")
    rec = R.Records.persistent()
    check(rec.career()["victories"] == 1 and not rec.history(), "the career counts it, the classic history does not")
