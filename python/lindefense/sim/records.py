"""Long-term progression: per-map records and medals, career totals, the run history and achievements.

Nothing here feeds back into the simulation. A run is summarised once, when it ends (victory, defeat, or abandoned by
quitting / restarting / closing the window), by RunSummary.of(game); Records.record(summary) folds it into the saved
records with a single write and returns a RunReport (new bests, achievements unlocked) for the end screen.

Excluded runs: the tutorial and admin-mode runs change nothing; reverse-mode matches only count toward the reverse
achievements (never map records, career totals or the history). A run abandoned before its first wave is not a run.

Storage: one JSON document (node "lindefense/records" in the prefs folder). Each save rotates the previous file to
.bak; a file that does not parse is moved aside (.corrupt-<time>) and the backup is used instead, so a damaged save
never crashes the game nor silently overwrites the last good copy. Tests use Records.in_memory()."""
import copy
import json
import math
import os
import time

from lindefense import prefs

SCHEMA = 1
NODE = "lindefense/records"
HISTORY_MAX = 50
MVP_ROWS = 5

VICTORY = "victory"
DEFEAT = "defeat"
ABANDONED = "abandoned"


# ====================================================================== run summary
class TowerLine:
    """One tower of a run (alive or sold) for the MVP table."""
    __slots__ = ("type", "name", "tier", "tier_label", "max_tier", "damage", "kills", "cost", "sold", "hero")

    def __init__(self, type_name, name, tier, tier_label, max_tier, damage, kills, cost, sold=False, hero=False):
        self.type = type_name
        self.name = name
        self.tier = tier
        self.tier_label = tier_label
        self.max_tier = max_tier
        self.damage = float(damage)
        self.kills = int(kills)
        self.cost = int(cost)
        self.sold = sold
        self.hero = hero

    @staticmethod
    def of(t, sold=False):
        ty = t.get_type()
        return TowerLine(ty.name, ty.display_name, t.get_tier(), t.get_tier_label(), t.get_max_tier(),
                         t.get_damage_dealt(), t.get_kills(), t.get_invested_cost(), sold, ty.is_hero())


class RunSummary:
    """A plain snapshot of one run: everything the records and achievements need. Built from a Game by of(); tests
    build synthetic ones with keyword arguments."""
    FIELDS = dict(map_name="", map_index=-1, difficulty="O1", seed=0, result=ABANDONED, wave=0, waves_cleared=0,
                  kills=0, leaks=0, bosses=(), lives=0, max_lives=0, time=0.0, play_time=0.0, cash_earned=0.0,
                  notes=(), notes_on=False, heroes_deployed=(), max_tier=0, towers=(), heroes_bought=(),
                  tutorial=False, reverse=False, admin=False, reverse_level=None, tags=(), date="")

    def __init__(self, **kw):
        for k, v in RunSummary.FIELDS.items():
            setattr(self, k, list(v) if isinstance(v, tuple) else v)
        for k, v in kw.items():
            if k not in RunSummary.FIELDS:
                raise TypeError("unknown RunSummary field " + k)
            setattr(self, k, list(v) if isinstance(v, (tuple, set, frozenset)) else v)
        if not self.date:
            self.date = time.strftime("%Y-%m-%d %H:%M")

    @property
    def won(self):
        return self.result == VICTORY

    @staticmethod
    def result_of(game):
        """victory / defeat / abandoned from the game's state; a run quit during the victory (or defeat) sequence
        counts as won (lost). For reverse matches: victory means the player's attack won."""
        from lindefense.sim.game import State
        st = game.get_state()
        if game.is_reverse():
            r = game.get_reverse()
            if st is State.PLAYING:
                return ABANDONED
            return VICTORY if r.attacker_won() else DEFEAT
        if st is State.VICTORY or game.is_victory_sequence_active():
            return VICTORY
        if st is State.DEFEAT or game.get_lives() <= 0:
            return DEFEAT
        return ABANDONED

    @staticmethod
    def of(game, result=None, tutorial=False, play_time=None):
        from lindefense.map import maps
        from lindefense.tower.tower_type import TowerType
        if result is None:
            result = RunSummary.result_of(game)
        em = game.get_enemy_manager()
        tm = game.get_tower_manager()
        v = game.get_variance()
        lines = [TowerLine.of(t) for t in tm.get_player_towers()]
        lines += [TowerLine.of(t, True) for t, _ in tm.get_sold()]
        rev = game.get_reverse()
        return RunSummary(
            map_name=game.get_map().get_name(), map_index=maps.index_of(game.get_map()),
            difficulty=game.get_difficulty().id, seed=game.get_seed(), result=result,
            wave=max(game.get_wave(), game.get_last_completed_wave()), waves_cleared=game.get_last_completed_wave(),
            kills=em.get_total_killed(), leaks=em.get_total_leaked(), bosses=[b.name for b in game.get_boss_kills()],
            lives=game.get_lives(), max_lives=game.get_max_lives(), time=game.get_time(),
            play_time=game.get_time() if play_time is None else play_time,
            cash_earned=max(0.0, game.get_total_cash_earned() - tm.get_total_refunds()),
            notes=[p.name for p in v.get_active()], notes_on=v.is_enabled(),
            heroes_deployed=[h.name for h in TowerType.heroes() if game.is_hero_deployed(h)],
            max_tier=max([ln.tier for ln in lines] or [0]), towers=lines,
            heroes_bought=[] if game.has_admin_money() else [h.name for h in game.get_heroes_bought()],
            tutorial=tutorial, reverse=rev is not None, admin=game.is_admin(),
            reverse_level=rev.get_level().id if rev is not None else None, tags=list(game.get_tags()))

    def mvp(self, n=MVP_ROWS):
        """The top n towers by damage (ties: more kills first), sold towers included."""
        return sorted(self.towers, key=lambda t: (-t.damage, -t.kills))[:n]

    def excluded_reason(self):
        if self.tutorial:
            return "tutorial"
        if self.admin:
            return "admin"
        if self.reverse:
            return "reverse"
        return None

    def counts_as_run(self):
        """Map records, career totals and the history take campaign runs that got past the start screen."""
        return self.excluded_reason() is None and (self.wave > 0 or self.result != ABANDONED)


