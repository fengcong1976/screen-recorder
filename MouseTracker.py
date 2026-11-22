# -*- coding: utf-8 -*-
"""鼠标点击追踪器

使用 Win32 低级鼠标钩子（WH_MOUSE_LL）在录制期间记录左键点击的
（相对时间，物理屏幕坐标）时间线，供 BeautifyProcessor 生成
"点击自动缩放"美化视频。

说明：
- 低级钩子回调返回的坐标是物理屏幕像素，与进程 DPI 感知无关，
  与 gdigrab 录制的物理像素坐标系一致。
- 纯 ctypes 实现，无第三方依赖。
"""

import ctypes
import json
import threading
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_QUIT = 0x0012


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('pt', wintypes.POINT),
        ('mouseData', wintypes.DWORD),
        ('flags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong,           # 返回 LRESULT（64位下为 LONG_PTR）
    ctypes.c_int,                # nCode
    wintypes.WPARAM,             # wParam
    ctypes.c_longlong            # lParam（LPARAM原始指针值，需要时再cast）
)

# 64位下句柄/指针必须显式声明类型，否则ctypes默认按32位int截断，
# 会导致 SetWindowsHookExW 安装失败
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC,
                                     wintypes.HMODULE, wintypes.DWORD]
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.restype = ctypes.c_longlong
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int,
                                  wintypes.WPARAM, ctypes.c_longlong]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                               wintypes.UINT, wintypes.UINT]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT,
                                      wintypes.WPARAM, ctypes.c_longlong]
user32.PostThreadMessageW.restype = wintypes.BOOL


class MouseTracker():
    """录制期间记录鼠标左键点击时间线"""

    def __init__(self):
        self.events = []           # [{'t': 秒, 'x': 物理px, 'y': 物理px}, ...]
        self._lock = threading.Lock()
        self._t0 = None            # 时间基准（perf_counter）
        self._thread = None
        self._thread_id = 0
        self._running = False
        self._hook = None
        self._proc = None          # 持有钩子回调引用，防止被GC

    def start(self):
        """开始追踪。返回是否成功启动。"""
        if self._running:
            return False
        with self._lock:
            self.events = []
        self._t0 = time.perf_counter()
        self._running = True
        self._thread = threading.Thread(target=self._hook_thread,
                                        name='MouseTracker', daemon=True)
        self._thread.start()
        return True

    def _hook_thread(self):
        """钩子线程：安装低级钩子并运行消息循环"""
        self._thread_id = kernel32.GetCurrentThreadId()
        self._proc = HOOKPROC(self._callback)
        hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc,
                                        kernel32.GetModuleHandleW(None), 0)
        if not hook:
            self._running = False
            err = kernel32.GetLastError()
            print('鼠标钩子安装失败(错误码%d)，本次录制不记录点击' % err)
            return
        self._hook = hook
        msg = wintypes.MSG()
        # 消息循环，收到 WM_QUIT 时退出（GetMessageW 返回 0）
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None

    def _callback(self, nCode, wParam, lParam):
        """低级钩子回调：记录左键按下事件"""
        try:
            if nCode >= 0 and wParam == WM_LBUTTONDOWN and self._running:
                info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                t = time.perf_counter() - self._t0
                with self._lock:
                    self.events.append({
                        't': round(t, 3),
                        'x': int(info.pt.x),
                        'y': int(info.pt.y),
                    })
        except Exception:
            pass
        return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

    def stop(self, save_path=None):
        """停止追踪。返回事件列表；save_path 不为空时另存为 JSON。"""
        if not self._running:
            return []
        self._running = False
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)
        self._thread_id = 0
        with self._lock:
            events = list(self.events)
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump({'events': events}, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print('保存点击事件失败: %s' % e)
        return events


if __name__ == '__main__':
    # 简单自测：运行 5 秒，期间点击鼠标会被记录
    tracker = MouseTracker()
    print('开始追踪 5 秒，请随意点击鼠标...')
    tracker.start()
    time.sleep(5)
    events = tracker.stop()
    print('捕获 %d 次点击:' % len(events))
    for e in events:
        print(e)
