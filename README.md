# Lindefense - The Last Line of Code

**Version: beta 2.01**

![Lindefense title card](docs/titlecard.png)

Lindefense is a complete, playable tower-defense game written in Java with the Stanford ACM Graphics
library (`GCanvas`, `GCompound`, `GOval`, `GRect`, `GPolygon`, `GLine`, `GLabel`). You defend a track
with 18 towers (17 AI models and companies plus **Zethos, the Quantum Architect**) and 18 unlockable
**Hero Store** heroes (up to 3 per game, led by the teacher himself, **Mr. Lindemann**) across seven maps,
against 100 waves of computer-science enemies - data structures, sorting algorithms and five corporate
MOAB-class bosses - ending with the BAD-class final boss **Palantir** on Wave 100. Every shop tower has an
overpowered ability you can unlock for $15,000 once it is fully upgraded. New players can start with the
guided **Tutorial**; the **Catalog** on the main menu explains every enemy, tower and hero.

The window opens large (about 92% of your screen) and is freely resizable: the whole game scales to
fit whatever size you drag it to.

All tuning numbers (tower stats, upgrades, abilities, enemy stats, boss phases, every wave) are in
data classes and documented in [DESIGN.md](DESIGN.md), which is generated from those classes.

### What's new in beta 2.01

- **Tower abilities are back**, much stronger than before, and locked behind a **$15,000** unlock once a shop tower
  has all three upgrades (side-panel **UNLOCK ABILITY** button or `U`). They are ready the moment you buy them.
- **New hero: Mr. Lindemann** ($2,500), the strongest hero. He fires black holes of Java code that leave a crushing
  singularity on the track, and every 20 s he warps space and sends every enemy, bosses included, back 5 s.
  **Spear Hanbo** is buffed to second strongest ($2,000).
- **At most 3 heroes per game.** **Zethos** is nerfed to about twice the strength of Gemini, Claude and GPT.
- **Mission briefing:** DEPLOY on a map card first shows the map's preview, description, mechanics and your
  difficulty; deploy from there (or press `Enter`).
- **`Esc` toggles the pause menu** in game. Fixed: pressing `Esc` on the map screen could leave the main menu's
  buttons unresponsive.
- **Volume sliders** for music and sound in the pause menu and the main menu's SETTINGS, next to the on/off toggles.
- The Hero Store no longer flickers whenever your cash changes, and the HUD's hostiles chip shows `alive / total`.

## 1. Setup

### Quick start (macOS / Linux)

Copy-paste this whole block into a terminal:

```bash
git clone https://github.com/hanb0i/Lindefense.git
cd Lindefense
./setup.sh      # finds or installs a compatible JDK, checks lib/acm.jar, builds, runs the tests
./run.sh        # launch the game
```

`setup.sh` is safe to re-run. It:

1. Looks for a JDK **11-25** (`$JAVA_HOME`, then `~/.jdks/*`, then `/usr/libexec/java_home` on macOS,
   then `javac` on your `PATH`). If none is found, it downloads **Eclipse Temurin JDK 21** into
   `~/.jdks/`. It needs no `sudo` and no Homebrew, and it doesn't change your system Java.
2. Downloads `lib/acm.jar` if it is missing (the jar is already committed, so normally nothing is downloaded).
3. Builds into `build/` and runs the headless test suite. The last line should read `Passed: N  Failed: 0`.

> **Why not the newest Java?** `acm.jar`'s `GraphicsProgram` extends `javax.swing.JApplet`, and the
> Applet API was removed in **JDK 26**. On JDK 26+ the build fails with
> `cannot access JApplet ... class file for javax.swing.JApplet not found`. Keep your newer JDK
> installed if you like: `build.sh` / `run.sh` / `test.sh` pick a compatible JDK automatically
> (see `scripts/java-env.sh`).

### Manual JDK install (if you'd rather not use `setup.sh`)

```bash
# macOS with Homebrew
brew install --cask temurin@21

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y openjdk-21-jdk

# Fedora
sudo dnf install -y java-21-openjdk-devel

# Any OS with SDKMAN (https://sdkman.io)
sdk install java 21-tem
```

Then confirm the JDK and point the scripts at it if it isn't the default:

```bash
javac -version                                   # expect javac 11 - 25
export JAVA_HOME=$(/usr/libexec/java_home -v 21)  # macOS only; on Linux use the JDK's install dir
```

### Windows (PowerShell)

