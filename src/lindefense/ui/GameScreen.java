package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import acm.graphics.GLine;
import acm.graphics.GRect;
import java.awt.Color;
import java.awt.Font;
import java.awt.event.KeyEvent;
import java.util.ArrayList;
import java.util.List;
import lindefense.enemy.Enemy;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerType;

/**
 * The in-game screen: composes the world view, HUD and side panel, routes
 * mouse/keyboard input (in logical coordinates) to game actions, and shows the
 * pause / victory / defeat overlays.
 */
public final class GameScreen extends GCompound {
    private static final long serialVersionUID = 1L;

    private final LindefenseProgram app;
    private final Game game;
    private final WorldView world;
    private final HudPanel hud;
    private final SidePanel side;
    /** Reverse mode ("Adversarial Training"): the attacker's spawn panel replaces the shop; null in the normal game. */
    private final AttackPanel attack;
    private final BossDock dock;
    private final AbilityBar abilities;
    /** PATCH NOTES / BREAKING NEWS strip under the top bar (hidden while run variance is off). */
    private final RunStrip strip;
    /** Draft state when the overlay was last built, and whether the draft overlay is the one showing. */
    private boolean draftSeen, draftOpen;
    private Tower targetingTower;
    private final GCompound overlay = new GCompound();
    private final List<UIButton> overlayButtons = new ArrayList<>();
    private Cyber.GlitchText overlayTitle;
    private double glitchTimer;
    private double dockShown;
    private boolean helpShown;
    private boolean heroStoreShown;
    private String heroStoreKey = "";
    /** Live parts of the open Hero Store, updated in place every frame so a cash change never rebuilds the overlay. */
    private GLabel heroStoreCash;
    private double heroStoreCashRight;
    private UIButton heroStoreNeedButton;
    private int heroStoreNeedPrice;
    private String heroStoreNotice;
    /** Hero Store: which hero's detail panel is open (the grid has 17 tiles). */
    private TowerType heroStoreSelection = TowerType.heroes()[0];

    private TowerType placing;
    private Tower selectedTower;
    private Enemy selectedEnemy;
    private Vec mouseWorld;
    private double mouseLx, mouseLy;
    private Game.State shownState = Game.State.PLAYING;
    private boolean pauseShown;
    private double fxTimer;
    private final lindefense.audio.MusicDirector musicDirector = new lindefense.audio.MusicDirector();   // AUDIO HOOK
    private double musicTimer;
    private AudioToggle[] pauseToggles;
    private Slider[] pauseSliders;   // AUDIO: pause-menu volume sliders beside the toggles
    /** Pending in-overlay confirmation of the pause menu (RESTART / QUIT LEVEL). */
    private enum Confirm { NONE, RESTART, QUIT }
    private Confirm menuConfirm = Confirm.NONE;

    private TutorialGuide tutorial;

    public GameScreen(LindefenseProgram app, Game game) { this(app, game, false); }

    /** {@code tutorial} adds the guided-tutorial card (see {@link TutorialScript}). */
    public GameScreen(LindefenseProgram app, Game game, boolean tutorial) {
        this.app = app;
        this.game = game;
        add(Ui.rect(0, 0, Ui.W, Ui.H, Ui.BG, Ui.BG));
        buildBackdrop();
        world = new WorldView(this);
        dock = new BossDock(game);
        hud = new HudPanel(this);
        side = new SidePanel(this);
        attack = game.isReverse() ? new AttackPanel(this) : null;   // REVERSE HOOK
        abilities = new AbilityBar(this);
        strip = new RunStrip(this);
        add(world);
        add(dock);
        add(hud);
        add(abilities);
        add(attack != null ? attack : side);   // REVERSE HOOK
        buildBrackets();
        add(strip);
        if (tutorial) { this.tutorial = new TutorialGuide(new TutorialScript(game)); add(this.tutorial); }
        add(overlay);
    }

    /** The running tutorial's script, or null outside the tutorial. */
    public TutorialScript getTutorial() { return tutorial == null ? null : tutorial.getScript(); }

    /** Faint grid behind the (possibly shrunken) playfield, visible in the margins while the boss dock is open. */
    private void buildBackdrop() {
        for (int x = 0; x <= Ui.WORLD_W; x += 40) { GLine l = new GLine(x + 0.5, Ui.WORLD_Y, x + 0.5, Ui.BOTTOM_Y); l.setColor(Cyber.alpha(Cyber.CYAN, 14)); add(l); }
        for (int y = Ui.WORLD_Y; y <= Ui.BOTTOM_Y; y += 40) { GLine l = new GLine(0, y + 0.5, Ui.WORLD_W, y + 0.5); l.setColor(Cyber.alpha(Cyber.CYAN, 14)); add(l); }
    }

    /** HUD corner brackets framing the playfield. */
    private void buildBrackets() {
        double len = 22, in = 3;
        double x0 = Ui.WORLD_X + in, y0 = Ui.WORLD_Y + in + 1, x1 = Ui.WORLD_X + Ui.WORLD_W - in, y1 = Ui.BOTTOM_Y - in - 1;
        double[][] c = { { x0, y0, 1, 1 }, { x1, y0, -1, 1 }, { x0, y1, 1, -1 }, { x1, y1, -1, -1 } };
        Color col = Cyber.alpha(Cyber.CYAN, 150);
        for (double[] k : c) {
            GLine a = new GLine(k[0], k[1], k[0] + len * k[2], k[1]);
            GLine b = new GLine(k[0], k[1], k[0], k[1] + len * k[3]);
            a.setColor(col); b.setColor(col);
            add(a); add(b);
        }
    }

    public Game getGame() { return game; }
    public TowerType getPlacing() { return placing; }
    public Tower getSelectedTower() { return selectedTower; }
    public Enemy getSelectedEnemy() { return selectedEnemy; }
    public Vec getMouseWorld() { return mouseWorld; }
    /** Tower whose targeted ability is waiting for a map click (targeting mode), or null. */
    public Tower getTargetingTower() { return targetingTower; }
    /** Last mouse position in logical coordinates {x, y}. */
    public double[] getMouseLogical() { return new double[] { mouseLx, mouseLy }; }
    public SidePanel getSidePanel() { return side; }
    /** B key / ALL button: switch the shop between one faction and all towers. */
    public void toggleShopAll() { if (!game.isReverse()) side.toggleAll(); }

    // ------------------------------------------------------------------ actions
    public void beginPlacing(TowerType t) {
        if (t != null && game.isReverse()) return;   // REVERSE HOOK: the AI builds, the player only inspects
        placing = t;
        if (t != null) { selectedTower = null; selectedEnemy = null; targetingTower = null; }
        side.requestRebuild();
    }

    public void selectTower(Tower t) {
        selectedTower = t;
        if (t != null) { placing = null; selectedEnemy = null; }
        side.requestRebuild();
    }

    public void selectEnemy(Enemy e) {
        selectedEnemy = e;
        if (e != null) { placing = null; selectedTower = null; }
        side.requestRebuild();
    }

