#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
现代化设置窗口
提供美观、直观的设置界面
"""

import sys, os
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
import DevicesInfo
from DevicesInfo import *
import RecordConfig
from RecordConfig import *
import os

class ModernSettingWindow(QDialog):
    """现代化设置窗口"""
    
    update_setting = Signal(bool)
    
    def __init__(self, parent=None):
        super(ModernSettingWindow, self).__init__(parent)
        
        self.changed = False
        self.key_map = {
            160: 'Shift', 161: 'Shift',          # L/R Shift
            162: 'Ctrl', 163: 'Ctrl',            # L/R Ctrl
            164: 'Alt', 165: 'Alt',              # L/R Alt
            91: 'Win', 92: 'Win',                # L/R Win
        }

        self.setup_ui()
        self.load()
        
    def setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("⚙️ 设置")
        self.setFixedSize(600, 450)  # 减少高度，因为去掉了标题区域
        self.setWindowIcon(QtGui.QIcon())
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)  # 添加一些边距
        main_layout.setSpacing(10)  # 设置间距
        self.setLayout(main_layout)
        
        # 标签页容器
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
                padding: 8px 20px;
                margin-right: 5px;
                border-bottom-left-radius: 0;
                border-bottom-right-radius: 0;
            }
            QTabBar::tab:selected {
                background-color: #4CAF50;
                color: white;
                border-bottom: 2px solid #4CAF50;
            }
            QTabBar::tab:hover {
                background-color: #e8f5e8;
            }
        """)
        
        # 创建各个标签页
        self.create_device_tab()
        self.create_shortcut_tab()
        self.create_record_tab()
        
        main_layout.addWidget(self.tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.save_button = QPushButton("💾 保存")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 25px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.save_button.clicked.connect(self.save_setting)
        
        self.cancel_button = QPushButton("❌ 取消")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 25px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.cancel_button.clicked.connect(self.cancel)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)
        
    def create_device_tab(self):
        """创建设备配置标签页"""
        device_widget = QWidget()
        device_layout = QVBoxLayout()
        device_widget.setLayout(device_layout)
        
        # 设备选择组
        device_group = QGroupBox("📹 设备选择")
        device_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #4CAF50;
            }
        """)
        device_form = QFormLayout()
        
        
        
        # 音频输入设备
        self.cb_audio_input = QComboBox()
        self.cb_audio_input.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 12px;
            }
            QComboBox:focus {
                border-color: #4CAF50;
            }
        """)
        device_form.addRow("🎤 音频输入:", self.cb_audio_input)
        
        # 屏幕画面：gdigrab 自动适配屏幕/区域，无设备可选
        self.screen_label = QLabel("全屏幕 / 所选区域（自动适配）")
        self.screen_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #f5f5f5;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 12px;
                color: #666;
            }
        """)
        device_form.addRow("🖥️ 屏幕画面:", self.screen_label)

        # 系统声音：使用 WASAPI loopback 内录默认扬声器，无需选择设备
        self.sysaudio_label = QLabel("自动（内录当前扬声器声音）")
        self.sysaudio_label.setStyleSheet(self.screen_label.styleSheet())
        device_form.addRow("🔊 系统声音:", self.sysaudio_label)
        
        device_group.setLayout(device_form)
        device_layout.addWidget(device_group)
        device_layout.addStretch()
        
        self.tab_widget.addTab(device_widget, "📱 设备")
        
    def create_shortcut_tab(self):
        """创建快捷键标签页"""
        shortcut_widget = QWidget()
        shortcut_layout = QVBoxLayout()
        shortcut_widget.setLayout(shortcut_layout)
        
        # 快捷键设置组
        shortcut_group = QGroupBox("⌨️ 快捷键设置")
        shortcut_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #4CAF50;
            }
        """)
        shortcut_form = QFormLayout()
        
        
        
        # 录制屏幕快捷键
        self.le_screen_shortcut = QLineEdit()
        self.le_screen_shortcut.setReadOnly(True)
        self.le_screen_shortcut.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 12px;
                background-color: #f9f9f9;
            }
        """)
        screen_layout = QHBoxLayout()
        screen_layout.addWidget(self.le_screen_shortcut)
        
        self.btn_screen_shortcut = QPushButton("设置")
        self.btn_screen_shortcut.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 15px;
                border-radius: 6px;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.btn_screen_shortcut.clicked.connect(lambda: self.set_shortcut('screen'))
        screen_layout.addWidget(self.btn_screen_shortcut)
        
        shortcut_form.addRow("🖥️ 录制屏幕:", screen_layout)
        
        # 停止录制快捷键
        self.le_stop_shortcut = QLineEdit()
        self.le_stop_shortcut.setReadOnly(True)
        self.le_stop_shortcut.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 12px;
                background-color: #f9f9f9;
            }
        """)
        stop_layout = QHBoxLayout()
        stop_layout.addWidget(self.le_stop_shortcut)
        
        self.btn_stop_shortcut = QPushButton("设置")
        self.btn_stop_shortcut.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 15px;
                border-radius: 6px;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.btn_stop_shortcut.clicked.connect(lambda: self.set_shortcut('stop'))
        stop_layout.addWidget(self.btn_stop_shortcut)
        
        shortcut_form.addRow("⏹️ 停止录制:", stop_layout)
        
        shortcut_group.setLayout(shortcut_form)
        shortcut_layout.addWidget(shortcut_group)
        
        # 提示信息
        tip_label = QLabel("💡 提示：点击'设置'按钮，然后按下想要设置的快捷键组合")
        tip_label.setStyleSheet("""
            color: #666666;
            font-size: 12px;
            padding: 10px;
            background-color: #f0f0f0;
            border-radius: 6px;
            margin-top: 10px;
        """)
        tip_label.setWordWrap(True)
        shortcut_layout.addWidget(tip_label)
        
        shortcut_layout.addStretch()
        
        self.tab_widget.addTab(shortcut_widget, "⌨️ 快捷键")
        
    def create_record_tab(self):
        """创建录制参数标签页"""
        record_widget = QWidget()
        record_layout = QVBoxLayout()
        record_widget.setLayout(record_layout)
        
        # 基本设置组
        basic_group = QGroupBox("🎬 基本设置")
        basic_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #4CAF50;
            }
        """)
        basic_form = QFormLayout()
        

        
        # 编码格式固定为H.264，显示为标签
        self.vcodec_label = QLabel("H.264 (libx264)")
        self.vcodec_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #f0f0f0;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 12px;
                color: #666;
            }
        """)
        basic_form.addRow("🔧 编码格式:", self.vcodec_label)
        
        # 帧率
        self.dsb_frame_rate = QDoubleSpinBox()
        self.dsb_frame_rate.setRange(10.0, 120.0)
        self.dsb_frame_rate.setDecimals(1)
        self.dsb_frame_rate.setValue(24.0)
        self.dsb_frame_rate.setSuffix(" fps")
        self.dsb_frame_rate.setStyleSheet("""
            QDoubleSpinBox {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 12px;
            }
            QDoubleSpinBox:focus {
                border-color: #4CAF50;
            }
        """)
        basic_form.addRow("⚡ 帧率:", self.dsb_frame_rate)
        
        basic_group.setLayout(basic_form)
        record_layout.addWidget(basic_group)
        
        # 高级设置组
        advanced_group = QGroupBox("🔧 高级设置")
        advanced_group.setStyleSheet(basic_group.styleSheet())
        advanced_form = QFormLayout()

        # 复选框选项（文件目录已移到主界面，这里去掉）
        self.ckb_gpu_acceleration = QCheckBox("启用GPU加速")
        self.ckb_gpu_acceleration.setChecked(False)  # 默认不勾选
        self.ckb_gpu_acceleration.setStyleSheet("""
            QCheckBox {
                font-size: 12px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #e0e0e0;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4CAF50;
                border-radius: 3px;
                background-color: #4CAF50;
            }
        """)
        
        # 自动缩放美化的开关在主窗口（避免重复），这里只提供缩放倍率
        self.dsb_beautify_zoom = QDoubleSpinBox()
        self.dsb_beautify_zoom.setRange(1.2, 4.0)
        self.dsb_beautify_zoom.setDecimals(1)
        self.dsb_beautify_zoom.setSingleStep(0.1)
        self.dsb_beautify_zoom.setValue(2.0)
        self.dsb_beautify_zoom.setSuffix(" x")
        self.dsb_beautify_zoom.setStyleSheet(self.dsb_frame_rate.styleSheet())

        advanced_form.addRow("", self.ckb_gpu_acceleration)
        advanced_form.addRow("🔍 缩放倍率:", self.dsb_beautify_zoom)
        
        advanced_group.setLayout(advanced_form)
        record_layout.addWidget(advanced_group)
        
        record_layout.addStretch()
        
        self.tab_widget.addTab(record_widget, "🎬 录制")
        
    def set_shortcut(self, shortcut_type):
        """设置快捷键"""
        dialog = ShortcutCaptureDialog(f"设置{'屏幕' if shortcut_type == 'screen' else '停止'}录制快捷键", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            shortcut_str = dialog.get_shortcut_string()
            if shortcut_type == 'screen':
                self.le_screen_shortcut.setText(shortcut_str)
            elif shortcut_type == 'stop':
                self.le_stop_shortcut.setText(shortcut_str)
                
            self.changed = True
            self.update_state()
            
    def convert_key_group_to_string(self, key_group):
        """将键组转换为字符串显示（修饰键按 Ctrl+Alt+Shift+Win 顺序）"""
        try:
            keys = [int(k.strip()) for k in key_group.split(',')]
            mod_names = [self.key_map[k] for k in keys if k in self.key_map]
            others = []
            for key in keys:
                if key in self.key_map:
                    continue
                if 65 <= key <= 90 or 48 <= key <= 57:
                    others.append(chr(key))
                else:
                    text = QKeySequence(key).toString()
                    others.append(text if text else 'Key%d' % key)
            ordered = [n for n in ('Ctrl', 'Alt', 'Shift', 'Win')
                       if n in mod_names]
            return '+'.join(ordered + others)
        except:
            return key_group

    def convert_string_to_key_group(self, shortcut_str):
        """将快捷键字符串转换为键组（VK 键码）"""
        try:
            if not shortcut_str:
                return "160,162,82"  # 默认 Ctrl+Shift+R
            mod_vk = {'Ctrl': 162, 'Alt': 164, 'Shift': 160, 'Win': 91}
            key_codes = []
            for key in shortcut_str.split('+'):
                key = key.strip()
                if key in mod_vk:
                    key_codes.append(str(mod_vk[key]))
                elif len(key) == 1:
                    key_codes.append(str(ord(key.upper())))
                else:
                    text = QKeySequence(key)
                    if text.count() > 0:
                        key_codes.append(str(text[0].toCombined() & 0x01FFFFFF
                                             or text[0].key()))
                    else:
                        key_codes.append('82')  # 默认 R
            return ','.join(key_codes)
        except:
            return "160,162,82"
            
    def load_combobox_data(self, combox, data):
        """加载下拉框数据"""
        combox.clear()
        for obj in data:
            name = obj[0]
            value = name 
            if len(obj) > 1:
                value = obj[1]
            combox.addItem(name, value)
            
    def load_config(self):
        """加载配置"""
        # 设备配置（麦克风；屏幕画面/系统声音为自动，无设备选择）
        voice_device = self.rc.config.get('devices', 'voice_device_name')
        idx = self.cb_audio_input.findData(voice_device)
        if idx < 0:
            # 配置里的设备名无效（如残留 None 或设备已拔出）→ 默认第一个麦克风
            idx = 0 if self.cb_audio_input.count() else -1
        self.cb_audio_input.setCurrentIndex(idx)
        
        # 快捷键配置
        screen_shortcut = self.rc.config.get('shortcut', 'screen')
        stop_shortcut = self.rc.config.get('shortcut', 'stop')
        
        self.le_screen_shortcut.setText(self.convert_key_group_to_string(screen_shortcut))
        self.le_stop_shortcut.setText(self.convert_key_group_to_string(stop_shortcut))
        
        # 录制配置（分辨率已移除，按实际录制大小保存，编码格式固定为H.264）
        # vcodec = self.rc.config.get('record', 'vcodec')  # 不再需要，固定为H264
        frame_rate = self.rc.config.getfloat('record', 'frame_rate')

        # 强制设置编码格式为H.264
        self.rc.config.set('record', 'vcodec', 'libx264')

        self.dsb_frame_rate.setValue(frame_rate)

        # 复选框配置
        self.ckb_gpu_acceleration.setChecked(self.rc.config.getboolean('record', 'gpu_acceleration'))

        # 缩放倍率（美化开关在主窗口）
        self.dsb_beautify_zoom.setValue(self.rc.config.getfloat('record', 'beautify_zoom', fallback=2.0))

    def load(self):
        """初始化加载"""
        self.rc = RecordConfig()

        # 加载设备数据（麦克风；屏幕画面/系统声音为自动）
        di = DevicesInfo()
        self.load_combobox_data(self.cb_audio_input, di.voice_devices)

        # 编码格式固定为H.264，不再提供选择

        # 加载配置
        self.load_config()

        # 连接信号
        self.connect_signals()

        # 更新状态
        self.update_state()

    def connect_signals(self):
        """连接信号"""
        # 设备信号
        self.cb_audio_input.currentIndexChanged.connect(self.state_changed)

        # 快捷键信号
        # 快捷键通过设置按钮触发，无需连接文本变化信号

        # 录制参数信号（文件路径和分辨率已移到主界面或自动处理，编码格式已固定）
        self.dsb_frame_rate.valueChanged.connect(self.state_changed)

        # 复选框信号
        self.ckb_gpu_acceleration.stateChanged.connect(self.state_changed)
        self.dsb_beautify_zoom.valueChanged.connect(self.state_changed)
        
    def state_changed(self):
        """状态变化处理"""
        self.changed = True
        self.update_state()
        
    def save_setting(self):
        """保存设置"""
        # 设备设置（麦克风；屏幕画面/系统声音为自动，不写配置）
        self.rc.config.set('devices', 'voice_device_name', str(self.cb_audio_input.currentData()))

        # 快捷键设置
        self.rc.config.set('shortcut', 'screen', self.convert_string_to_key_group(self.le_screen_shortcut.text()))
        self.rc.config.set('shortcut', 'stop', self.convert_string_to_key_group(self.le_stop_shortcut.text()))

        # 录制设置（文件路径和分辨率已移到主界面管理，按实际录制大小保存，编码格式固定为H.264）
        self.rc.config.set('record', 'vcodec', 'libx264')  # 强制使用H.264
        self.rc.config.set('record', 'frame_rate', str(self.dsb_frame_rate.value()))
        self.rc.config.set('record', 'gpu_acceleration', str(self.ckb_gpu_acceleration.isChecked()))
        # 自动缩放美化的开关在主窗口，这里不写该项，只保存缩放倍率
        self.rc.config.set('record', 'beautify_zoom', str(self.dsb_beautify_zoom.value()))
        
        # 写入配置文件
        self.rc.write()
        
        # 发送更新信号
        self.update_setting.emit(self.changed)
        self.changed = False
        self.update_state()
        
        # 显示保存成功提示
        QMessageBox.information(self, "保存成功", "设置已保存，部分设置需要重新启动软件后生效。")
        
        # 关闭窗口
        self.accept()
    
    def cancel(self):
        """取消设置"""
        self.load_config()
        self.changed = False
        self.update_state()
        
        # 关闭窗口
        self.accept()
    
    def update_state(self):
        """更新界面状态"""
        self.save_button.setEnabled(self.changed)
        self.cancel_button.setEnabled(self.changed)
        
    def showSettingWindow(self):
        """显示设置窗口"""
        if not self.isVisible():
            self.exec()


class ShortcutCaptureDialog(QDialog):
    """快捷键捕获对话框"""
    
    def __init__(self, title, parent=None):
        super(ShortcutCaptureDialog, self).__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 200)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        
        self.captured_keys = []
        
        layout = QVBoxLayout()
        
        # 提示标签
        info_label = QLabel("请按下您想要设置的快捷键组合...")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("""
            font-size: 14px;
            color: #333;
            padding: 20px;
        """)
        layout.addWidget(info_label)
        
        # 显示当前按键
        self.key_display = QLabel()
        self.key_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.key_display.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #4CAF50;
            padding: 20px;
            background-color: #f0f0f0;
            border-radius: 8px;
            margin: 10px;
        """)
        layout.addWidget(self.key_display)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_button = QPushButton("确定")
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        ok_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("取消")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def keyPressEvent(self, event):
        """按键事件处理"""
        key_code = event.key()
        
        # 忽略一些特殊按键
        if key_code in [Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta]:
            if key_code not in self.captured_keys:
                self.captured_keys.append(key_code)
        elif key_code not in [Qt.Key.Key_Escape]:
            # 如果是普通按键，替换最后一个
            if self.captured_keys and self.captured_keys[-1] not in [Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta]:
                self.captured_keys[-1] = key_code
            else:
                self.captured_keys.append(key_code)
        
        # 更新显示
        self.update_display()
        
    def update_display(self):
        """更新按键显示"""
        key_map = {
            Qt.Key.Key_Control: 'Ctrl',
            Qt.Key.Key_Alt: 'Alt',
            Qt.Key.Key_Shift: 'Shift',
            Qt.Key.Key_Meta: 'Win',
            Qt.Key.Key_Space: 'Space',
        }
        
        key_names = []
        for key_code in self.captured_keys:
            if key_code in key_map:
                key_names.append(key_map[key_code])
            else:
                # 获取按键字符
                key_text = QKeySequence(key_code).toString()
                if key_text:
                    key_names.append(key_text)
                else:
                    key_names.append(f'Key{key_code}')
        
        self.key_display.setText('+'.join(key_names) if key_names else "等待按键...")
        
    def get_shortcut_string(self):
        """获取快捷键字符串"""
        if not self.captured_keys:
            return ""
            
        key_map = {
            Qt.Key.Key_Control: 'Ctrl',
            Qt.Key.Key_Alt: 'Alt', 
            Qt.Key.Key_Shift: 'Shift',
            Qt.Key.Key_Meta: 'Win',
            Qt.Key.Key_Space: 'Space',
        }
        
        key_names = []
        for key_code in self.captured_keys:
            if key_code in key_map:
                key_names.append(key_map[key_code])
            else:
                key_text = QKeySequence(key_code).toString()
                if key_text:
                    key_names.append(key_text)
                else:
                    key_names.append(f'Key{key_code}')
        
        return '+'.join(key_names)