```powershell
winget install EclipseAdoptium.Temurin.21.JDK
# open a NEW terminal so PATH / JAVA_HOME refresh, then:
git clone https://github.com/hanb0i/Lindefense.git
cd Lindefense
.\test.bat
.\run.bat
```

`build.bat` checks your JDK and stops with a clear message if it is older than 11 or newer than 25.
If you also have JDK 26+ installed, set `JAVA_HOME` to the JDK 21 folder first (the `.bat` scripts
put `%JAVA_HOME%\bin` at the front of `PATH`):

```powershell
$env:JAVA_HOME = (Get-ChildItem "C:\Program Files\Eclipse Adoptium\jdk-21*" | Select-Object -First 1).FullName
```

### Same game on every computer

Everything the game needs ships in this repository, so it looks and sounds the same on Windows,
macOS and Linux: the fonts (`assets/fonts/`, SIL OFL), all sprites (drawn in code with ACM shapes),
the music (`assets/music/`) and sound effects (`assets/sfx/`, CC0). The code compiles with
`--release 11`, so any JDK from 11 to 25 builds and runs it. Assets are found relative to the project
even when you launch from an IDE, and `.gitattributes` keeps the shell scripts and binary assets
intact on every platform.

### The ACM graphics library

`lib/acm.jar` (the Stanford/ACM Java Task Force graphics library) is included in the repository.
If it is ever missing, `setup.sh` re-downloads it. To do it by hand:

```bash
mkdir -p lib
curl -L -o lib/acm.jar https://cs.stanford.edu/people/eroberts/jtf/acm.jar
unzip -l lib/acm.jar | grep GraphicsProgram      # should list acm/program/GraphicsProgram.class
```

(Any CS106A course copy of `acm.jar` also works.) There are no other dependencies or build tools.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `cannot access JApplet` / `class file for javax.swing.JApplet not found` | You are on JDK 26+. Run `./setup.sh`, or set `JAVA_HOME` to a JDK 11-25 |
| `No compatible JDK found` | Run `./setup.sh`, or install JDK 21 using one of the commands above |
| `lib/acm.jar is missing` | Run `./setup.sh`, or use the `curl` command above |
| `permission denied: ./run.sh` | `chmod +x *.sh` |
| Window doesn't open over SSH / in CI | Expected: the game needs a display. `./test.sh` runs headless |

## 2. Build and run

macOS / Linux:

```
./build.sh      # compiles src/ into build/ with -Xlint
./run.sh        # builds if needed, then launches the game
./test.sh       # builds and runs the headless verification suite
```

Windows (Command Prompt / PowerShell):

```
build.bat
run.bat
test.bat
```

Manual equivalents. If `java -version` shows JDK 26 or newer, first run
`export JAVA_HOME="$(scripts/java-env.sh)" && export PATH="$JAVA_HOME/bin:$PATH"` in that terminal:

```
javac -d build -cp lib/acm.jar @<(find src -name '*.java')      # or list the files
java  -cp build:lib/acm.jar lindefense.Main                      # use ; instead of : on Windows
java  -cp build:lib/acm.jar lindefense.test.HeadlessTests        # headless checks
java  -cp build:lib/acm.jar lindefense.tools.DesignDocGenerator  # regenerate DESIGN.md
java  -cp build:lib/acm.jar lindefense.tools.AutoPlayer [maxWave] [mapIndex]   # balance probe (bot plays the maps)
#   optional: -Dbot.maxTowers=N -Dbot.random=true to handicap the bot (tower cap / random placement)
#   optional: -Dbot.difficulty=O1|ON|ON2|ONN  (Difficulty Growth mode, default O1)  -Dbot.seed=N  -Dbot.maxMinutes=N  -Dbot.reportEvery=N
```

## Difficulty Growth

Four modes named after Big-O classes, picked on the map-select screen (or `-Dlindefense.difficulty=O1|ON|ON2|ONN`; default **O(1)**, the
unchanged original game). All knobs are relative multipliers on top of the base game and live in `lindefense.sim.Difficulty`.
HP, enemy count and elite chance ramp with the mode's curve (flat, linear, quadratic, capped super-exponential); tower damage and income are flat.