    public void startWave() { if (!game.isReverse()) game.startNextWave(); }
    public void setSpeed(int s) { game.setSpeed(s); game.setPaused(false); }
    public void togglePause() { game.togglePause(); }
    public void toggleAuto() { if (!game.isReverse()) game.getWaveManager().setAutoStart(!game.getWaveManager().isAutoStart()); }
    public void backToMenu() { app.showMenu(); }

    /**
     * Esc toggles the pause menu. An overlay drawn on top of the game (HELP, then the pause menu itself, then the Hero
     * Store) closes first; with none of them showing, Esc opens the pause menu, even while placing a tower or aiming an
     * ability (right-click still cancels those). Does nothing on the victory / defeat screen.
     */
    public void escapePressed() {
        if (game.getState() != Game.State.PLAYING) return;
        if (helpShown) toggleHelp();
        else if (isMenuOpen()) resumeGame();
        else if (heroStoreShown) toggleHeroStore();
        else openMenu();
    }

    /**
     * MENU button / Esc: pauses the game and opens the pause menu (resume, restart, sound, music, quit level, main menu).
     * A half-finished tower placement or ability aim is dropped so nothing is still armed when the game resumes.
     */
    public void openMenu() {
        if (game.getState() != Game.State.PLAYING) return;
        if (placing != null) beginPlacing(null);
        cancelTargeting();
        helpShown = false;
        menuConfirm = Confirm.NONE;
        game.setPaused(true);
        buildOverlay();
    }

    /** True while the pause menu overlay is showing. */
    public boolean isMenuOpen() { return game.getState() == Game.State.PLAYING && game.isPaused(); }
    /** Logic of the confirmation step, exposed for tests: 0 none, 1 restart, 2 quit. */
    public int getPendingConfirm() { return menuConfirm.ordinal(); }

    private void setConfirm(Confirm c) { menuConfirm = c; buildOverlay(); }
    private void resumeGame() { menuConfirm = Confirm.NONE; game.setPaused(false); buildOverlay(); }

    /** Opens / closes the full controls and modifier reference overlay (H key or the HELP button). */
    public void toggleHelp() { helpShown = !helpShown; if (helpShown) heroStoreShown = false; buildOverlay(); }

    // ---- Hero Store
    /** Opens / closes the Hero Store overlay (HEROES button or K). The game keeps running underneath. */
    public void toggleHeroStore() {
        if (game.getState() != Game.State.PLAYING || game.isReverse()) return;
        heroStoreShown = !heroStoreShown;
        if (heroStoreShown) { helpShown = false; heroStoreNotice = null; }
        heroStoreKey = "";
        buildOverlay();
    }
    public boolean isHeroStoreOpen() { return heroStoreShown; }

    /** Hero Store BUY button: spends the unlock price and shows the confirmation. */
    public void buyHero(TowerType t) {
        if (game.purchaseHero(t)) {
            heroStoreNotice = t.displayName + " unlocked permanently! Press DEPLOY to place on the map.";
            hud.flashBanner(t.displayName.toUpperCase() + " UNLOCKED", Ui.c(t.primaryRgb), 2.5);
        } else {
            String why = game.heroPurchaseProblem(t);
            heroStoreNotice = t.displayName + ": " + (why == null ? "purchase failed" : why.toLowerCase());
        }
        heroStoreKey = "";
        buildOverlay();
    }

    /** Hero Store DEPLOY button: closes the store and enters placement mode for the hero. */
    public void deployHero(TowerType t) {
        if (game.getTowerManager().heroProblem(t) != null) return;
        heroStoreShown = false;
        buildOverlay();
        beginPlacing(t);
    }

    /** Changes whenever a card's button or badge would change (cash crossing a price, unlock, deploy). */
    private String heroStoreStateKey() {
        StringBuilder sb = new StringBuilder();
        for (TowerType t : TowerType.heroes()) {
            sb.append(game.isHeroUnlocked(t) ? 'U' : game.getCash() >= lindefense.tower.Shop.unlockPriceOf(t) ? 'A' : 'L');
            sb.append(game.isHeroDeployed(t) ? 'D' : '-');
        }
        // no exact cash here: the credits readout and "NEED $X MORE" update in place (refreshHeroStoreLive), and a
        // rebuild on every cash change made the whole store flash and replay its glitch-in
        return sb.append(heroStoreSelection).toString();
    }

    private String heroStoreCashText() { return "CREDITS  " + (game.isAdmin() ? "ADMIN \u221e" : Ui.money(game.getCash())); }

    /** Updates the open Hero Store's credits readout and NEED-MORE button text without rebuilding it. */
    private void refreshHeroStoreLive() {
        if (heroStoreCash != null) {
            String txt = heroStoreCashText();
            if (!txt.equals(heroStoreCash.getLabel())) {
                heroStoreCash.setLabel(txt);
                heroStoreCash.setLocation(heroStoreCashRight - heroStoreCash.getWidth(), heroStoreCash.getY());
            }
        }
        if (heroStoreNeedButton != null) {
            String txt = "NEED " + Ui.money(Math.max(0, heroStoreNeedPrice - game.getCash())) + " MORE";
            if (!txt.equals(heroStoreNeedButton.getText())) heroStoreNeedButton.setText(txt);
        }
    }

    /** U / the upgrade button: buys the next upgrade; on a maxed tower with a locked ability it buys the ability. */
    public void upgradeSelected() {
        if (selectedTower == null || game.isReverse()) return;
        if (selectedTower.canUpgrade()) game.upgradeTower(selectedTower);
        else if (selectedTower.isAbilityLocked()) unlockAbilitySelected();
        side.requestRebuild();
    }

    /** UNLOCK ABILITY button: buys the selected maxed tower's ability ($15,000); it is ready at once. */
    public void unlockAbilitySelected() {
        Tower t = selectedTower;
        if (t == null || !t.isAbilityLocked() || game.isReverse()) return;
        String name = t.getAbilityDef().name;
        if (game.unlockAbility(t)) abilities.showHint(name + " UNLOCKED  -  press A or click it in the ability bar", Cyber.GREEN, 3);
        else if (!t.canUnlockAbility()) abilities.showHint(name + ": buy every upgrade first", Cyber.RED, 2.5);
        else abilities.showHint(name + ": needs " + Ui.money(lindefense.tower.Shop.abilityUnlockCost(game)), Cyber.RED, 2.5);
        side.requestRebuild();
    }

    public void sellSelected() {
        if (selectedTower != null && !game.isReverse()) { game.sellTower(selectedTower); selectedTower = null; side.requestRebuild(); }
    }

    public void abilitySelected() {
        if (selectedTower != null) fireAbility(selectedTower);
    }

