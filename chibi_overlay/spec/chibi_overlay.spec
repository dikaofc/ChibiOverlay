# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['..\\..\\run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('..\\..\\profiles', 'profiles'),
        ('..\\..\\assets', 'assets'),
    ],
    hiddenimports=[
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ChibiOverlay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='..\\..\\chibi_overlay.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ChibiOverlay',
)
