package lindefense.variance;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lindefense.enemy.Enemy;
import lindefense.enemy.Modifier;
import lindefense.sim.Game;
import lindefense.sim.Rng;
import lindefense.tower.Tower;
import lindefense.wave.SpawnGroup;
import lindefense.wave.WaveData;
import lindefense.wave.WaveDef;

/**
 * Run variance for one match: the drafted {@link PatchNote}s, the current {@link BreakingNews} event and the hooks the
 * economy, combat, tower and wave code call. Headless (no UI); the game owns one ({@link Game#getVariance()}).
 *
 * <p><b>Off by default.</b> A new {@code Game} has variance disabled, so tests, tools and the tutorial play the
 * unchanged game and every hook returns its neutral value (multipliers exactly 1). The windowed game turns it on for
 * real players with {@link #enable()}.</p>
 *
 * <p><b>Draft.</b> Before waves {@link #DRAFT_WAVES} (1, 20, 40, 60, 80) a draft of {@link #OFFER_SIZE} cards opens and
 * the next wave cannot start until one is picked ({@link #readyFor(int)}). With {@link Picker#PLAYER} the UI shows the
 * cards and calls {@link #pick(int)}; tools use {@link Picker#FIRST} or {@link Picker#RANDOM}, which pick on the spot.</p>
 *
 * <p><b>Seeds.</b> Offers, news and the RANDOM picker each draw from their own {@link Rng} stream derived from the game
 * seed and the wave ({@link #mix}), not from the shared combat stream: a seed always deals the same offers (given the
 * same earlier picks) and the same news on the same map, however the fight goes. Everything is reproducible from
 * {@link Game#getSeed()}.</p>
 */
public final class RunVariance {
    /** Who answers a draft. */
    public enum Picker {
        /** Wait for the player ({@link #pick(int)}); the UI shows the cards. */
        PLAYER,
        /** Take the first offered card at once (deterministic tests, the scripted demo). */
        FIRST,
        /** Take a seeded random offered card at once (the balance bot). */
        RANDOM
    }

    /** Waves before which a draft opens. */
    public static final int[] DRAFT_WAVES = { 1, 20, 40, 60, 80 };
    /** Cards offered per draft. */
    public static final int OFFER_SIZE = 3;
    /** Chance that a wave from {@link #NEWS_FIRST_WAVE} on gets a news event. */
    public static final double NEWS_CHANCE = 0.22;
    /** First wave that can have a news event. */
    public static final int NEWS_FIRST_WAVE = 6;
    /** Highest sell refund fraction any combination can reach. */
    public static final double MAX_SELL_FRACTION = 0.95;
    /** Adjusted shop prices are rounded to this many credits. */
    public static final int PRICE_STEP = 5;

    static final long DRAFT_SALT = 0x5EEDD2AF7L, NEWS_SALT = 0x0BAD9E55L, PICK_SALT = 0x91C477L;

    private final Game game;
    private boolean enabled;
    private Picker picker = Picker.PLAYER;
    private final List<PatchNote> active = new ArrayList<>();
    private final List<Integer> pickedBefore = new ArrayList<>();
    private List<PatchNote> offer;
    private int offerWave, offerIndex;
    private final boolean[] drafted = new boolean[DRAFT_WAVES.length];
    private BreakingNews news;
    private int newsWave, newsLane = -1, newsRolledFor;
    private final List<String> newsLog = new ArrayList<>();
    private Rng pickRng;
    private int freeUpgrades;
    private double lastInterest;
    /** Per tower id: list price not paid (discounts and free upgrades; negative for surcharges), so refunds use what was paid. */
    private final Map<Integer, Integer> unpaid = new HashMap<>();

    private Mods cards = Mods.NONE, current = Mods.NONE;
    // hot-path copies of the current values (read every hit / shot)
    private double fireRate = 1, range = 1, damage = 1, bossDamage = 1, nonBossDamage = 1, eliteDamage = 1, plainDamage = 1;
    private boolean damageActive;

    /** Variance state for {@code game}, disabled. */
    public RunVariance(Game game) { this.game = game; }

