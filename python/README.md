# Lindefense (Python)

The Python port of Lindefense: the full game (simulation, UI, audio) running as a native desktop app.

- **Window, input, audio:** [pygame-ce](https://pyga.me) (SDL2)
- **Graphics:** [Skia](https://skia.org) via `skia-python`, drawing every frame straight into the window's OpenGL
  framebuffer at the display's native (Retina) resolution, fully anti-aliased. Falls back to Skia's CPU rasteriser
  when OpenGL is unavailable (`LINDEFENSE_RENDERER=cpu` forces it).

## Run

```bash
./run.sh                 # first run creates .venv and installs requirements.txt
```

## Build the macOS app

```bash
packaging/build_app.sh   # -> dist/Lindefense.app (double-click to play)
```

## Tests

```bash
.venv/bin/python -m pytest tests -q -m "not slow"   # ~40 s
.venv/bin/python -m pytest tests -q                 # everything, ~6 min
```

## Layout

| Path | What |
|---|---|
| `lindefense/sim, enemy, tower, combat, effects, wave, map, variance, ai` | the simulation (bit-for-bit match with the Java game) |
| `lindefense/ui/` | screens, HUD, sprites and map art |
| `lindefense/ui/jawt.py`, `acm.py`, `jrt.py` | Java2D / ACM graphics / Java runtime equivalents on Skia that the UI is written against |
| `lindefense/audio/` | sound effects and music on `pygame.mixer` |
| `lindefense/app.py` | the desktop app: window, Skia GPU surface, input, frame loop |
| `lindefense/tools/` | AutoPlayer, ReverseProbe, DesignDocGenerator, PerfBench, RenderSoak, SfxSynth, snapshots |
| `packaging/` | PyInstaller spec, icon renderer, `build_app.sh` |
| `devtools/j2py.py` | the Java-to-Python transpiler used for the UI port (see below) |

## Developer switches (environment variables)

| Variable | Effect |
|---|---|
| `LINDEFENSE_START=<map>` | skip the menu and start a match on map N (`LINDEFENSE_START_WAVES=1` also starts waves) |
| `LINDEFENSE_SMOKE=<sec>[:shot.png]` | run for N seconds, optionally save a screenshot, print fps, quit |
| `LINDEFENSE_DEMO=<dir>` | scripted UI walkthrough (all screens, resizes, click-to-place); writes PNGs + PASS/FAIL |
| `LINDEFENSE_HIDDEN=1` | hidden window (automation) |
| `LINDEFENSE_NOSOUND=1` | no audio device |
| `LINDEFENSE_VARIANCE=off` | no Patch Notes / Breaking News |
| `LINDEFENSE_SEED`, `LINDEFENSE_DIFFICULTY`, `LINDEFENSE_QUALITY`, `LINDEFENSE_FPS`, `LINDEFENSE_WINDOWFX=false` | same as the Java `-Dlindefense.*` flags |
| `LINDEFENSE_PREFS_DIR` | where settings / Hero Store progress are saved (default `~/Library/Application Support/Lindefense`) |

## About the UI port

The UI (about 24k lines of Java) was converted with `devtools/j2py.py`, a type-aware transpiler built on `javalang`.
It reads the whole Java project so it knows declared types, which keeps Java semantics intact (integer division,
string concatenation, overloads, field-initialisation order, `long` overflow, NaN-propagating `Math.min/max`, ...).

The few places where the Python version must differ from the Java source (the pygame window instead of Swing,
Python tracebacks, WAV writing, ...) are recorded as patches in `devtools/j2py_patches.py` and re-applied on every run.

Generated files carry a `# j2py-managed` header line. While that line is present, re-running the transpiler
(`.venv/bin/python devtools/j2py.py ../src/lindefense .`) regenerates the file from Java; **delete the line when you
edit a file by hand** and the transpiler will leave it alone. Once the Java tree is retired, simply treat every file as
regular Python source.
