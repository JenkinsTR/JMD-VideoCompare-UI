# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for JMD Video Compare UI

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('images', 'images'),
        # Only fonts currently used by the UI.
        ('theme/fonts/BebasNeue-Regular.ttf', 'theme/fonts'),
        ('theme/fonts/Eurostile-Bold.ttf', 'theme/fonts'),
        ('theme/fonts/Eurostile-Regular.ttf', 'theme/fonts'),
        ('theme/fonts/fa-solid-900.ttf', 'theme/fonts'),
    ],
    hiddenimports=['PyQt6.QtWidgets', 'PyQt6.QtGui', 'PyQt6.QtCore'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='JMD-VideoCompare-UI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