    // ---- abilities: click-to-fire, targeting mode, refusal messages
    /** Fires a tower's ability; a targeted one enters targeting mode instead. Refusals are shown above the ability bar. */
    public void fireAbility(Tower t) {
        if (t == null || !t.isAlive() || t.getAbility() == null) return;
        if (game.getState() != Game.State.PLAYING) return;
        if (game.isReverse()) { abilities.showHint("The defender AI fires its own abilities", Cyber.MAGENTA, 2); return; }   // REVERSE HOOK
        String why = abilityRefusal(t);
        if (why != null) { abilities.showHint(t.getAbility().name + ": " + why, Cyber.RED, 2.5); return; }
        if (t.getAbility().needsTarget) {
            targetingTower = t;
            placing = null;
            abilities.clearHint();
            side.requestRebuild();
            return;
        }
        if (game.activateAbility(t)) abilities.showHint(t.getAbility().name + "!", Cyber.GREEN, 1.2);
        else abilities.showHint(t.getAbility().name + ": no enemy in range", Cyber.RED, 2.5);
        side.requestRebuild();
    }

    /** Why the ability cannot be used right now (null if it can be tried). */
    private String abilityRefusal(Tower t) {
        if (t.isSurveilled()) return "offline (surveillance)";
        if (t.isOffline()) return "offline (" + (t.isHijacked() ? "hijacked" : t.getIntrusion().isBlinded() ? "blinded" : "disabled") + ")";   // PROMPT INJECTION
        if (!t.isAbilityReady()) return String.format("recharging (%.0fs)", Math.ceil(t.getAbilityCooldownRemaining()));
        return null;
    }

    /** Casts the armed targeted ability at a world point; stays armed (with a message) if the sim refuses. */
    private void castTargeted(Vec w) {
        Tower t = targetingTower;
        if (t == null) return;
        if (!t.isAlive()) { cancelTargeting(); return; }
        if (game.activateAbility(t, w)) {
            abilities.showHint(t.getAbility().name + "!", Cyber.GREEN, 1.2);
            targetingTower = null;
            side.requestRebuild();
        } else {
            String why = abilityRefusal(t);
            abilities.showHint(t.getAbility().name + ": " + (why != null ? why : "no valid track point there"), Cyber.RED, 2.5);
            if (why != null) cancelTargeting();
        }
    }

    public void cancelTargeting() {
        if (targetingTower == null) return;
        targetingTower = null;
        abilities.clearHint();
        side.requestRebuild();
    }

    public void cycleTargeting(int dir) {
        if (selectedTower == null || game.isReverse()) return;
        selectedTower.cycleTargeting(dir);
        side.requestRebuild();
    }

    public void flashBanner(String text, Color col, double seconds) { hud.flashBanner(text, col, seconds); }

    // ---- PATCH NOTES draft
    /** True while the patch-notes draft overlay is showing (the next wave waits for a pick). */
    public boolean isDraftOpen() { return draftOpen; }

    /** Ships offered card {@code index} (draft overlay click, or keys 1-3). */
    public void pickPatchNote(int index) {
        lindefense.variance.RunVariance v = game.getVariance();
        java.util.List<lindefense.variance.PatchNote> offer = v.getOffer();
        if (index < 0 || index >= offer.size()) return;
        lindefense.variance.PatchNote p = offer.get(index);
        if (!v.pick(index)) return;
        hud.flashBanner("PATCH " + v.getVersion() + " SHIPPED: " + p.title.toUpperCase(), PatchNotesView.accent(p.category), 2.6);
        buildOverlay();
        side.requestRebuild();
    }

    // ------------------------------------------------------------------ input
    private List<UIButton> allButtons() {
        List<UIButton> all = new ArrayList<>(overlayButtons);
        if (tutorial != null && overlayButtons.isEmpty()) all.addAll(tutorial.getButtons());
        all.addAll(hud.getButtons());
        all.addAll(attack != null ? attack.getButtons() : side.getButtons());   // REVERSE HOOK
        all.addAll(abilities.getButtons());
        return all;
    }

    public void mousePressed(double lx, double ly, boolean rightButton) {
        mouseMoved(lx, ly);
        if (!rightButton && Slider.pressAny(lx, ly, pauseSliders)) return;   // AUDIO: volume sliders
        if (!overlayButtons.isEmpty()) {
            for (UIButton b : overlayButtons) if (b.hit(lx, ly)) { b.click(); return; }
            if (game.getState() != Game.State.PLAYING || helpShown || heroStoreShown || game.isPaused() || draftOpen) return;
        }
        if (rightButton) {
            if (targetingTower != null) { cancelTargeting(); return; }
            if (placing != null) beginPlacing(null);
            else { selectTower(null); selectEnemy(null); }
            return;
        }
        for (UIButton b : allButtons()) {
            if (b.hit(lx, ly)) { if (b.click()) return; }
        }
        if (lx >= Ui.PANEL_X) return;
        if (tutorial != null && tutorial.covers(lx, ly)) return;
        Vec w = toWorld(lx, ly);
        if (w == null) return;
        if (targetingTower != null) { castTargeted(w); return; }
        if (placing != null) {
            Tower t = game.placeTower(placing, w);
            if (t != null) {
                // keep placing the same type if affordable, otherwise select the new tower
                if (game.getCash() < lindefense.tower.Shop.priceOf(game, t.getType())) { placing = null; selectTower(t); }
                side.requestRebuild();
            }
            return;
        }
        Tower t = game.getTowerManager().towerAt(w);
        if (t != null) { selectTower(t); return; }
        Enemy e = world.pickEnemy(w);
        if (e != null) { selectEnemy(e); return; }
        selectTower(null);
        selectEnemy(null);
    }

    public void mouseMoved(double lx, double ly) {
        mouseLx = lx; mouseLy = ly;
        mouseWorld = toWorld(lx, ly);
        for (UIButton b : allButtons()) b.setHover(b.hit(lx, ly));
        Slider.hoverAll(lx, ly, pauseSliders);
    }

    /** Mouse drag (logical coordinates): moves a grabbed pause-menu volume slider. */
    public void mouseDragged(double lx, double ly) { Slider.dragAll(lx, ly, pauseSliders); }

    /** Mouse release: ends a volume-slider drag (the level is saved). */
    public void mouseReleased() { Slider.releaseAll(pauseSliders); }

    private Vec toWorld(double lx, double ly) { return world.toWorld(lx, ly); }

    /** Logical point {x, y} where world point {@code w} is drawn (tools and the scripted demo click through it). */
    public double[] worldToLogical(Vec w) { return world.toLogical(w); }

    /** Re-applies hover to every button for the last mouse position (after panels rebuild). */
    public void refreshHover() { for (UIButton b : allButtons()) b.setHover(b.hit(mouseLx, mouseLy)); }

