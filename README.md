# Lindefense - The Last Line of Code

**Version: beta 4.0**

![Lindefense title card](docs/titlecard.png)

Lindefense is a complete tower-defense game for the desktop, written in **Python**: a pygame-ce window with Skia GPU
rendering at native (Retina) resolution, fully anti-aliased. You defend a track with 18 towers (17 AI models and
companies plus **Zethos, the Quantum Architect**) and 18 unlockable **Hero Store** heroes (up to 3 per game, led by the
teacher himself, **Mr. Lindemann**) across seven maps, against 100 waves of computer-science enemies - data
structures, sorting algorithms and four corporate MOAB-class bosses, each with a signature ability - ending with the
BAD-class final boss **Palantir** on Wave 100. Beat it and the run can go on in endless **Freeplay**.

Every shop tower has an overpowered ability you can unlock for $15,000 once it is fully upgraded. Runs autosave
(**CONTINUE** on the main menu), and your records, career stats, run history and 29 achievements are kept between
sessions. There is a **Daily Run**, seed entry and five challenge rules, four Difficulty Growth modes, a reverse mode
where you attack an AI defender, a guided **Tutorial** and a **Catalog** of every enemy, tower and hero.

## What's new in beta 4.0

- **Python only.** The Java version is retired; `./run.sh` starts the Python game.
- **Much tougher enemies.** Health climbs from wave 20 to 2.1x by wave 100 (late waves are also faster). The four
  corporate bosses have more health and a signature ability each (Crest Shield, Outsourcing, Network Hub, Afterburner).
  **Palantir** has about 2.6x the health on O(1), scales with Difficulty Growth, stays immune to crowd control longer,
  surveils more towers more often, and launches escort squadrons whose Swarm Uplink shields it.
- **Save & Continue**: autosave every wave and on quit; CONTINUE on the main menu resumes the run exactly.
- **Records and achievements**: medals and best waves on the map cards, a RECORDS screen (career, map records,
  29 achievements, run history with REPLAY SEED), and an end-of-run report with RETRY.
- **Freeplay** after Palantir falls, with a short epilogue and credits.
- **Daily Run, seed entry and challenge rules** (No Heroes, One Life, No Selling, Frugal, Glass Cannon), and a
  Patch Notes on / off switch.
- **Battle intel**: next-wave preview with threat warnings, upgrade previews with stat changes, damage readouts.
- **Safer controls**: confirmations before a run can be lost, a tactical pause you can build in, auto-pause when the
  window loses focus, new hotkeys (`Tab`, `Shift+T`, `O`, `Shift+1-9`).
- **Settings**: full screen (`F11`), remembered window size and position, Reduced Motion, Colour-Blind Safe, FPS counter.

## 1. Setup

You need **Python 3.10 or newer** (`python3 --version`) and a display. Everything else is installed into a private
virtual environment the first time you run the game.

### macOS / Linux

Copy-paste this whole block into a terminal:

```bash
git clone https://github.com/hanb0i/Lindefense.git
cd Lindefense
./run.sh        # first run creates python/.venv and installs pygame-ce, skia-python and numpy
```

`./run.sh` (or `python/run.sh`) starts the game every time after that.

### Windows (PowerShell)

```powershell
git clone https://github.com/hanb0i/Lindefense.git
cd Lindefense\python
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m lindefense.app
```

### A double-clickable macOS app

```bash
python/packaging/build_app.sh   # -> python/dist/Lindefense.app
```

### Same game on every computer

Everything the game needs ships in this repository, so it looks and sounds the same on Windows, macOS and Linux: the
fonts (`assets/fonts/`, SIL OFL), all sprites (drawn in code), the music (`assets/music/`) and sound effects
(`assets/sfx/`, CC0). `python/requirements.txt` pins the graphics and window libraries. Assets are found relative to
the project from any working directory, and `.gitattributes` keeps the shell scripts and binary assets intact on every
platform.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `python3: command not found` / Python older than 3.10 | Install a current Python from python.org (or `brew install python`, `sudo apt install python3 python3-venv`) |
| `No module named venv` or `ensurepip` errors (Debian / Ubuntu) | `sudo apt install python3-venv`, then delete `python/.venv` and run `./run.sh` again |
| `pip` cannot find `skia-python` | Use a 64-bit Python 3.10 or newer (32-bit Python has no Skia wheels) |
| The window opens black or blank | Start once with `LINDEFENSE_RENDERER=cpu ./run.sh` (CPU rendering) and report your GPU |
| `permission denied: ./run.sh` | `chmod +x run.sh python/run.sh` |
| No window over SSH / in CI | Expected: the game needs a display. The tests run headless |
| No sound | Check SETTINGS > AUDIO; with no audio device the game simply stays silent |

Saved data (settings, Hero Store unlocks, records, the autosaved run) lives in `~/Library/Application Support/Lindefense`
on macOS, `%APPDATA%\Lindefense` on Windows and `~/.config/lindefense` on Linux. Delete that folder to start fresh.

## 2. Controls