| Knob | O(1) Constant | O(N) Linear (Normal) | O(N^2) Quadratic (Hard) | O(N^N) Super-exponential (Impossible) |
|---|---|---|---|---|
| Enemy HP x (wave 1 -> 100) | 1 | 1.1 -> 1.5 | 1.25 -> 3.1 | 1.3 -> 3.3 |
| Enemy count x (wave 1 -> 100) | 1 | 1.1 -> 1.4 | 1.25 -> 2.4 | 1.3 -> 2.5 |
| Tower damage x | 1 | 0.92 | 0.84 | 0.75 |
| Income x (kills + wave bonus) | 1 | 0.8 | 0.56 | 0.5 |
| Starting cash x | 1 | 1 | 1 | 2 |
| Elite chance per spawn | none | none | 3% -> 80% | 5% -> 80% |
| Elite rules | - | - | +2 random modifiers, 50% promoted to a tougher type | +2 random modifiers, 50% promoted |
| Extra bosses | none | none | none | 10 groups on waves 25-85 (MOABs, one BFB; see DESIGN.md section 7) |
| Palantir | unchanged | HP x damage-compensation | same | same (+3% per tier) |

Extra bosses (O(N^N) only): one MOAB each on 25, 30, 35, 45, 50, 55 and 65, a BFB on 70, two Fortified MOABs on 75 and 85. Palantir is never duplicated.
The O(N^2) and O(N^N) numbers above are raised past the original Difficulty values (O(N^2) HP final 2.2 -> 3.1, damage 0.86 -> 0.84, income 0.6 -> 0.56, count 2.3 -> 2.4,
elites 60% -> 80%; O(N^N) HP final 3.0 -> 3.3, count 2.4 -> 2.5, elites 60% -> 80%); O(N^N) keeps its double starting cash.

Balance-bot calibration (the near-optimal `AutoPlayer`): O(1) and O(N) are won on every map and seed; O(N^2) is won in 9-10 of 12 map x seed runs (the survivors keep 22-99 lives);
O(N^N) is brutal but beatable: 4 of 12 on the standard seeds and 33 of 80 over a 20-seed batch, with at least 3 wins on every map and losses almost all on waves 98-99
(The Legacy Monolith is the easy map and wins every mode). The 20-tower cap bot wins the base game only on Legacy and loses O(N^2) and O(N^N); the random-placement casual
bot loses mid-game in every mode. Full tables are in DESIGN.md section 7; re-run `AutoPlayer` with `-Dbot.difficulty=...` (`-Dbot.seeds=N`, `-Dbot.maxTowers=20`,
`-Dbot.random=true`) after any stat change.

## 3. Controls

| Input | Action |
|---|---|
| Shop card, then left-click on the map | Buy and place a tower (ghost shows range; cyan = valid, red with an X = invalid, with the reason) |
| `B` / **ALL** button | Toggle the shop between one faction tab and a grid of all 18 shop towers grouped by faction (unaffordable towers are dimmed with a red price; hovering shows the shortfall). Clicking a faction tab leaves ALL mode |
| Left-click a placed tower | Select it: stats, upgrade button, targeting, ability, sell |
| Left-click an enemy | Inspect it (HP, speed, mechanic, modifiers) |
| Right-click | Cancel placement or ability aiming, or deselect |
| `Esc` | Toggle the pause menu in game (it closes HELP or the Hero Store first, and drops a tower you were placing). On the map screen it closes the briefing popup, or goes back to the main menu; on the main menu it closes HELP / SETTINGS |
| **DEPLOY** on a map card | Opens the mission briefing: large map preview, description, map mechanics and your Difficulty Growth mode. Its **DEPLOY** (or `Enter`) starts the match; **BACK** / `Esc` closes it |
| `Space` / **Start Wave** button | Start the next wave (never starts automatically unless **Auto** is on) |
| `1` `2` `3` / buttons | Game speed 1x / 2x / 3x |
| `P` / `||` button | Pause: opens the pause menu (resume with `P`, `Esc` or the play button) |
| `U` | Upgrade the selected tower; on a fully upgraded shop tower, buy its ability for $15,000 |
| `S` | Sell the selected tower (70% refund) |
| `A` | Fire the selected tower's ability (once unlocked) |
| `T` | Cycle targeting priority (First / Last / Strongest / Weakest / Closest) |
| `K` / **HEROES** button | Open / close the Hero Store (buy heroes, deploy unlocked ones) |
| `M` / `N` | Toggle **M**usic / sou**N**d (also speaker and note buttons on the main menu, map select and the pause menu) |
| `H` / **? HELP** button | Open the in-game help overlay (full controls, modifiers, economy, bosses) |
| **Auto** button | Auto-start the next wave 8 s after the current one is cleared |
| **Menu** button | Pause and open the pause menu: **Resume**, **Restart** (same map and difficulty, asks to confirm), **Sound effects** and **Music** toggles with a **volume slider** beside each, **Quit level** (back to map select, asks to confirm) and **Main menu** |

## Audio

