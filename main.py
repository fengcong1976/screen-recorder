#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
影随录屏启动脚本
基于专业录屏软件设计，提供更优质的用户体验
"""

import sys
import os

# ---- 崩溃日志加固：stderr/stdout 重定向 + 全局/线程异常钩子 ----
# 窗口化 exe 中未捕获异常会无声退出（线程异常甚至直接中止进程），
# 统一落盘到 %LOCALAPPDATA%\影随录屏\crash.log 便于排查。
def _setup_crash_log():
    try:
        log_dir = os.path.join(
            os.environ.get('LOCALAPPDATA',
                           os.path.expanduser('~\\AppData\\Local')),
            '影随录屏')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'crash.log')
        sys.stderr = sys.stdout = open(log_path, 'a', buffering=1,
                                       encoding='utf-8', errors='replace')
        import threading
        sys.excepthook = lambda t, v, b: print('[EXC]', t.__name__, v, b)
        threading.excepthook = lambda a: print(
            '[THREAD-EXC]', a.exc_type.__name__, a.exc_value, a.exc_traceback)
    except Exception:
        pass

_setup_crash_log()

# 设置环境变量解决编码问题（可选）
# if sys.platform == 'win32':
#     import locale
#     locale.setlocale(locale.LC_ALL, 'Chinese (Simplified)_China.utf8')

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

print("启动影随录屏...")
print("Python版本:", sys.version)
print("当前目录:", current_dir)

# ---- Qt平台插件路径修复 ----
# 部分机器上 PySide6 不会自动定位 PySide6-Qt6 自带的平台插件，
# 导致 QApplication 报 "no Qt platform plugin could be initialized"。
# 这里在加载Qt前显式指定插件目录（PyInstaller打包的frozen环境不需要）。
if not getattr(sys, 'frozen', False):
    try:
        import PySide6
        _qt5_root = os.path.join(os.path.dirname(PySide6.__file__), 'Qt6')
        if os.path.isdir(_qt5_root):
            os.environ.setdefault('QT_PLUGIN_PATH',
                                  os.path.join(_qt5_root, 'plugins'))
            os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH',
                                  os.path.join(_qt5_root, 'plugins', 'platforms'))
            _qt5_bin = os.path.join(_qt5_root, 'bin')
            if _qt5_bin not in os.environ.get('PATH', ''):
                os.environ['PATH'] = _qt5_bin + os.pathsep + os.environ.get('PATH', '')
            print("Qt插件路径已修复:", _qt5_root)
    except Exception as _e:
        print("Qt插件路径修复跳过: %s" % _e)

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import Qt, QCoreApplication, QTimer, QEvent
    from PySide6.QtWidgets import QLCDNumber
    
    print("PySide6模块导入成功")
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle('Fusion')  # 设置现代样式
    print("QApplication创建成功")

    # 单实例锁：避免同时运行两个实例造成托盘/录制混淆
    import tempfile
    from PySide6.QtCore import QLockFile
    _lock = QLockFile(os.path.join(tempfile.gettempdir(),
                                   'YingSuiLuPing_single.lock'))
    if not _lock.tryLock(100):
        print("已有影随录屏在运行，本次启动取消")
        QtWidgets.QMessageBox.warning(
            None, '影随录屏已在运行',
            '影随录屏已经在运行了。\n\n'
            '请使用桌面上的主窗口或右下角托盘图标，无需重复打开。')
        sys.exit(0)
    
    # 导入现代化录制窗口
    from RecordWindowModern import ModernRecordWindow
    print("ModernRecordWindow导入成功")
    
    # 获取屏幕分辨率
    screen = app.primaryScreen().geometry()
    resolution = '{}x{}'.format(screen.width(), screen.height())
    print(f"屏幕分辨率: {resolution}")
    
    # 创建主窗口
    rw = ModernRecordWindow(screen_resolution=resolution)
    print("现代化主窗口创建成功")
    
    # 启动快捷键功能
    rw.monitor_shortcut()
    
    # 显示托盘图标
    if hasattr(rw, 'rti') and rw.rti:
        rw.rti.show()
        print("托盘图标显示成功")
    
    # 显示主窗口
    rw.show()
    print("主窗口显示成功")
    
    print("\n影随录屏启动完成!")
    print("\n功能特性:")
    print("  专业界面设计 - 基于现代录屏软件设计模式")
    print("  屏幕录制 - 支持全屏和区域选择录制")
    print("  暂停功能 - 支持录制暂停和继续")
    print("  实时计时 - 显示录制时长")
    print("  快捷键 - 支持键盘快捷操作")
    print("  托盘集成 - 系统托盘后台运行")
    
    print("\n操作指南:")
    print("  全屏录制 - 选择'录制屏幕' > '全屏幕'，点击开始录制")
    print("  区域录制 - 选择'录制屏幕' > '选择区域' > '选择录制区域'")
    print("  暂停录制 - 录制中点击'暂停'按钮")
    print("  停止录制 - 录制中点击'停止'按钮")
    print("  快捷键 - Ctrl+Shift+R(开始录制) Ctrl+Shift+S(停止录制)")
    
    print("\n使用提示:")
    print("  - 全屏录制时主窗口会自动最小化")
    print("  - 区域选择支持ESC键取消")
    print("  - 右键点击窗口访问更多功能")
    print("  - 录制完成自动停止计时器")
    
    # 运行应用
    sys.exit(app.exec())
    
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所需依赖: pip install PySide6 psutil pywin32")
    sys.exit(1)
    
except Exception as e:
    print(f"启动错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)