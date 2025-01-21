# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Get base directory
basedir = os.path.abspath(os.path.dirname('__file__'))

# Collect all webview dependencies
webview_datas = collect_data_files('webview')
webview_imports = collect_submodules('webview')

a = Analysis(
    ['main.py'],
    pathex=[basedir],
    binaries=[],
    datas=[
        ('dist/index.html', 'ui'),
        ('dist/assets/*', 'ui/assets'),
        ('setup_dreampi.py', '.'),
        ('router_handlers.py', '.')
    ] + webview_datas,
    hiddenimports=[
        'clr_loader',
        'webview',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'pythonnet',
        'win32api',
        'win32con',
        'win32gui',
        'requests',
        'urllib3',
        'json',
        'bottle'
    ] + webview_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='RetroPortForward',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)