    public void keyPressed(KeyEvent e) {
        if (draftOpen && !game.isPaused()) {   // PATCH NOTES draft: 1 / 2 / 3 ship a card; Esc, H and P still work
            int k = e.getKeyCode();
            if (k >= KeyEvent.VK_1 && k <= KeyEvent.VK_9) { pickPatchNote(k - KeyEvent.VK_1); return; }
            if (k != KeyEvent.VK_ESCAPE && k != KeyEvent.VK_H && k != KeyEvent.VK_P) return;
        }
        if (attack != null && game.getState() == Game.State.PLAYING && !game.isPaused() && !helpShown && attack.keyPressed(e)) return;   // REVERSE HOOK: attacker keys
        switch (e.getKeyCode()) {
            case KeyEvent.VK_SPACE: startWave(); break;
            case KeyEvent.VK_1: setSpeed(1); break;
            case KeyEvent.VK_2: setSpeed(2); break;
            case KeyEvent.VK_3: setSpeed(3); break;
            case KeyEvent.VK_P: togglePause(); break;
            case KeyEvent.VK_H: toggleHelp(); break;
            case KeyEvent.VK_K: toggleHeroStore(); break;
            case KeyEvent.VK_ESCAPE: escapePressed(); break;
            case KeyEvent.VK_U: upgradeSelected(); break;
            case KeyEvent.VK_S: sellSelected(); break;
            case KeyEvent.VK_A: abilitySelected(); break;
            case KeyEvent.VK_T: cycleTargeting(1); break;
            case KeyEvent.VK_B: toggleShopAll(); break;
            // M (music) and N (sound) are handled globally in LindefenseProgram.keyPressed
            default: break;
        }
    }

    // ------------------------------------------------------------------ frame
    /**
     * Most fixed simulation steps ({@link Game#DT}) run for one rendered frame. At 60 fps a frame needs 1-3 steps
     * (1x-3x speed); the cap leaves room to catch up after a hiccup, but when frames stay slow the game runs slower
     * than real time instead of spending ever longer frames on simulation (the "spiral of death" at 3x).
     */
    public static final int MAX_SIM_STEPS_PER_FRAME = 8;

