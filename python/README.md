# Lindefense: developer notes

The whole game (simulation, UI, audio) as a native desktop app. Player documentation is in the
[main README](../README.md); this page is for working on the code.

- **Window, input, audio:** [pygame-ce](https://pyga.me) (SDL2)
- **Graphics:** [Skia](https://skia.org) via `skia-python`, drawing every frame straight into the window's OpenGL
  framebuffer at the display's native (Retina) resolution, fully anti-aliased. Falls back to Skia's CPU rasteriser
  when OpenGL is unavailable (`LINDEFENSE_RENDERER=cpu` forces it).

## Run

```bash
./run.sh                 # first run creates .venv and installs requirements.txt (from python/)
```

## Build the macOS app

```bash
packaging/build_app.sh   # -> dist/Lindefense.app (double-click to play)
```

## Tests

```bash
.venv/bin/python -m pytest tests -q -m "not slow"   # about 1 minute
.venv/bin/python -m pytest tests -q                 # everything, about 8 minutes
```

## Layout

| Path | What |
|---|---|
| `lindefense/sim, enemy, tower, combat, effects, wave, map, variance, ai` | the simulation: deterministic and seeded (fixed 1/60 s steps, Java-compatible math in `javacompat.py`) |
| `lindefense/ui/` | screens, HUD, sprites and map art |
| `lindefense/ui/jawt.py`, `acm.py`, `jrt.py` | the 2-D graphics, scene-graph (ACM-style `GCompound` / `GRect` / ...) and runtime helpers on Skia that the UI is written against |
| `lindefense/audio/` | sound effects and music on `pygame.mixer` |
| `lindefense/app.py` | the desktop app: window, Skia GPU surface, input, frame loop |
| `lindefense/savegame.py` | Save & Continue: the autosave slot (exact snapshot of the match at each wave boundary and on quit) |
| `lindefense/tools/` | AutoPlayer, ReverseProbe, DesignDocGenerator, PerfBench, RenderSoak, SfxSynth, snapshots |
| `packaging/` | PyInstaller spec, icon renderer, `build_app.sh` |

## Developer switches (environment variables)

| Variable | Effect |
|---|---|
| `LINDEFENSE_START=<map>` | skip the menu and start a match on map N (`LINDEFENSE_START_WAVES=1` also starts waves); `tutorial` starts the tutorial |
| `LINDEFENSE_CONTINUE=1` | skip the menu and CONTINUE the saved run |
| `LINDEFENSE_SMOKE=<sec>[:shot.png]` | run for N seconds, optionally save a screenshot, print fps, quit |
| `LINDEFENSE_DEMO=<dir>` | scripted UI walkthrough (all screens, resizes, click-to-place, RECORDS, SETTINGS, the daily and seed briefings, CONTINUE, the end-screen REPORT); writes PNGs + PASS/FAIL. Its runs stay out of the player's records and saved run |
| `LINDEFENSE_HIDDEN=1` | hidden window (automation). Hidden, demo and smoke runs never auto-pause on focus loss and quit at once when closed (no QUIT GAME? confirmation); they also neither restore nor save the window size / position or full screen |
| `LINDEFENSE_NOSOUND=1` | no audio device |
| `LINDEFENSE_VARIANCE=off` | no Patch Notes / Breaking News (overrides the briefing's PATCH NOTES switch) |
| `LINDEFENSE_PAINT_CACHE=0` | paint every tower part every frame instead of replaying unchanged parts (for comparisons) |
| `LINDEFENSE_SEED=<code>`, `LINDEFENSE_DIFFICULTY=O1\|ON\|ON2\|ONN`, `LINDEFENSE_QUALITY=LOW\|MEDIUM\|HIGH`, `LINDEFENSE_FPS=30\|60\|120`, `LINDEFENSE_WINDOWFX=false` | force the run seed, Difficulty Growth mode, graphics quality, frame cap, or turn Palantir's window grab off for one run |
| `LINDEFENSE_RENDERER=cpu` | Skia CPU rendering instead of OpenGL |
| `LINDEFENSE_SHOW_FPS`, `LINDEFENSE_REDUCED_MOTION`, `LINDEFENSE_COLOURBLIND` `=1/0` | force SETTINGS > FPS COUNTER / REDUCED MOTION / COLOUR-BLIND SAFE on or off for one run (not saved) |
| `LINDEFENSE_PREFS_DIR` | where settings, Hero Store progress, records (`lindefense_records.json`: map records, career stats, run history, achievements; a `.bak` copy is kept), the saved run (`run_save.bin`), `display.json` (display / accessibility switches) and `window.json` (last window size, position and maximised state) are kept (default `~/Library/Application Support/Lindefense`) |

## About the code

The UI was written in Java (on the Stanford ACM graphics library) and machine-translated to Python for beta 3.0; the Java
version was retired afterwards. That is why the UI is a scene graph of ACM-style objects and uses small Java-runtime
helpers (`_j.cat`, `_j.imod`, ...): they keep the translated semantics exact (integer division, string formatting,
NaN-propagating min / max). Everything is now ordinary Python; edit it directly. Java-style `-Dfoo.bar` properties
read through `jrt.get_property` map to `FOO_BAR` environment variables.

Checks worth knowing about:

- **The simulation is deterministic.** A seeded run must replay step for step (Save & Continue depends on it). Keep
  randomness on the game's own `Rng`; the UI must only read game state.
- **Tower sprites cache unchanged parts** (`acm.PaintCache`): any new mutator of a shape used inside towers must call
  `acm._touch` (ACM setters already do), or cached towers show stale parts. `tests/test_paint_cache.py` compares cache
  on and off pixel for pixel.
- **Saves are tied to the game version**: bump `lindefense/version.py` whenever a release changes simulation classes,
  so old saves are refused instead of loaded into changed code.
