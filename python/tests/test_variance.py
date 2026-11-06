"""Run variance: Patch Notes (drafted run modifiers) and Breaking News (one-wave events). Port of VarianceTests.java."""
import math
import os

from kit import DT, buildable_near, hit_for, spawn_at, tower_near_track
from lindefense.combat.hit_spec import DamageType
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.javacompat import JavaRandom, jround
from lindefense.jenum import EnumSet
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game
from lindefense.sim.vec import Vec
from lindefense.tower import catalog, shop
from lindefense.tower.tower_type import TowerType as T
from lindefense.variance import variance as V
from lindefense.variance.variance import BreakingNews, Knob, Mods, PatchNote, Picker, RunVariance
from lindefense.wave import waves
from lindefense.wave.waves import WaveManager

K = Knob
_probed = set()
LONG_MIN, LONG_MAX = -(1 << 63), (1 << 63) - 1


# ---------------------------------------------------------------- helpers
def _clean(check, m=0):
    g = Game(maps.create(m), 42, Difficulty.O1)
    check(g.start_next_wave(), "variance-off game starts wave 1 at once")
    _finish(g)
    g.get_variance().enable()
    return g


def _finish(g):
    g.get_enemy_manager().clear()
    g.get_wave_manager().end_wave()
    g.on_wave_completed(g.get_wave(), g.get_wave_manager().get_current_def())


def _play_through(g):
    if not g.start_next_wave():
        return False
    _finish(g)
    return True


def _round5(lst, mult):
    return lst if mult == 1 else int(jround(lst * mult / 5.0) * 5)


def _near(a, b):
    return abs(a - b) <= 1e-9 * max(1, abs(b))


def _place(check, g, t):
    p = buildable_near(g, Vec(400, 250), 320)
    tw = g.place_tower(t, p)
    check(tw is not None, "placed %s (%s)" % (t, g.placement_problem(t, p)))
    return tw


def _spawn_big(g, t, ms):
    e = g.get_enemy_manager().spawn_scaled(t, ms, 0, 300, 1000, 1.0)
    g.get_enemy_manager().update(0)
    return e


def _player_default():
    """Mirrors the launcher's variance switch: on unless LINDEFENSE_VARIANCE=off/false."""
    v = os.environ.get("LINDEFENSE_VARIANCE")
    return v is None or v.lower() not in ("off", "false")


# ---------------------------------------------------------------- off switch
def test_off_by_default(check):
    g = Game(maps.create(0), 42, Difficulty.O1)
    v = g.get_variance()
    check(not v.is_enabled() and not v.is_draft_pending() and not v.get_active(), "a new Game has variance off")
    check(g.get_wave_manager().can_start_next_wave(), "no draft blocks wave 1")
    check(v.fire_rate() == 1 and v.range() == 1 and v.enemy_hp() == 1 and v.enemy_speed() == 1 and v.kill_income() == 1
          and v.wave_bonus() == 1 and v.ability_cooldown() == 1, "every multiplier hook is exactly 1")
    check(v.leak_lives(5) == 5 and v.closed_route(2) == -1 and v.sell_fraction(shop.SELL_FRACTION) == shop.SELL_FRACTION, "neutral")
    for t in T.shop_towers():
        check(shop.price_of(t, g) == shop.price_of(t), "%s costs its list price" % t)
    check(shop.ability_unlock_cost(g) == catalog.ABILITY_UNLOCK_COST, "ability unlock at list price")
    for w in range(1, waves.WAVE_COUNT + 1):
        d = waves.get(w)
        if v.shape_wave(d) is not d:
            check(False, "wave %d reshaped while off" % w)
            break
    e = _spawn_big(g, EnemyType.STATIC_ARRAY, None)
    check(v.damage_against(e) == 1, "damage neutral")
    played = 0
    while played < 99 and _play_through(g):
        played += 1
    check(played == 99, "99 waves play without a draft while off (%d)" % played)
    check(not v.get_news_log() and not v.get_active() and not v.is_draft_pending(), "no draft or news while off")


def test_off_switch(check, monkeypatch):
    g = Game(maps.create(0), 42, Difficulty.O1)
    g.get_variance().enable()
    check(g.get_variance().is_draft_pending() and not g.get_wave_manager().can_start_next_wave() and not g.start_next_wave(),
          "enabled: the wave-1 draft blocks the wave")
    g.get_variance().grant(PatchNote.QUANTIZATION)
    check(g.get_variance().fire_rate() == 1.2, "a granted card applies")
    g.get_variance().disable()
    check(not g.get_variance().is_enabled() and not g.get_variance().is_draft_pending() and g.get_variance().fire_rate() == 1
          and g.get_global_rate_multiplier() == 1, "disable: every hook neutral again")
    check(g.start_next_wave(), "disable: the wave starts")
    monkeypatch.delenv("LINDEFENSE_VARIANCE", raising=False)
    check(_player_default(), "players get variance by default")
    monkeypatch.setenv("LINDEFENSE_VARIANCE", "off")
    check(not _player_default(), "LINDEFENSE_VARIANCE=off turns it off for players")