| Input | Action |
|---|---|
| Shop card, then left-click on the map | Buy and place a tower (ghost shows range; cyan = valid, red with an X = invalid, with the reason) |
| `B` / **ALL** button | Toggle the shop between one faction tab and a grid of all 18 shop towers grouped by faction (unaffordable towers are dimmed with a red price; hovering shows the shortfall). Clicking a faction tab leaves ALL mode |
| Left-click a placed tower | Select it: stats, upgrade button, targeting, ability, sell |
| Left-click an enemy | Inspect it (HP, speed, mechanic, modifiers) |
| Right-click | Cancel placement or ability aiming, or deselect |
| `Esc` | In game it cancels the innermost thing first: HELP, a confirmation (= NO), the pause menu, the Hero Store, ability aiming, a tower placement, the selection; with none of them it opens the pause menu. Closing the pause menu with `Esc` returns to how the game was (running, or the tactical pause). On the map screen it closes the briefing popup, or goes back to the main menu; on the main menu it closes HELP / SETTINGS |
| **DEPLOY** on a map card | Opens the mission briefing: large map preview, description, map mechanics and your Difficulty Growth mode, and the RUN SETUP band (seed, Patch Notes, challenge rules). Its **DEPLOY** (or `Enter`) starts the match; **BACK** / `Esc` closes it |
| **PLAY DAILY** on the DAILY RUN card | Opens today's daily run briefing; **START DAILY** (or `Enter`) starts it |
| SEED field in the briefing | Click it, then type or paste (`Cmd+V` / `Ctrl+V`) a run code; `Backspace` deletes, `Enter` deploys, `Esc` or a click elsewhere leaves the field (while it is active `M` / `N` type letters) |
| `Space` / **Start Wave** button | Start the next wave (never starts automatically unless **Auto** is on) |
| `1` `2` `3` / buttons | Game speed 1x / 2x / 3x |
| `P` / `||` button | Tactical pause: the game stops but the map stays usable (place, upgrade, sell, select, retarget, start a wave); a **PAUSED - press P to resume** banner shows. `P` again, the play button or a speed key resumes. With the pause menu open, `P` resumes |
| `Tab` / `Shift+Tab` | Select the next / previous placed tower (placement order) |
| `Shift+1` ... `Shift+9` | Pick the 1st ... 9th card of the shop as shown (the open faction tab, or ALL) for placement; the card tooltip shows its key |
| `O` | Toggle **Auto** (start each next wave by itself) |
| `U` | Upgrade the selected tower; on a fully upgraded shop tower, buy its ability for $15,000 |
| `S` | Sell the selected tower (70% refund; refused under the No Selling rule). Dismissing a hero asks first (**DISMISS** / **KEEP**, or `Enter` / `Esc`): it cannot be deployed again that match |
| `A` | Fire the selected tower's ability (once unlocked) |
| `T` / `Shift+T` | Cycle targeting priority forwards / backwards (First / Last / Strongest / Weakest / Closest) |
| `K` / **HEROES** button | Open / close the Hero Store (buy heroes, deploy unlocked ones) |
| `M` / `N` | Toggle **M**usic / sou**N**d (also speaker and note buttons on the main menu, map select and the pause menu) |
| `1` `2` `3` during a Patch Notes draft | Pick that card (or click it); the next wave waits until you pick |
| `H` / **? HELP** button | Open the in-game help overlay (full controls, modifiers, economy, bosses) |
| **Auto** button | Auto-start the next wave 8 s after the current one is cleared |
| **Menu** button | Pause and open the pause menu: **Resume**, **Restart** (same map and difficulty, asks to confirm), **Sound effects** and **Music** toggles with a **volume slider** beside each, **Quit level** (back to map select, asks to confirm) and **Main menu** (asks to confirm). In a confirmation `Enter` = YES and `Esc` = NO |
| Closing the window / `Cmd+Q` | During a match it asks first (the run is saved for **CONTINUE**); a second close request, or closing anywhere else, quits. Hidden, demo and smoke runs quit at once |
| Window loses focus / minimised | A running match pauses (pause menu). Palantir's System Takeover moving the window does not count; hidden, demo and smoke runs never auto-pause |

## 3. Gameplay

- You start with **$650** and **100 lives**. Enemies that reach an exit remove lives based on their
  strength (1 for a Primitive Variable, up to 100 for a ZOMG or Palantir). At 0 lives you lose.
- Destroying enemies pays cash; every wave pays a bonus ($1,178 after wave 1, falling to a flat $300 from wave 40)
  and Perplexity towers add research income. Kill rewards are 3x the listed value to wave 60, 4x on waves 61-80 and 1.6x
  after, because the 20-tower roster costs several times the original one. Enemy HP scale is flat to wave 20, then climbs
  to 1.2x at wave 40, 1.45x at 60, 1.75x at 80 and 2.1x at 100 for every enemy, bosses included (late waves are also up to
  1.35x faster); boss base HPs are MOAB 1,700, BFB 8,500, ZOMG 12,000, DDT 1,400 and Palantir 80,000, so no enemy gets
  weaker as the waves go on (DESIGN.md section 1 and 4).
- Every original tower has a base form and **exactly three upgrades** named after its model lineup in order of
  model intelligence - upgrading Claude buys "Claude Sonnet 5.5", then "Claude Opus 5.5" and finally
  "Claude Fable 5.1". Every original tower also has an **overpowered ability** that is locked until the tower is
  fully upgraded: then the side panel offers **UNLOCK ABILITY** for **$15,000** (or press `U`), and the ability is
  ready the moment you buy it (fire it with `A` or the ability bar; the unlock counts toward the sell refund).
  **Zethos** (Primary, $650) has **four** upgrades ($350 / $650 / $1,200 / $2,500, $5,350 in total); its Reality
  Collapse ability unlocks the same way, for $15,000 after the fourth upgrade. It is tuned to about twice the best of
  Gemini, Claude and GPT at each tier.
  Towers have configurable **targeting** (Grok U2+ adds Densest Cluster) and sell for 70% of everything spent.