# ====================================================================== achievements
class Achievement:
    """One achievement: test(summary, records) is checked when a run ends, after the run has been folded into the
    records (so career totals include it). live ones are also checked during a run for an early toast."""
    __slots__ = ("id", "title", "description", "group", "mode", "live", "test")

    def __init__(self, id_, title, description, group, test, mode="campaign", live=False):
        self.id = id_
        self.title = title
        self.description = description
        self.group = group
        self.mode = mode
        self.live = live
        self.test = test


def _slug(s):
    out = "".join(c.lower() if c.isalnum() else "_" for c in s)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def _diff_text(d):
    return d.ascii_label if "ᴺ" in d.label else d.label


def _build_achievements():
    from lindefense.ai.units import DefenderProfile
    from lindefense.enemy.types import EnemyType
    from lindefense.map import maps
    from lindefense.sim.difficulty import Difficulty
    from lindefense.tower.tower_type import TowerType
    tiers = {"Beginner": 0, "Intermediate": 1, "Advanced": 2, "Expert": 3}
    ms = maps.create_all()
    map_names = [m.get_name() for m in sorted(ms, key=lambda m: tiers.get(m.get_difficulty(), 4))]   # map-select order
    heroes = [h.name for h in TowerType.heroes()]
    order = {d.id: d.ordinal for d in Difficulty}

    def at_least(d):
        return lambda s, r: s.won and order.get(s.difficulty, -1) >= d.ordinal

    def won_map(n):
        return lambda s, r: s.won and s.map_name == n

    def killed(b):
        return lambda s, r: b in s.bosses

    def beat_ai(d):
        return lambda s, r: s.reverse and s.won and s.reverse_level == d.id

    a = [Achievement("first_win", "Hello, World", "Win a campaign on any map.", "campaign", lambda s, r: s.won)]
    for n in map_names:
        short = n[4:] if n.startswith("The ") else n
        a.append(Achievement("win_" + _slug(n), "Secured: " + short, "Win a campaign on " + n + ".", "maps", won_map(n)))
    a.append(Achievement("all_maps", "Full Coverage", "Win a campaign on every map.", "maps",
                         lambda s, r: all(r.has_won_map(n) for n in map_names)))
    titles = {"ON": "Linear Time", "ON2": "Quadratic Time", "ONN": "Intractable"}
    for d in Difficulty:
        if d.id in titles:
            a.append(Achievement("win_" + d.id, titles[d.id], "Win a campaign on " + _diff_text(d) + " or harder.",
                                 "difficulty", at_least(d)))
    boss_titles = {"BELLARMINE_COLLEGE_PREP": ("Graduated", "Defeat Bellarmine College Prep."),
                   "SW_RESOURCE_CONSULTANT": ("Contract Terminated", "Defeat the SW Resource Consultant."),
                   "THREE_COM": ("Connection Refused", "Defeat 3Com."),
                   "LOCKHEED_MARTIN": ("Stealth Detected", "Defeat Lockheed Martin."),
                   "PALANTIR": ("Eye Closed", "Defeat Palantir, the final boss.")}
    for e in EnemyType:
        if e.is_boss():
            t, desc = boss_titles.get(e.name, (e.display_name + " Down", "Defeat " + e.display_name + "."))
            a.append(Achievement("boss_" + e.name.lower(), t, desc, "bosses", killed(e.name), live=True))
    a += [
        Achievement("flawless", "Zero Leaks", "Win a campaign without a single enemy leaking.", "challenge",
                    lambda s, r: s.won and s.leaks == 0),
        Achievement("no_heroes", "Solo Build", "Win a campaign without deploying a hero.", "challenge",
                    lambda s, r: s.won and not s.heroes_deployed),
        Achievement("tier_cap", "Minimum Viable Product", "Win a campaign with no tower above tier 2.", "challenge",
                    lambda s, r: s.won and s.max_tier <= 2),
        Achievement("roster", "Full Roster", "Unlock every Hero Store hero.", "heroes",
                    lambda s, r: set(heroes) <= r.heroes_bought(), live=True),
        Achievement("lindemann", "Office Hours", "Deploy Mr. Lindemann.", "heroes",
                    lambda s, r: TowerType.MR_LINDEMANN.name in s.heroes_deployed, live=True),
        Achievement("kills_100k", "Garbage Collector", "Purge 100,000 enemies across all runs.", "career",
                    lambda s, r: r.career()["enemies_killed"] >= 100_000, live=True),
        Achievement("waves_1000", "Long-Running Process", "Clear 1,000 waves across all runs.", "career",
                    lambda s, r: r.career()["waves_cleared"] >= 1000, live=True),
        Achievement("wins_10", "Production Ready", "Win 10 campaigns.", "career",
                    lambda s, r: r.career()["victories"] >= 10),
    ]
    for d in Difficulty:
        name = DefenderProfile.of(d).display_name
        a.append(Achievement("reverse_" + d.id, "Red Team: " + name,
                             "Win Adversarial Training (reverse mode) against the " + name + " AI.", "reverse",
                             beat_ai(d), mode="reverse"))
    return tuple(a)