# ---------------------------------------------------------------- tables
def test_card_table(check):
    notes = list(PatchNote)
    check(15 <= len(notes) <= 20, "15-20 patch notes (%d)" % len(notes))
    titles, chips = set(), set()
    for p in notes:
        check(p.title not in titles and p.chip not in chips, "%s title and chip are unique" % p)
        titles.add(p.title)
        chips.add(p.chip)
        check(len(p.chip) <= 16 and p.chip == p.chip.upper(), "%s chip is short upper case" % p)
        check(bool(p.flavor), "%s has flavour text" % p)
        check(bool(p.upsides(1)), "%s has an upside" % p)
        check(bool(p.downsides(1)), "%s has a downside" % p)
        for e in p.mods().effects(1):
            check(e.text and "NaN" not in e.text and "nan" not in e.text, "%s effect text %r" % (p, e))
        check(not p.mods().has(K.ALL_CAMO) and not p.mods().has(K.CLOSE_LANE) and not p.mods().has(K.REFRESH_ABILITIES), "%s run-long knobs" % p)
    check(len(list(BreakingNews)) >= 6, "at least six news events")
    for n in BreakingNews:
        check(not n.mods().is_neutral() and n.headline(10), "%s changes something and has a headline" % n)
        check(n.min_wave >= RunVariance.NEWS_FIRST_WAVE, "%s never before the first news wave" % n)
        harsh = any(not e.good for e in n.mods().effects(10))
        if harsh and n is not BreakingNews.GPU_SHORTAGE:
            check(not n.on_boss_waves, "%s (a downside) is kept off boss waves" % n)
    outside = []
    for src in list(PatchNote) + list(BreakingNews):
        for k in Knob:
            if src.mods().get(k) < k.min or src.mods().get(k) > k.max:
                outside.append("%s.%s" % (src, k))
    check(not outside, "every single card and event fits inside the stacking bounds %r" % outside)
    st = _clean(check)
    v = st.get_variance()
    v.grant(PatchNote.DATA_DROUGHT)
    v.grant(PatchNote.VENTURE_CAPITAL)
    v.grant(PatchNote.BATCH_INFERENCE)
    check(_near(v.kill_income(), K.KILL_INCOME.min), "three income cuts stop at the bound (%s)" % v.kill_income())
    v.grant(PatchNote.EDGE_DEPLOYMENT)
    v.grant(PatchNote.COMPUTE_FUTURES)
    v.force_news(BreakingNews.GPU_SHORTAGE, -1)
    check(v.upgrade_price(1000) == jround(1000 * K.UPGRADE_COST.max), "stacked upgrade surcharges stop at the bound")
    v.grant(PatchNote.QUANTIZATION)
    v.grant(PatchNote.GRADIENT_CLIPPING)
    v.grant(PatchNote.CONSTITUTIONAL_AI)
    plain = _spawn_big(st, EnemyType.DYNAMIC_ARRAY, None)
    check(_near(v.damage_against(plain), K.DAMAGE.min), "stacked damage cuts stop at the bound")
    a = Mods.of().set(K.DAMAGE, 1.2).set(K.SELL_REFUND, -0.2)
    b = Mods.of().set(K.DAMAGE, 0.5).set(K.SELL_REFUND, 0.1).flag(K.ALL_CAMO)
    c = a.combine(b)
    check(_near(c.get(K.DAMAGE), 0.6) and _near(c.get(K.SELL_REFUND), -0.1) and c.has(K.ALL_CAMO) and Mods.NONE.is_neutral(),
          "mods combine: multiply, add, or")


# ---------------------------------------------------------------- every card / event really applies
def test_card_effects_apply(check):
    for p in PatchNote:
        def modded(p=p):
            g = _clean(check)
            g.get_variance().grant(p)
            return g
        _verify(check, p.name, p.mods(), modded)
        g = _clean(check)
        before = g.get_cash()
        g.get_variance().grant(p)
        check(p in g.get_variance().get_active(), "%s is active after the grant" % p)
        cash = p.mods().cash_for(2)
        check(_near(g.get_cash() - before, cash), "%s pays its one-off credits (%s)" % (p, cash))
        if cash > 0:
            _probed.add(K.CASH_NOW)
        if cash > 0 and p.mods().has(K.CASH_PER_WAVE):
            check(p.mods().cash_for(40) > cash, "%s one-off credits grow with the wave" % p)
            _probed.add(K.CASH_PER_WAVE)