Lindefense has sound effects and a streaming music system, both built on the JDK's `javax.sound.sampled` (no
libraries). Audio is strictly best effort: with no sound device, a headless run, or a missing / unsupported file
the game stays silent and keeps running.

### Toggles and hotkeys

There are two independent switches, **Sound** (effects, speaker icon) and **Music** (note icon). Each shows
`ON` / `OFF` in the menus and the icon is struck through when off. They live in:

- the main menu (under QUIT) and the map / difficulty select screen,
- the in-game pause menu (MENU button, `Esc` or `P`).

Each channel also has a **volume slider** (0-100%, default 100% = the loudness the game was tuned at) in the in-game
pause menu and in the main menu's **SETTINGS** panel: click the track or drag the knob. Mute is separate: muting keeps
the slider level, unmuting restores it, and a muted channel's slider is greyed out.

Hotkeys work on every screen: **`M`** toggles music, **`N`** toggles sound. All four settings are saved between runs with
`java.util.prefs.Preferences` (node `lindefense/audio`). Assets (`assets/fonts`, `assets/sfx`, `assets/music`) are located by `lindefense.Assets`, which tries `-Dlindefense.home=<folder>`, the working directory, the folder above `build/`, then the classpath, so the game also runs from an IDE. File names are case-sensitive on Linux; a test checks that every referenced name matches exactly. Start with `-Dlindefense.nosound=true` to never open the device.

### Sound effects

Effects are loaded once at start-up from `assets/sfx/` (16-bit PCM WAV, mono, 22.05 kHz, under 1 MB in total; the interface sounds are synthesised by `lindefense.tools.SfxSynth`), mixed
by a small software mixer with at most 12 voices, throttled per sound (for example enemy pops at most 20 per second,
attack sounds at most about 15 per second per family) and given slight random pitch / volume variation. Mixing runs on a
daemon thread, so the game loop never waits on audio. Attack sounds are chosen from the tower's damage type and attack
kind (laser, projectile shot, explosion, sonic pulse, magic, kinetic, gravity / true damage, chain lightning).
Sources, authors and licenses (all CC0) are listed in [assets/sfx/CREDITS.md](assets/sfx/CREDITS.md).

### Music

Seven tracks ship in `assets/music/` (about 26 MB); add or replace files there and they are picked up automatically. Every file is optional.
Tracks stream from disk on a background thread (they are never loaded whole), loop seamlessly, and crossfade (about 1.5 s)
when the context changes. A track keeps playing across waves and is not restarted. Once the last boss dies, the boss
theme lingers about 6 s before returning to the battle track.

| File (`assets/music/`) | Plays when | Fallback |
|---|---|---|
| `menu.wav` | title screen, How to Play, map / difficulty select | (none) |
| `battle.wav` | normal waves 1-59 | (none) |
| `battle_late.wav` | normal waves 60-99 | `battle.wav` |
| `battle_onn.wav` | any normal wave on O(N^N) difficulty (overrides the two above) | `battle_late.wav`, then `battle.wav` |
| `boss.wav` | any MOAB-class boss on the field (Bellarmine, SW Resource Consultant, 3Com, Lockheed Martin) | the current battle track |
| `palantir.wav` | wave 100 / Palantir on the field (overrides everything) | `boss.wav` |
| `incoming_data.wav` | victory and defeat screens (loops, crossfades in) | (none) |

**Format.** WAV, either G.711 mu-law (the default of the convert script: 22.05 kHz stereo, about 2.6 MB per minute) or
16-bit PCM (44.1 or 22.05 kHz, mono or stereo). Use loopable audio and keep each track to about 60-90 s so the repo stays
small. The game decodes mu-law (including the WAVE_FORMAT_EXTENSIBLE header `afconvert` writes for stereo) with its own pure-Java RIFF reader. MP3 / OGG / FLAC must be converted first.

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

## 4. Gameplay

- You start with **$650** and **100 lives**. Enemies that reach an exit remove lives based on their
  strength (1 for a Primitive Variable, up to 100 for a ZOMG or Palantir). At 0 lives you lose.
- Destroying enemies pays cash; every wave pays a bonus ($1,178 after wave 1, falling to a flat $300 from wave 40)
  and Perplexity towers add research income. Kill rewards are 3x the listed value to wave 60, 4x on waves 61-80 and 1.6x
  after, because the 20-tower roster costs several times the original one. Enemy HP scale is flat to wave 60, 1.1x at 80 and
  1.3x at 100 for every enemy, bosses included; boss base HPs are their debut-wave values (MOAB 1,500, BFB 7,500, ZOMG 8,000,
  DDT 1,000, Palantir 50,000), so no enemy gets weaker as the waves go on (DESIGN.md section 1 and 4).