    // ------------------------------------------------------------------ switch
    /** True when patch notes and news are on for this match. */
    public boolean isEnabled() { return enabled; }

    /** Turns variance on with the player answering drafts (the windowed game). */
    public void enable() { enable(Picker.PLAYER); }

    /** Turns variance on with the given picker and opens the draft that is due (wave 1 on a fresh match). */
    public void enable(Picker p) {
        enabled = true;
        picker = p == null ? Picker.PLAYER : p;
        refresh();
        if (game.getWaveManager() != null && !game.getWaveManager().isWaveActive()) prepareFor(game.getWave() + 1);
    }

    /** Turns variance off: no draft blocks a wave and every hook is neutral again (picked cards stop applying). */
    public void disable() {
        enabled = false;
        offer = null;
        news = null;
        refresh();
    }

    /** Who answers drafts. */
    public Picker getPicker() { return picker; }

    /** Changes who answers drafts; an automatic picker answers a pending draft at once. */
    public void setPicker(Picker p) {
        picker = p == null ? Picker.PLAYER : p;
        if (offer != null && picker != Picker.PLAYER) autoPick();
    }

    // ------------------------------------------------------------------ schedule
    /** Index of the draft that precedes {@code wave} in {@link #DRAFT_WAVES}, or -1. */
    public static int draftIndex(int wave) {
        for (int i = 0; i < DRAFT_WAVES.length; i++) if (DRAFT_WAVES[i] == wave) return i;
        return -1;
    }

    /**
     * Gets {@code wave} ready to start: opens its draft if one is due and rolls its news (each at most once). Returns
     * false while a draft is waiting for the player. Always true when disabled.
     */
    public boolean readyFor(int wave) {
        prepareFor(wave);
        return offer == null;
    }

    /** Opens the draft due before {@code wave} and rolls the wave's news (idempotent). */
    public void prepareFor(int wave) {
        if (!enabled || wave < 1 || wave > WaveData.WAVE_COUNT) return;
        int d = draftIndex(wave);
        if (d >= 0 && !drafted[d] && offer == null) openDraft(d, wave);
        if (wave > newsRolledFor) rollNews(wave);
    }

    private void openDraft(int index, int wave) {
        offer = offerFor(game.getSeed(), wave, active);
        offerWave = wave;
        offerIndex = index;
        if (offer.isEmpty()) { offer = null; drafted[index] = true; return; }
        if (picker != Picker.PLAYER) autoPick();
    }

    /**
     * The cards offered before {@code wave} for a seed: a seeded shuffle of every card not already taken, first
     * {@link #OFFER_SIZE}. Deterministic in (seed, wave, taken).
     */
    public static List<PatchNote> offerFor(long seed, int wave, Collection<PatchNote> taken) {
        List<PatchNote> pool = new ArrayList<>();
        for (PatchNote p : PatchNote.values()) if (!taken.contains(p)) pool.add(p);
        Rng r = new Rng(mix(seed, wave, DRAFT_SALT));
        for (int i = pool.size() - 1; i > 0; i--) Collections.swap(pool, i, r.nextInt(i + 1));
        return new ArrayList<>(pool.subList(0, Math.min(OFFER_SIZE, pool.size())));
    }

    private void autoPick() {
        if (offer == null) return;
        if (picker == Picker.FIRST) { pick(0); return; }
        if (pickRng == null) pickRng = new Rng(mix(game.getSeed(), 0, PICK_SALT));
        pick(pickRng.nextInt(offer.size()));
    }

    /** True while a draft waits for the player (the next wave is blocked). */
    public boolean isDraftPending() { return offer != null; }

    /** The pending offer (unmodifiable), or an empty list. */
    public List<PatchNote> getOffer() { return offer == null ? Collections.<PatchNote>emptyList() : Collections.unmodifiableList(offer); }

    /** The wave the pending (or last) draft precedes. */
    public int getOfferWave() { return offerWave; }

    /** 1-based number of the pending (or last) draft. */
    public int getDraftNumber() { return offerIndex + 1; }

