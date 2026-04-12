# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — pdf_prepress (onedir, windowed).

Запускати з папки build/:
    python -m PyInstaller build.spec --distpath ../dist --workpath ../build_tmp

SPECPATH — автоматично встановлюється PyInstaller як папка, де лежить цей файл.
"""
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── Directories ────────────────────────────────────────────────────────────
ROOT_DIR     = os.path.dirname(SPECPATH)
PREPRESS_DIR = os.path.join(ROOT_DIR, 'pdf_prepress')
GS_DIR       = os.path.join(SPECPATH, 'ghostscript')
ICON_FILE    = os.path.join(ROOT_DIR, 'icon.ico')

# ── Collect pywebview data + submodules ────────────────────────────────────
datas_webview  = collect_data_files('webview')
hidden_webview = collect_submodules('webview')

# ── Datas: (source, dest_folder_in_bundle) ────────────────────────────────
datas = [
    (os.path.join(PREPRESS_DIR, 'ui'),           'ui'),
    (os.path.join(PREPRESS_DIR, 'icc_profiles'), 'icc_profiles'),
] + datas_webview

# Bundle Ghostscript only if the files have been placed in build/ghostscript/
if os.path.isfile(os.path.join(GS_DIR, 'bin', 'gswin64c.exe')):
    datas.append((GS_DIR, 'gs'))

# ── Analysis ───────────────────────────────────────────────────────────────
a = Analysis(
    [os.path.join(PREPRESS_DIR, 'main.py')],
    pathex=[PREPRESS_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'webview.platforms.winforms',
        'clr',
        'System',
        'System.Windows.Forms',
        'pythonnet',
    ] + hidden_webview,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy.testing', 'PIL.ImageTk'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pdf_prepress',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pdf_prepress',
)
