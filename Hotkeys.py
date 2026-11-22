# -*- coding: utf-8 -*-
"""Windows 全局热键：基于 RegisterHotKey 原生实现（不依赖 PyHook3）。

用法：
    hk = GlobalHotkeys()
    hk.triggered.connect(callback)      # callback(热键id字符串)
    hk.setup([('screen', [162, 164, 160, 66]), ...])  # VK键码列表
"""

import ctypes
import ctypes.wintypes
import threading

from PySide6.QtCore import QObject, Signal

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8

# 左右修饰键 VK -> RegisterHotKey 修饰标志
_VK_MOD = {
    160: MOD_SHIFT, 161: MOD_SHIFT,      # L/R Shift
    162: MOD_CONTROL, 163: MOD_CONTROL,  # L/R Ctrl
    164: MOD_ALT, 165: MOD_ALT,          # L/R Alt
    91: MOD_WIN, 92: MOD_WIN,            # L/R Win
}


class GlobalHotkeys(QObject):
    """全局热键监听；触发时在主线程发出 triggered(id) 信号"""

    triggered = Signal(str)

    def __init__(self):
        super().__init__()
        self._thread = None
        self._thread_id = None
        self._bindings = []  # [(id, mods, vk), ...]

    def setup(self, bindings):
        """(重)注册热键并开始监听。bindings: [(id字符串, [VK键码...]), ...]"""
        self.stop()
        self._bindings = []
        for hid, keys in bindings:
            mods = 0
            vk = 0
            for k in keys:
                if k in _VK_MOD:
                    mods |= _VK_MOD[k]
                else:
                    vk = k
            if vk:
                self._bindings.append((hid, mods, vk))
        if self._bindings:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def _loop(self):
        """工作线程：注册热键 + 消息循环"""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        registered = []
        for i, (hid, mods, vk) in enumerate(self._bindings, start=1):
            if user32.RegisterHotKey(None, i, mods, vk):
                registered.append((i, hid))
            else:
                print('热键注册失败（可能被其他程序占用）: %s' % hid)
        if not registered:
            return
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                for i, hid in registered:
                    if i == msg.wParam:
                        # 跨线程 emit，Qt 自动以队列方式投递到主线程
                        self.triggered.emit(hid)
        for i, _ in registered:
            user32.UnregisterHotKey(None, i)

    def stop(self):
        """停止监听并注销热键"""
        if self._thread_id:
            try:
                ctypes.windll.kernel32.PostThreadMessageW(
                    self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
        self._thread = None
        self._thread_id = None