- Every original tower has a base form and **exactly three upgrades** named after its model lineup in order of
  model intelligence - upgrading Claude buys "Claude Sonnet 5.5", then "Claude Opus 5.5" and finally
  "Claude Fable 5.1". Every original tower also has an **overpowered ability** that is locked until the tower is
  fully upgraded: then the side panel offers **UNLOCK ABILITY** for **$15,000** (or press `U`), and the ability is
  ready the moment you buy it (fire it with `A` or the ability bar; the unlock counts toward the sell refund).
  **Zethos** (Primary, $650) has **four** upgrades ($350 / $650 / $1,200 / $2,500, $5,350 in total) and its Reality
  Collapse ability from placement; it is tuned to about twice the best of Gemini, Claude and GPT at each tier.
  Towers have configurable **targeting** (Grok U2+ adds Densest Cluster) and sell for 70% of everything spent.
- **Hero Store** (`HEROES` button or `K`): 18 heroes ($850 to $2,500). Everyone starts with none. Buying one with
  match cash unlocks it **permanently** (saved with `java.util.prefs`, node `lindefense/heroes`); unlocked
  heroes deploy **for free, once per match**, and **at most 3 different heroes per game** (dismissing one does not
  give its deployment or its slot back). Heroes level up through three purchasable upgrades and have no active
  abilities. **Mr. Lindemann** ($2,500) is the strongest hero: his shots are black holes of Java code that leave a
  crushing singularity on the track, and every 20 s (15 s when maxed) he warps space and sends every enemy on the
  map, bosses included, back 5 s along the track. **Spear Hanbo** ($2,000) is the second strongest.
  The heroes' and Zethos's ranges, radii and projectile speeds are specified in map units (1 unit = 4 px).
- **Modifiers**: *Camo* enemies cannot be targeted without detection (Grok,
  Perplexity or its aura, Gemini U2, Llama U2). *Regrow* enemies heal 1 HP every 2 s.
  *Fortified* enemies have double HP (Qwen's ability strips it from airships).
- **Damage types** (see DESIGN.md): Sharp cannot hurt *Lead-type* enemies (Heap Sort, Lockheed Martin,
  Radix Sort's armoured phases); Blunt/Kinetic/Sonic deal double to *Ceramic-type* outer layers (Merge,
  Quick and Tim Sort); Explosive cannot pop Camo without detection; Magic hurts everything.
- **Bosses** appear on waves 40 (MOAB), 60 (BFB), 80 (ZOMG), 90 (DDT) and 100 (BAD) with large
  health bars, armour, and children released on destruction.
- **Palantir** (Wave 100) has three phases (armour 60% / 35% / 10%, faster each phase, Lockheed
  escorts in phase 3) and **Predictive Surveillance**: every 30/20/14 s it analyses your
  highest-investment towers for 3 s (red reticles and analysis lines), then disrupts them for 8 s
  (-50% speed, -30% range, abilities locked). Counter it with Perplexity U2's radius (Predictive
  Analysis), or by spreading your investment. Destroying Palantir wins the campaign.

## 5. Towers

| Faction | Towers | Role |
|---|---|---|
| Heroes (Hero Store, max 3 per game) | Lobber Luis, Sage Aarav, Iron Imraan, Boom Sam, Chillstin, Kaiju Kai, Abhi-Ace, Zippy Matt, Sunny Joe, Nik-Scope, Cami-Mine, Justin Time, Spear Hanbo, Thorn Tuhin, Trapper Che, Blitz Arnav, Tanimbus, Mr. Lindemann | Artillery; healing; melee control; explosives; ice; beam kaiju; flyer; chain lightning; economy; sniper; mines; time control; piercing spears (second strongest); poison; traps; suppressing fire; tower support; black holes of Java code + map-wide space warp (strongest) |
| Primary | Gemini, Claude, GPT, Zethos | Chain lightning vs groups; piercing + slowing crowd control; adaptive all-rounder; piercing / splashing / bouncing quantum projectiles (four upgrades) |
| Military | DeepSeek, Copilot | Railgun vs complex enemies/bosses; attack-speed aura (double for Military) and Surveillance firewall |
| Magic | DALL-E, Sora, Suno | Splash + Sprite summons; time-slowing pulses; sonic pulses vs dense groups |
| Support | Grok, Perplexity | Disruption of enemy mechanics; camo detection, marks and income |
| Experimental Titans | Qwen, Llama, Mistral, Cohere, GLM, Kimi, MiniMax | Layer/Fortified stripping; kinetic knockback; wind vs fast enemies; armour-breaking single target; gravity crowd control; scaling damage vs non-Fortified; bouncing/cloning orbs |