_ACHIEVEMENTS = []


def achievements():
    """The achievement table, in display order (built on first use: it reads the map and boss catalogs)."""
    if not _ACHIEVEMENTS:
        _ACHIEVEMENTS.extend(_build_achievements())
    return tuple(_ACHIEVEMENTS)


def achievement(id_):
    for a in achievements():
        if a.id == id_:
            return a
    return None


# ====================================================================== storage
class MemoryStorage:
    """In-memory storage for tests; saves round-trip through JSON so anything unsaveable fails here too."""

    def __init__(self, data=None):
        self.data = None if data is None else json.loads(json.dumps(data))
        self.saves = 0

    def load(self):
        return None if self.data is None else json.loads(json.dumps(self.data))

    def save(self, d):
        self.data = json.loads(json.dumps(d))
        self.saves += 1


class FileStorage:
    """One JSON file with a rotating .bak; unreadable files are moved aside, never overwritten."""

    def __init__(self, path):
        self.path = path
        self.backup = path + ".bak"
        self.recovered = None    # path of a corrupt file that was moved aside on load, if any

    @staticmethod
    def default():
        return FileStorage(os.path.join(prefs._base_dir(), NODE.replace("/", "_") + ".json"))

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            raise ValueError("records file is not a JSON object")
        return d

    def load(self):
        if os.path.exists(self.path):
            try:
                return self._read(self.path)
            except (OSError, ValueError, UnicodeDecodeError):
                aside = self.path + ".corrupt-" + time.strftime("%Y%m%d-%H%M%S")
                try:
                    os.replace(self.path, aside)
                    self.recovered = aside
                except OSError:
                    pass
        if os.path.exists(self.backup):
            try:
                return self._read(self.backup)
            except (OSError, ValueError, UnicodeDecodeError):
                pass
        return None

    def save(self, d):
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=1, ensure_ascii=False)
            if os.path.exists(self.path):
                os.replace(self.path, self.backup)
            os.replace(tmp, self.path)
        except OSError:
            pass


