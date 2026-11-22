# -*- coding: utf-8 -*-
"""录制中的悬浮指示条：红点 + 实时时长，置顶、可拖动。

放在录制区域外（如区域正上方）时不会被录进视频；
全屏录制或拖入区域内则会入镜，用户可自行拖动调整。
"""

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt, QTimer


class RecIndicator(QtWidgets.QWidget):
    """录制中/已暂停的悬浮提示条"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._drag_offset = None
        self._elapsed = -1  # 首次 _tick 后从 00:00 开始
        self._paused = False

        self.label = QtWidgets.QLabel()
        self.label.setStyleSheet(
            "color:#ffffff; background:transparent;"
            "font-size:14px; font-weight:bold;")
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(16, 7, 16, 7)
        lay.addWidget(self.label)
        self.setStyleSheet("QWidget { background: rgba(25,25,25,205);"
                           "border-radius: 12px; }")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def showEvent(self, e):
        super().showEvent(e)
        # 显示后才能拿到有效 winId
        self._apply_capture_exclusion()

    # ------------------------------------------------------------------
    def _tick(self):
        if not self._paused:
            self._elapsed += 1
        m, s = divmod(self._elapsed, 60)
        h, m = divmod(m, 60)
        t = '%02d:%02d:%02d' % (h, m, s) if h else '%02d:%02d' % (m, s)
        if self._paused:
            self.label.setText('<span style="color:#ffc107">⏸</span> 已暂停 %s' % t)
        else:
            self.label.setText('<span style="color:#ff5252">●</span> 录制中 %s' % t)

    def set_paused(self, paused):
        self._paused = bool(paused)
        self._tick()

    def place_outside(self, region):
        """把指示条放到录制区域外的屏幕边缘，返回是否成功。

        依次尝试：区域上方 -> 下方 -> 左侧 -> 右侧；都放不下返回 False
        （调用方应不显示指示条，避免它被录进视频）。
        注意：gdigrab 采集不响应 WDA_EXCLUDEFROMCAPTURE，
        所以"不进画面"只能靠放在录制区域外来保证。
        """
        hint = self.sizeHint()
        self.setFixedSize(hint)
        W, H = hint.width(), hint.height()
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        x, y, w, h = region
        gap = 8
        candidates = [
            (x + w - W - 12, y - H - gap),   # 区域正上方
            (x + w - W - 12, y + h + gap),   # 区域正下方
            (x - W - gap, y),                # 区域左侧
            (x + w + gap, y),                # 区域右侧
        ]
        for cx, cy in candidates:
            if screen.left() <= cx and cx + W <= screen.right() \
                    and screen.top() <= cy and cy + H <= screen.bottom():
                self.move(cx, cy)
                return True
        return False

    def _apply_capture_exclusion(self):
        """让本窗口不进入任何屏幕采集（录屏/截图里看不到，肉眼可见）。

        WDA_EXCLUDEFROMCAPTURE 需要 Windows 10 2004+；失败则静默忽略。
        """
        try:
            import ctypes
            hwnd = int(self.winId())
            WDA_EXCLUDEFROMCAPTURE = 0x00000011
            ok = ctypes.windll.user32.SetWindowDisplayAffinity(
                hwnd, WDA_EXCLUDEFROMCAPTURE)
            print('录制指示条采集排除: %s' % ('生效' if ok else '不支持'))
        except Exception as e:
            print('录制指示条采集排除失败: %s' % e)

    # ------------------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (e.globalPosition().toPoint()
                                 - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and (
                e.buttons() & Qt.MouseButton.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, e):
        self._drag_offset = None
