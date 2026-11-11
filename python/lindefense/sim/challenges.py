"""Challenge rules: optional handicaps the player switches on in the mission briefing (all off by default). Game
applies them through explicit flags (Game.set_challenges); a game without challenges simulates exactly as before.
Reverse mode (Adversarial Training) never takes challenges, so the defender AI is unaffected."""
from lindefense.jenum import JEnum

ONE_LIFE_LIVES = 1
GLASS_CANNON_LIVES = 25
GLASS_CANNON_DAMAGE = 1.5
FRUGAL_PRICE = 1.5


class Challenge(JEnum):
    NO_HEROES = ("no-heroes", "NO HEROES", "No Heroes",
                 "Heroes cannot be deployed this run (hero limit 0).", 0xffe94a)
    ONE_LIFE = ("one-life", "ONE LIFE", "One Life",
                "You start with 1 integrity: the first leak ends the run.", 0xff3b4e)
    NO_SELLING = ("no-selling", "NO SELLING", "No Selling",
                  "Towers cannot be sold and heroes cannot be dismissed.", 0xff8c3b)
    FRUGAL = ("frugal", "FRUGAL", "Frugal",
              "Towers, heroes and upgrades cost 50% more. Income is unchanged.", 0x3bff8a)
    GLASS_CANNON = ("glass-cannon", "GLASS CANNON", "Glass Cannon",
                    "Your towers deal +50% damage, but you start with 25 integrity.", 0xff2bd6)

    def _init(self, tag, chip, title, description, rgb):
        self.tag = tag                  # run tag (Game.run_tags) and save / records key
        self.chip = chip                # HUD / end-screen chip text
        self.title = title
        self.description = description
        self.rgb = rgb

    @staticmethod
    def by_tag(tag):
        for c in Challenge:
            if c.tag == tag:
                return c
        return None


def ordered(challenges):
    """The given challenges without duplicates, in declaration order (a stable order for chips and tags)."""
    s = set(challenges or ())
    return tuple(c for c in Challenge if c in s)