- **Hero Store** (`HEROES` button or `K`): 18 heroes ($1,150 to $3,400 to unlock). Everyone starts with none. Buying
  one with match cash unlocks it **permanently** (saved on this computer); an
  unlocked hero then costs a separate, smaller **deploy fee** ($200-$700) to place, **once per match**, and
  **at most 3 different heroes per game** (dismissing one does not give its deployment or its slot back, though it
  refunds 70% of its deploy cost and any upgrades bought, like selling a tower). Heroes level up through three
  purchasable upgrades and have no active abilities. **Mr. Lindemann** ($3,400 to unlock, $700 to deploy) is the
  strongest hero: his shots are black holes of Java code that leave a crushing singularity on the track, and every
  20 s (15 s when maxed) he warps space and sends every enemy on the map, bosses included, back 5 s along the
  track. **Spear Hanbo** ($2,700 to unlock) is the second strongest.
  The heroes' and Zethos's ranges, radii and projectile speeds are specified in map units (1 unit = 4 px).
- **Modifiers**: *Camo* enemies cannot be targeted without detection (Grok,
  Perplexity or its aura, Gemini U2, Llama U2). *Regrow* enemies heal 1 HP every 2 s.
  *Fortified* enemies have double HP (Qwen's ability strips it from airships).
- **Damage types** (see DESIGN.md): Sharp cannot hurt *Lead-type* enemies (Heap Sort, Lockheed Martin,
  Radix Sort's armoured phases); Blunt/Kinetic/Sonic deal double to *Ceramic-type* outer layers (Merge,
  Quick and Tim Sort); Explosive cannot pop Camo without detection; Magic hurts everything.
- **Bosses** appear on waves 40 (MOAB), 60 (BFB), 80 (ZOMG), 90 (DDT) and 100 (BAD) with large
  health bars, armour, and children released on destruction. Each corporate boss has a **signature ability**, shown
  over the boss and in the boss dock: **Bellarmine College Prep** raises a *Crest Shield* worth 35% of its max HP the
  first time it drops to half health; **SW Resource Consultant** is *Outsourcing* (3 Quick Sort contractors every 9 s);
  **3Com** is a *Network Hub* (enemies within 200 px take half damage, and it repairs 0.6%/s); **Lockheed Martin** fires
  its *Afterburner* (1.5x speed for 1 s every 7 s).
- **Prompt injection** (from wave 30, more often later and at harder Difficulty Growth): an injector broadcasts when a
  tower comes within 150 px and every 9 s after, hijacking the 2 nearest towers that are not immune for 3 s. A hijacked
  tower stops attacking and zaps a neighbour offline for 1.5 s. Chains are one hop, and a tower that was just knocked
  out gets 4 s of protection. Immune: **Claude** (Constitutional AI), **Copilot** (Security Copilot; towers in its
  150 px firewall are protected too), **DeepSeek**, **Perplexity** and **Mr. Lindemann**; the tower panel and the
  catalog say so.
- **Palantir** (Wave 100, 168,000 HP on O(1) and more on harder Difficulty Growth) is slow but massive: three
  phases (armour 60% / 35% / 10%, faster each phase, immune to slows, stuns and knockback in phases 1 and 2), an
  **escort squadron** launched from the entrance at each phase change (3 Fortified Bellarmines, then a Lockheed Martin
  and a Fortified SW Resource Consultant) whose **Swarm Uplink** cuts Palantir's damage taken by 12% per escort within
  260 px (max 36%; kill them), and **Predictive Surveillance**: first after 20 s, then every 24/16/11 s it analyses your
  highest-investment towers (15-25% of them) for 3 s (red reticles and analysis lines), then disrupts them for 8 s
  (-50% speed, -30% range, abilities locked). Counter it with Perplexity U2's radius (Predictive
  Analysis), or by spreading your investment. Each phase also has a signature ability:
  **Panopticon** (phase 1, a sweeping beam blinds the towers it crosses for 2 s; Perplexity U2 protects),
  **Prompt Broadcast** (phase 2, every 10 s hijacks your most expensive towers that are not immune and keeps 3 hologram
  decoys with 4% of its HP each in the air, which only fool towers that are not immune) and **System Takeover** (phase 3:
  twin Panopticon beams sweep again, a one-time kill switch restarts your
  unlocked abilities' cooldowns, and Palantir **grabs the game window**, shrinking it to 72%; while the window stays
  under 85% of its size Palantir is **sealed**: it takes 30% damage and regenerates, so drag the window back).
  The window grab only resizes and moves your window inside the screen, never goes full screen, restores the window
  afterwards, and is off in SETTINGS > DISPLAY > WINDOW EFFECTS. Destroying Palantir wins the campaign.
  The first victory of a run plays a short **epilogue and credits** (click or Esc skips it).
