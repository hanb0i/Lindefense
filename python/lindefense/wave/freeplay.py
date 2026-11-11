"""Freeplay: endless generated waves after Palantir (wave 101 onwards).

Every freeplay wave is generated from (run seed, wave number) with its own Rng, so a seed always replays the same
waves and nothing here touches Game._rng or the hand-written campaign (waves 1-100 are unchanged). All of the
escalation lives in the named constants of FreeplayWaves: enemy health grows exponentially without bound, counts
grow until COUNT_CAP, modifiers and boss escorts get more common, a headline boss arrives every BOSS_EVERY waves and
a rebuilt Palantir every PALANTIR_EVERY waves."""
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.jenum import EnumSet
from lindefense.sim.rng import Rng
from lindefense.wave.waves import WAVE_COUNT, SpawnGroup, WaveDef

_E = EnemyType


def _ramp(spec, depth):
    """(base, per_wave, cap) -> base + per_wave * depth, at most cap."""
    base, per, cap = spec
    return min(cap, base + per * depth)


class FreeplayWaves:
    FIRST_WAVE = WAVE_COUNT + 1
    SALT = 0x0F4EE9A7

    # ---- per-enemy scaling (depth = wave - WAVE_COUNT; continues the campaign curve: waves.hp_scale(100) is 2.1,
    # speed_scale(100) is 1.35)
    HP_START = 2.1            # health multiplier at depth 0
    HP_GROWTH = 1.06          # x per freeplay wave, forever: this is what makes freeplay impossible eventually
    SPEED_START = 1.35
    SPEED_PER_WAVE = 0.01
    SPEED_CAP = 1.75
    MAX_DEPTH = 5000          # health stops growing here only to keep the numbers finite (x1e147)
    REWARD_SCALE = 1.6        # kill income multiplier (same as waves 81-100)
    WAVE_BONUS = 300          # end-of-wave bonus (same as waves 40-100)

    # ---- regular groups
    GROUPS = (3, 4)           # regular groups per wave (min, max inclusive)
    GROUP_COUNT = (22, 36)    # enemies per regular group at depth 0 (min, max inclusive)
    COUNT_GROWTH = 0.02       # +2% enemies per wave ...
    COUNT_CAP = 2.0           # ... until 2x (health keeps growing; this keeps the frame rate sane)
    GROUP_SPAN = 22.0         # seconds a regular group takes to spawn
    GROUP_STAGGER = 5.0       # seconds between regular group starts
    MIN_INTERVAL = 0.12
    ROSTER = ((_E.TIMSORT, 4), (_E.QUICK_SORT, 3), (_E.HEAP_SORT, 3), (_E.RADIX_SORT, 3), (_E.BUCKET_SORT, 2),
              (_E.MERGE_SORT, 2), (_E.SHELL_SORT, 2), (_E.INSERTION_SORT, 2), (_E.SELECTION_SORT, 1),
              (_E.COUNTING_SORT, 1), (_E.DOUBLY_LINKED_LIST, 2), (_E.SINGLY_LINKED_LIST, 1))

    # ---- modifier chance per group: (base, per wave, cap)
    CAMO = (0.30, 0.010, 0.80)
    FORTIFIED = (0.45, 0.015, 0.90)
    REGROW = (0.20, 0.010, 0.70)
    INJECTORS = (3, 0.1, 8)   # prompt injectors per wave: 3 + depth / 10, at most 8

    # ---- MOAB-class escorts in every wave: (base, per wave, cap) counts, from their first depth
    MOAB_ESCORTS = (3, 0.2, 12)
    DDT_ESCORTS = (1, 0.1, 6)
    DDT_FROM = 1
    BFB_ESCORTS = (1, 1 / 12.0, 4)
    BFB_FROM = 1
    ESCORT_FORTIFIED = (0.60, 0.015, 0.95)
    ESCORT_CAMO = (0.10, 0.008, 0.50)

    # ---- headline bosses
    BOSS_EVERY = 10           # waves 110, 120, ...: 3Com, then a BFB pack, then a DDT swarm (rotating)
    PALANTIR_EVERY = 25       # waves 125, 150, ...: a rebuilt Palantir (overrides the boss rotation)
    ZOMG_COUNT = (1, 1 / 30.0, 4)
    BFB_PACK = (2, 1 / 25.0, 6)
    DDT_SWARM = (3, 1 / 8.0, 10)
    PALANTIR_COUNT = (1, 1 / 75.0, 3)
    HEADLINE_FORTIFIED = (0.0, 0.02, 0.80)   # chance the headline bosses are Fortified

    _cache = {}
    _CACHE_MAX = 64

    # ------------------------------------------------------------------ scaling
    @staticmethod
    def depth(wave):
        return max(0, wave - WAVE_COUNT)

    @staticmethod
    def hp_scale(wave):
        return FreeplayWaves.HP_START * FreeplayWaves.HP_GROWTH ** min(FreeplayWaves.MAX_DEPTH, FreeplayWaves.depth(wave))

    @staticmethod
    def speed_scale(wave):
        return min(FreeplayWaves.SPEED_CAP, FreeplayWaves.SPEED_START + FreeplayWaves.SPEED_PER_WAVE * FreeplayWaves.depth(wave))

    @staticmethod
    def reward_scale(wave):
        return FreeplayWaves.REWARD_SCALE

    @staticmethod
    def wave_bonus(wave):
        return FreeplayWaves.WAVE_BONUS

    @staticmethod
    def count_scale(wave):
        return min(FreeplayWaves.COUNT_CAP, 1.0 + FreeplayWaves.COUNT_GROWTH * FreeplayWaves.depth(wave))

    @staticmethod
    def is_boss_wave(wave):
        d = FreeplayWaves.depth(wave)
        return d > 0 and d % FreeplayWaves.BOSS_EVERY == 0

    @staticmethod
    def is_palantir_wave(wave):
        d = FreeplayWaves.depth(wave)
        return d > 0 and d % FreeplayWaves.PALANTIR_EVERY == 0

    # ------------------------------------------------------------------ generation
    @staticmethod
    def get(seed, wave):
        """The base (unshaped) WaveDef of freeplay wave `wave` (> WAVE_COUNT) for this run seed. Cached: the HUD asks
        every frame. The result must not be mutated (Difficulty / RunVariance shaping always copies)."""
        if wave <= WAVE_COUNT:
            raise ValueError("freeplay starts at wave " + str(FreeplayWaves.FIRST_WAVE))
        key = (seed, wave)
        w = FreeplayWaves._cache.get(key)
        if w is None:
            if len(FreeplayWaves._cache) >= FreeplayWaves._CACHE_MAX:
                FreeplayWaves._cache.clear()
            w = FreeplayWaves._cache[key] = FreeplayWaves.generate(seed, wave)
        return w

    @staticmethod
    def generate(seed, wave):
        from lindefense.variance.variance import mix
        F = FreeplayWaves
        r = Rng(mix(seed, wave, F.SALT))
        d = F.depth(wave)
        groups = []
        palantir = F.is_palantir_wave(wave)
        boss = F.is_boss_wave(wave) and not palantir
        note = None
        # headline boss first (it leads the wave), then the regular groups, then the escorts
        if palantir:
            n = int(_ramp(F.PALANTIR_COUNT, d))
            groups.append(SpawnGroup(_E.PALANTIR, n, None, 30.0, 6.0, -1))
            note = ("PALANTIR RETURNS: " + ("a rebuilt Palantir" if n == 1 else str(n) + " rebuilt Palantirs")
                    + " (BAD-class) at x" + _fmt(F.hp_scale(wave)) + " health.")
        elif boss:
            kind = (d // F.BOSS_EVERY - 1) % 3
            if kind == 0:
                n = int(_ramp(F.ZOMG_COUNT, d))
                groups.append(SpawnGroup(_E.THREE_COM, n, F._mods(r, 0, F.HEADLINE_FORTIFIED, 0, d), 12.0, 4.0, -1))
                what = _plural(n, "3Com") + " (ZOMG)"
            elif kind == 1:
                n = int(_ramp(F.BFB_PACK, d))
                groups.append(SpawnGroup(_E.SW_RESOURCE_CONSULTANT, n, F._mods(r, 0, F.HEADLINE_FORTIFIED, 0, d), 6.0, 3.0, -1))
                what = "a pack of " + str(n) + " SW Resource Consultants (BFB)"
            else:
                n = int(_ramp(F.DDT_SWARM, d))
                groups.append(SpawnGroup(_E.LOCKHEED_MARTIN, n, F._mods(r, 0, F.HEADLINE_FORTIFIED, 0, d), 2.5, 3.0, -1))
                what = "a swarm of " + str(n) + " Lockheed Martins (DDT)"
            note = "FREEPLAY BOSS: " + what + ". Enemy health x" + _fmt(F.hp_scale(wave)) + "."
        n_groups = F.GROUPS[0] + r.next_int(F.GROUPS[1] - F.GROUPS[0] + 1)
        if boss or palantir:
            n_groups -= 1
        cs = F.count_scale(wave)
        total_weight = sum(wt for _, wt in F.ROSTER)
        regular = []
        for i in range(n_groups):
            pick = r.next_int(total_weight)
            t = F.ROSTER[-1][0]
            for typ, wt in F.ROSTER:
                if pick < wt:
                    t = typ
                    break
                pick -= wt
            base = F.GROUP_COUNT[0] + r.next_int(F.GROUP_COUNT[1] - F.GROUP_COUNT[0] + 1)
            count = max(1, int(round(base * cs)))
            mods = F._mods(r, F.CAMO, F.FORTIFIED, F.REGROW, d)
            interval = max(F.MIN_INTERVAL, F.GROUP_SPAN / count)
            delay = i * F.GROUP_STAGGER + r.range(0.0, 2.0)
            regular.append(SpawnGroup(t, count, mods, interval, delay, -1))
        groups.extend(regular)
        escorts = 0
        escorts += F._escort(groups, r, _E.BELLARMINE_COLLEGE_PREP, int(_ramp(F.MOAB_ESCORTS, d)), 3.0, 4.0, d)
        if d >= F.DDT_FROM:
            escorts += F._escort(groups, r, _E.LOCKHEED_MARTIN, int(_ramp(F.DDT_ESCORTS, d)), 4.0, 10.0, d)
        if d >= F.BFB_FROM and not (boss or palantir):   # the headline replaces the BFB escorts
            escorts += F._escort(groups, r, _E.SW_RESOURCE_CONSULTANT, int(_ramp(F.BFB_ESCORTS, d)), 8.0, 7.0, d)
        injectors = F._inject(groups, int(_ramp(F.INJECTORS, d)))
        if note is None:
            note = ("Freeplay: enemy health x" + _fmt(F.hp_scale(wave)) + ", " + str(escorts) + " boss escorts, "
                    + str(injectors) + " prompt injectors.")
        return WaveDef(wave, note, groups)

    @staticmethod
    def total_hp(w):
        """Estimated total health of a WaveDef at its wave's health scale, children included (armour, shields, regrowth
        and difficulty shaping ignored). Used to check and tune the escalation."""
        from lindefense.wave import waves
        scale = waves.hp_scale(w.number)
        return sum(g.count * _unit_hp(g.type, Modifier.FORTIFIED in g.modifiers) for g in w.groups) * scale

    @staticmethod
    def _mods(r, camo, fortified, regrow, d):
        m = EnumSet()
        # always draw three numbers so one modifier's table never shifts another's roll
        rc, rf, rr = r.next(), r.next(), r.next()
        if camo and rc < _ramp(camo, d):
            m.add(Modifier.CAMO)
        if fortified and rf < _ramp(fortified, d):
            m.add(Modifier.FORTIFIED)
        if regrow and rr < _ramp(regrow, d):
            m.add(Modifier.REGROW)
        return m

    @staticmethod
    def _escort(groups, r, t, n, interval, delay, d):
        if n <= 0:
            return 0
        F = FreeplayWaves
        mods = F._mods(r, F.ESCORT_CAMO if t is not _E.LOCKHEED_MARTIN else 0, F.ESCORT_FORTIFIED, 0, d)
        groups.append(SpawnGroup(t, n, mods, interval, delay, -1))
        return n

    @staticmethod
    def _inject(groups, want):
        """Turns `want` enemies of the biggest regular group into Prompt Injection carriers (like the campaign does)."""
        best = -1
        for i, g in enumerate(groups):
            if g.type.is_boss() or g.count < 2:
                continue
            if best < 0 or g.count > groups[best].count:
                best = i
        if want <= 0 or best < 0:
            return 0
        g = groups[best]
        k = min(want, g.count - 1)
        mods = g.modifiers.copy()
        mods.add(Modifier.INJECTION)
        interval = g.interval * g.count / k
        groups[best] = SpawnGroup(g.type, g.count - k, g.modifiers, g.interval, g.start_delay, g.route)
        groups.append(SpawnGroup(g.type, k, mods, interval, g.start_delay + interval * 0.5, g.route))
        return k


def _unit_hp(t, fortified):
    hp = t.base_hp * (2 if fortified else 1)
    inherit = fortified and t.is_boss()
    if t is not _E.PALANTIR:
        for ct, n in zip(t.get_child_types(), t.get_child_counts()):
            hp += n * _unit_hp(ct, inherit)
    return hp


def _fmt(x):
    return ("%.1f" % x) if x < 100 else (str(int(round(x))) if x < 1e6 else "%.2g" % x)


def _plural(n, name):
    return ("a " + name) if n == 1 else (str(n) + " " + name + "s")
