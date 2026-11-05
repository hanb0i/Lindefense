package lindefense.ui;

import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerType;

/**
 * The guided tutorial's steps and completion rules (pure logic, no ACM, so it is tested headlessly). Each step either
 * waits for the player to do something in the real game or is an info card advanced with NEXT. Steps that need cash
 * top it up once on entry so a new player can never get stuck. The tutorial match uses an in-memory hero collection,
 * so heroes bought here are practice unlocks and never reach the saved collection.
 */
public final class TutorialScript {
    /** One tutorial step. */
    public enum Step {
        WELCOME("Welcome to Lindefense", "Enemies march along the glowing track toward the exit. Each one that escapes costs lives; at 0 you lose. Earn cash by destroying them and build towers beside the track.", false, 0),
        PLACE("Build your first tower", "Pick a tower card in the ARMORY on the right (try GPT or Gemini under PRIMARY), then click a free spot next to the track. The ring shows its range.", true, 0),
        WAVE("Start a wave", "Press SPACE or the START WAVE button at the top. Waves never start on their own unless AUTO is on.", true, 0),
        UPGRADE("Upgrade a tower", "Click one of your towers, then press UPGRADE in the panel (or U). Each upgrade is a stronger tier; selling refunds 70%. Tutorial bonus: +$900.", true, 900),
        TARGETING("Targeting", "With a tower selected, press T or the < > arrows to choose who it shoots: First, Last, Strongest, Weakest or Closest.", false, 0),
        HERO_STORE("Open the Hero Store", "Press HEROES at the top right (or K) and BUY a hero. Real unlocks are permanent; this one is a practice unlock. Tutorial bonus: +$1,000.", true, 1000),
        DEPLOY("Deploy your hero", "Press DEPLOY on the hero's card and click a spot on the map. Deploying is free, but each hero can be deployed only once per match.", true, 0),
        HERO_UPGRADE("Upgrade your hero", "Heroes level up like towers: select the hero and press UPGRADE (or U) to buy the first of its three upgrades. Each one changes what it does and how it looks. Tutorial bonus: +$600.", true, 600),
        ZETHOS("Meet Zethos", "Zethos (PRIMARY tab, $650) is a regular tower with FOUR upgrades: piercing quantum shots that gain splash, then bounce between enemies. After the fourth upgrade, $15,000 unlocks Reality Collapse.", false, 0),
        DONE("You're ready", "Towers and heroes grow through upgrades. Once a shop tower has every upgrade, you can buy its overpowered ability for $15,000. Look anything up in the CATALOG on the main menu. Press H in game for controls. Good luck!", false, 0);

        public final String title, text;
        /** True when the step completes by doing something in the game (false = info card with NEXT). */
        public final boolean action;
        /** Cash granted once when the step starts. */
        public final int grant;
        Step(String title, String text, boolean action, int grant) { this.title = title; this.text = text; this.action = action; this.grant = grant; }
    }

    private final Game game;
    private int index;
    private boolean granted;
    private boolean finished;
    private int heroTierAtStart;

    public TutorialScript(Game game) { this.game = game; enter(); }

    public Step current() { return Step.values()[index]; }
    public int index() { return index; }
    public int count() { return Step.values().length; }
    public boolean isFinished() { return finished; }

    /** NEXT on an info card (or SKIP on an action step). */
    public void next() {
        if (finished) return;
        if (index >= count() - 1) { finished = true; return; }
        index++;
        enter();
    }

    /** Ends the tutorial early. */
    public void skipAll() { finished = true; }

    private void enter() {
        granted = false;
        Step s = current();
        if (s.grant > 0) { game.addCash(s.grant, null); granted = true; }
        if (s == Step.HERO_UPGRADE) {
            Tower h = hero();
            heroTierAtStart = h == null ? 0 : h.getTier();
        }
    }

    /** True if this step's grant has been paid. */
    public boolean grantPaid() { return granted; }

    private Tower hero() {
        for (Tower t : game.getTowerManager().getPlayerTowers()) if (t.getType().isHero()) return t;
        return null;
    }

    /** Checks the game and advances action steps whose goal is met. Call every frame. */
    public void update() {
        if (finished || !current().action) return;
        if (isComplete(current())) next();
    }

    /** Whether the goal of an action step is met right now. */
    public boolean isComplete(Step s) {
        switch (s) {
            case PLACE: return !game.getTowerManager().getPlayerTowers().isEmpty();
            case WAVE: return game.getWave() >= 1;
            case UPGRADE:
                for (Tower t : game.getTowerManager().getPlayerTowers()) if (t.getTier() >= 1) return true;
                return false;
            case HERO_STORE:
                for (TowerType h : TowerType.heroes()) if (game.isHeroUnlocked(h)) return true;
                return false;
            case DEPLOY: return hero() != null;
            case HERO_UPGRADE: {
                Tower h = hero();
                return h != null && h.getTier() > heroTierAtStart;
            }
            default: return false;
        }
    }
}
