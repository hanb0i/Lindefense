"""Hand adaptations applied by j2py after generating a module, so ported files stay regenerable.

Each entry maps a generated module (path relative to the python root) to a list of operations:
  ("replace", old, new)               old must occur in the generated text
  ("region", start, end, new)         replaces from `start` (inclusive) up to `end` (exclusive)
  ("append", text)                    appended at the end of the module
"""

PATCHES = {
    # ------------------------------------------------------------------ main menu footer names the Python stack
    "lindefense/ui/menu_screen.py": [
        ("replace", "'JAVA + STANFORD ACM GRAPHICS  •  RESIZE THE WINDOW FREELY'",
         "'PYTHON + SKIA GRAPHICS  •  RESIZE THE WINDOW FREELY'"),
    ],
    # ------------------------------------------------------------------ module-level aliases used by tests
    "lindefense/ui/intrusion_text.py": [
        ("append", """
# module-level aliases (tests and hand-written code use the functions directly)
IMMUNE = IntrusionText.IMMUNE
tower_line = IntrusionText.tower_line
is_warning = IntrusionText.is_warning
type_line = IntrusionText.type_line
firewall_line = IntrusionText.firewall_line
vulnerable_line = IntrusionText.vulnerable_line
enemy_line = IntrusionText.enemy_line
state_key = IntrusionText.state_key
"""),
    ],
    # ------------------------------------------------------------------ scripted demo: pygame window resize
    "lindefense/ui/demo_driver.py": [
        ("replace", """        win = SwingUtilities.get_window_ancestor(self.app.get_g_canvas())
        win.set_size(w, h)
        win.validate()""", """        self.app.resize_window(w, h)"""),
    ],
    # ------------------------------------------------------------------ SfxSynth: WAV output via the wave module
    "lindefense/tools/sfx_synth.py": [
        ("region", "    def write(dir_, name, b):", "    @staticmethod\n    def main(args):", '''    def write(dir_, name, b):
        """Writes 16-bit PCM mono little-endian WAV."""
        import struct
        import wave
        frames = b"".join(struct.pack("<h", int(max(-32767, min(32767, _j.jround(x * 32767.0))))) for x in b.d)
        with wave.open(_j.File(dir_, _j.cat(name, '.wav')).path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(SfxSynth.RATE))
            w.writeframes(frames)
'''),
    ],
    # ------------------------------------------------------------------ PerfBench: no JVM management beans
    "lindefense/tools/perf_bench.py": [
        ("replace", "import math\n", "import math\nimport struct\n\n\ndef _dbits(x):\n    return struct.unpack('<q', struct.pack('<d', float(x)))[0]\n"),
        ("replace", "return PerfBench.THREADS.get_thread_allocated_bytes(None.get_id()) if PerfBench.THREADS.is_thread_allocated_memory_supported() else 0",
         "return 0   # no per-thread allocation counter in CPython"),
        ("replace", "return PerfBench.THREADS.get_current_thread_cpu_time() if PerfBench.CPU_CLOCK else _j.nano_time()",
         "return __import__('time').thread_time_ns() if PerfBench.CPU_CLOCK else _j.nano_time()"),
        ("replace", "ManagementFactory.get_operating_system_mx_bean().get_system_load_average()", "__import__('os').getloadavg()[0]"),
        ("replace", "Double.double_to_long_bits(g.get_cash())", "_dbits(g.get_cash())"),
        ("replace", "Double.double_to_long_bits(t.get_damage_dealt())", "_dbits(t.get_damage_dealt())"),
        ("replace", "            Class.for_name('lindefense.ui.LindefenseProgram').get_method('configureCanvas', GCanvas).invoke(None, canvas)\n",
         "            canvas.set_auto_repaint_flag(False)\n            canvas.set_native_arc_flag(True)\n"),
        ("replace", """        for b in ManagementFactory.get_garbage_collector_mx_beans():
            n += max(0, b.get_collection_count())""", """        import gc
        n += sum(st.get("collections", 0) for st in gc.get_stats())"""),
        ("replace", "PerfBench.THREADS = ManagementFactory.get_thread_mx_bean()", "PerfBench.THREADS = None"),
    ],
    # ------------------------------------------------------------------ RenderSoak: pygame app, Python tracebacks
    "lindefense/tools/render_soak.py": [
        ("replace", "import math\n", "import math\nimport os\nimport sys\n"),
        ("region", "        RenderSoak.log = PrintWriter(FileWriter(log_name), True)", "        t0 = _j.current_time_millis()", '''        os.makedirs(os.path.dirname(log_name), exist_ok=True)
        RenderSoak.log = PrintWriter(FileWriter(log_name), True)
        os.environ.setdefault("LINDEFENSE_HIDDEN", "1")
        os.environ.setdefault("LINDEFENSE_NOSOUND", "1")
        from lindefense.app import LindefenseApp
        RenderSoak.app = LindefenseApp()
        RenderSoak.app.show_menu()
        def _lam1():
            raise RuntimeError('render-soak selftest')
        RenderSoak.edt('selftest', _j.Fn(_lam1))
        captured = any('selftest' in k for k in RenderSoak.SEEN)
        for k in [k for k in RenderSoak.SEEN if 'selftest' in k]:
            del RenderSoak.SEEN[k]
        print(_j.s(('PASS self-test: exceptions are captured' if captured else 'FAIL self-test: exception was not captured')))
        if not captured:
            sys.exit(2)
'''),
        ("region", "    def record(where, e):", "    @staticmethod\n    def edt(where, a):", '''    def record(where, e):
        import traceback
        frames = traceback.extract_tb(e.__traceback__)[-5:]
        key = _j.StringBuilder(type(e).__name__)
        key.append(': ').append(_j.replace_all(str(e), '[0-9.\\\\-]+', '#'))
        for fr in reversed(frames):
            key.append('\\n  at ').append('%s:%s %s' % (os.path.basename(fr.filename), fr.lineno, fr.name))
        k = key.to_string()
        n = _j_compute_if_absent(RenderSoak.SEEN, k, _j.Fn(lambda x: ([0] * 1)))
        n[0] += 1
        if n[0] == 1:
            full = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            _j_put(RenderSoak.FIRST, k, full)
            RenderSoak.log.println(_j.cat('---- [', where, '] ', full))
            if not ('selftest' in k):
                print(_j.s(_j.cat('   NEW ERROR [', where, '] ', _j.split(k, '\\n')[0], ' | ', k.split('\\n')[1] if '\\n' in k else '')))
'''),
        ("replace", """        win = SwingUtilities.get_window_ancestor(RenderSoak.app.get_g_canvas())
        win.set_size(w, h)
        win.validate()""", """        RenderSoak.app.resize_window(w, h)"""),
        ("replace", "from lindefense.ui.lindefense_program import LindefenseProgram  # noqa: E402\n", ""),
    ],
}


def apply(module_rel, text, warn):
    """Applies the patches for module_rel (posix path) to text; warn(msg) reports anchors that no longer match."""
    for op in PATCHES.get(module_rel, ()):
        kind = op[0]
        if kind == "replace":
            old, new = op[1], op[2]
            if old not in text:
                warn("patch anchor not found in %s: %r" % (module_rel, old[:60]))
                continue
            text = text.replace(old, new, 1)
        elif kind == "region":
            start, end, new = op[1], op[2], op[3]
            i = text.find(start)
            j = text.find(end, i + 1) if i >= 0 else -1
            if i < 0 or j < 0:
                warn("patch region not found in %s: %r" % (module_rel, start[:60]))
                continue
            text = text[:i] + new + text[j:]
        elif kind == "append":
            text = text.rstrip("\n") + "\n" + op[1]
    return text