# ====================================================================== records
_CAREER_KEYS = ("runs", "victories", "defeats", "abandoned", "waves_cleared", "enemies_killed", "bosses_killed",
                "cash_earned", "play_time", "leaks", "best_wave")


def _empty():
    return {"schema": SCHEMA, "maps": {}, "career": {k: 0 for k in _CAREER_KEYS}, "history": [],
            "achievements": {}, "heroes_bought": [], "heroes_seeded": False}


def _num(v, default=0):
    """v if it is a finite number (JSON may hold NaN / Infinity), else default."""
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else default


_HISTORY_NUMBERS = ("map_index", "seed", "wave", "waves_cleared", "lives", "time", "kills")
_HISTORY_TEXTS = ("date", "map", "difficulty", "seed_code", "result")
_HISTORY_LISTS = ("notes", "tags")


def _clean_history_entry(h):
    """A history row the screens can trust: a field of the wrong type is dropped (they show a default; REPLAY SEED is
    disabled without a seed), unknown fields are kept."""
    out = dict(h)
    for k in _HISTORY_NUMBERS:
        if k in out and _num(out[k], None) is None:
            del out[k]
    for k in _HISTORY_TEXTS:
        if k in out and not isinstance(out[k], str):
            del out[k]
    for k in _HISTORY_LISTS:
        if k in out:
            out[k] = [x for x in out[k] if isinstance(x, str)] if isinstance(out[k], list) else []
    if "notes_on" in out:
        out["notes_on"] = out["notes_on"] is True
    return out


def _clean(d):
    """A well-formed records document from whatever was loaded: bad parts are dropped, the rest is kept."""
    out = _empty()
    if not isinstance(d, dict):
        return out
    maps_ = d.get("maps")
    if isinstance(maps_, dict):
        for name, per in maps_.items():
            if not isinstance(per, dict):
                continue
            keep = {}
            for diff, rec in per.items():
                if isinstance(rec, dict):
                    keep[str(diff)] = {k: _num(v, None) for k, v in rec.items() if _num(v, None) is not None}
            out["maps"][str(name)] = keep
    car = d.get("career")
    if isinstance(car, dict):
        for k in _CAREER_KEYS:
            out["career"][k] = _num(car.get(k), 0)
    hist = d.get("history")
    if isinstance(hist, list):
        out["history"] = [_clean_history_entry(h) for h in hist if isinstance(h, dict)][:HISTORY_MAX]
    ach = d.get("achievements")
    if isinstance(ach, dict):
        out["achievements"] = {str(k): str(v) for k, v in ach.items()}
    hb = d.get("heroes_bought")
    if isinstance(hb, list):
        out["heroes_bought"] = [str(h) for h in hb]
    out["heroes_seeded"] = bool(d.get("heroes_seeded", False))
    return out


class RunReport:
    """What one run changed, for the end screen: the map record before / after, the records it broke and the
    achievements it unlocked. counted is False for excluded runs (excluded names why)."""

    def __init__(self, summary, counted, excluded=None, before=None, after=None, new_bests=(), unlocked=()):
        self.summary = summary
        self.counted = counted
        self.excluded = excluded
        self.before = before or {}
        self.after = after or {}
        self.new_bests = list(new_bests)    # [(key, label)]: best_wave / fastest / best_lives / first_win
        self.unlocked = list(unlocked)      # [Achievement]

    def is_new_best(self):
        return bool(self.new_bests)


