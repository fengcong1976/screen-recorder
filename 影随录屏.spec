# -*- mode: python ; coding: utf-8 -*-
# 影随录屏 PyInstaller 打包配置（目录模式）
# ffmpeg-shared、resource、图标.png、configByLinxiao.ini 不打进包，
# 由安装程序/绿色版包放到 exe 同级目录。

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('图标.png', '.'),
        ('resource', 'resource'),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5'],
    noarchive=True,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='影随录屏',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='图标.ico',
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='影随录屏',
)