Full stats, upgrade paths and abilities: [DESIGN.md section 2](DESIGN.md#2-towers).

## 6. Enemies

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

Bosses: Bellarmine College Prep (MOAB), SW Resource Consultant (BFB), 3Com (ZOMG), Lockheed Martin
(DDT: camo, fast, Physical-immune), Palantir (BAD). Details and precise rules:
[DESIGN.md sections 3-4](DESIGN.md#3-enemies).

## 7. Maps

| Map | Difficulty | Unique mechanics |
|---|---|---|
| The Silicon Circuit | Beginner | Two lanes; Capacitor Pads charge Support/Hero towers for cash and speed; Trace Short-Circuits zap one lane and boost towers along it |
| The Legacy Monolith | Intermediate | Serpentine server rack; chassis block line of sight; Thermal Overload Venting every 10 waves on a random floor |
| The Hallucination Canyon | Advanced | Two crossing routes; Attention Drift teleports 25% of enemies at the hub; Noise Storms halve range unless a Logic Specialist (DeepSeek/Copilot) is near |
| The Singularity Core | Expert | Four portals spiralling into a vortex; Gravitational Pull speeds enemies up near the core; Event Horizon Collapse on wave 50 resets cooldowns and scatters enemies |
| Silicon Valley | Intermediate | One long winding campus road; buildings block placement and the rounded bends reward towers that cover two stretches at once |
| The Neural Network | Advanced | Two inputs branch through hidden layers into six routes that merge at one output neuron |
| Abandoned Data Center | Beginner | A long maintenance route; every 16 s one of four marked track sections malfunctions and slows enemies there by 45% for 7 s |

The map select screen lays out every map registered in `MapCatalog` (4 per row), so additional maps appear automatically; `DESIGN.md` section 5 is generated from the same registry.
Clicking a card's **DEPLOY** opens a mission briefing (large preview with entry / exit markers, description, map
mechanics and the selected Difficulty Growth mode); its own **DEPLOY** or `Enter` starts the match.

## 8. Project layout

```
src/lindefense/
  Main.java                 entry point
  sim/      Game (state, economy, fixed-step loop), Vec, Rng
  map/      GameMap, Path (waypoints), Obstacle, the seven maps, MapCatalog
  enemy/    EnemyType (data table), Enemy, Boss (phases + Predictive Surveillance), EnemyManager, modifiers/status,
            EnemyGrid (spatial hash grid for proximity queries; see Performance)
  tower/    TowerType, TowerCatalog, TowerDef/TowerStats/UpgradeDef/AbilityDef, Tower (buff book),
            TowerManager, AbilityManager, Shop, Targeting
  tower/data/      the tower data table, one file per faction (HeroTowers, PrimaryTowers, ...)
  tower/behavior/  one TowerBehavior per tower: the special mechanics (see docs/TOWER_ENGINE.md)
  effects/  reusable sim primitives: TrackZone, TrackWalker, Drone, NodeHazard, Barrage, Effects
  combat/   Combat (targeting, attacks, damage formula), Projectile, HitSpec, HitContext, Clusters, DamageType, VisualEvent
  wave/     WaveData (all 100 waves), WaveDef, SpawnGroup, WaveManager
  ui/       LindefenseProgram (ACM GraphicsProgram), ScaledLayer (resize scaling), GameScreen, WorldView,
            HudPanel, SidePanel, TowerSprite, MenuScreen, MapSelectScreen (+ mission briefing), UIButton, Slider
            (volume sliders), Ui, DemoDriver
  ui/sprites/  enemy + boss character sprites (SpriteFactory, EnemySprite, BossSprite, Logo, death/split
               effects); SpriteGallery previews every enemy/state
  ui/sprites/towers/  tower art for every tower and tier (TowerArtFactory, *Art), TowerIcons (shop icons),
               ProjectileSprites (per-tower projectiles + beam/chain/hit/explosion effects); TowerGallery
  audio/    AudioManager (sound effects, music, switches), Sfx, Track, MusicDirector, Mixer, MusicStream
  test/     HeadlessTests plus GlobalRulesTests, EnginePrimitiveTests, the per-faction group tests, HeroStoreTests,
            AbilityUnlockTests and VolumeTests - run without a window
  tools/    DesignDocGenerator (DESIGN.md), AutoPlayer (balance bot), PerfBench (performance benchmark)
lib/acm.jar
assets/fonts/                 bundled OFL fonts used by every UI label (see below)
assets/sfx/                   sound effects (CC0) + CREDITS.md;  assets/music/  optional music tracks
setup.sh                      one-shot setup: JDK check/install, acm.jar check, build + tests
scripts/java-env.sh           picks a JDK 11-25 for the shell scripts (JDK 26+ removed JApplet)
scripts/perfbench.sh          builds and runs PerfBench (optionally with a JFR profile)
build.sh / run.sh / test.sh   (and .bat equivalents)
```

### Bundled fonts

So the UI looks identical on Windows, Linux and macOS, the game ships its own fonts in `assets/fonts/` and loads them at
startup (`Font.createFont` + `registerFont`, resolved relative to the working directory, the build output directory or the
classpath; a missing file falls back to a logical Java font). All are licensed under the SIL Open Font License 1.1; the
license texts sit next to the font files.

| Role | Font | License file |
|---|---|---|
| Techno display (headings, buttons, names) | Rajdhani (Indian Type Foundry) | `assets/fonts/OFL-rajdhani.txt` |
| UI sans (paragraph text) | Barlow (Jeremy Tribby) | `assets/fonts/OFL-barlow.txt` |
| Monospace (numbers, readouts) | IBM Plex Mono (IBM Corp.) | `assets/fonts/OFL-ibmplexmono.txt` |

UI code gets fonts only through `Ui.display / Ui.mono / Ui.body` (backed by `ui/Cyber.java`).

The simulation (`sim`, `map`, `enemy`, `tower`, `combat`, `wave`) has no dependency on ACM or AWT
and runs headless; the `ui` package renders it.

## 9. Testing

`./test.sh` runs `lindefense.test.HeadlessTests`, which exercises the real game logic: purchase /
upgrade / sell and the 70% refund, every upgrade path (three upgrades for shop towers and heroes, four for Zethos), the
$15,000 ability unlocks and every unlocked ability, the Hero Store (prices, permanent unlocks, the 3-heroes-per-game cap,
Mr. Lindemann strongest and Spear Hanbo second), the global tower rules (damage types, statuses, buff caps, camo, hero uniqueness), the sim primitives and every tower's data-table numbers, volume settings, rewards without
duplicate-kill exploits, lives on leaks, every targeting priority, camo vs detection, Fortified and
Regrow, every splitter's children, boss children, all 100 wave compositions (including Palantir on
Wave 100), Palantir's phases and Predictive Surveillance, ability cooldowns, traversal of every
route on all seven maps, map mechanics, win and loss conditions, and a late-wave stress run.

