# PyInstaller spec for the desktop app.
#
# Build from this folder:  pyinstaller AbyssTracker.spec
#   Windows: dist/AbyssTracker.exe (one file)
#   macOS:   dist/AbyssTracker.app
#
# Everything in assets/ (icon, fonts) is bundled and found through theme.asset_path.
import sys

from PyInstaller.utils.hooks import collect_data_files

NAME = "AbyssTracker"
MAC = sys.platform == "darwin"
ICON = "assets/icon.icns" if MAC else "assets/icon.ico"

a = Analysis(
    ["gui.py"],
    datas=collect_data_files("customtkinter") + [("assets", "assets")],
    excludes=["colorama"],  # only used by the terminal tracker
)
pyz = PYZ(a.pure)

if MAC:
    # One-folder build wrapped in an .app; one-file .app bundles are deprecated
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False, icon=ICON)
    coll = COLLECT(exe, a.binaries, a.datas, name=NAME)
    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        icon=ICON,
        bundle_identifier="com.fazorath.abysstracker",
        info_plist={"CFBundleDisplayName": "Abyss Tracker", "NSHighResolutionCapable": True},
    )
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name=NAME, console=False, icon=ICON)