def test_news_effects_apply(check):
    for n in BreakingNews:
        def modded(n=n):
            g = _clean(check)
            g.get_variance().force_news(n, 1)
            return g
        _verify(check, n.name, n.mods(), modded)
        g = _clean(check)
        before = g.get_cash()
        g.get_variance().force_news(n, 1)
        check(_near(g.get_cash() - before, n.mods().cash_for(2)), "%s pays its one-off credits" % n)
    g = _clean(check)
    g.add_cash(100_000, None)
    t = tower_near_track(g, T.CLAUDE, 3, 400)
    check(g.unlock_ability(t), "Claude ability unlocked")
    spawn_at(g, EnemyType.STATIC_ARRAY, None, 0, 300)
    check(g.activate_ability(t) and t.get_ability_cooldown_remaining() > 0, "ability on cooldown")
    g.get_variance().force_news(BreakingNews.SOLAR_FLARE, -1)
    check(t.get_ability_cooldown_remaining() > 0, "Solar Flare waits for its wave")
    check(g.start_next_wave() and t.get_ability_cooldown_remaining() == 0, "Solar Flare resets cooldowns when the wave starts")
    _probed.add(K.REFRESH_ABILITIES)
    _finish(g)
    check(g.get_variance().get_news() is None, "Solar Flare ends with its wave")