- **Freeplay**: the victory screen offers **CONTINUE - FREEPLAY**. The board, cash, lives and towers carry over and
  endless waves follow from wave 101, generated from the run seed (the same seed always brings the same waves). Enemy
  health grows 6% per wave without limit, counts and Camo / Fortified / Regrow / Prompt Injection rates rise, every
  wave has MOAB-class escorts, every 10th wave brings a headline boss (3Com, a BFB pack or a DDT swarm) and every 25th
  a rebuilt Palantir. Patch Notes drafts continue before waves 121, 141, ... and Breaking News keeps running. Freeplay
  ends when lives reach 0, and the run still counts as a victory ("VICTORY - reached wave N in freeplay"). All the
  tuning knobs are named constants in `python/lindefense/wave/freeplay.py` (`FreeplayWaves`). Calibration: the
  balance bot (`BOT_FREEPLAY=true python -m lindefense.tools.auto_player 200`) wins on O(1) and then falls on freeplay
  waves 110-125 (seed 1234); the first headline boss, a 3Com on wave 110, is the usual wall.
- **Patch Notes** (run modifiers): at the start of a match and after waves 19, 39, 59 and 79 the game offers 3 random
  cards and you keep 1 for the rest of the run (18 cards, e.g. *Open Source*: towers 15% cheaper but sales refund 50%;
  *Overfitting*: +40% vs bosses, -15% vs everything else). Stacking is capped so no combination can wreck a run.
  **Breaking News**: from wave 6, each wave has a 22% chance of an event announced on the news ticker that lasts that
  wave (GPU shortage, Viral meme: all Camo, DDoS: faster enemies, Bug bounty, Server outage: one lane closed, ...).
  Every run has a short seed code (pause menu and end screen); **REPLAY SEED** on the end screen replays it, and
  the SEED field in the mission briefing (or `LINDEFENSE_SEED=CODE`) picks one. The tutorial plays without Patch Notes or news.
- **Run setup** (the RUN SETUP band at the bottom of the mission briefing):
  - **SEED**: click it, then type or paste (Cmd+V) a run code to play that exact run (same drafts, news and elites);
    leave it blank for a random seed. A code that is not valid is refused with the reason under the field.
  - **PATCH NOTES: ON / OFF** (saved): off means no drafts and no Breaking News, the plain game.
  - **Challenge rules** (off by default, kept until you quit the game): **No Heroes** (heroes cannot be deployed),
    **One Life** (1 integrity: the first leak ends the run), **No Selling** (towers cannot be sold nor heroes
    dismissed), **Frugal** (towers, heroes and upgrades cost 50% more) and **Glass Cannon** (towers deal +50% damage,
    25 integrity). Active rules show as chips under the top bar and on the end screen; RESTART and REPLAY SEED keep them.
- **Daily run** (the DAILY RUN card on the map screen): one run a day, the same for everyone on that date: the seed,
  map, Difficulty Growth mode (O(N) or O(N²)) and one challenge rule come from the date, and Patch Notes are always on.
  Your best wave of the day is kept.

### Difficulty Growth

Four modes named after Big-O classes, picked on the map-select screen (or `LINDEFENSE_DIFFICULTY=O1|ON|ON2|ONN`; the last mode you picked is remembered). All knobs are relative
multipliers on top of the base game and live in `python/lindefense/sim/difficulty.py`.
HP, enemy count and elite chance ramp with the mode's curve (flat, linear or quadratic); tower damage and income are flat.

| Knob | O(1) Constant | O(N) Linear (Normal) | O(N^2) Quadratic (Hard) | O(N^N) Super-exponential (Impossible) |
|---|---|---|---|---|
| Enemy HP x (wave 1 -> 100) | 1 | 1.1 -> 1.5 | 1.1 -> 1.85 | 1.25 -> 3.1 |
| Enemy count x (wave 1 -> 100) | 1 | 1.1 -> 1.4 | 1.1 -> 1.6 | 1.25 -> 2.4 |
| Tower damage x | 1 | 0.92 | 0.90 | 0.84 |
| Income x (kills + wave bonus) | 1 | 0.8 | 0.72 | 0.56 |
| Elite chance per spawn | none | none | 2% -> 22% | 3% -> 80% |
| Elite rules | - | - | +1 random modifier, 20% promoted to a tougher type | +2 random modifiers, 50% promoted |
| Palantir HP x (on top of the wave curve) | 1 | 1.15 | 1.3 | 2 |

More prompt injectors appear at higher modes (they ride the enemy-count multiplier).

Balance-bot calibration after the final-beta enemy buff (the near-optimal `auto_player`, all 7 maps x seeds 1234 and 2000): O(1) wins 5 / 6
of 7 (before: 7 / 7, all with 100 lives), and every loss is Palantir reaching the exit on wave 100 (Singularity Core, Neural Network);
with $15,000 ability unlocks (`BOT_ABILITIES=60:10`) 5 / 5. O(N) wins 3 / 3 (before 7 / 7), O(N^2) 3 / 3 (before 4 / 4), O(N^N) 0 / 0
(before 3 / 3); their losses come on boss waves (50-99) and, for O(N^N), also at Palantir on wave 100. Palantir now lasts 97-122 s (was 30-42 s)
and dies 79-98% along the short routes. The long-route maps (Legacy Monolith, Silicon Valley, Abandoned Data Center) stay the easy ones.
Full tables are in DESIGN.md section 7; re-run `BOT_DIFFICULTY=O1|ON|ON2|ONN BOT_SEED=1234 .venv/bin/python -m lindefense.tools.auto_player 100`
after any stat change.