class Records:
    """The saved progression. in_memory() never touches disk; persistent() is the shared, saved instance."""
    _shared = None

    def __init__(self, storage=None):
        self._storage = storage
        d = None
        if storage is not None:
            try:
                d = storage.load()
            except Exception:
                d = None
        self._d = _clean(d)

    @staticmethod
    def in_memory(data=None):
        return Records(MemoryStorage(data))

    @staticmethod
    def with_storage(storage):
        return Records(storage)

    @staticmethod
    def persistent():
        if Records._shared is None:
            r = Records(FileStorage.default())
            r._seed_heroes_once()
            Records._shared = r
        return Records._shared

    def _seed_heroes_once(self):
        """First run of this version: heroes unlocked by earlier versions count as bought, unless admin mode has been
        unlocked on this machine (then their provenance is unknown and only new real purchases count)."""
        if self._d["heroes_seeded"]:
            return
        try:
            from lindefense.sim.misc import AdminMode, HeroCollection
            if not AdminMode.is_unlocked():
                have = set(self._d["heroes_bought"])
                for h in HeroCollection.persistent().unlocked():
                    if h.name not in have:
                        self._d["heroes_bought"].append(h.name)
        except Exception:
            pass
        self._d["heroes_seeded"] = True

    def data(self):
        """A deep copy of the whole document (tests, debugging)."""
        return copy.deepcopy(self._d)

    def _save(self):
        if self._storage is not None:
            try:
                self._storage.save(self._d)
            except Exception:
                pass

    # ---------------- queries
    def map_record(self, map_name, difficulty):
        """{runs, victories, best_wave, fastest, best_lives} for one map and difficulty (id or Difficulty); fastest
        and best_lives are absent until the first victory."""
        did = getattr(difficulty, "id", difficulty)
        r = self._d["maps"].get(map_name, {}).get(did)
        out = {"runs": 0, "victories": 0, "best_wave": 0}
        if r:
            out.update(r)
        return out

    def has_won(self, map_name, difficulty):
        return self.map_record(map_name, difficulty)["victories"] > 0

    def has_won_map(self, map_name):
        return any(r.get("victories", 0) > 0 for r in self._d["maps"].get(map_name, {}).values())

    def medals(self, map_name):
        """{difficulty id: won?} for every difficulty, in Difficulty order."""
        from lindefense.sim.difficulty import Difficulty
        return {d.id: self.has_won(map_name, d.id) for d in Difficulty}

    def best_wave(self, map_name, difficulty=None):
        per = self._d["maps"].get(map_name, {})
        if difficulty is not None:
            return int(per.get(getattr(difficulty, "id", difficulty), {}).get("best_wave", 0))
        return int(max([r.get("best_wave", 0) for r in per.values()] or [0]))

    def career(self):
        return dict(self._d["career"])

    def history(self):
        """The last runs, newest first (dicts: date, map, map_index, difficulty, seed, seed_code, notes_on, wave,
        waves_cleared, result, notes, tags, lives, time, kills)."""
        return [dict(h) for h in self._d["history"]]

    def heroes_bought(self):
        return set(self._d["heroes_bought"])

    def is_unlocked(self, ach_id):
        return ach_id in self._d["achievements"]

    def unlocked(self):
        """{achievement id: date unlocked}."""
        return dict(self._d["achievements"])

    def unlocked_count(self):
        ids = {a.id for a in achievements()}
        return sum(1 for k in self._d["achievements"] if k in ids)

    # ---------------- updates
    def pending_live(self, summary, announced=(), baseline=None):
        """Live achievements a running game has already earned (not yet saved, not yet announced). No write. baseline:
        the summary this run was already recorded with (a Freeplay continuation), so only what happened since counts."""
        if summary.excluded_reason() is not None:
            return []
        probe = Records(None)
        probe._d = copy.deepcopy(self._d)
        if baseline is None:
            probe._fold(summary, live=True)
        else:
            probe._fold_heroes(summary)
            probe._extend_career(baseline, summary)
        out = []
        for a in achievements():
            if a.live and a.mode == "campaign" and a.id not in announced and not self.is_unlocked(a.id):
                try:
                    if a.test(summary, probe):
                        out.append(a)
                except Exception:
                    pass
        return out

    def record(self, summary):
        """Folds one finished run into the records (one save) and returns its RunReport."""
        why = summary.excluded_reason()
        if why in ("tutorial", "admin"):
            return RunReport(summary, False, why)
        before = self.map_record(summary.map_name, summary.difficulty)
        heroes = len(self._d["heroes_bought"])
        new_bests = []
        if why is None:
            new_bests = self._fold(summary)
        unlocked = self._check(summary, "reverse" if summary.reverse else "campaign")
        if summary.counts_as_run() or unlocked or len(self._d["heroes_bought"]) != heroes:
            self._save()    # one write per run end (a run quit before its first wave usually changes nothing)
        return RunReport(summary, why is None and summary.counts_as_run(), why, before,
                         self.map_record(summary.map_name, summary.difficulty), new_bests, unlocked)

    def extend(self, before, after):
        """Freeplay: the run recorded at its campaign victory (`before`) kept going; folds what happened since (waves,
        kills, bosses, time...) into the same run instead of counting a second one, updates its history entry and the
        map's best wave, and checks the achievements again. Returns a RunReport for `after`."""
        why = after.excluded_reason()
        if why is not None or not after.counts_as_run():
            return RunReport(after, False, why)
        map_before = self.map_record(after.map_name, after.difficulty)
        self._fold_heroes(after)
        self._extend_career(before, after)
        rec = self._d["maps"].setdefault(after.map_name, {}).setdefault(
            after.difficulty, {"runs": 0, "victories": 0, "best_wave": 0})
        bests = []
        if after.wave > rec.get("best_wave", 0):
            bests.append(("best_wave", "BEST WAVE"))
            rec["best_wave"] = after.wave
        for h in self._d["history"][:1]:
            if h.get("seed") == int(after.seed) and h.get("map") == after.map_name:
                h.update({"wave": after.wave, "waves_cleared": after.waves_cleared, "lives": after.lives,
                          "time": round(float(after.time), 1), "kills": after.kills, "tags": list(after.tags)})
        unlocked = self._check(after, "campaign")
        self._save()
        return RunReport(after, True, None, map_before, self.map_record(after.map_name, after.difficulty), bests,
                         unlocked)

    def _fold_heroes(self, s):
        have = set(self._d["heroes_bought"])
        for h in s.heroes_bought:
            if h not in have:
                self._d["heroes_bought"].append(h)
                have.add(h)

    def _extend_career(self, before, after):
        """Career totals for what a recorded run did since `before` (Freeplay)."""
        c = self._d["career"]
        c["waves_cleared"] += max(0, after.waves_cleared - before.waves_cleared)
        c["enemies_killed"] += max(0, after.kills - before.kills)
        c["bosses_killed"] += max(0, len(after.bosses) - len(before.bosses))
        c["cash_earned"] += max(0, int(after.cash_earned) - int(before.cash_earned))
        c["play_time"] += max(0.0, float(after.play_time) - float(before.play_time))
        c["leaks"] += max(0, after.leaks - before.leaks)
        c["best_wave"] = max(c["best_wave"], after.wave)

    def _fold(self, s, live=False):
        """Applies a campaign run to heroes / maps / career / history; returns the map records it broke."""
        self._fold_heroes(s)
        if not s.counts_as_run():
            return []
        c = self._d["career"]
        c["waves_cleared"] += s.waves_cleared
        c["enemies_killed"] += s.kills
        c["bosses_killed"] += len(s.bosses)
        if live:
            return []
        c["runs"] += 1
        c["victories" if s.result == VICTORY else ("defeats" if s.result == DEFEAT else "abandoned")] += 1
        c["cash_earned"] += int(s.cash_earned)
        c["play_time"] += float(s.play_time)
        c["leaks"] += s.leaks
        c["best_wave"] = max(c["best_wave"], s.wave)
        per = self._d["maps"].setdefault(s.map_name, {})
        old = dict(per.get(s.difficulty, {}))
        rec = per.setdefault(s.difficulty, {"runs": 0, "victories": 0, "best_wave": 0})
        rec["runs"] = rec.get("runs", 0) + 1
        bests = []
        if s.wave > rec.get("best_wave", 0):
            if old.get("runs", 0) > 0:
                bests.append(("best_wave", "BEST WAVE"))
            rec["best_wave"] = s.wave
        if s.won:
            if rec.get("victories", 0) == 0:
                bests.append(("first_win", "FIRST CLEAR"))
            rec["victories"] = rec.get("victories", 0) + 1
            if "fastest" not in rec or s.time < rec["fastest"]:
                if "fastest" in rec:
                    bests.append(("fastest", "FASTEST WIN"))
                rec["fastest"] = round(float(s.time), 2)
            if "best_lives" not in rec or s.lives > rec["best_lives"]:
                if "best_lives" in rec:
                    bests.append(("best_lives", "MOST LIVES"))
                rec["best_lives"] = int(s.lives)
        from lindefense.variance import variance
        self._d["history"].insert(0, {
            "date": s.date, "map": s.map_name, "map_index": s.map_index, "difficulty": s.difficulty,
            "seed": int(s.seed), "seed_code": variance.seed_format(int(s.seed)), "notes_on": bool(s.notes_on),
            "wave": s.wave, "waves_cleared": s.waves_cleared, "result": s.result, "notes": list(s.notes),
            "tags": list(s.tags), "lives": s.lives, "time": round(float(s.time), 1), "kills": s.kills})
        del self._d["history"][HISTORY_MAX:]
        return bests

    def _check(self, s, mode):
        out = []
        for a in achievements():
            if a.mode != mode or self.is_unlocked(a.id):
                continue
            try:
                ok = a.test(s, self)
            except Exception:
                ok = False
            if ok:
                self._d["achievements"][a.id] = s.date
                out.append(a)
        return out