def _verify(check, tag, m, modded):
    def base():
        return _clean(check)
    gpt = T.GPT
    if m.has(K.TOWER_COST):
        g = modded()
        want = _round5(catalog.get(gpt).base_cost, m.get(K.TOWER_COST))
        before = g.get_cash()
        check(shop.price_of(gpt, g) == want, "%s: GPT costs %d (got %d)" % (tag, want, shop.price_of(gpt, g)))
        _place(check, g, gpt)
        check(_near(before - g.get_cash(), want), "%s: placing charges the adjusted price" % tag)
        _probed.add(K.TOWER_COST)
    if m.has(K.UPGRADE_COST):
        g = modded()
        g.add_cash(5000, None)
        t = _place(check, g, gpt)
        lst = t.next_upgrade().cost
        want = _round5(lst, m.get(K.UPGRADE_COST))
        before = g.get_cash()
        check(shop.upgrade_cost(t, g) == want and g.upgrade_tower(t) and _near(before - g.get_cash(), want),
              "%s: upgrade charges %d for a %d upgrade" % (tag, want, lst))
        _probed.add(K.UPGRADE_COST)
    if m.has(K.ABILITY_UNLOCK_COST):
        g = modded()
        g.add_cash(200_000, None)
        t = tower_near_track(g, T.CLAUDE, 3, 400)
        want = _round5(catalog.ABILITY_UNLOCK_COST, m.get(K.ABILITY_UNLOCK_COST))
        before = g.get_cash()
        check(shop.ability_unlock_cost(g) == want and g.unlock_ability(t) and _near(before - g.get_cash(), want),
              "%s: ability unlock charges %d" % (tag, want))
        _probed.add(K.ABILITY_UNLOCK_COST)
    if m.has(K.SELL_REFUND):
        g = modded()
        frac = max(0.0, min(RunVariance.MAX_SELL_FRACTION, shop.SELL_FRACTION + m.get(K.SELL_REFUND)))
        paid = shop.price_of(gpt, g)
        t = _place(check, g, gpt)
        want = int(math.floor(paid * frac))
        check(_near(shop.sell_fraction(g), frac) and g.sell_tower(t) == want, "%s: selling refunds %d" % (tag, want))
        _probed.add(K.SELL_REFUND)
    if m.has(K.KILL_INCOME):
        g, b = modded(), base()
        check(_near(g.get_reward_scale(), b.get_reward_scale() * m.get(K.KILL_INCOME)), "%s: kill reward scale" % tag)
        e = spawn_at(g, EnemyType.STATIC_ARRAY, None, 0, 300)
        before = g.get_cash()
        g.get_enemy_manager().kill(e)
        check(_near(g.get_cash() - before, jround(EnemyType.STATIC_ARRAY.reward * g.get_reward_scale())), "%s: a kill pays the scaled reward" % tag)
        _probed.add(K.KILL_INCOME)
    if m.has(K.WAVE_BONUS):
        g = modded()
        before = g.get_cash()
        check(g.start_next_wave(), "%s: wave 2 starts" % tag)
        _finish(g)
        want = jround(waves.wave_bonus(2) * m.get(K.WAVE_BONUS))
        check(_near(g.get_cash() - before, want), "%s: wave-2 bonus is %d (got %s)" % (tag, want, g.get_cash() - before))
        _probed.add(K.WAVE_BONUS)
    if m.has(K.INTEREST_RATE):
        for bank in (8_000.0, 200_000.0):
            g = modded()
            g.add_cash(bank - g.get_cash(), None)
            check(g.start_next_wave(), "%s: wave 2 starts" % tag)
            _finish(g)
            after_bonus = bank + jround(waves.wave_bonus(2) * m.get(K.WAVE_BONUS))
            interest = math.floor(after_bonus * m.get(K.INTEREST_RATE))
            if m.has(K.INTEREST_CAP):
                interest = min(interest, m.get(K.INTEREST_CAP))
            check(_near(g.get_cash(), after_bonus + interest) and _near(g.get_variance().get_last_interest(), interest),
                  "%s: interest %s on %s" % (tag, interest, after_bonus))
        _probed.add(K.INTEREST_RATE)
        _probed.add(K.INTEREST_CAP)
    dmg_knobs = (K.DAMAGE, K.BOSS_DAMAGE, K.NON_BOSS_DAMAGE, K.ELITE_DAMAGE, K.PLAIN_DAMAGE)
    if any(m.has(k) for k in dmg_knobs):
        kinds = ((EnemyType.DYNAMIC_ARRAY, None), (EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.CAMO)),
                 (EnemyType.BELLARMINE_COLLEGE_PREP, None), (EnemyType.BELLARMINE_COLLEGE_PREP, EnumSet.of(Modifier.FORTIFIED)))
        for type_, ms in kinds:
            g, b = modded(), base()
            g.set_global_enemy_speed_multiplier(0)
            b.set_global_enemy_speed_multiplier(0)
            dm = hit_for(g, _spawn_big(g, type_, ms), 100, DamageType.TRUE)
            db = hit_for(b, _spawn_big(b, type_, ms), 100, DamageType.TRUE)
            want = (m.get(K.DAMAGE) * (m.get(K.BOSS_DAMAGE) if type_.is_boss() else m.get(K.NON_BOSS_DAMAGE))
                    * (m.get(K.PLAIN_DAMAGE) if ms is None else m.get(K.ELITE_DAMAGE)))
            check(_near(dm, db * want), "%s: damage vs %s %s x%s (%s vs %s)" % (tag, type_, ms, want, dm, db))
        for k in dmg_knobs:
            if m.has(k):
                _probed.add(k)
    if m.has(K.FIRE_RATE) or m.has(K.RANGE):
        g, b = modded(), base()
        tg, tb = _place(check, g, gpt), _place(check, b, gpt)
        check(tg.get_tier() == tb.get_tier(), "%s: same tier for the rate / range probe" % tag)
        if m.has(K.FIRE_RATE):
            check(_near(tg.effective_rate(g), tb.effective_rate(b) * m.get(K.FIRE_RATE)), "%s: attack rate" % tag)
            _probed.add(K.FIRE_RATE)
        if m.has(K.RANGE):
            check(_near(tg.effective_range(g), tb.effective_range(b) * m.get(K.RANGE)), "%s: range" % tag)
            _probed.add(K.RANGE)
    if m.has(K.ABILITY_COOLDOWN):
        g = modded()
        g.add_cash(200_000, None)
        t = tower_near_track(g, T.CLAUDE, 3, 400)
        check(g.unlock_ability(t), "%s: ability unlocked" % tag)
        spawn_at(g, EnemyType.STATIC_ARRAY, None, 0, 300)
        check(g.activate_ability(t) and _near(t.get_ability_cooldown_remaining(), t.get_ability().cooldown * m.get(K.ABILITY_COOLDOWN)),
              "%s: cooldown scaled" % tag)
        _probed.add(K.ABILITY_COOLDOWN)
    if m.has(K.ENEMY_HP):
        g, b = modded(), base()
        check(_near(g.get_wave_hp_scale(), b.get_wave_hp_scale() * m.get(K.ENEMY_HP)), "%s: HP scale" % tag)
        eg = spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 300)
        eb = spawn_at(b, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 300)
        check(abs(eg.get_max_hp() - eb.get_max_hp() * m.get(K.ENEMY_HP)) <= 1, "%s: spawned enemies get the HP" % tag)
        _probed.add(K.ENEMY_HP)
    if m.has(K.ENEMY_SPEED):
        g, b = modded(), base()
        check(_near(g.get_wave_speed_scale(), b.get_wave_speed_scale() * m.get(K.ENEMY_SPEED)), "%s: speed scale" % tag)
        eg = spawn_at(g, EnemyType.STATIC_ARRAY, None, 0, 10)
        eb = spawn_at(b, EnemyType.STATIC_ARRAY, None, 0, 10)
        dg, db = eg.get_distance(), eb.get_distance()
        for _ in range(30):
            g.get_enemy_manager().update(DT)
            b.get_enemy_manager().update(DT)
        check(_near(eg.get_distance() - dg, (eb.get_distance() - db) * m.get(K.ENEMY_SPEED)), "%s: enemies travel scaled" % tag)
        _probed.add(K.ENEMY_SPEED)
    if m.has(K.ENEMY_COUNT) or m.has(K.SPAWN_GAP) or m.has(K.ALL_CAMO):
        g = modded()
        cm, gap = m.get(K.ENEMY_COUNT), m.get(K.SPAWN_GAP)
        for w in (10, 50, 90):
            d = waves.get(w)
            s = g.get_variance().shape_wave(d)
            check(s is not d and len(s.groups) == len(d.groups) and s.number == w, "%s: wave %d reshaped" % (tag, w))
            for a, z in zip(d.groups, s.groups):
                if a.type.is_boss():
                    check(z is a, "%s: boss group untouched (wave %d)" % (tag, w))
                    continue
                check(z.count == max(1, jround(a.count * cm)), "%s: count (wave %d)" % (tag, w))
                check(_near(z.interval, a.interval * gap / (1 + 0.5 * (cm - 1))), "%s: spawn gap (wave %d)" % (tag, w))
                check((Modifier.CAMO in z.modifiers) == (m.has(K.ALL_CAMO) or Modifier.CAMO in a.modifiers), "%s: camo (wave %d)" % (tag, w))
            for a, orig in zip(d.groups, waves.get(w).groups):
                check(a.modifiers == orig.modifiers, "%s: the campaign data is never modified" % tag)
        check(g.start_next_wave(), "%s: wave 2 starts" % tag)
        live = g.get_wave_manager().get_current_def()
        want = g.get_variance().shape_wave(waves.get(2))
        check(live.total_spawns() == want.total_spawns(), "%s: the live wave uses the reshaped groups" % tag)
        for k in (K.ENEMY_COUNT, K.SPAWN_GAP, K.ALL_CAMO):
            if m.has(k):
                _probed.add(k)
    if m.has(K.CLOSE_LANE):
        g, b = modded(), base()
        closed = g.get_variance().closed_route(len(g.get_map().get_routes()))
        check(closed == 1, "%s: lane 1 is closed" % tag)
        picks = [g.get_map().pick_route(g) for _ in range(300)]
        check(closed not in picks and any(r != closed for r in picks), "%s: no enemy enters the closed lane" % tag)
        seen = {b.get_map().pick_route(b) for _ in range(300)}
        check(len(seen) == len(b.get_map().get_routes()), "%s: without the outage every lane is used" % tag)
        check(g.get_variance().closed_route(1) == -1, "%s: a one-lane map never closes its lane" % tag)
        _probed.add(K.CLOSE_LANE)
    if m.has(K.LIVES_PER_WAVE):
        g = modded()
        before = g.get_lives()
        check(before == g.get_max_lives() and g.start_next_wave(), "%s: full integrity, wave 2 starts" % tag)
        _finish(g)
        check(g.get_lives() == before + int(m.get(K.LIVES_PER_WAVE)), "%s: integrity per wave past the maximum (%d)" % (tag, g.get_lives()))
        over = g.get_lives()
        check(g.restore_lives(5) == 0 and g.get_lives() == over, "%s: healing never lowers integrity above the maximum" % tag)
        _probed.add(K.LIVES_PER_WAVE)
    if m.has(K.LEAK_LIVES):
        g = modded()
        r = g.get_map().get_routes()[0]
        spawn_at(g, EnemyType.HEAP_SORT, None, 0, r.get_total_length() - 1)
        before = g.get_lives()
        i = 0
        while i < 120 and g.get_lives() == before:
            g.step(DT)
            i += 1
        want = max(1, jround(EnemyType.HEAP_SORT.lives * m.get(K.LEAK_LIVES)))
        check(before - g.get_lives() == want, "%s: a leak costs %d (cost %d)" % (tag, want, before - g.get_lives()))
        check(g.get_variance().leak_lives(1) == 1, "%s: a leak always costs at least 1" % tag)
        _probed.add(K.LEAK_LIVES)
    if m.has(K.FREE_FIRST_UPGRADE):
        g = modded()
        price = shop.price_of(gpt, g)
        before = g.get_cash()
        t = _place(check, g, gpt)
        check(t.get_tier() == 1 and _near(before - g.get_cash(), price), "%s: a new GPT arrives at tier 1 for its base price" % tag)
        check(shop.sell_value(t, g) == int(math.floor(price * shop.sell_fraction(g))), "%s: the free upgrade is not refunded" % tag)
        g.add_cash(100_000, None)
        hp = buildable_near(g, Vec(800, 600), 320)
        h = g.place_tower(T.LOBBER_LUIS, hp)
        if h is None:
            g.get_hero_collection().unlock(T.LOBBER_LUIS)
            h = g.place_tower(T.LOBBER_LUIS, buildable_near(g, Vec(800, 600), 320))
        check(h is not None and h.get_tier() == 0, "%s: heroes do not get the free upgrade" % tag)
        _probed.add(K.FREE_FIRST_UPGRADE)


