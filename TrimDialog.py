# -*- coding: utf-8 -*-
"""视频裁剪对话框：视频窗口预览 + 一条时间进度条。

进度条上：
  - 蓝色手柄（两端）= 开始点 / 结束点，拖动设置保留范围
  - 红色竖线 = 当前播放位置，点击进度条任意处跳转播放
开始点之前、结束点之后的内容被裁掉，只保留中间一段（导出用 ffmpeg 重编码，精确到帧）。
"""

import os
import re
import subprocess
import threading

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from BeautifyProcessor import get_ffmpeg_path


def _ffmpeg():
    return get_ffmpeg_path() or 'ffmpeg'


def probe_duration(path):
    """用 ffmpeg -i 解析视频总时长（秒）"""
    try:
        p = subprocess.run([_ffmpeg(), '-i', path], capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           timeout=15)
        m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', p.stderr)
        if m:
            h, mn, s = m.groups()
            return int(h) * 3600 + int(mn) * 60 + float(s)
    except Exception as e:
        print('读取视频时长失败: %s' % e)
    return 0.0


def fmt_time(t):
    m, s = divmod(int(t), 60)
    h, m = divmod(m, 60)
    if h:
        return '%d:%02d:%02d' % (h, m, s)
    return '%02d:%02d' % (m, s)


