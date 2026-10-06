# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_dynamic_libs
from PyInstaller.utils.hooks import collect_all

project_root = Path(SPEC).resolve().parents[2]
datas = []
datas += [(str(project_root / 'web' / 'dist'), 'web/dist')]
binaries = []
hiddenimports = []
for package in ('webview','pythonnet','clr_loader'):
    datas += collect_data_files(package)
    binaries += collect_dynamic_libs(package)
hiddenimports += ['webview.platforms.winforms','webview.platforms.edgechromium',
                  'clr','pythonnet','clr_loader','_cffi_backend']
datas += [(str(project_root / 'assets' / 'icon.ico'),'assets')]
datas += collect_data_files('onnxruntime')
binaries += collect_dynamic_libs('onnxruntime')
tmp_ret = collect_all('rapidocr_onnxruntime')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5','PyQt6','PySide2','PySide6','gi','webview.platforms.qt','webview.platforms.gtk',
              'webview.platforms.cef','webview.platforms.cocoa','webview.platforms.android','webview.platforms.mshtml'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ChatReplyAssistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(project_root / 'assets' / 'icon.ico')],
)