def test_every_knob_probed(check):
    used = set()
    for src in list(PatchNote) + list(BreakingNews):
        for k in Knob:
            if src.mods().has(k):
                used.add(k)
    for k in sorted(used, key=lambda k: k.ordinal):
        check(k in _probed, "knob %s is used by a card or event and was probed in the real game" % k)


# ---------------------------------------------------------------- draft schedule
def test_draft_schedule(check):
    g = Game(maps.create(0), 42, Difficulty.O1)
    v = g.get_variance()
    v.enable()
    drafts = 0
    for w in range(1, 100):
        due = RunVariance.draft_index(w) >= 0
        check(v.is_draft_pending() == due, "draft open before wave %d iff it is a draft wave (%s)" % (w, due))
        if due:
            check(not g.get_wave_manager().can_start_next_wave() and not g.start_next_wave(), "wave %d waits for the pick" % w)
            offer = v.get_offer()
            check(len(offer) == RunVariance.OFFER_SIZE and len(set(offer)) == len(offer), "three different cards before wave %d" % w)
            for p in offer:
                check(p not in v.get_active(), "%s not offered again once taken" % p)
            check(v.get_offer_wave() == w and v.get_draft_number() == drafts + 1, "draft %d precedes wave %d" % (drafts + 1, w))
            check(not v.pick(7) and v.is_draft_pending(), "an out-of-range pick is refused")
            check(v.pick(w % len(offer)), "pick accepted")
            drafts += 1
        check(_play_through(g), "wave %d starts after the draft" % w)
    act = v.get_active()
    check(drafts == 5 and len(act) == 5 and len(set(act)) == 5, "five drafts, five different cards")
    for i in range(5):
        check(v.get_picked_before(i) == RunVariance.DRAFT_WAVES[i], "card %d recorded its draft wave" % i)
    check(v.get_version() == "1.5", "patch version 1.5 after five picks")
    h = Game(maps.create(0), 43, Difficulty.O1)
    h.get_variance().enable(Picker.FIRST)
    h.get_variance().set_picker(Picker.PLAYER)
    for _ in range(18):
        _play_through(h)
    check(not h.get_variance().is_draft_pending() and h.start_next_wave(), "wave 19 starts")
    _finish(h)
    check(h.get_variance().is_draft_pending() and h.get_variance().get_offer_wave() == 20, "clearing wave 19 opens the wave-20 draft")
    h.get_wave_manager().set_auto_start(True)
    h.run(60 * 20)
    check(h.get_wave() == 19, "auto-start never skips a pending draft")
    h.get_variance().pick(0)
    h.run(int(60 * (WaveManager.PREP_TIME + 1)))
    check(h.get_wave() == 20, "auto-start resumes after the pick")


