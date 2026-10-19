# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
]
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
    [],
    exclude_binaries=True,
    name="Findarium",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Findarium",
)
app = BUNDLE(
    coll,
    name="Findarium.app",
    icon=str(ROOT / "packaging" / "AppIcon.icns"),
    bundle_identifier="com.findarium.desktop",
    info_plist={
        "CFBundleDisplayName": "寻册",
        "CFBundleShortVersionString": "0.1.0",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSDesktopFolderUsageDescription": "寻册需要读取你选择的目录来建立本地内容索引。",
        "NSDocumentsFolderUsageDescription": "寻册需要读取你选择的目录来建立本地内容索引。",
        "NSDownloadsFolderUsageDescription": "寻册需要读取你选择的目录来建立本地内容索引。",
        "NSNetworkVolumesUsageDescription": "寻册需要读取你选择的网络卷来建立本地内容索引。",
        "NSRemovableVolumesUsageDescription": "寻册需要读取你选择的外接磁盘来建立本地内容索引。",
    },
)
