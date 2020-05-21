# -*- mode: python ; coding: utf-8 -*-
# !!! create virtualenv to disable TQDM unused module

block_cipher = None

app_name = 'mdict'
pkg_path = 'mdict_utils'

script_path = os.path.join(workpath, f'{app_name}-script.py')

with open(script_path, 'wt') as f:
    f.write(f'import {pkg_path}.__main__\n{pkg_path}.__main__.run()')

a = Analysis([script_path],
             pathex=['.'],
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

if False: # one folder
    exe = EXE(pyz,
            a.scripts,
            [],
            exclude_binaries=True,
            name=app_name,
            debug=False,
            bootloader_ignore_signals=False,
            strip=False,
            upx=True,
            console=True )
    coll = COLLECT(exe,
                a.binaries,
                a.zipfiles,
                a.datas,
                strip=False,
                upx=True,
                upx_exclude=[],
                name=app_name)
else: # onefile
    exe = EXE(pyz,
            a.scripts,
            a.binaries,
            a.zipfiles,
            a.datas,
            name=app_name,
            debug=False,
            strip=False,
            upx=True,
            runtime_tmpdir=None,
            console=True )