def _random_run(seed):
    g = Game(maps.create(0), seed, Difficulty.O1)
    g.get_variance().enable(Picker.RANDOM)
    for _ in range(99):
        _play_through(g)
    return list(g.get_variance().get_active())


def test_auto_pickers(check):
    seed = 99
    f = Game(maps.create(0), seed, Difficulty.O1)
    f.get_variance().enable(Picker.FIRST)
    expect = RunVariance.offer_for(seed, 1, [])[0]
    act = f.get_variance().get_active()
    check(not f.get_variance().is_draft_pending() and len(act) == 1 and act[0] is expect, "FIRST takes the first offered card")
    check(f.start_next_wave(), "tools never wait for a draft")
    a, b = _random_run(seed), _random_run(seed)
    check(a == b and len(a) == 5, "RANDOM picks are seeded: %r" % a)
    p = Game(maps.create(0), seed, Difficulty.O1)
    p.get_variance().enable()
    check(p.get_variance().is_draft_pending(), "PLAYER waits")
    p.get_variance().set_picker(Picker.FIRST)
    check(not p.get_variance().is_draft_pending() and p.get_variance().get_active()[0] is expect, "switching answers the pending draft")


# ---------------------------------------------------------------- news
def test_news_rate(check):
    rolls = hits = early = bad_lane = unstable = 0
    seen = set()
    for seed in range(400):
        for w in range(1, waves.WAVE_COUNT + 1):
            r = BreakingNews.roll(seed, w, False, 2)
            if w < RunVariance.NEWS_FIRST_WAVE or w >= waves.WAVE_COUNT:
                if r is not None:
                    early += 1
                continue
            rolls += 1
            if r is None:
                continue
            hits += 1
            seen.add(r.news)
            if w < r.news.min_wave:
                early += 1
            if r.news is BreakingNews.SERVER_OUTAGE and not (0 <= r.lane < 2):
                bad_lane += 1
            again = BreakingNews.roll(seed, w, False, 2)
            if again is None or again.news is not r.news or again.lane != r.lane:
                unstable += 1
    check(early == 0, "no event before its first wave (%d)" % early)
    check(bad_lane == 0, "an outage always closes a real lane (%d)" % bad_lane)
    check(unstable == 0, "a roll is deterministic in (seed, wave) (%d differ)" % unstable)
    rate = hits / float(rolls)
    check(abs(rate - RunVariance.NEWS_CHANCE) < 0.01, "news rate %s ~ %s" % (rate, RunVariance.NEWS_CHANCE))
    check(len(seen) == len(list(BreakingNews)), "every event appears (%d)" % len(seen))
    boss_bad = boss_news = 0
    for seed in range(300):
        r = BreakingNews.roll(seed, 50, True, 1)
        if r is None:
            continue
        boss_news += 1
        if not r.news.on_boss_waves or r.news is BreakingNews.SERVER_OUTAGE:
            boss_bad += 1
    check(boss_news > 30 and boss_bad == 0, "boss waves on a one-lane map only get harmless events (%d of %d)" % (boss_bad, boss_news))