    /**
     * Takes offered card {@code index}: it applies for the rest of the run (one-off credits are paid now). Returns false
     * if no draft is pending or the index is out of range.
     */
    public boolean pick(int index) {
        if (offer == null || index < 0 || index >= offer.size()) return false;
        PatchNote p = offer.get(index);
        active.add(p);
        pickedBefore.add(offerWave);
        drafted[offerIndex] = true;
        offer = null;
        cards = cards.combine(p.mods());
        refresh();
        int cash = p.mods().cashFor(offerWave);
        if (cash > 0) game.addCash(cash, null);
        return true;
    }

    /** Takes the offered card {@code p} (see {@link #pick(int)}); false if it is not on offer. */
    public boolean pick(PatchNote p) { return offer != null && pick(offer.indexOf(p)); }

    /**
     * Test / tool hook: applies a card as if it had been picked before the next wave, without a draft (one-off credits
     * are paid). Ignored if the card is already active.
     */
    public void grant(PatchNote p) {
        if (active.contains(p)) return;
        int wave = Math.max(1, game.getWave() + (game.getWaveManager().isWaveActive() ? 0 : 1));
        active.add(p);
        pickedBefore.add(wave);
        cards = cards.combine(p.mods());
        refresh();
        int cash = p.mods().cashFor(wave);
        if (cash > 0) game.addCash(cash, null);
    }

    /**
     * Test / tool hook: breaks {@code n} as the news of the current wave (or of the next one between waves), replacing
     * any other; {@code lane} is the lane a Server Outage closes. One-off credits are paid.
     */
    public void forceNews(BreakingNews n, int lane) {
        int wave = Math.max(1, game.getWave() + (game.getWaveManager().isWaveActive() ? 0 : 1));
        newsRolledFor = Math.max(newsRolledFor, wave);
        news = n;
        newsWave = wave;
        newsLane = lane;
        newsLog.add("Wave " + wave + ": " + n.headline(wave));
        refresh();
        int cash = n.mods().cashFor(wave);
        if (cash > 0) game.addCash(cash, null);
    }

    /** Cards taken this run, in pick order (unmodifiable). */
    public List<PatchNote> getActive() { return Collections.unmodifiableList(active); }

    /** The wave the {@code i}-th taken card was drafted before. */
    public int getPickedBefore(int i) { return pickedBefore.get(i); }

    /** "1.3" after three picks: the run's patch version. */
    public String getVersion() { return "1." + active.size(); }

    // ------------------------------------------------------------------ news
    private void rollNews(int wave) {
        newsRolledFor = wave;
        boolean boss = game.getDifficulty().shape(WaveData.get(wave), game.getSeed()).containsBoss();
        BreakingNews.Roll r = BreakingNews.roll(game.getSeed(), wave, boss, game.getMap().getRoutes().size());
        if (r == null) return;
        news = r.news;
        newsWave = wave;
        newsLane = r.lane;
        newsLog.add("Wave " + wave + ": " + news.headline(wave));
        refresh();
        int cash = news.mods().cashFor(wave);
        if (cash > 0) game.addCash(cash, null);
    }

    /** The news event announced for the next / current wave, or null. */
    public BreakingNews getNews() { return news; }

    /** The wave the current news applies to. */
    public int getNewsWave() { return newsWave; }

    /** The lane a Server Outage closed, or -1. */
    public int getNewsLane() { return news != null && news.mods().has(Knob.CLOSE_LANE) ? newsLane : -1; }

    /** Every headline of the run so far, oldest first (unmodifiable). */
    public List<String> getNewsLog() { return Collections.unmodifiableList(newsLog); }

    // ------------------------------------------------------------------ game hooks
    /** Called by the game when a wave starts: drops stale news and applies wave-start effects (Solar Flare). */
    public void onWaveStarted(int wave) {
        if (!enabled) return;
        if (news != null && newsWave != wave) { news = null; refresh(); }
        if (news != null && news.mods().has(Knob.REFRESH_ABILITIES)) {
            for (Tower t : game.getTowerManager().getTowers()) if (t.getAbility() != null) t.resetAbilityCooldown();
        }
    }

