# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Base directory
base_dir = os.path.abspath(SPECPATH)
src_dir = os.path.join(base_dir, 'src')
data_dir = os.path.join(base_dir, 'data')

# Hidden imports needed for FoFiX
hidden_imports = [
    'tkinter',
    'tkinter.filedialog',
    'tkinter.commondialog',
    'sng_parser',
    'sng_parser.decode',
    'sng_parser.common',
    'soundfile',
    'cffi',
    'PIL',
    'PIL.Image',
    'OpenGL',
    'OpenGL.GL',
    'OpenGL.GLU',
    'OpenGL.platform',
    'pygame',
    'numpy',
] + collect_submodules('OpenGL')

# Collect data directory (excluding songs to keep bundle lightweight)
data_files = []
for root, dirs, files in os.walk(data_dir):
    # Exclude .DS_Store, cache files, and heavy song charts from the internal bundle
    rel_root = os.path.relpath(root, data_dir)
    if rel_root.startswith('songs') and rel_root != 'songs':
        continue
    for f in files:
        if f.startswith('.') or f.endswith('.pyc') or f.endswith('.sng'):
            continue
        src_path = os.path.join(root, f)
        target_dir = os.path.join('data', rel_root) if rel_root != '.' else 'data'
        data_files.append((src_path, target_dir))

a = Analysis(
    [os.path.join(src_dir, 'FoFiX.py')],
    pathex=[src_dir],
    binaries=[],
    datas=data_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['Tkinter', 'tkFileDialog'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FoFiX',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FoFiX'
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='FoFiX.app',
        icon=None,
        bundle_identifier='net.fofix.game',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': '3.123',
            'CFBundleDisplayName': 'FoFiX',
        }
    )