def _count_announced(seed, g):
    n = 0
    for w in range(1, 100):
        boss = g.get_difficulty().shape(waves.get(w), seed).contains_boss()
        if BreakingNews.roll(seed, w, boss, len(g.get_map().get_routes())) is not None:
            n += 1
    return n


def test_news_lifetime(check):
    announced = 0
    for seed in range(1, 5):
        g = Game(maps.create(0), seed, Difficulty.O1)
        v = g.get_variance()
        v.enable(Picker.FIRST)
        bad = 0
        for w in range(1, 100):
            if not (v.get_news() is None or v.get_news_wave() == w):
                bad += 1
            pre = v.get_news()
            if not g.start_next_wave():
                bad += 1
                break
            if v.get_news() is not pre:
                bad += 1
            if pre is not None:
                announced += 1
            _finish(g)
            if not (v.get_news() is None or v.get_news_wave() == w + 1):
                bad += 1
        check(bad == 0, "news announced before its wave, lasts it and expires (seed %d, %d violations)" % (seed, bad))
        check(len(v.get_news_log()) == _count_announced(seed, g), "the log lists every headline (seed %d)" % seed)
    check(announced > 40, "news happened during the runs (%d)" % announced)
    g = _clean(check)
    g.get_variance().force_news(BreakingNews.DDOS, -1)
    check(g.start_next_wave() and g.get_variance().get_news() is BreakingNews.DDOS, "DDoS live on its wave")
    g.get_enemy_manager().clear()
    g.get_wave_manager().end_wave()
    check(g.start_next_wave() and g.get_variance().get_news() is None, "stale news is dropped on the next wave")


# ---------------------------------------------------------------- determinism
def _transcript(seed, m, noise):
    g = Game(maps.create(m), seed, Difficulty.ON2)
    g.get_variance().enable(Picker.RANDOM)
    for _ in range(99):
        if noise:
            for _ in range(137):
                g.get_rng().next()
        _play_through(g)
    act = g.get_variance().get_active()
    offers = [RunVariance.offer_for(seed, RunVariance.DRAFT_WAVES[i], act[:i]) for i in range(5)]
    return repr((list(act), list(g.get_variance().get_news_log()), offers))