    /**
     * Called by the game after a wave's bonus is paid: integrity per wave, interest, the wave's news expires, and the
     * next wave is prepared (its draft opens and its news is announced).
     */
    public void onWaveCompleted(int wave) {
        if (!enabled) return;
        int lives = (int) current.get(Knob.LIVES_PER_WAVE);
        if (lives > 0) game.addLives(lives);
        lastInterest = 0;
        double rate = current.get(Knob.INTEREST_RATE);
        if (rate > 0) {
            double interest = Math.floor(Math.max(0, game.getCash()) * rate);
            double cap = current.get(Knob.INTEREST_CAP);
            if (cap > 0) interest = Math.min(interest, cap);
            if (interest > 0) { game.addCash(interest, null); lastInterest = interest; }
        }
        if (news != null && newsWave == wave) { news = null; refresh(); }
        if (wave < WaveData.WAVE_COUNT) prepareFor(wave + 1);
    }

    /** Interest paid at the last wave clear (0 without Compute Futures). */
    public double getLastInterest() { return lastInterest; }

    /**
     * The wave as it will spawn: more enemies (Hype Cycle), denser spawns (Distributed Training) and Camo for all
     * (Viral Meme) are applied to non-boss groups. Returns {@code def} itself when nothing applies; never modifies it.
     */
    public WaveDef shapeWave(WaveDef def) {
        double count = current.get(Knob.ENEMY_COUNT), gap = current.get(Knob.SPAWN_GAP);
        boolean camo = current.has(Knob.ALL_CAMO);
        if (count == 1 && gap == 1 && !camo) return def;
        List<SpawnGroup> out = new ArrayList<>();
        for (SpawnGroup g : def.groups) {
            if (g.type.isBoss()) { out.add(g); continue; }
            int n = Math.max(1, (int) Math.round(g.count * count));
            double interval = g.interval * gap / (1 + 0.5 * (count - 1));   // like Difficulty: extra spawns do not stretch the wave
            EnumSet<Modifier> mods = EnumSet.copyOf(g.modifiers);
            if (camo) mods.add(Modifier.CAMO);
            out.add(new SpawnGroup(g.type, n, mods, interval, g.startDelay, g.route));
        }
        return new WaveDef(def.number, def.note, out.toArray(new SpawnGroup[0]));
    }

    /** Tower attack-rate multiplier. */
    public double fireRate() { return fireRate; }

    /** Tower range multiplier. */
    public double range() { return range; }

    /** Damage multiplier for a hit on {@code e} (all damage, boss / non-boss, modified / plain). */
    public double damageAgainst(Enemy e) {
        if (!damageActive) return 1;
        double m = damage * (e.isBoss() ? bossDamage : nonBossDamage);
        if (eliteDamage != 1 || plainDamage != 1) m *= e.getModifiers().isEmpty() ? plainDamage : eliteDamage;
        return m;
    }

    /** Ability cooldown length multiplier. */
    public double abilityCooldown() { return current.get(Knob.ABILITY_COOLDOWN); }

    /** Enemy HP multiplier for spawns. */
    public double enemyHp() { return current.get(Knob.ENEMY_HP); }

    /** Enemy speed multiplier for spawns. */
    public double enemySpeed() { return current.get(Knob.ENEMY_SPEED); }

    /** Kill reward multiplier. */
    public double killIncome() { return current.get(Knob.KILL_INCOME); }

    /** End-of-wave bonus multiplier. */
    public double waveBonus() { return current.get(Knob.WAVE_BONUS); }

    /** Lives a leak worth {@code lives} actually costs (never below 1 for a real leak). */
    public int leakLives(int lives) {
        double m = current.get(Knob.LEAK_LIVES);
        if (m == 1 || lives <= 0) return lives;
        return Math.max(1, (int) Math.round(lives * m));
    }

    /** The lane closed for this wave on a map with {@code routes} lanes, or -1 (Server Outage). */
    public int closedRoute(int routes) {
        if (routes < 2 || news == null || !news.mods().has(Knob.CLOSE_LANE)) return -1;
        return Math.floorMod(newsLane, routes);
    }