# ====================================================================== one run's link to the records
class RunSession:
    """Ties one running Game to the Records: live achievement checks for toasts while it plays, and exactly one
    record() when it ends (finish() is idempotent; cancel() drops the run without recording it)."""
    LIVE_INTERVAL = 1.0

    def __init__(self, records, game, tutorial=False):
        self.records = records
        self.game = game
        self.tutorial = tutorial
        # play time rides along on the Game too, so a saved run continued later keeps the time played before the save
        self.play_time = float(getattr(game, "_records_play_time", 0.0)) if game is not None else 0.0
        self.report = None
        self.done = False
        self.announced = set()
        self._live_t = 0.0
        # the summary last recorded: Freeplay extends it. It rides along on the Game, so a Freeplay run saved and
        # continued later still extends its campaign victory instead of counting a second run.
        self._recorded = getattr(game, "_records_baseline", None) if game is not None else None

    def is_finished(self):
        return self.done

    def summary(self, result=None):
        return RunSummary.of(self.game, result, self.tutorial, self.play_time)

    def tick(self, real_dt, playing=True):
        """Call once per frame; returns the live achievements newly earned this frame (for a toast)."""
        if self.done:
            return []
        if playing:
            self.play_time += real_dt
            if self.game is not None:
                self.game._records_play_time = self.play_time
        self._live_t -= real_dt
        if self._live_t > 0:
            return []
        self._live_t = RunSession.LIVE_INTERVAL
        try:
            fresh = self.records.pending_live(self.summary(), self.announced, self._recorded)
        except Exception:
            return []
        for a in fresh:
            self.announced.add(a.id)
        return fresh

    def finish(self, result=None):
        if not self.done:
            self.done = True
            try:
                s = self.summary(result)
                if self._recorded is not None:     # a Freeplay continuation of a run already recorded
                    self.report = self.records.extend(self._recorded, s)
                else:
                    self.report = self.records.record(s)
                self._recorded = s
                if self.game is not None:
                    self.game._records_baseline = s
            except Exception:
                self.report = None
        return self.report

    def reopen(self):
        """CONTINUE - FREEPLAY: the recorded run goes on; finish() later extends that record instead of adding one."""
        if self.done and self._recorded is not None:
            self.done = False
            self._live_t = 0.0

    def cancel(self):
        self.done = True


# ====================================================================== remembered difficulty
_SELECTION_NODE = "lindefense/selection"


def remember_difficulty(d):
    """Saves the Difficulty Growth mode last picked on the map-select screen."""
    if d is not None:
        prefs.node(_SELECTION_NODE).put("difficulty", d.id)


def restore_difficulty():
    """At launch: re-selects the saved mode (the LINDEFENSE_DIFFICULTY switch, when set, wins). Returns it or None."""
    from lindefense.sim.difficulty import PROPERTY, Difficulty
    if os.environ.get(PROPERTY):
        return None
    d = Difficulty.parse(prefs.node(_SELECTION_NODE).get("difficulty"))
    if d is not None:
        Difficulty.set_selected(d)
    return d