`JAVA_OPTS="-Dlindefense.demo=<dir>" ./run.sh` runs a scripted UI walkthrough
(menu -> map select -> mission briefing -> game -> window resizes -> Palantir -> pause menu and volume sliders) that
writes PNG snapshots and verifies click-to-place after resizing, `Esc` handling on every screen, the briefing popup
and the pause-menu flows.

## 10. Performance

### Measuring: PerfBench

```
scripts/perfbench.sh [sim|render|all] [-Dperf.option=value ...]
PERF_JFR=1 scripts/perfbench.sh render      # also records build/perf.jfr and prints hot methods + allocations
java -cp build:lib/acm.jar lindefense.tools.PerfBench all     # same thing by hand (use ; on Windows)
```

`lindefense.tools.PerfBench` is a reusable, fully headless benchmark (`java.awt.headless=true`, no window, no screen capture):

* **sim**: on every map a dense roster of 72 maxed towers (all 20 types) plays late waves for real
  (`perf.from`/`perf.to`, default 90-100; add `-Dlindefense.difficulty=ONN` for O(N^N)), then a **siege** keeps a crowd
  of `perf.siege` (default 400) enemies alive on top of wave 96. It reports ms per `Game.step` (mean / p50 / p95 / p99 /
  max), enemy / projectile / effect counts, visual events per tick, KB allocated per tick, GC count, and an outcome
  **fingerprint** (kills, leaks, cash, per-tower damage) that must not change when the simulation code is optimized.