    /**
     * One rendered frame: advances the simulation (fixed steps, capped by {@link #MAX_SIM_STEPS_PER_FRAME}, the
     * remainder of a step carried over by {@link Game#advance}) and then updates every view from the new state.
     */
    public void frame(double realDt) {
        game.advance(Math.min(realDt, MAX_SIM_STEPS_PER_FRAME * Game.DT / Math.max(1, game.getSpeed())));
        if (selectedTower != null && !selectedTower.isAlive()) selectTower(null);
        if (selectedEnemy != null && (!selectedEnemy.isAlive() && game.getTime() - selectedEnemy.getLastHitTime() > 3)) selectEnemy(null);
        dock.update(realDt);
        double target = dock.getHeight();
        dockShown += (target - dockShown) * Math.min(1, realDt * 9);
        if (Math.abs(target - dockShown) < 0.3) dockShown = target;
        double stripH = strip.height();   // PATCH NOTES strip sits under the top bar; the boss dock opens below it
        dock.setLocation(0, Ui.WORLD_Y + stripH);
        world.setDock(dockShown + stripH);
        mouseWorld = toWorld(mouseLx, mouseLy);
        world.update(realDt);
        hud.update(realDt);
        strip.update(realDt);
        if (attack != null) attack.update(realDt); else side.update(realDt);   // REVERSE HOOK
        if (targetingTower != null && !targetingTower.isAlive()) cancelTargeting();
        abilities.update(realDt);
        if (tutorial != null) tutorial.update(realDt);
        for (UIButton b : allButtons()) b.animate(realDt);
        if (overlayTitle != null) {
            glitchTimer -= realDt;
            if (glitchTimer <= 0) { overlayTitle.burst(0.25); glitchTimer = 2.2 + Math.random() * 2.5; }
            overlayTitle.animate(realDt);
        }
        if (game.isVictorySequenceActive()) victoryFireworks(realDt);
        updateMusic(realDt);
        if (pauseToggles != null) AudioToggle.syncAll(pauseToggles);
        Slider.frameAll(realDt, pauseSliders);
        Game.State st = game.getState();
        if (st != shownState) {
            shownState = st;
            buildOverlay();
            // AUDIO HOOK: end-of-game stingers
            if (game.isReverse()) lindefense.audio.AudioManager.sfx(game.getReverse().attackerWon() ? lindefense.audio.Sfx.VICTORY : lindefense.audio.Sfx.DEFEAT);   // REVERSE HOOK
            else if (st == Game.State.VICTORY) lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.VICTORY);
            else if (st == Game.State.DEFEAT) lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.DEFEAT);
        }
        else if (st == Game.State.PLAYING && game.isPaused() != pauseShown) buildOverlay();
        else if (st == Game.State.PLAYING && game.getVariance().isDraftPending() != draftSeen) buildOverlay();   // PATCH NOTES
        else if (heroStoreShown && !heroStoreStateKey().equals(heroStoreKey)) buildOverlay();
        if (heroStoreShown) refreshHeroStoreLive();
    }

    private Game.State shownMusicState;

    /** AUDIO HOOK: picks the music track from the game situation about 4 times a second. */
    private void updateMusic(double dt) {
        lindefense.audio.AudioManager am = lindefense.audio.AudioManager.get();
        if (am == null) return;
        musicTimer -= dt;
        Game.State st = game.getState();
        if (musicTimer > 0 && st == shownMusicState) return;
        musicTimer = 0.25;
        shownMusicState = st;
        boolean palantir = false, boss = false;
        for (Enemy e : game.getEnemyManager().getEnemies()) {
            if (!e.getType().isBoss() || !e.isAlive()) continue;
            if (e.getType() == lindefense.enemy.EnemyType.PALANTIR) palantir = true; else boss = true;
        }
        boolean won = st == Game.State.VICTORY, lost = st == Game.State.DEFEAT;
        int wave = game.getWave();
        if (game.isReverse()) { won = lost; lost = st == Game.State.VICTORY; wave = game.getReverse().equivalentWave(); }   // REVERSE HOOK: the attacker's view
        am.setMusic(musicDirector.choose(won, lost, wave,
            game.getDifficulty() == lindefense.sim.Difficulty.ONN, palantir, boss, game.getTime()));
    }

    private void victoryFireworks(double dt) {
        fxTimer -= dt;
        if (fxTimer > 0) return;
        fxTimer = 0.12;
        Vec c = game.getPalantir() != null ? game.getPalantir().getPosition() : new Vec(600, 450);
        double ang = game.getRng().range(0, Math.PI * 2), d = game.getRng().range(20, 260);
        Vec p = new Vec(c.x + Math.cos(ang) * d, c.y + Math.sin(ang) * d);
        int[] cols = { 0xffe94a, 0xff3b4e, 0x3bff8a, 0x00f0ff, 0xff2bd6 };
        game.getEvents().add(lindefense.combat.VisualEvent.explosion(p, game.getRng().range(30, 90), cols[game.getRng().nextInt(cols.length)]));
    }

    private void buildOverlay() {
        overlay.removeAll();
        heroStoreCash = null;
        heroStoreNeedButton = null;
        overlayButtons.clear();
        overlayTitle = null;
        pauseToggles = null;
        Slider.releaseAll(pauseSliders);   // a rebuild mid-drag still saves the level
        pauseSliders = null;
        pauseShown = game.isPaused();
        draftSeen = game.getVariance().isDraftPending();
        draftOpen = false;
        Game.State st = game.getState();
        if (st != Game.State.PLAYING) heroStoreShown = false;
        if (helpShown && st == Game.State.PLAYING) { buildHelpOverlay(); return; }
        if (draftSeen && st == Game.State.PLAYING && !game.isPaused()) { buildDraftOverlay(); return; }
        if (heroStoreShown && st == Game.State.PLAYING && !game.isPaused()) { buildHeroStoreOverlay(); return; }
        if (st == Game.State.PLAYING && !game.isPaused()) { menuConfirm = Confirm.NONE; return; }
        if (st == Game.State.PLAYING) { buildMenuOverlay(); return; }
        boolean ended = st != Game.State.PLAYING;
        overlay.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, ended ? 190 : 140), Ui.c(0x000000, 0)));
        double cx = Ui.WORLD_X + Ui.WORLD_W / 2.0, cy = Ui.WORLD_Y + Ui.WORLD_H / 2.0;
        String title, micro, sub; Color col;
        if (st == Game.State.VICTORY) {
            title = "VICTORY"; col = Cyber.YELLOW; micro = "// mission complete";
            sub = "Palantir has fallen. All " + lindefense.wave.WaveData.WAVE_COUNT + " waves survived on " + game.getMap().getName() + ".";
        } else if (st == Game.State.DEFEAT) {
            title = "DEFEAT"; col = Cyber.RED; micro = "// system breach";
            sub = "Your defenses were breached on wave " + game.getWave() + ".";
        } else {
            return;   // PLAYING is handled by buildMenuOverlay()
        }
        if (game.isReverse()) {   // REVERSE HOOK: the player is the attacker
            String[] rt = AttackPanel.endTexts(game);
            title = rt[0]; micro = rt[1]; sub = rt[2]; col = "win".equals(rt[3]) ? Cyber.YELLOW : Cyber.RED;
        }
        boolean notes = ended && game.getVariance().isEnabled();   // PATCH NOTES: the run's cards and a seed replay
        double pw = 720, ph = ended ? 404 + (notes ? 44 : 0) : 270;
        double px = cx - pw / 2, py = cy - ph / 2;
        overlay.add(new Cyber.Chamfer(px, py, pw, ph, 26).fill(new Color(6, 10, 24, 238)).border(col).glow(1.1).lineWidth(2).ticks(true));
        overlay.add(Ui.rect(px + 24, py + 12, 140, 3, Cyber.MAGENTA, Cyber.MAGENTA));
        GLabel m = Ui.label(Cyber.spaced(micro), 0, py + 44, Cyber.mono(Font.BOLD, 12), Cyber.alpha(col, 230));
        m.setLocation(cx - m.getWidth() / 2, py + 44);
        overlay.add(m);
        Cyber.GlitchText t = new Cyber.GlitchText(title, Cyber.display(Font.BOLD, 88), Cyber.lerp(col, Color.WHITE, 0.3));
        t.setLocation(cx - t.textWidth() / 2, py + 130);
        overlay.add(t);
        overlayTitle = t;
        t.burst(0.5);
        glitchTimer = 2.5;
        double sy = py + 166;
        for (String line : Ui.wrap(sub, Cyber.body(Font.PLAIN, 16), pw - 100)) {
            GLabel s = Ui.label(line, 0, sy, Cyber.body(Font.PLAIN, 16), Cyber.TEXT);
            s.setLocation(cx - s.getWidth() / 2, sy);
            overlay.add(s);
            sy += 22;
        }
        if (ended) {
            String[][] stats = {
                { "waves cleared", String.valueOf(game.getLastCompletedWave()), "" },
                { "hostiles purged", Cyber.commas(game.getEnemyManager().getTotalKilled()), "" },
                { "credits earned", Ui.money(game.getTotalCashEarned()), "y" },
                { "integrity left", String.valueOf(game.getLives()), "r" } };
            if (game.isReverse()) stats = AttackPanel.endStats(game);   // REVERSE HOOK
            double cw = 158, gap = 12, sx = cx - (4 * cw + 3 * gap) / 2, cyy = py + 214;
            for (int i = 0; i < 4; i++) {
                double x = sx + i * (cw + gap);
                Color ac = stats[i][2].equals("y") ? Cyber.YELLOW : stats[i][2].equals("r") ? Cyber.RED : Cyber.CYAN;
                overlay.add(new Cyber.Chamfer(x, cyy, cw, 58, 8).scan(false).fill(new Color(8, 14, 32, 235)).border(Cyber.alpha(ac, 170)));
                overlay.add(Ui.label(Cyber.spaced(stats[i][0]), x + 12, cyy + 19, Cyber.mono(Font.BOLD, 9), Cyber.alpha(ac, 210)));
                overlay.add(Ui.label(stats[i][1], x + 12, cyy + 45, Cyber.mono(Font.BOLD, 20), Cyber.TEXT));
            }
            // DIFFICULTY HOOK: show the Difficulty Growth mode on the end screen
            Font modeFont = Cyber.mono(Font.BOLD, 13);
            GLabel mode = Ui.label("MODE // " + DifficultySelector.display(game.getDifficulty(), modeFont)
                + "  " + game.getDifficulty().subtitle.toUpperCase() + "   //   " + PatchNotesView.seedText(game), 0, cyy + 86, modeFont, Cyber.MAGENTA);
            if (game.isReverse()) mode.setLabel("ADVERSARIAL TRAINING // " + DifficultySelector.display(game.getReverse().getLevel(), modeFont)
                + "  " + game.getReverse().getProfile().displayName.toUpperCase() + " AI");   // REVERSE HOOK
            mode.setLocation(cx - mode.getWidth() / 2, cyy + 86);
            overlay.add(mode);
            if (notes) PatchNotesView.chipRows(overlay, game.getVariance().getActive(), cx, cyy + 102, pw - 80);
            double bw = notes ? 212 : 240;
            UIButton again = new UIButton(notes ? cx - 326 : cx - 250, py + ph - 76, bw, 50, "PLAY AGAIN", Cyber.display(Font.BOLD, 22), () -> app.showMapSelect());
            again.setPrimary(true);
            if (notes) {
                UIButton replay = new UIButton(cx - 106, py + ph - 76, bw, 50, "REPLAY SEED", Cyber.display(Font.BOLD, 22), () -> app.replaySeed());
                replay.setAccent(Cyber.CYAN);
                overlay.add(replay); overlayButtons.add(replay);
            }
            UIButton menu = new UIButton(notes ? cx + 114 : cx + 10, py + ph - 76, bw, 50, "MAIN MENU", Cyber.display(Font.BOLD, 22), () -> app.showMenu());
            menu.setAccent(Cyber.MAGENTA);
            overlay.add(again); overlay.add(menu);
            overlayButtons.add(again); overlayButtons.add(menu);
        }
        refreshHover();
    }

    private UIButton menuButton(double x, double y, double w, double h, String text, Cyber.Kind icon, Color accent, Runnable r) {
        UIButton b = new UIButton(x, y, w, h, text, Cyber.display(Font.BOLD, 20), r);
        if (icon != null) b.setIcon(icon);
        if (accent != null) b.setAccent(accent);
        overlay.add(b);
        overlayButtons.add(b);
        return b;
    }

    /** PATCH NOTES draft: three cards over the playfield; the next wave waits until one is shipped. */
    private void buildDraftOverlay() {
        if (placing != null) beginPlacing(null);
        cancelTargeting();
        heroStoreShown = false;
        draftOpen = true;
        overlayTitle = PatchNotesView.buildDraft(overlay, overlayButtons, game, this::pickPatchNote);
        glitchTimer = 2.5;
        refreshHover();
    }

    /** The pause menu: RESUME, RESTART, SOUND EFFECTS and MUSIC (each toggle with its volume slider), QUIT LEVEL, MAIN MENU (or a Yes / No confirmation). */
    private void buildMenuOverlay() {
        overlay.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, 150), Ui.c(0x000000, 0)));
        double cx = Ui.WORLD_X + Ui.WORLD_W / 2.0, cy = Ui.WORLD_Y + Ui.WORLD_H / 2.0;
        boolean confirm = menuConfirm != Confirm.NONE;
        Color col = confirm ? Cyber.RED : Cyber.CYAN;
        double pw = 600, ph = confirm ? 320 : 520;
        double px = cx - pw / 2, py = cy - ph / 2;
        overlay.add(new Cyber.Chamfer(px, py, pw, ph, 26).fill(new Color(6, 10, 24, 238)).border(col).glow(1.1).lineWidth(2).ticks(true));
        overlay.add(Ui.rect(px + 24, py + 12, 140, 3, Cyber.MAGENTA, Cyber.MAGENTA));
        String micro = confirm ? "// confirm" : "// simulation halted";
        GLabel m = Ui.label(Cyber.spaced(micro), 0, py + 44, Cyber.mono(Font.BOLD, 12), Cyber.alpha(col, 230));
        m.setLocation(cx - m.getWidth() / 2, py + 44);
        overlay.add(m);
        String title = confirm ? (menuConfirm == Confirm.RESTART ? "RESTART?" : "QUIT LEVEL?") : "PAUSED";
        Cyber.GlitchText t = new Cyber.GlitchText(title, Cyber.display(Font.BOLD, confirm ? 56 : 64), Cyber.lerp(col, Color.WHITE, 0.3));
        t.setLocation(cx - t.textWidth() / 2, py + (confirm ? 114 : 118));
        overlay.add(t);
        overlayTitle = t;
        glitchTimer = 2.5;
        if (confirm) {
            String q = menuConfirm == Confirm.RESTART ? "Restart level? Progress will be lost." : "Quit level? Progress will be lost.";
            GLabel s = Ui.label(q, 0, py + 160, Cyber.body(Font.PLAIN, 17), Cyber.TEXT);
            s.setLocation(cx - s.getWidth() / 2, py + 160);
            overlay.add(s);
            Runnable yes = menuConfirm == Confirm.RESTART ? app::restartLevel : app::quitLevel;
            UIButton y = menuButton(cx - 260, py + ph - 90, 250, 54, "YES", Cyber.Kind.CHECK, Cyber.RED, yes);
            y.setPrimary(true);
            UIButton n = menuButton(cx + 10, py + ph - 90, 250, 54, "NO", null, Cyber.CYAN, () -> setConfirm(Confirm.NONE));
            refreshHover();
            return;
        }
        String seed = "   //   " + PatchNotesView.seedText(game) + (game.getVariance().isEnabled() ? "   //   PATCH " + game.getVariance().getVersion() : "");
        GLabel hint = Ui.label("P / Esc to resume" + seed, 0, py + 146, Cyber.mono(Font.BOLD, 12), Cyber.MUTED);
        hint.setLocation(cx - hint.getWidth() / 2, py + 146);
        overlay.add(hint);
        double bw = 500, bx = cx - bw / 2, by = py + 172, bh = 46, gap = 10, tw = 200;   // tw: audio toggle width, its slider fills the rest of the row
        UIButton resume = menuButton(bx, by, bw, bh, "RESUME", Cyber.Kind.PLAY, null, this::resumeGame);
        resume.setPrimary(true);
        menuButton(bx, by + (bh + gap), bw, bh, "RESTART", Cyber.Kind.AUTO, Cyber.YELLOW, () -> setConfirm(Confirm.RESTART));
        AudioToggle snd = AudioToggle.sound(bx, by + 2 * (bh + gap), tw, bh, "SOUND EFFECTS:");
        AudioToggle mus = AudioToggle.music(bx, by + 3 * (bh + gap), tw, bh, "MUSIC:");
        pauseToggles = new AudioToggle[] { snd, mus };
        for (AudioToggle at : pauseToggles) { overlay.add(at.getButton()); overlayButtons.add(at.getButton()); }
        pauseSliders = new Slider[] { AudioToggle.soundVolume(bx + tw + gap, by + 2 * (bh + gap), bw - tw - gap, bh, "VOL"),
            AudioToggle.musicVolume(bx + tw + gap, by + 3 * (bh + gap), bw - tw - gap, bh, "VOL") };
        for (Slider sl : pauseSliders) overlay.add(sl);
        menuButton(bx, by + 4 * (bh + gap), bw, bh, "QUIT LEVEL", Cyber.Kind.SKULL, Cyber.RED, () -> setConfirm(Confirm.QUIT));
        menuButton(bx, by + 5 * (bh + gap), bw, bh, "MAIN MENU", Cyber.Kind.MENU, Cyber.MAGENTA, this::backToMenu);
        AudioToggle.syncAll(pauseToggles);
        refreshHover();
    }

    /**
     * The Hero Store: a grid of all 17 heroes (sprite, name, price, lock status) beside a detail panel for the
     * selected one showing its role, base ability, current statistics and all three purchasable upgrades with their
     * names, prices and exactly what each changes. Buying only unlocks a hero; deploying is a separate action.
     */
    private void buildHeroStoreOverlay() {
        heroStoreKey = heroStoreStateKey();
        overlay.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, 200), Ui.c(0x000000, 0)));
        double pw = 1180, ph = 870, px = Ui.WORLD_X + (Ui.WORLD_W - pw) / 2, py = Ui.WORLD_Y + (Ui.WORLD_H - ph) / 2;
        overlay.add(new Cyber.Chamfer(px, py, pw, ph, 24).fill(new Color(6, 10, 24, 245)).border(Cyber.YELLOW).glow(1).lineWidth(2).ticks(true));
        overlay.add(Ui.label(Cyber.spaced("// permanent unlocks"), px + 30, py + 32, Cyber.mono(Font.BOLD, 12), Cyber.alpha(Cyber.MAGENTA, 230)));
        overlay.add(Ui.label("HERO STORE", px + 30, py + 68, Cyber.display(Font.BOLD, 34), Cyber.TEXT));
        GLabel cash = Ui.label(heroStoreCashText(), 0, py + 62, Cyber.mono(Font.BOLD, 18), Cyber.YELLOW);
        heroStoreCashRight = px + pw - 30 - 130 - 20;
        cash.setLocation(heroStoreCashRight - cash.getWidth(), py + 62);
        overlay.add(cash);
        heroStoreCash = cash;
        heroStoreNeedButton = null;
        UIButton close = new UIButton(px + pw - 30 - 130, py + 38, 130, 36, "CLOSE  [K]", Cyber.display(Font.BOLD, 16), this::toggleHeroStore);
        close.setAccent(Cyber.MAGENTA);
        overlay.add(close); overlayButtons.add(close);
        String sub = heroStoreNotice != null ? heroStoreNotice
            : "Buy a hero once to unlock it forever. Unlocked heroes deploy free, once per match (up to " + lindefense.tower.TowerManager.MAX_HEROES_PER_GAME + " heroes per game), then level up with three upgrades bought in game.";
        overlay.add(Ui.label(sub, px + 30, py + 92, Cyber.body(Font.BOLD, 14), heroStoreNotice != null ? Cyber.GREEN : Cyber.MUTED));

        // ---- left: the roster grid
        TowerType[] heroes = TowerType.heroes();
        int cols = 5;
        double gx = px + 22, gy = py + 108, gap = 8;
        double tw = 118, th = 104;
        for (int i = 0; i < heroes.length; i++) {
            heroTile(heroes[i], gx + (i % cols) * (tw + gap), gy + (i / cols) * (th + gap), tw, th);
        }
        double gridW = cols * tw + (cols - 1) * gap;
        // ---- right: the detail panel
        heroDetail(heroStoreSelection, gx + gridW + 18, gy, pw - gridW - 58, ph - 108 - 22);
        refreshHover();
    }

    /** One tile in the roster grid: sprite, name, price and lock state; clicking it opens that hero's details. */
    private void heroTile(TowerType t, double x, double y, double w, double h) {
        boolean unlocked = game.isHeroUnlocked(t), deployed = game.isHeroDeployed(t);
        boolean selected = t == heroStoreSelection;
        int price = lindefense.tower.TowerCatalog.get(t).unlockCost;
        Color accent = Ui.c(t.primaryRgb);
        Color border = selected ? Cyber.CYAN : Cyber.alpha(unlocked ? accent : Cyber.DIM, unlocked ? 190 : 120);
        // the click target goes in first; the tile's own art is drawn over it
        UIButton pick = new UIButton(x, y, w, h, "", Cyber.mono(Font.BOLD, 1), () -> { heroStoreSelection = t; heroStoreKey = ""; });
        pick.setFlat(true);
        pick.setAccent(border);
        overlay.add(pick); overlayButtons.add(pick);
        overlay.add(new Cyber.Chamfer(x, y, w, h, 10).scan(false)
            .fill(new Color(selected ? 16 : 9, selected ? 26 : 15, selected ? 48 : 34, 240)).border(border).lineWidth(selected ? 2 : 1.3));
        acm.graphics.GCompound icon = lindefense.ui.sprites.towers.TowerIcons.create(t, 0, 54);
        icon.setLocation(x + w / 2, y + 34);
        overlay.add(icon);
        if (!unlocked) overlay.add(new Cyber.Ring(x + w / 2 - 28, y + 34 - 28, 56, 56, new Color(5, 9, 22, 130), null));
        GLabel nm = Ui.label(t.displayName, 0, 0, Cyber.display(Font.BOLD, 13), selected ? Cyber.TEXT : Cyber.lerp(accent, Color.WHITE, 0.4));
        for (int sz = 13; nm.getWidth() > w - 10 && sz > 8; sz--) nm.setFont(Cyber.displayCompact(Font.BOLD, sz));
        nm.setLocation(x + (w - nm.getWidth()) / 2, y + h - 26);
        overlay.add(nm);
        String tag = deployed ? "DEPLOYED" : unlocked ? "READY" : Ui.money(price);
        Color tc = deployed ? Cyber.DIM : unlocked ? Cyber.GREEN : game.getCash() >= price ? Cyber.YELLOW : Cyber.RED;
        GLabel pl = Ui.label(tag, 0, 0, Cyber.mono(Font.BOLD, 10), tc);
        pl.setLocation(x + (w - pl.getWidth()) / 2, y + h - 9);
        overlay.add(pl);
    }

    /** The selected hero's full card: role, base ability, live statistics, the three upgrades and the action button. */
    private void heroDetail(TowerType t, double x, double y, double w, double h) {
        lindefense.tower.TowerDef d = lindefense.tower.TowerCatalog.get(t);
        boolean unlocked = game.isHeroUnlocked(t), deployed = game.isHeroDeployed(t);
        int price = d.unlockCost;
        boolean afford = game.getCash() >= price;
        Color accent = Ui.c(t.primaryRgb);
        overlay.add(new Cyber.Chamfer(x, y, w, h, 14).scan(false).fill(new Color(8, 13, 30, 245)).border(Cyber.alpha(accent, 220)).lineWidth(1.8));
        acm.graphics.GCompound icon = lindefense.ui.sprites.towers.TowerIcons.create(t, 0, 86);
        icon.setLocation(x + 60, y + 60);
        overlay.add(icon);
        double tx = x + 116, tw = w - 130;
        overlay.add(Ui.label(t.displayName, tx, y + 36, Cyber.display(Font.BOLD, 26), Cyber.lerp(accent, Color.WHITE, 0.35)));
        overlay.add(Ui.label(HeroStatText.role(t), tx, y + 56, Cyber.body(Font.PLAIN, 13), Cyber.MUTED));
        String status = deployed ? "DEPLOYED THIS MATCH" : unlocked ? "UNLOCKED" : "LOCKED";
        Color sc = deployed ? Cyber.DIM : unlocked ? Cyber.GREEN : Cyber.RED;
        GLabel sl = Ui.label(status, 0, 0, Cyber.mono(Font.BOLD, 11), sc);
        overlay.add(new Cyber.Chamfer(tx, y + 66, sl.getWidth() + 16, 18, 5).scan(false).fill(Cyber.alpha(sc, 40)).border(sc));
        sl.setLocation(tx + 8, y + 79);
        overlay.add(sl);
        GLabel pr = Ui.label(unlocked ? "owned" : Ui.money(price), 0, 0, Cyber.mono(Font.BOLD, 18), unlocked ? Cyber.DIM : afford ? Cyber.YELLOW : Cyber.RED);
        pr.setLocation(x + w - 16 - pr.getWidth(), y + 40);
        overlay.add(pr);
        double yy = y + 104;
        for (String l : Ui.wrap(d.description, Cyber.body(Font.PLAIN, 12), w - 32)) { overlay.add(Ui.label(l, x + 16, yy, Cyber.body(Font.PLAIN, 12), Cyber.MUTED)); yy += 15; }
        // base level
        yy += 10;
        overlay.add(Ui.label(Cyber.spaced("// level 1: " + d.tierLabels[0]), x + 16, yy, Cyber.mono(Font.BOLD, 10), Cyber.CYAN));
        for (String l : HeroStatText.attackLines(t, 0)) { yy += 16; overlay.add(Ui.label(l, x + 16, yy, Cyber.mono(Font.BOLD, 11), Cyber.TEXT)); }
        // the three upgrades, with what each one changes
        for (int i = 0; i < d.upgrades.length; i++) {
            lindefense.tower.UpgradeDef up = d.upgrades[i];
            yy += 20;
            overlay.add(Ui.label(Cyber.spaced("// level " + (i + 2) + ": " + up.name), x + 16, yy, Cyber.mono(Font.BOLD, 10), Cyber.alpha(accent, 240)));
            GLabel uc = Ui.label(Ui.money(up.cost), 0, yy, Cyber.mono(Font.BOLD, 11), Cyber.YELLOW);
            uc.setLocation(x + w - 16 - uc.getWidth(), yy);
            overlay.add(uc);
            int lines = 0;
            for (String l : Ui.wrap(up.description, Cyber.body(Font.PLAIN, 12), w - 32)) {
                if (++lines > 3) break;
                yy += 15; overlay.add(Ui.label(l, x + 16, yy, Cyber.body(Font.PLAIN, 12), Cyber.MUTED));
            }
        }
        yy += 20;
        overlay.add(Ui.label("Fully upgraded: " + Ui.money(d.totalCost()) + " of in-match credits on top of the unlock",
            x + 16, yy, Cyber.mono(Font.BOLD, 10), Cyber.DIM));
        // action
        double by = y + h - 54;
        UIButton b;
        if (!unlocked) {
            b = new UIButton(x + 16, by, w - 32, 40, afford ? "BUY  " + Ui.money(price) : "NEED " + Ui.money(price - game.getCash()) + " MORE", Cyber.display(Font.BOLD, 17), () -> buyHero(t));
            if (!afford) { heroStoreNeedButton = b; heroStoreNeedPrice = price; }
            b.setEnabled(afford);
            b.setAccent(Cyber.YELLOW);
            if (afford) b.setPrimary(true);
        } else if (!deployed && game.getTowerManager().heroesDeployedThisMatch() >= game.getHeroLimit()) {
            b = new UIButton(x + 16, by, w - 32, 40, "HERO LIMIT  " + game.getHeroLimit() + " PER GAME", Cyber.display(Font.BOLD, 16), null);
            b.setEnabled(false);
        } else if (!deployed) {
            b = new UIButton(x + 16, by, w - 32, 40, "DEPLOY (FREE)  " + game.getTowerManager().heroesDeployedThisMatch() + " / " + game.getHeroLimit() + " USED", Cyber.display(Font.BOLD, 17), () -> deployHero(t));
            b.setAccent(Cyber.GREEN);
            b.setPrimary(true);
        } else {
            b = new UIButton(x + 16, by, w - 32, 40, "ALREADY DEPLOYED THIS MATCH", Cyber.display(Font.BOLD, 16), null);
            b.setEnabled(false);
        }
        overlay.add(b); overlayButtons.add(b);
    }

    /** Full controls / modifiers / economy reference, opened from the side panel. */
    private void buildHelpOverlay() {
        overlay.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, 205), Ui.c(0x000000, 0)));
        double cx = Ui.WORLD_X + Ui.WORLD_W / 2.0, cy = Ui.WORLD_Y + Ui.WORLD_H / 2.0;
        double pw = 860, ph = 640, px = cx - pw / 2, py = cy - ph / 2;
        overlay.add(new Cyber.Chamfer(px, py, pw, ph, 24).fill(new Color(6, 10, 24, 240)).border(Cyber.CYAN).glow(1).lineWidth(2).ticks(true));
        overlay.add(Ui.label(Cyber.spaced("// field manual"), px + 34, py + 40, Cyber.mono(Font.BOLD, 12), Cyber.alpha(Cyber.MAGENTA, 230)));
        overlay.add(Ui.label("HELP", px + 34, py + 80, Cyber.display(Font.BOLD, 40), Cyber.TEXT));
        String[][] keys = { { "SPACE", "start next wave" }, { "1  2  3", "game speed" }, { "P", "pause / resume" }, { "B", "all towers / faction tabs" },
            { "ESC", "cancel / deselect, else pause menu" }, { "U", "upgrade selected tower" }, { "S", "sell selected tower" }, { "A", "fire selected tower's ability" },
            { "T", "cycle targeting priority" }, { "K", "Hero Store" }, { "M", "music on / off" }, { "N", "sound on / off" }, { "H", "toggle this help" } };
        if (game.isReverse()) keys = AttackPanel.HELP_KEYS;   // REVERSE HOOK
        double ky = py + 126;
        overlay.add(Ui.label(Cyber.spaced("// controls"), px + 34, ky, Cyber.mono(Font.BOLD, 11), Cyber.CYAN));
        for (String[] k : keys) {
            ky += 24;
            overlay.add(Ui.label(k[0], px + 34, ky, Cyber.mono(Font.BOLD, 14), Cyber.CYAN));
            overlay.add(Ui.label(k[1], px + 130, ky, Cyber.body(Font.PLAIN, 15), Cyber.TEXT));
        }
        double rx = px + 470, ry = py + 126, rw = pw - 470 - 34;
        String[][] notes = {
            { "enemy modifiers", "Camo enemies need detection (Perplexity, Grok, or Gemini / Llama after their second upgrade). Regrow enemies heal over time. Fortified enemies carry double HP. Prompt Injection enemies (wave 30+) hijack nearby towers; Claude, Copilot (and its radius), DeepSeek, Perplexity and Mr. Lindemann are immune." },
            { "hero store", "Open with HEROES or K. Buy a hero once to unlock it permanently, then deploy it free, once per match. Heroes are not in the tower shop." },
            { "economy", "Enemies pay cash when destroyed and every wave pays a bonus. Selling refunds most of what you spent on a tower." },
            { "bosses", "Boss health shows in the dock under the top bar. Palantir (wave " + lindefense.wave.WaveData.WAVE_COUNT + ") disrupts your strongest towers with Predictive Surveillance; watch the telegraph. Towers near Perplexity are immune." } };
        if (game.isReverse()) notes = AttackPanel.HELP_NOTES;   // REVERSE HOOK
        for (String[] n : notes) {
            overlay.add(Ui.label(Cyber.spaced("// " + n[0]), rx, ry, Cyber.mono(Font.BOLD, 11), Cyber.CYAN));
            for (String l : Ui.wrap(n[1], Cyber.body(Font.PLAIN, 14), rw)) { ry += 20; overlay.add(Ui.label(l, rx, ry, Cyber.body(Font.PLAIN, 14), Cyber.MUTED)); }
            ry += 34;
        }
        UIButton close = new UIButton(cx - 100, py + ph - 70, 200, 46, "CLOSE", Cyber.display(Font.BOLD, 20), this::toggleHelp);
        close.setPrimary(true);
        overlay.add(close);
        overlayButtons.add(close);
        refreshHover();
    }
}
