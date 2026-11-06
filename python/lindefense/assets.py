"""Locates the bundled assets directory from any working directory (source tree, run.sh, or a packaged .app)."""
import os
import sys


def roots():
    """Candidate project roots, most specific first."""
    out = []
    env = os.environ.get("LINDEFENSE_ASSETS")
    if env:
        out.append(os.path.dirname(os.path.abspath(env)))
    base = getattr(sys, "_MEIPASS", None)   # PyInstaller bundle
    if base:
        out.append(base)
    here = os.path.dirname(os.path.abspath(__file__))
    for up in range(1, 5):
        out.append(os.path.normpath(os.path.join(here, *([".."] * up))))
    out.append(os.getcwd())
    return out


def path(rel):
    """Absolute path of rel (e.g. "assets/fonts") under the first root where it exists."""
    for r in roots():
        p = os.path.join(r, rel)
        if os.path.exists(p):
            return p
    return os.path.join(os.getcwd(), rel)


def file(rel):
    from lindefense.ui.jrt import File
    return File(path(rel))


class Assets:
    """Class-style entry points used by the ported UI."""
    roots = staticmethod(roots)
    file = staticmethod(file)
    path = staticmethod(path)
