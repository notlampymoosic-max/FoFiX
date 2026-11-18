# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['FoFiX.py'],
             pathex=['C:\\Users\\vpsam\\Documents\\My Games\\FoFiX\\src'],
             binaries=[],
             datas=[('../data', 'data')],
             hiddenimports=['Tkinter', 'tkFileDialog', 'tkCommonDialog', 'FileDialog'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='FoFiX',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False , icon='fofix.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='FoFiX')