def _simulate(seed):
    g = Game(maps.create(0), seed, Difficulty.ON)
    g.get_variance().enable(Picker.RANDOM)
    g.set_invincible(True)
    g.add_cash(20_000, None)
    spots = (Vec(380, 300), Vec(700, 250), Vec(460, 520), Vec(820, 660))
    types = (T.GPT, T.CLAUDE, T.PERPLEXITY, T.DEEPSEEK)
    for s, t in zip(spots, types):
        g.place_tower(t, buildable_near(g, s, 200))
    g.get_wave_manager().set_auto_start(True)
    g.start_next_wave()
    g.run(60 * 240)
    return "wave %d cash %d lives %d killed %d cards %r news %d" % (
        g.get_wave(), int(g.get_cash()), g.get_lives(), g.get_enemy_manager().get_total_killed(),
        list(g.get_variance().get_active()), len(g.get_variance().get_news_log()))


def test_determinism(check):
    a, b, noisy, other = _transcript(7, 0, False), _transcript(7, 0, False), _transcript(7, 0, True), _transcript(8, 0, False)
    check(a == b, "same seed, same picks: same offers, cards and news")
    check(a == noisy, "offers and news do not depend on the combat RNG")
    check(a != other, "another seed deals another run")
    s1, s2 = _simulate(2024), _simulate(2024)
    check(s1 == s2, "a simulated run with variance on is reproducible: " + s1)


# ---------------------------------------------------------------- refunds
def test_refunds_what_was_paid(check):
    g = _clean(check)
    g.add_cash(10_000, None)
    t = _place(check, g, T.GPT)
    g.get_variance().force_news(BreakingNews.GPU_SHORTAGE, -1)
    surcharge = shop.upgrade_cost(t, g)
    check(surcharge == _round5(t.next_upgrade().cost, 1.25) and g.upgrade_tower(t), "GPU shortage: upgrade at +25%")
    paid = catalog.get(T.GPT).base_cost + surcharge
    check(g.get_variance().unpaid_on(t) == t.get_invested_cost() - paid, "the surcharge is recorded")
    check(shop.sell_value(t, g) == int(math.floor(paid * shop.SELL_FRACTION)), "selling refunds 70% of what was paid")
    h = _clean(check)
    early = _place(check, h, T.GPT)
    h.get_variance().grant(PatchNote.OPEN_SOURCE)
    check(shop.sell_value(early, h) == int(math.floor(catalog.get(T.GPT).base_cost * (shop.SELL_FRACTION - 0.20))),
          "Open Source refunds 50% of the list price actually paid before it")
    refund = h.sell_tower(early)
    check(refund > 0 and h.get_variance().unpaid_on(early) == 0, "a sold tower is forgotten")
    off = Game(maps.create(0), 42, Difficulty.O1)
    off.add_cash(10_000, None)
    o = _place(check, off, T.GPT)
    off.upgrade_tower(o)
    check(shop.sell_value(o, off) == shop.sell_value(o), "variance off: the classic 70% of the invested cost")


# ---------------------------------------------------------------- seeds
def test_seeds_and_restart(check, monkeypatch):
    r = JavaRandom(5)
    for i in range(200):
        s = LONG_MIN if i == 0 else LONG_MAX if i == 1 else r.next_long()
        check(V.seed_parse(V.seed_format(s)) == s, "seed code round trip %d" % s)
    check(V.seed_format(1234) == "YA" and V.seed_parse(" ya ") == 1234 and V.seed_parse("not a seed!") is None, "seed codes are base 36")
    monkeypatch.delenv(V.SEED_PROPERTY, raising=False)
    for _ in range(50):
        s = V.seed_next()
        check(0 <= s < V.SEED_SPACE and len(V.seed_format(s)) <= 6, "fresh seed is a short code")
    monkeypatch.setenv(V.SEED_PROPERTY, "K3X9QZ")
    check(V.seed_next() == V.seed_parse("K3X9QZ"), "LINDEFENSE_SEED forces the seed")
    g = Game(maps.create(1), 777, Difficulty.ON)
    g.get_variance().enable()
    first = g.get_variance().get_offer()
    replay = Game.fresh_copy(g, g.get_seed())
    check(replay.get_seed() == 777 and replay.get_variance().is_enabled() and replay.get_variance().get_offer() == first,
          "REPLAY SEED deals the same first offer")
    restart = Game.fresh_copy(g)
    check(restart.get_variance().is_enabled() and restart.get_variance().is_draft_pending(), "RESTART keeps variance on")