## 4. Saves, records and achievements

- **Autosave and CONTINUE.** A run is saved every time a wave is cleared and whenever you leave it (QUIT LEVEL, MAIN
  MENU, closing the window), even mid-wave. The main menu then offers **CONTINUE** (with the map, mode and wave), which
  restores the run exactly as it was, down to the random numbers: a continued run plays out the same as if you had never
  left. There is one save slot; starting any new run replaces it, and winning or losing deletes it. Tutorial and reverse
  matches are never saved. A save from another game version is not loaded (the menu says so once).
- **Records** are kept per map and Difficulty Growth mode: best wave, victories, fastest win and most lives left. Each
  map card on the map screen shows four medals (lit for each mode you have won on) and your best wave for the selected
  mode; the mission briefing shows the full record.
- **RECORDS** (main menu, next to CATALOG): **CAREER** (runs, wins, waves, kills, boss kills, credits, play time, a medal
  cabinet), **MAP RECORDS**, **ACHIEVEMENTS** (29, the locked ones greyed with how to earn them) and **HISTORY** (your
  last 50 runs with date, map, mode, seed, wave, result, Patch Notes and rules; **REPLAY SEED** plays any of them again).
- **End of a run**: the victory / defeat panel has two tabs (`Tab` switches): **SUMMARY** (with **NEW BEST!** when a
  record fell and the achievements earned) and **REPORT** (leaks, game time, bosses destroyed, your map best and the top
  5 towers by damage, sold towers included). Buttons: **RETRY** (same map and mode, new seed), **REPLAY SEED**, **MAP
  SELECT** and **MAIN MENU**; after the first Palantir victory also **CONTINUE - FREEPLAY**.
- Achievements earned during a match pop up as a toast above the map and are saved when the run ends. Tutorial runs never
  count; reverse matches only count toward the four reverse-mode achievements.

## 5. Settings and accessibility

The main menu's **SETTINGS** panel (every change applies at once and is saved):

| Row | Settings |
|---|---|
| AUDIO | Sound and music switches, each with a volume slider (also in the in-game pause menu) |
| DISPLAY | **QUALITY** (LOW / MEDIUM / HIGH), **MAX FPS** (30 / 60 / 120), **FULLSCREEN** (also `F11`, on a Mac also `Cmd+Ctrl+F`, on every screen), **FPS COUNTER** |
| ACCESSIBILITY | **REDUCED MOTION** (no screen shake, glitch bursts or flashes; blinking warnings become steady highlights, nothing is hidden), **COLOUR-BLIND SAFE** (good / bad cues switch from green / red to azure / vermillion: HP bars, placement, prices, buffs and debuffs), **WINDOW EFFECTS** (whether Palantir may grab the window) |

The window remembers its size, position and maximised state between launches (a window last seen on a monitor that is
gone reappears on the main display). In full screen, Palantir cannot grab the window: the grab is blocked and its seal
broken, as with a maximised window. A match pauses itself when the window loses focus or is minimised.

## 6. Adversarial Training (reverse mode)

You are the attacker. Pick a map and a Difficulty Growth mode (it chooses the AI: **O(1)** Novice, **O(N)** Competent,
**O(N²)** Expert, **O(Nᴺ)** Superintelligence), click DEPLOY, then **ATTACK INSTEAD** in the briefing.

- **Goal:** break the AI's integrity (80 to 150, see below) within 15:00 of game time (15 one-minute epochs; units already
  on the track get up to a minute of overtime). If the AI survives, it wins.
- **Difficulty:** the harder the mode, the harder the AI's towers hit and the more integrity it has, and the less health
  your units have and the less compute you earn (shown in the briefing):

  | Mode | AI | AI tower damage | AI integrity | Your unit health | Your income |
  |---|---|---|---|---|---|
  | O(1) | Novice | x0.9 | 80 | x1.1 | x1.1 |
  | O(N) | Competent | x1 | 100 | x1 | x1 |
  | O(N²) | Expert | x1.1 | 125 | x0.95 | x0.95 |
  | O(Nᴺ) | Superintelligence | x1.2 | 150 | x0.9 | x0.9 |

- **Compute credits:** you start with 250 and earn an income that grows every minute (on O(N): 12/s at the start, about
  160/s at 10:00); **SCALE COMPUTE** (`C`) raises it. Every integrity point a leak costs the AI pays you 8 (times your
  income multiplier).
