# PyInstaller spec for the macOS app bundle:  .venv/bin/pyinstaller packaging/Lindefense.spec
# (or just run packaging/build_app.sh). Output: dist/Lindefense.app
import os
from PyInstaller.utils.hooks import collect_submodules

HERE = os.path.abspath(os.path.dirname(SPEC))
ROOT = os.path.abspath(os.path.join(HERE, ".."))          # python/
ASSETS = os.path.abspath(os.path.join(ROOT, "..", "assets"))

datas = []
for sub in ("fonts", "sfx", "music"):
    d = os.path.join(ASSETS, sub)
    if os.path.isdir(d):
        datas.append((d, os.path.join("assets", sub)))

a = Analysis(
    [os.path.join(ROOT, "lindefense", "app.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=collect_submodules("lindefense"),
    excludes=["pytest", "tkinter", "javalang"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Lindefense", console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Lindefense", upx=False)
app = BUNDLE(
    coll,
    name="Lindefense.app",
    icon=os.path.join(HERE, "Lindefense.icns"),
    bundle_identifier="dev.lindefense.game",
    info_plist={
        "CFBundleName": "Lindefense",
        "CFBundleDisplayName": "Lindefense",
        "CFBundleShortVersionString": "3.0",
        "CFBundleVersion": "3.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
    },
)