class TimelineBar(QtWidgets.QWidget):
    """时间进度条：播放进度 + 开始/结束手柄 + 保留范围，一条全搞定"""

    changed = None   # 范围变化回调
    seek_to = None   # 跳转播放回调 callable(ms)

    def __init__(self, duration_ms=0):
        super().__init__()
        self.duration_ms = max(duration_ms, 1)
        self.start_ms = 0
        self.end_ms = self.duration_ms
        self.playhead_ms = 0
        self._drag = None  # 'start' / 'end' / 'play'
        self.scrub_start = None  # 开始拖播放线回调（暂停播放）
        self.scrub_end = None    # 结束拖播放线回调（恢复播放）
        self.setFixedHeight(38)
        self.setMinimumWidth(300)

    def set_duration(self, ms):
        self.duration_ms = max(ms, 1)
        self.end_ms = min(self.end_ms, self.duration_ms)
        self.update()

    def set_playhead(self, ms):
        self.playhead_ms = ms
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        track_y, track_h = h // 2 - 6, 12
        # 底轨（被裁掉的部分：深灰）
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(205, 205, 205))
        p.drawRoundedRect(0, track_y, w, track_h, 6, 6)
        # 已播放进度（浅蓝叠加在保留段/底轨上）
        px = int(w * self.playhead_ms / self.duration_ms)
        p.setBrush(QColor(144, 202, 249))
        p.drawRoundedRect(0, track_y, px, track_h, 6, 6)
        # 保留段（绿色）
        x0 = int(w * self.start_ms / self.duration_ms)
        x1 = int(w * self.end_ms / self.duration_ms)
        p.setBrush(QColor(76, 175, 80, 120))
        p.drawRoundedRect(x0, track_y, max(x1 - x0, 2), track_h, 6, 6)
        p.setPen(QPen(QColor(33, 150, 83), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(x0, track_y, max(x1 - x0, 2), track_h, 6, 6)
        # 开始/结束手柄（蓝色竖条，上下超出轨道方便抓取）
        p.setBrush(QColor(25, 118, 210))
        p.setPen(QPen(QColor(255, 255, 255), 1))
        for xx in (x0, x1):
            p.drawRoundedRect(xx - 4, track_y - 7, 8, track_h + 14, 3, 3)
        # 播放位置红线
        p.setPen(QPen(QColor(229, 57, 53), 2))
        p.drawLine(px, 2, px, h - 2)
        # 红线顶部小三角
        p.setBrush(QColor(229, 57, 53))
        p.setPen(Qt.PenStyle.NoPen)
        from PySide6.QtCore import QPointF
        p.drawPolygon([QPointF(px - 5, 2), QPointF(px + 5, 2), QPointF(px, 9)])
        p.end()

    # ------------------------------------------------------------------
    def _ms_at(self, x):
        return max(0, min(self.duration_ms,
                          int(x / max(self.width(), 1) * self.duration_ms)))

    def mousePressEvent(self, e):
        w = max(self.width(), 1)
        x0 = w * self.start_ms / self.duration_ms
        x1 = w * self.end_ms / self.duration_ms
        x, y = e.position().x(), e.position().y()
        if y <= 13:
            # 顶部区域是红色播放线专属（红三角所在），避免与手柄重叠时抢不到
            self._drag = 'play'
        elif abs(x - x0) <= 8:
            self._drag = 'start'
        elif abs(x - x1) <= 8:
            self._drag = 'end'
        else:
            self._drag = 'play'
            self.playhead_ms = self._ms_at(x)
            if self.seek_to:
                self.seek_to(self.playhead_ms)
        if self._drag == 'play' and self.scrub_start:
            self.scrub_start()
        self.update()

    def mouseMoveEvent(self, e):
        if not self._drag:
            return
        ms = self._ms_at(e.position().x())
        if self._drag == 'start':
            self.start_ms = min(ms, self.end_ms - 200)
        elif self._drag == 'end':
            self.end_ms = max(ms, self.start_ms + 200)
        else:  # 拖动播放位置
            self.playhead_ms = ms
            if self.seek_to:
                self.seek_to(ms)
        self.update()
        if self.changed:
            self.changed()

    def mouseReleaseEvent(self, _):
        if self._drag == 'play' and self.scrub_end:
            self.scrub_end()
        self._drag = None


class TrimDialog(QtWidgets.QDialog):
    """视频窗口预览 + 单条时间进度条裁剪"""

    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle('裁剪视频 - 影随录屏')
        self.resize(980, 760)
        self.video = video_path
        self._export_thread = None
        self._export_ok = False

        # 播放器
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(1.0)
        self.player.setSource(QUrl.fromLocalFile(video_path))
        self.duration_ms = int(probe_duration(video_path) * 1000)

        root = QtWidgets.QVBoxLayout(self)

        info = QtWidgets.QLabel('文件：%s　总时长 %s　—　拖动蓝色手柄设开始/结束点，'
                                '点击进度条跳转播放，保留中间一段。'
                                % (os.path.basename(video_path),
                                   fmt_time(self.duration_ms / 1000.0)))
        info.setStyleSheet('font-size: 13px; color: #333;')
        root.addWidget(info)

        # 视频窗口（随窗口放大）
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(400)
        self.player.setVideoOutput(self.video_widget)
        root.addWidget(self.video_widget, 1)

        # 播放控制：播放按钮 + 当前时间
        ctrl = QtWidgets.QHBoxLayout()
        self.btn_play = QtWidgets.QPushButton('▶ 播放')
        self.btn_play.setFixedWidth(86)
        self.btn_play.clicked.connect(self._toggle_play)
        self.lb_pos = QtWidgets.QLabel('00:00')
        self.lb_pos.setFixedWidth(56)
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.lb_pos)
        ctrl.addStretch(1)
        root.addLayout(ctrl)

        # 时间进度条（播放位置 + 开始/结束点都在这条上）
        self.timeline = TimelineBar(self.duration_ms)
        self.timeline.changed = self._sync_labels
        self.timeline.seek_to = self.player.setPosition
        self.timeline.scrub_start = self._scrub_start
        self.timeline.scrub_end = self._scrub_end
        root.addWidget(self.timeline)

        # 时间刻度：总时长
        row_t = QtWidgets.QHBoxLayout()
        self.lb_start = QtWidgets.QLabel('开始 00:00')
        self.lb_total = QtWidgets.QLabel(fmt_time(self.duration_ms / 1000.0))
        self.lb_end = QtWidgets.QLabel('结束 %s' % fmt_time(self.duration_ms / 1000.0))
        for lb, align in ((self.lb_start, Qt.AlignmentFlag.AlignLeft),
                          (self.lb_total, Qt.AlignmentFlag.AlignCenter),
                          (self.lb_end, Qt.AlignmentFlag.AlignRight)):
            lb.setStyleSheet('color: #777; font-size: 12px;')
            row_t.addWidget(lb, 1, align)
        root.addLayout(row_t)

        # 辅助设点按钮 + 保留信息
        row = QtWidgets.QHBoxLayout()
        btn_s = QtWidgets.QPushButton('当前位置设为开始点')
        btn_s.clicked.connect(self._set_start_here)
        btn_e = QtWidgets.QPushButton('当前位置设为结束点')
        btn_e.clicked.connect(self._set_end_here)
        row.addWidget(btn_s)
        row.addWidget(btn_e)
        row.addStretch(1)
        self.lb_keep = QtWidgets.QLabel()
        self.lb_keep.setStyleSheet('font-size: 13px; font-weight: bold; color: #2196F3;')
        row.addWidget(self.lb_keep)
        root.addLayout(row)

        # 底部按钮
        btns = QtWidgets.QHBoxLayout()
        self.btn_export = QtWidgets.QPushButton('导出裁剪后的视频')
        self.btn_export.setStyleSheet(
            'QPushButton { background:#2196F3; color:white; padding:7px 18px;'
            'border-radius:4px; font-size:14px; font-weight:bold; }'
            'QPushButton:hover { background:#1976D2; }'
            'QPushButton:disabled { background:#9ec7ee; }')
        self.btn_export.clicked.connect(self._export)
        btn_cancel = QtWidgets.QPushButton('关闭')
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(self.btn_export)
        btns.addWidget(btn_cancel)
        root.addLayout(btns)

        # 信号
        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.playbackStateChanged.connect(self._on_state)

        self._sync_labels()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_export)
        self._poll_timer.start(200)

    # ------------------------------------------------------------------
    def _scrub_start(self):
        """开始拖播放线：暂停播放，松手后按原状态恢复"""
        self._was_playing = (
            self.player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState)
        self.player.pause()

    def _scrub_end(self):
        if getattr(self, '_was_playing', False):
            self.player.play()

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state(self, st):
        playing = st == QMediaPlayer.PlaybackState.PlayingState
        self.btn_play.setText('⏸ 暂停' if playing else '▶ 播放')

    def _on_position(self, ms):
        self.lb_pos.setText(fmt_time(ms / 1000.0))
        self.timeline.set_playhead(ms)

    def _on_duration(self, ms):
        if ms > 0:
            self.duration_ms = ms
            self.timeline.set_duration(ms)
            self.lb_total.setText(fmt_time(ms / 1000.0))
            self.lb_end.setText('结束 %s' % fmt_time(ms / 1000.0))

    def _set_start_here(self):
        self.timeline.start_ms = min(self.player.position(),
                                     self.timeline.end_ms - 200)
        self.timeline.update()
        self._sync_labels()

    def _set_end_here(self):
        self.timeline.end_ms = max(self.player.position(),
                                   self.timeline.start_ms + 200)
        self.timeline.update()
        self._sync_labels()

    def _sync_labels(self):
        s = self.timeline.start_ms / 1000.0
        e = self.timeline.end_ms / 1000.0
        self.lb_start.setText('开始 %s' % fmt_time(s))
        self.lb_end.setText('结束 %s' % fmt_time(e))
        self.lb_keep.setText('保留 %s ~ %s（约 %s）'
                             % (fmt_time(s), fmt_time(e), fmt_time(e - s)))

    # ------------------------------------------------------------------
    def _poll_export(self):
        if self._export_thread and not self._export_thread.is_alive():
            self._export_thread = None
            self.btn_export.setEnabled(True)
            self.btn_export.setText('导出裁剪后的视频')
            if self._export_ok and getattr(self, 'out_path', None):
                QtWidgets.QMessageBox.information(
                    self, '导出完成', '已保存：\n%s' % self.out_path)
                self.accept()
            else:
                QtWidgets.QMessageBox.warning(
                    self, '导出失败', '导出失败，详情请查看 %LOCALAPPDATA%\\影随录屏 下的 log.txt')

    def _export(self):
        s = self.timeline.start_ms / 1000.0
        e = self.timeline.end_ms / 1000.0
        if e - s < 0.5:
            QtWidgets.QMessageBox.warning(self, '范围太小',
                                          '保留的片段太短（不足0.5秒），请调整范围。')
            return
        self.player.pause()
        base, ext = os.path.splitext(self.video)
        out = '%s_裁剪%s' % (base, ext)
        n = 1
        while os.path.exists(out):
            out = '%s_裁剪(%d)%s' % (base, n, ext)
            n += 1
        self.out_path = out
        self._export_ok = False
        self.btn_export.setEnabled(False)
        self.btn_export.setText('正在导出...')

        def work():
            try:
                cmd = [_ffmpeg(), '-y',
                       '-ss', '%.3f' % s, '-i', self.video,
                       '-t', '%.3f' % (e - s),
                       '-c:v', 'libx264', '-preset', 'veryfast',
                       '-crf', '18', '-pix_fmt', 'yuv420p',
                       '-vf', 'crop=trunc(iw/2)*2:trunc(ih/2)*2',
                       '-movflags', '+faststart', out]
                p = subprocess.run(cmd, capture_output=True, text=True,
                                   encoding='utf-8', errors='replace',
                                   timeout=3600)
                if p.returncode == 0 and os.path.exists(out):
                    self._export_ok = True
                    return True
                print('裁剪导出失败: %s' % (p.stderr or '')[-500:])
            except Exception as ex:
                print('裁剪导出失败: %s' % ex)
            return False

        self._export_thread = threading.Thread(target=work, daemon=True)
        self._export_thread.start()

    def closeEvent(self, e):
        try:
            self.player.stop()
        except Exception:
            pass
        super().closeEvent(e)


def open_trim_dialog(video_path=None, parent=None):
    """打开裁剪对话框；video_path 为空时让用户选择文件"""
    if not video_path or not os.path.exists(video_path):
        video_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent, '选择要裁剪的视频', '',
            '视频文件 (*.mp4 *.mkv *.avi *.mov);;所有文件 (*.*)')
    if video_path and os.path.exists(video_path):
        dlg = TrimDialog(video_path, parent)
        dlg.exec()
