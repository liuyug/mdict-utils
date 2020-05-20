# -*- mode: python ; coding: utf-8 -*-
# !!! create virtualenv to disable TQDM unused module

block_cipher = None

script_path = os.path.join(workpath, 'mdict-script.py')

with open(script_path, 'wt') as f:
    f.write('import mdict_utils.__main__\nmdict_utils.__main__.run()')

a = Analysis([script_path],
             pathex=[workpath, '.'],
             binaries=[],
             datas=[],
             hiddenimports=['pkg_resources.py2_warn'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

# one folder
# exe = EXE(pyz,
#           a.scripts,
#           [],
#           exclude_binaries=True,
#           name='mdict_utils',
#           debug=False,
#           bootloader_ignore_signals=False,
#           strip=False,
#           upx=True,
#           console=True )
# coll = COLLECT(exe,
#                a.binaries,
#                a.zipfiles,
#                a.datas,
#                strip=False,
#                upx=True,
#                upx_exclude=[],
#                name='mdict_utils')

# onefile
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='mdict',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True )