* **render**: the real `GameScreen` / `WorldView` / sprites inside a real `GCanvas` (configured exactly like the game's
  canvas), with the same dense roster and a crowd of exactly N enemies (`perf.enemies`, default 150,300,600) that is
  kept topped up while the towers fire. Each frame runs `GameScreen.frame(1/60)` and paints the whole canvas into a
  `BufferedImage`, like the demo driver's snapshots. It reports update / paint / frame ms (p50 / mean / p95 / max),
  live GObjects and KB allocated per frame. `-Dperf.breakdown=true` adds the paint cost of every layer and sprite class;
  `-Dperf.snap=<dir>` writes the final frames as PNGs; `-Dlindefense.lod=0|1|2` pins the level of detail.

Timings use the benchmark thread's CPU time by default (`-Dperf.clock=wall` for elapsed time), so other programs on a
busy machine do not distort them.

### What makes big fights fast

* **Spatial hash grid** (`enemy.EnemyGrid`): the 1200x900 world is split into 48 px cells held in a two-dimensional
  array `cells[column][row]` of `ArrayList<Enemy>` buckets. Every "enemies near here" question asks only the cells
  around the point: tower targeting, projectile collisions, splash, auras and enemy fields, track zones, walkers and node
  hazards, chain and bounce hops, and the densest-cluster search (`Clusters` uses the grid whenever it is handed the live
  enemy list), instead of looping over every enemy. Enemies report each move, so an enemy crossing a cell border
  changes bucket immediately. The grid rebuilds itself lazily when enemies are added or removed. Candidates come back in
  the same order as a full scan and the original exact test is still applied to them, so outcomes are bit-for-bit
  unchanged (same seed, same game). Behaviour code can use it too:
  `game.getEnemyManager().getGrid().near(x, y, radius, scratchList)` returns the candidates (a superset, in list order)
  to run the usual exact test on. Use `grid.scan(...)` instead when the loop body can move enemies (hits with knockback).
* **Allocation cuts in the simulation**: no boxed hit-id lookups before the cheap distance test, statuses stored in an
  array indexed by kind instead of an `EnumMap` with iterators, cached comparators, reused per-route lists with
  binary-searched neighbour windows, `Path` segment lengths and directions cached in arrays, projectile steering
  without temporary vectors, and `Math.hypot` avoided in range checks (`Vec.withinDist`, exact).
* **Rendering**: ACM's native arc drawing is switched on (`LindefenseProgram.configureCanvas`). The default ACM
  fallback turns every oval into a polygon with about 6 vertices per pixel of diameter, which was about 70% of frame
  time. A **level of detail** depends on how many sprites are on screen: decorative parts (shadows, gloss, cracks,
  status accents) go first, then eyes and thin outlines, and HP bars are drawn simplified. Bosses always keep full
  detail. Transparent outlines are never rasterized. Visual effects are capped (fewer under load) and the simple ones are
  pooled. Quality hints are set once per frame instead of per object, and per-frame setters skip unchanged values.
* **Game loop**: the simulation runs in fixed 1/60 s steps decoupled from rendering. At most
  `GameScreen.MAX_SIM_STEPS_PER_FRAME` (8) steps run per rendered frame, so at 3x speed a slow frame makes the game
  briefly run slower instead of piling more simulation onto the next frame. The Swing timer produces at most ~60
  frames per second and coalesces, so input is handled between frames.

### Before / after (Apple M4 Pro, JDK 24, benchmark-thread CPU time)

| Scenario | Before | After |
|---|---|---|
| Render, 72 maxed towers + 50 enemies, ms/frame (mean / p95) | 59.9 / 65.2 | 34.5 / 42.0 |
| Render, 72 maxed towers + 150 enemies | 91.9 / 100.7 | 29.1 / 31.0 |
| Render, 72 maxed towers + 300 enemies | 143.9 / 162.3 | 39.9 / 45.1 |
| Render, 72 maxed towers + 600 enemies | 238.8 / 288.7 | 64.5 / 74.6 |
| Render, 30 maxed towers + 300 enemies | 130.8 / 175.1 | 31.6 / 34.2 |
| Render allocation per frame (50 / 600 enemies, 72 towers) | 12.3 / 52.8 MB | 2.4 / 4.0 MB |
| Sim, O(N^N) waves 90-100, all maps, ms/tick (mean / p95) | 0.023 / 0.066 | 0.018 / 0.046 |
| Sim, siege of 400 enemies, ms/tick (mean / p95) | 0.224 / 0.349 | 0.096 / 0.160 |
| Sim, siege of 1000 enemies, ms/tick (mean / p95) | 0.713 / 1.345 | 0.359 / 0.637 |
| Sim allocation per tick (siege 400 / 1000) | 266 / 500 KB | 25 / 51 KB |

Simulation fingerprints are identical before and after on every map and scenario.