    // ------------------------------------------------------------------ prices
    /** Price of placing a tower that lists at {@code list}. */
    public int towerPrice(int list) { return price(list, current.get(Knob.TOWER_COST)); }

    /** Price of an upgrade that lists at {@code list}. */
    public int upgradePrice(int list) { return price(list, current.get(Knob.UPGRADE_COST)); }

    /** Price of an ability unlock that lists at {@code list}. */
    public int abilityUnlockPrice(int list) { return price(list, current.get(Knob.ABILITY_UNLOCK_COST)); }

    /** Sell refund fraction given the base fraction (clamped to 0..{@link #MAX_SELL_FRACTION}). */
    public double sellFraction(double base) {
        double add = current.get(Knob.SELL_REFUND);
        return add == 0 ? base : Math.max(0, Math.min(MAX_SELL_FRACTION, base + add));
    }

    /** The tower-price multiplier (the shop rebuilds its cards when it changes). */
    public double towerCostMultiplier() { return current.get(Knob.TOWER_COST); }

    private static int price(int list, double mult) {
        if (mult == 1 || list <= 0) return list;
        return (int) (Math.round(list * mult / PRICE_STEP) * PRICE_STEP);
    }

    /** Records a placement paid at {@code paid}; Data Drought then gives the first upgrade free. */
    public void onTowerPlaced(Tower t, int paid) {
        note(t, t.getDef().baseCost - paid);
        if (enabled && current.has(Knob.FREE_FIRST_UPGRADE) && !t.getType().isHero() && !t.isTemporary() && t.canUpgrade()) {
            int list = t.nextUpgrade().cost;
            t.applyUpgrade(game);
            game.getTowerManager().recomputeAuras();
            note(t, list);
            freeUpgrades++;
            game.emitText(t.getPosition(), "FREE UPGRADE", 0x3bff8a);
        }
    }

    /** Records an upgrade or ability unlock that lists at {@code list} and was paid at {@code paid}. */
    public void onPurchase(Tower t, int list, int paid) { note(t, list - paid); }

    /** Forgets a sold tower. */
    public void onTowerSold(Tower t) { unpaid.remove(t.getId()); }

    /** List price of everything on the tower that the player did not pay for (negative after surcharges). */
    public int unpaidOn(Tower t) {
        Integer v = unpaid.get(t.getId());
        return v == null ? 0 : v;
    }

    /** Free first upgrades granted so far (Data Drought). */
    public int getFreeUpgrades() { return freeUpgrades; }

    private void note(Tower t, int delta) { if (delta != 0) unpaid.merge(t.getId(), delta, Integer::sum); }

    // ------------------------------------------------------------------ state
    /** Everything currently applied: the taken cards plus the active news event (neutral when disabled). */
    public Mods getCurrent() { return current; }

    private void refresh() {
        current = !enabled ? Mods.NONE : (news == null ? cards : cards.combine(news.mods())).clamped();   // stacking caps (Knob bounds)
        fireRate = current.get(Knob.FIRE_RATE);
        range = current.get(Knob.RANGE);
        damage = current.get(Knob.DAMAGE);
        bossDamage = current.get(Knob.BOSS_DAMAGE);
        nonBossDamage = current.get(Knob.NON_BOSS_DAMAGE);
        eliteDamage = current.get(Knob.ELITE_DAMAGE);
        plainDamage = current.get(Knob.PLAIN_DAMAGE);
        damageActive = damage != 1 || bossDamage != 1 || nonBossDamage != 1 || eliteDamage != 1 || plainDamage != 1;
    }

    /** Seed for a derived stream: (game seed, wave, purpose) scrambled together; {@link Rng} scrambles it further. */
    static long mix(long seed, int wave, long salt) {
        long h = seed * 0x9E3779B97F4A7C15L + wave * 0xC2B2AE3D27D4EB4FL + salt;
        h ^= h >>> 31;
        return h * 0xBF58476D1CE4E5B9L;
    }
}