- **Units** unlock over time, from Primitive Variables at 0:00 to the five bosses (MOAB 5:00 ... Palantir 12:00).
  Modifiers multiply the price: Regrow x1.3, Camo x1.5, Fortified x2, **Prompt Injection x1.6** (from 6:00; it hijacks
  the AI's towers that are not immune).
- **Exploits:** `Q` Overclock (your units +50% speed), `W` Hotfix (heal everything on the track), `E` Zero-Day (jam the
  AI's 3 most expensive towers).
- **Controls:** click a unit card to send it, `X` cycles the quantity (x1 / x5 / x10 / x25), `L` picks the lane,
  `Space` repeats the last send. Long single-lane maps give your units a speed and income bonus (shown in the briefing).
- The defender plays by the normal rules (3 heroes per game, $15,000 ability unlocks) and its moves appear in the feed.

## 7. Towers

| Faction | Towers | Role |
|---|---|---|
| Heroes (Hero Store, max 3 per game) | Lobber Luis, Sage Aarav, Iron Imraan, Boom Sam, Chillstin, Kaiju Kai, Abhi-Ace, Zippy Matt, Sunny Joe, Nik-Scope, Cami-Mine, Justin Time, Spear Hanbo, Thorn Tuhin, Trapper Che, Blitz Arnav, Tanimbus, Mr. Lindemann | Artillery; healing; melee control; explosives; ice; beam kaiju; flyer; chain lightning; economy; sniper; mines; time control; piercing spears (second strongest); poison; traps; suppressing fire; tower support; black holes of Java code + map-wide space warp (strongest) |
| Primary | Gemini, Claude, GPT, Zethos | Chain lightning vs groups; piercing + slowing crowd control; adaptive all-rounder; piercing / splashing / bouncing quantum projectiles (four upgrades) |
| Military | DeepSeek, Copilot | Railgun vs complex enemies/bosses; attack-speed aura (double for Military) and Surveillance firewall |
| Magic | DALL-E, Sora, Suno | Splash + Sprite summons; time-slowing pulses; sonic pulses vs dense groups |
| Support | Grok, Perplexity | Disruption of enemy mechanics; camo detection, marks and income |
| Experimental Titans | Qwen, Llama, Mistral, Cohere, GLM, Kimi, MiniMax | Layer/Fortified stripping; kinetic knockback; wind vs fast enemies; armour-breaking single target; gravity crowd control; scaling damage vs non-Fortified; bouncing/cloning orbs |

Full stats, upgrade paths and abilities: [DESIGN.md section 2](DESIGN.md#2-towers).

## 8. Enemies

| Enemy | HP | Speed | Mechanic |
|---|---|---|---|
| Primitive Variable | 1 | 1.0x | Basic |
| Static Array | 2 | 1.4x | Releases 1 Primitive Variable |
| Dynamic Array | 3 | 1.8x | Releases 1 Static Array |
| Singly Linked List | 4 | 3.2x | Very fast |
| Doubly Linked List | 5 | 3.5x | Accelerates when damaged |
| Bubble Sort | 3 | 0.9x | Swaps position with the enemy ahead |
| Selection Sort | 4 | 1.0x | Jumps to the front of its group |
| Insertion Sort | 4 | 1.5x | Leapfrogs the enemy ahead |
| Shell Sort | 5 | 2.0x | Gap jumps (140 / 70 / 35 / 18 px) |
| Merge Sort | 6 | 1.1x | Splits into two Merge Runs (2 HP) |
| Quick Sort | 7 | 1.8x | Splits into two Quick Partitions (3 HP) |
| Heap Sort | 8 | 1.2x | Lead-type (Sharp-immune); shields enemies behind it |
| Counting Sort | 1 + 4 nodes | 1.3x | Releases 4 Primitive Variables |
| Radix Sort | 8 | 1.5x | Armour changes every two layers |
| Bucket Sort | 6 | 1.4x | Stores nearby weaker enemies, releases them on death |
| TimSort | 10 | 1.6x | Fast; splits into Merge Sort + Insertion Sort |

Bosses: Bellarmine College Prep (MOAB, Crest Shield), SW Resource Consultant (BFB, Outsourcing), 3Com (ZOMG, Network
Hub), Lockheed Martin (DDT: camo, fast, Physical-immune, Afterburner) and Palantir (BAD: three phases, escorts and Swarm
Uplink; see Gameplay). Details and precise rules:
[DESIGN.md sections 3-4](DESIGN.md#3-enemies).

## 9. Maps

| Map | Difficulty | Unique mechanics |
|---|---|---|
| The Silicon Circuit | Beginner | Two lanes; Capacitor Pads charge Support/Hero towers for cash and speed; Trace Short-Circuits zap one lane and boost towers along it |
| The Legacy Monolith | Intermediate | Serpentine server rack; chassis block line of sight; Thermal Overload Venting every 10 waves on a random floor |
| The Hallucination Canyon | Advanced | Two crossing routes; Attention Drift teleports 25% of enemies at the hub; Noise Storms halve range unless a Logic Specialist (DeepSeek/Copilot) is near |
| The Singularity Core | Expert | Four portals spiralling into a vortex; Gravitational Pull speeds enemies up near the core; Event Horizon Collapse on wave 50 resets cooldowns and scatters enemies |
| Silicon Valley | Intermediate | One long winding campus road; buildings block placement and the rounded bends reward towers that cover two stretches at once |
| The Neural Network | Advanced | Two inputs branch through hidden layers into six routes that merge at one output neuron |
| Abandoned Data Center | Beginner | A long maintenance route; every 16 s one of four marked track sections malfunctions and slows enemies there by 45% for 7 s |

The map select screen lays out every map registered in `python/lindefense/map/maps.py` (4 per row), so additional maps appear automatically; `DESIGN.md` section 5 is generated from the same registry.
Clicking a card's **DEPLOY** opens a mission briefing (large preview with entry / exit markers, description, map
mechanics and the selected Difficulty Growth mode); its own **DEPLOY** or `Enter` starts the match.

## 10. Audio

Sound effects and music play through `pygame.mixer`. Audio is strictly best effort: with no sound device, a headless run,
or a missing / unsupported file the game stays silent and keeps running.

### Toggles and hotkeys

There are two independent switches, **Sound** (effects, speaker icon) and **Music** (note icon). Each shows `ON` / `OFF`
and the icon is struck through when off. They live on the main menu (under QUIT), the map select screen, the in-game
pause menu and SETTINGS, and **`M`** (music) / **`N`** (sound) toggle them on every screen. Each channel also has a
**volume slider** (0-100%, default 100% = the loudness the game was tuned at) in the pause menu and in SETTINGS. Mute is
separate: muting keeps the slider level. All four settings are saved.

### Sound effects

Effects are loaded once at start-up from `assets/sfx/` (16-bit PCM WAV, mono, 22.05 kHz, under 1 MB in total; the
interface sounds are synthesised by `python -m lindefense.tools.sfx_synth`) and played on a pool of 12 voices with
priority stealing, throttled per sound (for example enemy pops at most 20 per second, attack sounds about 15 per second
per family) and given slight random pitch / volume variation. Attack sounds are chosen from the tower's damage type and
attack kind (laser, projectile shot, explosion, sonic pulse, magic, kinetic, gravity / true damage, chain lightning).
Sources, authors and licenses (all CC0) are listed in [assets/sfx/CREDITS.md](assets/sfx/CREDITS.md).

### Music

Seven tracks ship in `assets/music/` (about 26 MB); add or replace files there and they are picked up automatically.
Every file is optional. Tracks loop seamlessly on two reserved channels and crossfade (about 1.5 s) when the context
changes. A track keeps playing across waves and is not restarted. Once the last boss dies, the boss theme lingers about
6 s before returning to the battle track.

| File (`assets/music/`) | Plays when | Fallback |
|---|---|---|
| `menu.wav` | title screen, How to Play, map / difficulty select | (none) |
| `battle.wav` | normal waves 1-59 | (none) |
| `battle_late.wav` | normal waves 60-99 and Freeplay | `battle.wav` |
| `battle_onn.wav` | any normal wave on O(N^N) difficulty (overrides the two above) | `battle_late.wav`, then `battle.wav` |
| `boss.wav` | any MOAB-class boss on the field (Bellarmine, SW Resource Consultant, 3Com, Lockheed Martin) | the current battle track |
| `palantir.wav` | wave 100 / Palantir on the field, including Freeplay's rebuilt Palantirs (overrides everything) | `boss.wav` |
| `incoming_data.wav` | victory and defeat screens (loops, crossfades in) | (none) |

**Format.** WAV, either G.711 mu-law (the default of the convert script: 22.05 kHz stereo, about 2.6 MB per minute) or
16-bit PCM (44.1 or 22.05 kHz, mono or stereo). Use loopable audio and keep each track to about 60-90 s so the repo stays
small. MP3 / OGG / FLAC must be converted first.

**Convert on macOS** (afconvert; MP3, M4A, AAC, AIFF and WAV are accepted; MP4 / M4A inputs, including Opus-in-M4A and MP4
with video, are first passed through `avconvert` to get plain AAC audio):

```bash
scripts/convert-music.sh ~/Downloads/my_theme.mp3 assets/music/battle.wav        # mu-law 22.05 kHz stereo
scripts/convert-music.sh ~/Downloads/my_theme.m4a assets/music/boss.wav --pcm   # 16-bit PCM 22.05 kHz mono
```

**Convert on Windows / Linux** (ffmpeg):

```bash
# mu-law 22.05 kHz stereo (compact), limited to 90 s
ffmpeg -i input.mp3 -t 90 -ar 22050 -ac 2 -c:a pcm_mulaw assets/music/battle.wav
# 16-bit PCM 22.05 kHz mono
ffmpeg -i input.mp3 -t 90 -ar 22050 -ac 1 -c:a pcm_s16le assets/music/boss.wav
# video file: drop the video stream
ffmpeg -i input.mp4 -vn -t 90 -ar 22050 -ac 2 -c:a pcm_mulaw assets/music/menu.wav
```

## 11. Project layout

```
run.sh                        launches the game (forwards to python/run.sh)
python/
  run.sh                      creates python/.venv on the first run, then starts the game
  requirements.txt            pygame-ce, skia-python, numpy (+ pytest for the tests)
  lindefense/
    app.py                    the desktop app: window, Skia GPU surface, input, frame loop, autosave
    sim/      Game (state, economy, fixed 1/60 s steps), Difficulty, records (records, career, achievements),
              run_setup + challenges (seeds, daily run, rules), prompt injection, Vec, Rng
    map/      GameMap, Path, the seven maps and their mechanics
    enemy/    enemy types, Enemy, Boss (Palantir's phases and protocols), boss_abilities, EnemyManager,
              EnemyGrid (spatial hash for proximity queries)
    tower/    tower types and data tables, Tower, TowerManager, shop, behavior/ (one behaviour per tower)
    combat/   targeting, attacks, the damage formula, projectiles
    effects/  track zones, walkers, drones, mines, barrages
    wave/     waves.py (the 100 campaign waves, HP / speed curves), freeplay.py (endless waves)
    variance/ Patch Notes, Breaking News, run seeds
    ai/       Adversarial Training: the AI defender (also the balance bot), ReverseMatch, attacker units
    audio/    sound effects and music on pygame.mixer
    savegame.py               save & continue (one slot, version-checked)
    prefs.py                  the small JSON settings store
    ui/       screens (menu, map select + briefing, game, RECORDS, catalog, settings), HUD, side panel, world
              view, effects; sprites/ (every enemy, boss and tower drawn in code); acm.py / jawt.py / jrt.py:
              the scene-graph, 2-D graphics and runtime layer the UI is written against, on Skia
    tools/    auto_player (balance bot), reverse_probe, perf_bench, render_soak, design_doc_generator, sfx_synth
  tests/                      pytest suite
  packaging/                  PyInstaller spec, icon, build_app.sh
assets/fonts/  assets/sfx/  assets/music/
scripts/convert-music.sh      converts audio into the game's WAV format (macOS)
DESIGN.md                     every number in the game, generated from the live data tables
```

The simulation (`sim`, `map`, `enemy`, `tower`, `combat`, `effects`, `wave`, `variance`) has no UI dependency and
runs headless; the `ui` package renders it. The UI was originally written in Java on the Stanford ACM graphics library
and machine-translated to Python, which is why it is a scene graph of `GCompound` / `GRect` / `GLabel` objects; it is
now ordinary Python. The Java version was retired after beta 3.0.

### Bundled fonts

So the UI looks identical everywhere, the game ships its own fonts in `assets/fonts/` and never uses system fonts. All are
licensed under the SIL Open Font License 1.1; the license texts sit next to the font files.

| Role | Font | License file |
|---|---|---|
| Techno display (headings, buttons, names) | Rajdhani (Indian Type Foundry) | `assets/fonts/OFL-rajdhani.txt` |
| UI sans (paragraph text) | Barlow (Jeremy Tribby) | `assets/fonts/OFL-barlow.txt` |
| Monospace (numbers, readouts) | IBM Plex Mono (IBM Corp.) | `assets/fonts/OFL-ibmplexmono.txt` |

## 12. Testing and tools

```bash
cd python
.venv/bin/python -m pytest tests -q -m "not slow"   # about 1 minute
.venv/bin/python -m pytest tests -q                 # everything, about 8 minutes
```

The suite exercises the real game headless: every tower, upgrade path and ability, the Hero Store, prompt injection,
the bosses' abilities and Palantir's phases, every Patch Notes card and news event, Difficulty Growth, reverse mode,
freeplay, save & continue (a continued run must match an uninterrupted one step for step), records and achievements,
the daily run and challenge rules, the settings, and the real screens painted offscreen.

| Tool (run from `python/`) | What it does |
|---|---|
| `LINDEFENSE_DEMO=<dir> LINDEFENSE_PREFS_DIR=<tmp> .venv/bin/python -m lindefense.app` | Scripted walkthrough of every screen (resizes, click-to-place, pause flows); writes PNGs and PASS / FAIL |
| `BOT_DIFFICULTY=O1 BOT_SEED=1234 .venv/bin/python -m lindefense.tools.auto_player 100 [map]` | The balance bot plays whole campaigns (`BOT_ABILITIES=true` buys abilities, `BOT_FREEPLAY=true` continues into Freeplay) |
| `.venv/bin/python -m lindefense.tools.reverse_probe` | Reverse-mode balance probe |
| `.venv/bin/python -m lindefense.tools.design_doc_generator ../DESIGN.md` | Regenerates DESIGN.md |
| `.venv/bin/python -m lindefense.tools.perf_bench [sim\|render\|all]` | Headless performance benchmark |
| `.venv/bin/python -m lindefense.ui.ui_snapshots <dir>` | Paints real screens to PNGs without a window (also `injection_snapshots`, `reverse_snapshots`, `variance_snapshots`) |

Developer switches (environment variables such as `LINDEFENSE_START`, `LINDEFENSE_SEED`, `LINDEFENSE_RENDERER=cpu`)
are listed in [python/README.md](python/README.md).

## 13. Performance

The simulation runs in fixed 1/60 s steps, decoupled from rendering, with at most 8 steps per rendered frame. Big
late-game fights on an Apple Silicon Mac (hidden window, GPU, 3200x2000 Retina):

| Fight | Frame time | Frame rate |
|---|---|---|
| 40 towers, 100 enemies | 30 ms | 33 fps |
| 50 towers, 200 enemies | 46 ms | 22 fps |
| 72 maxed towers, 300 enemies | 76 ms | 13 fps |

What keeps it fast:

* **Simulation fast paths** that give bit-for-bit the same results: a spatial hash grid for every "enemies near here"
  query, cached path geometry and aura sums, and allocation-free hot loops.
* **Unchanged-part caching**: tower sprites record parts that have not changed for a few frames into Skia pictures and
  replay them; turrets aim by rotating the drawing rather than recomputing their shapes.
* **Level of detail** that depends on how many sprites are on screen (bosses always keep full detail), capped and pooled
  visual effects, and garbage-collector pauses moved to screen changes.

## 14. Credits and license

Lindefense is by Hanbo Song and Austin. The code is MIT-licensed ([LICENSE](LICENSE)); the fonts are SIL OFL 1.1 and
the sound effects CC0 (see [assets/sfx/CREDITS.md](assets/sfx/CREDITS.md)).
