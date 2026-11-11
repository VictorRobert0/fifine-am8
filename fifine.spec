# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec do Fifine AM8 Control (build onedir).
Gera dist/FifineAM8Control/ com o .exe e todas as libs nativas
(rnnoise.dll, PortAudio, etc.). O instalador Inno empacota essa pasta.

Build:  python -m PyInstaller fifine.spec --noconfirm
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("pyrnnoise", "sounddevice", "comtypes", "pycaw", "numpy", "pystray", "PIL"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# ícone acompanha o app (usado pela janela e bandeja)
datas += [("fifine.ico", ".")]

a = Analysis(
    ["fifine_ui.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "tkinter.test", "pywinusb"],  # pywinusb opcional
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="FifineAM8Control",
    console=False,
    icon="fifine.ico",
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name="FifineAM8Control",
)
