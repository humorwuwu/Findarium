# -*- mode: python ; coding: utf-8 -*-
"""Single-file (PyInstaller onefile) executable.

Produces ``dist-onefile/Findarium``: one Mach-O file containing Python,
FastAPI, pywebview, the extractors, the semantic runtime and the built frontend.
The first launch extracts to a temporary directory, so startup is slower than
the onedir .app; use the .app for day-to-day double-click use.
"""
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

ROOT = Path(SPECPATH).parent

datas = [(str(ROOT / "frontend" / "dist"), "frontend/dist")]
datas += collect_data_files("jieba")
datas += collect_data_files("fastembed")
binaries = collect_dynamic_libs("onnxruntime") + collect_dynamic_libs("pymupdf")

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "watchdog.observers.fsevents",
    "webview.platforms.cocoa",
    "jieba.analyse",
    "fastembed",
    "onnxruntime",
    "pymupdf",
    "docx",
    "openpyxl",
    "pptx",
    "bs4",
    "markdown_it",
    "charset_normalizer",
    "rapidfuzz",
    "numpy",
    "olefile",
    "platformdirs",
]
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("webview")

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pandas", "scipy"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Findarium",
    icon=str(ROOT / "packaging" / "AppIcon.icns"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)
