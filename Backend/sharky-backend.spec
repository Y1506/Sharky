# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Sharky Backend sidecar.
Produces a one-directory distribution that Tauri bundles as an external binary.
"""

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('download_manager', 'download_manager'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        'fastapi',
        'yt_dlp',
        'websockets',
        'httpx',
        'rich',
        'requests',
        'psutil',
        'textual',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'test',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='sharky-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='sharky-backend',
)
