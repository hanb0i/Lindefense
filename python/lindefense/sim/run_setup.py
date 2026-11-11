"""How a player run is set up from the mission briefing: an optional typed seed (run code), challenge rules, the
Patch Notes switch, and the daily run (one seed, map, difficulty and rule per calendar date, the same for everyone).
Also the two small saved stores behind them: RunOptions (Patch Notes on / off) and DailyRecords (best wave per day).
Both are in memory for headless runs and tests (or injected with set_instance), never the player's save folder."""
import datetime
import hashlib
import os
import re

from lindefense import prefs
from lindefense.sim.challenges import Challenge, ordered
from lindefense.sim.difficulty import Difficulty
from lindefense.variance.variance import SEED_SPACE, seed_format, seed_next, seed_parse

_SEED_PREFIX = re.compile(r"^seed(\s*[:#]\s*|\s+)", re.IGNORECASE)
_SEED_CHARS = re.compile(r"^-?[0-9A-Za-z]+$")


# ====================================================================== seed entry
def parse_seed_entry(text):
    """Parses the briefing's SEED field. Returns (seed, error): (None, None) for a blank field (random seed), (seed,
    None) for a valid run code, (None, message) otherwise. Accepts what the game prints ("K3X9QZ", any case) and a
    pasted "SEED K3X9QZ"; spaces are ignored."""
    s = "" if text is None else text.strip()
    s = _SEED_PREFIX.sub("", s, count=1)
    s = re.sub(r"\s+", "", s)
    if not s:
        return None, None
    if not _SEED_CHARS.match(s):
        return None, "Seeds use only letters A-Z and digits 0-9"
    v = seed_parse(s)
    if v is None:
        return None, "That seed is too long"
    return v, None


# ====================================================================== daily run
DAILY_DIFFICULTIES = (Difficulty.ON, Difficulty.ON2)
DAILY_RULES = (Challenge.NO_HEROES, Challenge.NO_SELLING, Challenge.FRUGAL, Challenge.GLASS_CANNON)
DAILY_SALT = "lindefense/daily/v1/"


def date_key(d):
    """"YYYY-MM-DD" for a date / datetime (local calendar date)."""
    return "%04d-%02d-%02d" % (d.year, d.month, d.day)


class DailyRun:
    """The daily run for one calendar date: a seed, map, Difficulty Growth mode and one challenge rule, all derived
    from a SHA-256 hash of "YYYY-MM-DD", so every player gets the same run on the same date. Patch Notes are always on
    (the draft offers and Breaking News follow the seed)."""

    def __init__(self, date):
        from lindefense.map import maps
        self.date = date_key(date) if not isinstance(date, str) else date
        d = hashlib.sha256((DAILY_SALT + self.date).encode("ascii")).digest()
        self.seed = int.from_bytes(d[0:8], "big") % SEED_SPACE
        self.map_index = int.from_bytes(d[8:12], "big") % maps.MAP_COUNT
        self.difficulty = DAILY_DIFFICULTIES[d[12] % len(DAILY_DIFFICULTIES)]
        self.rule = DAILY_RULES[d[13] % len(DAILY_RULES)]
        self.challenges = (self.rule,)

    @staticmethod
    def for_date(d):
        return DailyRun(d)

    @staticmethod
    def today(clock=None):
        """Today's daily run by the local clock (clock: a function returning a date, for tests)."""
        return DailyRun((clock or datetime.date.today)())

    def seed_text(self):
        return seed_format(self.seed)

    def tag(self):
        return "daily:" + self.date

    def label(self):
        """"MON 09 NOV 2026"."""
        y, m, d = (int(x) for x in self.date.split("-"))
        return datetime.date(y, m, d).strftime("%a %d %b %Y").upper()

    def setup(self):
        return RunSetup(self.map_index, self.difficulty, self.seed, self.challenges, True, self.date)

    def __eq__(self, o):
        return isinstance(o, DailyRun) and (o.date, o.seed, o.map_index, o.difficulty, o.rule) == (
            self.date, self.seed, self.map_index, self.difficulty, self.rule)

    def __hash__(self):
        return hash(self.date)

    def __repr__(self):
        return "DailyRun(%s seed %s map %d %s %s)" % (self.date, self.seed_text(), self.map_index, self.difficulty.id,
                                                       self.rule.name)


# ====================================================================== RunSetup
class RunSetup:
    """Everything the briefing decides about a defense run. create_game builds the Game in the same order as a plain
    DEPLOY did before, so a run without a seed, challenges or daily date simulates exactly as before."""

    def __init__(self, map_index, difficulty, seed=None, challenges=(), patch_notes=True, daily=None):
        self.map_index = map_index
        self.difficulty = difficulty
        self.seed = seed
        self.challenges = ordered(challenges)
        self.patch_notes = patch_notes
        self.daily = daily

    def create_game(self, heroes=None, admin=None):
        from lindefense.map import maps
        from lindefense.sim.game import Game
        g = Game(maps.create(self.map_index), seed_next() if self.seed is None else self.seed, self.difficulty)
        if heroes is not None:
            g.set_hero_collection(heroes)
        if admin is not None:
            g.set_admin(*admin)
        g.set_challenges(self.challenges)
        if self.seed is not None:
            g.set_seed_fixed(True)
            g.add_run_tag("daily:" + self.daily if self.daily else "custom-seed")
        if self.patch_notes:
            g.get_variance().enable()
        return g


# ====================================================================== stores
class _MemoryNode:
    """prefs.Node stand-in that keeps everything in memory."""

    def __init__(self):
        self._d = {}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def put(self, key, value):
        self._d[key] = value


def _transient_run():
    return (os.environ.get("SDL_VIDEODRIVER") == "dummy" or bool(os.environ.get("LINDEFENSE_HEADLESS"))
            or bool(os.environ.get("LINDEFENSE_DEMO")))


class RunOptions:
    """Run options from the briefing. Patch Notes on / off is saved (prefs node lindefense/run_options);
    LINDEFENSE_VARIANCE=off still forces them off. The challenge toggles are remembered for the session only, so they
    start off every time the game is launched."""
    NODE = "lindefense/run_options"
    ENV = "LINDEFENSE_VARIANCE"
    instance = None

    def __init__(self, node):
        self._node = node
        self.challenges = ()

    @staticmethod
    def in_memory():
        return RunOptions(_MemoryNode())

    @staticmethod
    def get():
        if RunOptions.instance is None:
            RunOptions.instance = RunOptions(_MemoryNode() if _transient_run() else prefs.node(RunOptions.NODE))
        return RunOptions.instance

    @staticmethod
    def set_instance(o):
        RunOptions.instance = o

    @staticmethod
    def env_allows_patch_notes():
        v = os.environ.get(RunOptions.ENV)
        return v is None or v.strip().lower() not in ("off", "false")

    def is_patch_notes_saved_on(self):
        v = self._node.get("patch_notes", True)
        return v if isinstance(v, bool) else True

    def patch_notes_on(self):
        """True when new runs get Patch Notes and Breaking News (the saved switch, unless the env var forces them off)."""
        return self.env_allows_patch_notes() and self.is_patch_notes_saved_on()

    def set_patch_notes(self, on):
        self._node.put("patch_notes", bool(on))

    def toggle_patch_notes(self):
        self.set_patch_notes(not self.is_patch_notes_saved_on())
        return self.patch_notes_on()

    def set_challenges(self, cs):
        self.challenges = ordered(cs)

    def toggle_challenge(self, c):
        cs = set(self.challenges)
        cs.symmetric_difference_update({c})
        self.challenges = ordered(cs)
        return c in cs


class DailyRecords:
    """Best wave reached in each day's daily run (prefs node lindefense/daily, the latest KEEP_DAYS dates)."""
    NODE = "lindefense/daily"
    KEEP_DAYS = 60
    instance = None

    def __init__(self, node):
        self._node = node

    @staticmethod
    def in_memory():
        return DailyRecords(_MemoryNode())

    @staticmethod
    def get():
        if DailyRecords.instance is None:
            DailyRecords.instance = DailyRecords(_MemoryNode() if _transient_run() else prefs.node(DailyRecords.NODE))
        return DailyRecords.instance

    @staticmethod
    def set_instance(r):
        DailyRecords.instance = r

    def _all(self):
        v = self._node.get("best", {})
        return v if isinstance(v, dict) else {}

    def best(self, date):
        """Best wave cleared in the daily run of date ("YYYY-MM-DD"), 0 if never played."""
        v = self._all().get(date, 0)
        return v if isinstance(v, int) and not isinstance(v, bool) else 0

    def record(self, date, wave):
        """Stores wave as date's best if it beats it; True if it did."""
        if wave <= self.best(date):
            return False
        d = dict(self._all())
        d[date] = int(wave)
        for k in sorted(d)[:-self.KEEP_DAYS]:
            del d[k]
        self._node.put("best", d)
        return True

    def note(self, game):
        """Called every frame of a match: saves a daily run's progress as soon as a wave beats the day's best. Admin-mode
        runs keep no daily best, as they keep no records."""
        date = game.get_daily_date()
        return date is not None and not game.is_admin() and self.record(date, game.get_last_completed_wave())
