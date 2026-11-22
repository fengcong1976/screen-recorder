import sys, datetime, time, os, threading
import PySide6
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QCoreApplication, QTimer, QEvent
from PySide6.QtWidgets import QLCDNumber, QApplication, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox
from PySide6.QtWidgets import QMessageBox, QLabel, QProgressBar
import RecordVideo, RecordType
from RecordVideo import *
from RecordType import *
import SettingWindow, SettingWindowModern
from SettingWindow import *
from SettingWindowModern import *
import Shortcut_temp as Shortcut
from Shortcut_temp import *
from RecIndicator import RecIndicator
import RecordTrayIcon
from RecordTrayIcon import *
import RecordConfig
from RecordConfig import *
from AboutDialog import app_icon, show_about

# 直接从当前目录导入，不需要添加子目录到path
from area_selector import select_area
from area_overlay import AreaOverlay
from MouseTracker import MouseTracker
from BeautifyProcessor import BeautifyProcessor

class ModernRecordWindow(QtWidgets.QMainWindow):
    """现代化录制主窗口"""

    # 自动美化完成信号（跨线程回UI）
    beautify_done = QtCore.Signal(str)
    
    def __init__(self, parent=None, screen_resolution=None):
        super(ModernRecordWindow, self).__init__(parent)
        self.screen_resolution = screen_resolution
        self.selected_region = None
        self.area_overlay = None
        self.is_paused = False
        self.recording_time = 0
        self.mouse_tracker = None   # 当前录制的鼠标点击追踪器
        self.beautify_thread = None

        # 自动美化完成信号（跨线程回UI）
        self.beautify_done.connect(self._on_beautify_done)
        
 # 创建右键菜单容器（为托盘图标使用）
        self.context_menu = QtWidgets.QMenu(self)
        self.contextMenu = self.context_menu
        
        # 初始化UI和模块
        self.init_modules()
        self.setup_ui()
        self.init_timer()
        self.update_state()
        
        # 初始化文件目录显示（在UI创建后）
        self.init_file_directory()
        
        # 填充右键菜单内容
        self.setup_context_menu_content()
        
    def init_modules(self):
        """初始化核心模块"""
        # 录制模块
        self.rv = RecordVideo()
        
        # 托盘图标
        self.rti = RecordTrayIcon(self)
        self.rti.update_state(self.recording, self.record_type)
        
        # 快捷键
        self.sc = Shortcut()
        
        # 设置窗口 - 使用现代化版本
        self.sw = ModernSettingWindow()
        
        # 配置
        self.update_setting(True)
        
    def init_file_directory(self):
        """初始化文件目录显示"""
        if hasattr(self, 'le_file_path'):
            rc = RecordConfig()
            file_dir = rc.config.get('record', 'file_dir')

            # 检查配置文件中的目录是否存在（'.'/空值/不存在的目录均视为未配置）
            if file_dir and file_dir != '.' and os.path.isdir(file_dir):
                self.le_file_path.setText(os.path.abspath(file_dir))
                print(f"已加载保存目录: {os.path.abspath(file_dir)}")
            else:
                # 创建默认目录：视频库\影随录屏（用户媒体文件）
                default_dir = default_record_dir()
                if not os.path.exists(default_dir):
                    os.makedirs(default_dir, exist_ok=True)
                    print(f"已创建默认保存目录: {default_dir}")

                self.le_file_path.setText(default_dir)
                rc.config.set('record', 'file_dir', default_dir)
                rc.write()
                print(f"已设置默认保存目录: {default_dir}")

            # 同步录制模块的保存目录（避免启动时读取到无效配置导致录制失败）
            if hasattr(self.rv, 'file_dir') and self.le_file_path.text():
                self.rv.file_dir = os.path.abspath(self.le_file_path.text())
        else:
            print("警告: le_file_path 控件尚未创建")
        
    def setup_ui(self):
        """设置用户界面"""
        self.setWindowTitle("影随录屏")
        # 设置窗口在屏幕右侧，避免闪现
        # self.setGeometry(1100, 600, 500, 400)  # 已屏蔽
        self.setWindowIcon(app_icon() or QtGui.QIcon())
        
        # 主部件和布局
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()  # 将主布局改为水平布局
        central_widget.setLayout(main_layout)

        # 菜单栏：帮助（使用说明 / 关于）
        help_menu = self.menuBar().addMenu("帮助")
        help_menu.addAction("📖 使用说明", self.show_help_dialog)
        help_menu.addAction("ℹ️ 关于 影随录屏", self.show_about_dialog)

        # 左侧主面板
        left_layout = QVBoxLayout()  # 左侧布局，用于现有组件
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_layout)
        main_layout.addWidget(left_widget)
        
        # 录制设置组
        settings_group = QGroupBox("录制设置")
        settings_layout = QVBoxLayout()
        settings_group.setLayout(settings_layout)
        left_layout.addWidget(settings_group)
        
        # 录制模式选择 - 默认只录制屏幕，移除选择控件
        # mode_layout = QHBoxLayout()
        # self.rb_screen = QtWidgets.QRadioButton("🖥️ 录制屏幕")
        # self.rb_screen.setChecked(True)  # 默认选择屏幕录制
        # 
        # mode_layout.addWidget(self.rb_screen)
        # mode_layout.addStretch()
        # settings_layout.addLayout(mode_layout)
        
        # # 添加一个标签说明当前录制模式（已移除）
        # screen_mode_label = QLabel("当前录制模式：🖥️ 屏幕录制")
        # screen_mode_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        # settings_layout.addWidget(screen_mode_label)
        
        # 屏幕录制选项（已移除屏幕选项组，直接添加内容）
        # self.screen_options_group = QGroupBox("屏幕选项")
        # self.screen_options_group.setVisible(True)  # 始终显示
        # screen_options_layout = QVBoxLayout()
        # 
        # # 屏幕录制模式
        # 屏幕录制选项
        screen_mode_layout = QHBoxLayout()
        self.rb_fullscreen = QtWidgets.QRadioButton("全屏幕")
        self.rb_fullscreen.setChecked(True)
        self.rb_fullscreen.toggled.connect(self.on_screen_mode_changed)
        
        self.rb_region = QtWidgets.QRadioButton("选择区域")
        self.rb_region.toggled.connect(self.on_screen_mode_changed)
        
        screen_mode_layout.addWidget(self.rb_fullscreen)
        screen_mode_layout.addWidget(self.rb_region)
        screen_mode_layout.addStretch()
        settings_layout.addLayout(screen_mode_layout)
        
        # 音源选择
        audio_source_layout = QHBoxLayout()
        audio_source_label = QLabel("音源选择:")
        self.audio_source_combo = QtWidgets.QComboBox()
        self.audio_source_combo.addItem("系统声音", "system")
        self.audio_source_combo.addItem("麦克风输入", "mic")
        self.audio_source_combo.setCurrentIndex(0)  # 缺省为系统声音
        
        audio_source_layout.addWidget(audio_source_label)
        audio_source_layout.addWidget(self.audio_source_combo)
        audio_source_layout.addStretch()
        settings_layout.addLayout(audio_source_layout)

        # 是否美化开关（随鼠标点击自动缩放）
        beautify_layout = QHBoxLayout()
        self.cb_beautify = QtWidgets.QCheckBox("停止后按鼠标点击自动缩放")
        try:
            self.cb_beautify.setChecked(
                self.rv.config.getboolean('record', 'auto_beautify', fallback=False))
        except Exception:
            self.cb_beautify.setChecked(False)
        self.cb_beautify.toggled.connect(self.on_beautify_toggled)
        beautify_layout.addWidget(self.cb_beautify)
        beautify_layout.addStretch()
        settings_layout.addLayout(beautify_layout)
        
        # 区域选择控制
        area_control_layout = QHBoxLayout()
        self.area_label = QLabel("当前: 全屏幕")
        self.btn_select_region = QtWidgets.QPushButton("选择录制区域")
        self.btn_select_region.clicked.connect(self.select_record_region)
        self.btn_select_region.setEnabled(False)
        
        self.btn_clear_region = QtWidgets.QPushButton("消除选择")
        self.btn_clear_region.clicked.connect(self.clear_selected_region)
        self.btn_clear_region.setEnabled(False)
        
        area_control_layout.addWidget(self.area_label)
        area_control_layout.addWidget(self.btn_select_region)
        area_control_layout.addWidget(self.btn_clear_region)
        settings_layout.addLayout(area_control_layout)
        
        # # 屏幕选项组相关代码已移除
        # self.screen_options_group.setLayout(screen_options_layout)
        # settings_layout.addWidget(self.screen_options_group)
        
        
        
        # 保存目录设置
        file_group = QGroupBox("保存设置")
        file_layout = QVBoxLayout()
        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group)
        
        # 文件保存目录
        file_control_layout = QHBoxLayout()
        self.file_label = QLabel("保存目录:")
        self.le_file_path = QtWidgets.QLineEdit()
        self.le_file_path.setReadOnly(True)
        self.le_file_path.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #f9f9f9;
            }
        """)
        
        self.btn_browse = QtWidgets.QPushButton("📁 浏览")
        self.btn_browse.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.btn_browse.clicked.connect(self.browse_file_dir)
        
        # 打开目录按钮
        self.btn_open_dir = QtWidgets.QPushButton("📂 打开")
        self.btn_open_dir.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.btn_open_dir.clicked.connect(self.open_current_file_dir)

        # 裁剪视频按钮
        self.btn_trim = QtWidgets.QPushButton("✂️ 裁剪")
        self.btn_trim.setStyleSheet(self.btn_open_dir.styleSheet())
        self.btn_trim.setToolTip("去掉录制视频的开头或结尾多余内容")
        self.btn_trim.clicked.connect(self.open_trim_video)

        file_control_layout.addWidget(self.file_label)
        file_control_layout.addWidget(self.le_file_path)
        file_control_layout.addWidget(self.btn_browse)
        file_control_layout.addWidget(self.btn_open_dir)
        file_control_layout.addWidget(self.btn_trim)
        file_layout.addLayout(file_control_layout)
        
        # 录制控制组
        control_group = QGroupBox("录制控制")
        control_layout = QGridLayout()
        control_group.setLayout(control_layout)
        left_layout.addWidget(control_group)
        
        # 录制按钮
        self.btn_record = QtWidgets.QPushButton("🔴 开始录制")
        self.btn_record.clicked.connect(self.on_record_button_clicked)
        self.btn_record.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        control_layout.addWidget(self.btn_record, 0, 0)
        
        # 暂停按钮
        self.btn_pause = QtWidgets.QPushButton("⏸️ 暂停")
        self.btn_pause.clicked.connect(self.toggle_pause_recording)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background-color: #ffaa00;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #ff8800;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        control_layout.addWidget(self.btn_pause, 0, 1)
        
        # 停止按钮
        self.btn_stop = QtWidgets.QPushButton("⏹️ 停止")
        self.btn_stop.clicked.connect(self.stop_record)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #333333;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        control_layout.addWidget(self.btn_stop, 1, 0)
        
        # 设置按钮
        self.btn_setting = QtWidgets.QPushButton("⚙️ 设置")
        self.btn_setting.clicked.connect(self.show_setting)
        self.btn_setting.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        control_layout.addWidget(self.btn_setting, 1, 1)

        # 状态显示
        self.status_label = QLabel("状态: 准备就绪")
        self.status_label.setStyleSheet("color: green; font-weight: bold; margin: 5px;")
        left_layout.addWidget(self.status_label)

        # 快捷键与行为提示条（随主窗口显示/消失）
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet(
            "color: #666; font-size: 12px; margin: 2px 5px;")
        self.hint_label.setText(self._build_hint_text())
        left_layout.addWidget(self.hint_label)
        
        # 录制时长显示
        self.time_label = QLabel("录制时长: 00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setVisible(False)
        left_layout.addWidget(self.time_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        # 设置窗口的最小尺寸
        self.setMinimumSize(640, 500)

    # 使用说明内容（菜单栏「帮助 → 使用说明」展示）
    USAGE_HTML = """
    <h3>影随录屏 · 使用说明</h3>

    <p><strong>一、快速上手（三步录制）</strong></p>
    <ul>
    <li>第1步：选模式——「全屏幕」或「选择区域」（点"选择录制区域"后框选屏幕一块区域）。</li>
    <li>第2步：选声音——「系统声音」（录电脑里播放的声音）或「麦克风输入」（录解说）。</li>
    <li>第3步：点「🔴 开始录制」，像平时一样操作电脑；完成后点「⏹️ 停止」。</li>
    </ul>

    <p><strong>二、随鼠标自动缩放（本软件的核心特色）</strong></p>
    <p>你只管正常操作和<font color="#c62828"><strong>点鼠标</strong></font>，镜头会自动跟随你的点击推近、拉远，无需任何剪辑：</p>
    <ul>
    <li><strong>开关位置：</strong>主界面「停止后按鼠标点击自动缩放」勾选框，默认不勾选；录教程需要突出重点时再勾选。</li>
    <li><strong>使用方法：</strong>录制时，想突出哪个按钮、哪段文字，就用鼠标<strong>点它一下</strong>。</li>
    <li><strong>效果：</strong>点「⏹️ 停止」后弹出对话框输入文件名——生成的视频直接用这个名字，回放时镜头自动推近你点击的位置（默认2倍），停留片刻再平滑拉回。</li>
    <li><strong>举例：</strong>录软件教学时点一下"导出"按钮 → 回放时镜头自动推近"导出"按钮，观众一眼看到操作重点。</li>
    <li><strong>说明：</strong>没勾选或没点过鼠标就不做缩放处理，文件直接按输入的名字保存；缩放倍率可在设置里调（1.2～4.0倍）；勾选并做了缩放时，视频按输入的名字保存，未处理的原始版本以「名字_原视频」保留在同一文件夹。</li>
    </ul>

    <p><strong>三、暂停与继续</strong></p>
    <ul>
    <li>录制中点「⏸️ 暂停」真正停止录制，休息或准备后点「继续」接着录，自动拼成一条完整视频。</li>
    </ul>

    <p><strong>四、保存位置</strong></p>
    <ul>
    <li>「📁 浏览」选好保存目录后自动记住，下次打开无需重选。</li>
    <li>默认保存到系统的「视频\\影随录屏」，并按日期自动归档子文件夹，例如 2026-10-23\\。</li>
    </ul>

    <p><strong>五、更多设置</strong></p>
    <ul>
    <li>「⚙️ 设置」里可调：分辨率、帧率、GPU加速（N卡可开启，录制更流畅）、录制/停止快捷键。</li>
    <li>全屏幕录制开始后主窗口自动缩到右下角，不挡画面；到托盘图标点击即可唤回。</li>
    </ul>
    """

    def show_help_dialog(self):
        """弹出「使用说明」对话框"""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("使用说明")
        dlg.resize(520, 480)
        layout = QVBoxLayout(dlg)
        browser = QtWidgets.QTextBrowser()
        browser.setHtml(self.USAGE_HTML)
        layout.addWidget(browser)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.reject)
        btns.clicked.connect(dlg.accept)
        layout.addWidget(btns)
        dlg.exec()
    
    def init_timer(self):
        """初始化计时器"""
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_recording_time)
        
    def setup_context_menu_content(self):
        """填充右键菜单内容"""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # 录制控制
        self.record_control_action = self.context_menu.addAction('开始/停止录制')
        self.record_control_action.triggered.connect(self.on_record_button_clicked)
        
        # 打开文件目录
        self.open_dir_action = self.context_menu.addAction('打开文件目录')
        self.open_dir_action.triggered.connect(self.open_file_dir)
        
        # 分隔栏
        self.context_menu.addSeparator()

        # 关于
        self.about_action = self.context_menu.addAction('关于 影随录屏')
        self.about_action.triggered.connect(self.show_about_dialog)

        # 退出
        self.exit_action = self.context_menu.addAction('退出')
        self.exit_action.triggered.connect(self.close)

    def show_about_dialog(self):
        """弹出「关于」对话框"""
        show_about("影随录屏", self)
        
    def show_context_menu(self, pos):
        """显示右键菜单"""
        self.context_menu.exec(self.mapToGlobal(pos))
        
    @property
    def recording(self):
        return self.rv.recording
    
    @property
    def exception_exit(self):
        return self.rv.exception_exit
    
    @property
    def record_type(self):
        return self.rv.record_type
    
    def update_state(self):
        """更新界面状态"""
        if self.recording:
            self.status_label.setText("状态: 正在录制...")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            
            # 由于现在只支持屏幕录制模式，不再需要根据record_type设置不同选项
            # if self.record_type == RecordType.Screen:
            #     # 不再需要设置rb_screen
            #     # self.rb_screen.setChecked(True)
            
            # 更新按钮状态
            self.btn_record.setText("🔴 录制中")
            self.btn_record.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            
            # 显示时间和进度
            self.time_label.setVisible(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # 无限进度条
            
        else:
            self.status_label.setText("状态: 准备就绪")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            
            # 更新按钮状态
            self.btn_record.setText("🔴 开始录制")
            self.btn_record.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
            
            # 隐藏时间和进度
            self.time_label.setVisible(False)
            self.progress_bar.setVisible(False)
            
        # 更新托盘图标状态
        self.rti.update_state(self.recording, self.record_type)
    
    def on_record_mode_changed(self):
        """录制模式改变事件处理"""
        # 仅支持屏幕录制，不需要切换
        pass
        
    def on_screen_mode_changed(self):
        """屏幕录制模式改变事件处理"""
        is_region_mode = self.rb_region.isChecked()
        self.btn_select_region.setEnabled(is_region_mode)
        self.btn_clear_region.setEnabled(is_region_mode and self.selected_region is not None)
        
        if not is_region_mode:
            self.area_label.setText("当前: 全屏幕")
            self.selected_region = None
        else:
            self.area_label.setText("当前: 请选择区域")
    
    def select_record_region(self):
        """选择录制区域"""
        try:
            print("开始选择录制区域，主窗口将隐藏")
            self.hide()  # 隐藏主窗口
            
            # 使用main.py中的区域选择方法
            area = select_area()
            
            if area:
                self.selected_region = QtCore.QRect(area[0], area[1], area[2], area[3])
                print(f"选择录制区域: {area}")
                
                # 更新UI显示
                self.area_label.setText(f"当前: {area[2]}×{area[3]} (位置: {area[0]}, {area[1]})")
                self.btn_clear_region.setEnabled(True)
                
                # 显示区域覆盖层
                self.show_area_overlay(area)
            else:
                print("取消选择区域")
                
        except Exception as e:
            print(f"区域选择失败: {e}")
            
        finally:
            # 恢复主窗口显示
            self.show()
            self.raise_()
            self.activateWindow()
    

    
    def show_area_overlay(self, area):
        """显示区域覆盖层"""
        try:
            # 先隐藏现有的覆盖层
            self.hide_area_overlay()
            
            # 创建新的覆盖层
            self.area_overlay = AreaOverlay(area, simple_corners=True)
            self.area_overlay.show_overlay()
            
            print(f"区域覆盖层已显示: {area}")
            
        except Exception as e:
            print(f"显示区域覆盖层失败: {e}")
    
    def hide_area_overlay(self):
        """隐藏区域覆盖层"""
        if hasattr(self, 'area_overlay') and self.area_overlay:
            try:
                self.area_overlay.hide_overlay()
                self.area_overlay.close()
                self.area_overlay = None
                print("区域覆盖层已隐藏")
            except Exception as e:
                print(f"隐藏区域覆盖层失败: {e}")
    
    def clear_selected_region(self):
        """消除选择区域"""
        self.selected_region = None
        self.area_label.setText("当前: 请选择区域")
        self.btn_clear_region.setEnabled(False)
        
        # 隐藏区域覆盖层
        self.hide_area_overlay()
        
        print("已消除选择区域")
    
    def on_record_button_clicked(self):
        """录制按钮点击事件处理"""
        if self.recording:
            self.stop_record()
        else:
            self.start_record()
    
    def start_record(self):
        """开始录制"""
        # 检查保存目录是否为空或不存在
        if not self.check_save_directory():
            return False
            
        if self.recording:
            if self.recording == self.record_type:
                return True
                
            print('检测到正在录制，录制类型将切换...')
            self.stop_record()
        
        # 区域模式未选择区域时明确提示（避免静默退化为全屏录制）
        if self.rb_region.isChecked() and not self.selected_region:
            QMessageBox.information(self, '提示',
                                    '当前为区域录制模式，请先点击"选择录制区域"框选区域；'
                                    '或切换回"全屏幕"模式。')
            return False

        # 保存目录以界面显示为准（防止配置与内存不一致）
        if hasattr(self, 'le_file_path'):
            ui_dir = self.le_file_path.text().strip()
            if ui_dir and os.path.isdir(ui_dir) and \
                    os.path.abspath(self.rv.file_dir) != os.path.abspath(ui_dir):
                self.rv.file_dir = os.path.abspath(ui_dir)

        if self.rv.check_device():
            # 获取当前选择的音源
            audio_source = self.audio_source_combo.currentData() or "system"

            # 录制即将开始，先隐藏主窗口避免被录进画面（区域/全屏模式均隐藏）
            was_hidden = self.isHidden()
            self.hide()

            # 开始录制 - 仅支持屏幕录制
            # 移除对self.rb_screen的检查，因为现在只有屏幕录制这一种模式
            if self.rb_region.isChecked() and self.selected_region:
                print(f'开始录制屏幕区域... 音源: {audio_source}')
                # 将QRect转换为元组
                if isinstance(self.selected_region, QtCore.QRect):
                    region_tuple = (
                        self.selected_region.x(), 
                        self.selected_region.y(), 
                        self.selected_region.width(), 
                        self.selected_region.height()
                    )
                    self.rv.record_screen_region(region_tuple, audio_source=audio_source)
                else:
                    self.rv.record_screen_region(self.selected_region, audio_source=audio_source)
                self.rv.record_type = RecordType.Screen
            else:
                print(f'开始录制全屏幕... 音源: {audio_source}')
                self.rv.record_screen(resolution=self.screen_resolution, audio_source=audio_source)
                self.rv.record_type = RecordType.Screen

            # 启动失败时给出明确提示（如保存目录无法创建等），并恢复主窗口
            if not self.rv.recording:
                if not was_hidden:
                    self.show()
                detail = getattr(self.rv, 'last_error', '') or ''
                msg = ('录制启动失败，常见原因：\n'
                       '1. 保存目录无法创建或不可写\n'
                       '2. 音频设备被占用\n')
                if detail:
                    msg += '\n本次原因：%s' % detail
                msg += '\n详情请查看 %LOCALAPPDATA%\\影随录屏 下的 log.txt'
                QMessageBox.warning(self, '启动失败', msg)
                return False
        
            # 启动计时器
            self.recording_time = 0
            self.is_paused = False
            self.timer.start()

            # 悬浮录制指示条
            self._show_rec_indicator()

            # 自动美化：开始记录鼠标点击时间线
            self.mouse_tracker = None
            try:
                auto_beautify = self.rv.config.getboolean('record', 'auto_beautify', fallback=False)
            except Exception:
                auto_beautify = False
            if auto_beautify:
                self.mouse_tracker = MouseTracker()
                if self.mouse_tracker.start():
                    print('鼠标点击追踪已启动（用于自动缩放美化）')
                else:
                    self.mouse_tracker = None

            # 窗口已在录制开始前隐藏（区域/全屏均隐藏）

            self.update_state()
        else:
            question = QMessageBox()
            question.setText('检测到录制设备缺失，无法进行录制，请先完善设备设置。')
            question.setWindowTitle('提示')
            question.setIcon(QMessageBox.Icon.Question)
            question.addButton(QMessageBox.StandardButton.Yes)
            tmp_btn = question.button(QMessageBox.StandardButton.Yes)
            tmp_btn.setText('确定')
        
            question.adjustSize()
            screen_center = QtWidgets.QApplication.primaryScreen().geometry()
            question.move(int((screen_center.width() - question.width()) /2), int((screen_center.height() - question.height())/2))
            question.exec()
    
    def stop_record(self):
        """停止录制"""
        if self.recording or self.timer.isActive():
            self.timer.stop()
            self._close_rec_indicator()
            
            if self.record_type == RecordType.Screen:
                print('停止录制屏幕.')
            
            self.is_paused = False
            
            try:
                self.rv.stop_record()
            except KeyboardInterrupt as e:
                print(e)
            finally:
                # 恢复主窗口显示
                if self.isHidden():
                    self.show()
                    self.raise_()
                    self.activateWindow()

                # 停止录制后自动清除选择区域
                if self.record_type == RecordType.Screen and self.rb_region.isChecked():
                    self.clear_selected_region()

                self.update_state()

            # 弹窗让用户输入文件名；有美化时美化结果直接用该名字，原片保留默认名
            desired = self._ask_filename()
            if not self._run_auto_beautify(desired) and desired:
                # 没有生成美化视频（无点击等）时，直接把原片命名为用户输入的名字
                self._apply_name(getattr(self.rv, '_current_filename', None), desired)

    def _show_rec_indicator(self):
        """显示悬浮录制指示条——只放在录制区域外，保证不被录进视频。

        全屏录制或区域四周都放不下时不显示（屏幕上任何元素都会被录进去）。
        """
        self._close_rec_indicator()
        try:
            if not (self.record_type == RecordType.Screen
                    and self.rb_region.isChecked() and self.selected_region):
                print('全屏录制：不显示悬浮指示条（避免录进视频），'
                      '状态看右下角主窗口或托盘图标')
                return
            ind = RecIndicator()
            if not ind.place_outside(self.selected_region):
                print('录制区域周边放不下指示条，本次不显示（避免录进视频）')
                return
            ind.show()
            self.rec_indicator = ind
        except Exception as e:
            print('录制指示条显示失败: %s' % e)

    def _close_rec_indicator(self):
        """关闭悬浮录制指示条"""
        ind = getattr(self, 'rec_indicator', None)
        if ind:
            try:
                ind.close()
            except Exception:
                pass
            self.rec_indicator = None

    def _ask_filename(self):
        """停止后弹出对话框，让用户输入文件名（取消、留空或未改动返回 None）"""
        from PySide6.QtWidgets import QInputDialog, QLineEdit
        final = getattr(self.rv, '_current_filename', None)
        if not final or not os.path.exists(final):
            return None
        base = os.path.splitext(os.path.basename(final))[0]
        folder = os.path.dirname(final)
        text, ok = QInputDialog.getText(self, '保存录像',
                                        '请输入文件名：\n（保存位置：%s）' % folder,
                                        QLineEdit.EchoMode.Normal, base)
        if not ok:
            return None
        new_base = ''.join(c for c in text.strip() if c not in '\\/:*?"<>|')
        return new_base if new_base and new_base != base else None

    def _unique_path(self, folder, base, ext):
        """生成不重名的目标路径：重名自动加 (1)(2)… 序号"""
        target = os.path.join(folder, base + ext)
        n = 1
        while os.path.exists(target):
            target = os.path.join(folder, '%s(%d)%s' % (base, n, ext))
            n += 1
        return target

    def _apply_name(self, final, new_base):
        """把录制文件重命名为 new_base（重名自动加序号），并同步内部路径"""
        if not final or not os.path.exists(final):
            return
        folder = os.path.dirname(final)
        ext = os.path.splitext(final)[1]
        target = self._unique_path(folder, new_base, ext)
        try:
            os.rename(final, target)
            self.rv._final_filename = target
            self.rv._current_filename = target
            print('文件已命名为: %s' % target)
        except Exception as e:
            print('重命名失败: %s' % e)

    def _run_auto_beautify(self, desired_name=None):
        """停止鼠标追踪，并在后台线程生成缩放美化视频；返回是否启动了美化"""
        tracker = getattr(self, 'mouse_tracker', None)
        self.mouse_tracker = None
        if not tracker:
            return False
        events = tracker.stop()
        if not events:
            print('未检测到鼠标点击，跳过自动美化')
            return False
        video = getattr(self.rv, '_current_filename', None)
        if not video or not os.path.exists(video) or os.path.getsize(video) <= 0:
            print('未找到有效录制文件，跳过自动美化')
            return False
        try:
            zoom = self.rv.config.getfloat('record', 'beautify_zoom', fallback=2.0)
        except Exception:
            zoom = 2.0
        # 区域录制时，把屏幕坐标换算为视频坐标（录制区域原点）
        region = getattr(self.rv, 'current_region', None)
        origin = (region[0], region[1]) if region else (0, 0)

        # 用户命名且要做美化时：美化结果用输入名，原视频改名为 输入名_原视频
        out_path = None
        if desired_name:
            folder = os.path.dirname(video)
            ext = os.path.splitext(video)[1]
            out_path = self._unique_path(folder, desired_name, ext)
            raw_target = self._unique_path(folder, desired_name + '_原视频', ext)
            try:
                os.rename(video, raw_target)
                self.rv._final_filename = raw_target
                self.rv._current_filename = raw_target
                video = raw_target
                print('原视频保存为: %s' % raw_target)
            except Exception as e:
                print('原视频重命名失败，保留默认名: %s' % e)

        self.status_label.setText("状态: 正在生成缩放美化视频...")
        print('开始自动美化（后台处理，共 %d 次点击）...' % len(events))

        # 状态栏显示已用时，避免长时间无反馈像卡死
        self._beautify_t0 = time.time()
        self._beautify_clock = QTimer(self)
        self._beautify_clock.timeout.connect(self._tick_beautify_status)
        self._beautify_clock.start(1000)

        def worker():
            try:
                out = BeautifyProcessor().process(video, events, zoom=zoom,
                                                  origin=origin,
                                                  output_path=out_path)
                if out:
                    self.beautify_done.emit(out)
            except Exception as e:
                print('自动美化失败: %s' % e)

        self.beautify_thread = threading.Thread(target=worker,
                                                name='Beautify', daemon=True)
        self.beautify_thread.start()
        return True

    def _tick_beautify_status(self):
        """美化期间每秒刷新状态栏；处理结束自动停表"""
        th = getattr(self, 'beautify_thread', None)
        if th and not th.is_alive():
            self._beautify_clock.stop()
            self.update_state()
            return
        elapsed = int(time.time() - self._beautify_t0)
        self.status_label.setText(
            "状态: 正在生成缩放美化视频...（已用时 %d 秒，视频越长耗时越久）" % elapsed)

    def on_beautify_toggled(self, checked):
        """开关「随鼠标缩放美化」并立即保存，下次录制即生效"""
        try:
            rc = RecordConfig()
            rc.config.set('record', 'auto_beautify', '1' if checked else '0')
            rc.write()
        except Exception as e:
            print('保存美化开关失败: %s' % e)
        print('随鼠标缩放美化: %s' % ('开' if checked else '关'))

    def _on_beautify_done(self, output_path):
        """美化完成回调（UI线程）"""
        self.update_state()
        QMessageBox.information(self, '保存完成',
                                '文件已保存：\n%s\n\n（未处理的原始版本以"_原视频"结尾，在同一文件夹）' % output_path)

    def toggle_pause_recording(self):
        """切换暂停状态（真实暂停：暂停期间不录制画面，恢复后自动无损拼接）"""
        if self.recording:
            if not self.is_paused:
                if self.rv.pause_record():
                    self.is_paused = True
                    self.btn_pause.setText("▶️ 继续")
                    self.status_label.setText("状态: 录制已暂停")
                    ind = getattr(self, 'rec_indicator', None)
                    if ind:
                        ind.set_paused(True)
                    print("录制已暂停")
            else:
                if self.rv.resume_record():
                    self.is_paused = False
                    self.btn_pause.setText("⏸️ 暂停")
                    self.status_label.setText("状态: 正在录制...")
                    ind = getattr(self, 'rec_indicator', None)
                    if ind:
                        ind.set_paused(False)
                    print("录制已恢复")
        else:
            print("当前没有录制，无法暂停")
    
    def update_recording_time(self):
        """更新录制时间显示"""
        # FFmpeg进程异常退出时（如音频设备不可用），1秒内自动恢复界面状态
        if not self.rv.recording:
            self.timer.stop()
            self.is_paused = False
            self.update_state()
            QMessageBox.warning(self, '录制已终止',
                                'FFmpeg录制进程异常退出，录制已停止。\n'
                                '常见原因：音频设备被占用或不可用。\n'
                                '详情请查看 %LOCALAPPDATA%\\影随录屏 下的 log.txt')
            return

        if not self.is_paused:
            self.recording_time += 1
        
        hours = self.recording_time // 3600
        minutes = (self.recording_time % 3600) // 60
        seconds = self.recording_time % 60
        
        time_text = f"录制时长: {hours:02d}:{minutes:02d}:{seconds:02d}"
        
        if self.is_paused:
            time_text += " (暂停)"
        
        self.time_label.setText(time_text)
    
    def show_setting(self):
        """显示设置窗口"""
        self.sw.update_setting.connect(self.update_setting)
        self.sw.showSettingWindow()
    
    def update_setting(self, changed):
        """更新设置"""
        if changed:
            print('update setting..')
            self.rv.load_config()
            
            self.rc = RecordConfig()
            self.load_shortcut()
            
            # 更新保存目录
            if hasattr(self, 'le_file_path'):
                file_dir = self.rc.config.get('record', 'file_dir')
                if file_dir and os.path.isdir(file_dir):
                    self.le_file_path.setText(os.path.abspath(file_dir))
            
            if hasattr(self, 'file_dir'):
                self.file_dir = self.rc.config.get('record', 'file_dir')
    
    def load_shortcut(self):
        """加载快捷键"""
        try:
            self.sc.clear()
            
            if hasattr(self, 'rc'):
                screen_key_group = self.rc.config.get('shortcut', 'screen')
                stop_record_key_group = self.rc.config.get('shortcut', 'stop')
                
                screen_shortcut = [int(key) for key in screen_key_group.split(',')]
                stop_shortcut = [int(key) for key in stop_record_key_group.split(',')]
                
                print('screen shortcut: %s' % screen_shortcut)
                print('stop shortcut: %s' % stop_shortcut)
                
                if screen_key_group:
                    self.sc.add(2, screen_shortcut, lambda: self.record(RecordType.Screen))
                if stop_record_key_group:
                    self.sc.add(3, stop_shortcut, self.stop_record)
        except Exception as e:
            print(f"加载快捷键失败: {e}")
    
    def record(self, rtype):
        """指定类型的录制"""
        # 设置录制模式 - 仅支持屏幕录制
        # 由于现在只支持屏幕录制，不需要设置rb_screen
        # if rtype == RecordType.Screen:
        #     self.rb_screen.setChecked(True)
        
        # 开始录制
        self.start_record()
    
    def monitor_shortcut(self):
        """注册全局热键（Ctrl+Shift+R 开始录制 / Ctrl+Shift+S 停止），并刷新提示条"""
        try:
            from Hotkeys import GlobalHotkeys
            rc = getattr(self, 'rc', None) or RecordConfig()
            bindings = []
            self._hint_keys = {}
            for name in ('screen', 'stop'):
                try:
                    keys = [int(k) for k in
                            rc.config.get('shortcut', name).split(',')]
                    bindings.append((name, keys))
                    self._hint_keys[name] = keys
                except Exception:
                    pass
            self.hotkeys = GlobalHotkeys()
            self.hotkeys.triggered.connect(self._on_hotkey)
            self.hotkeys.setup(bindings)
            print('全局热键已启用: %s' % self._hint_keys)
            if hasattr(self, 'hint_label'):
                self.hint_label.setText(self._build_hint_text())
        except Exception as e:
            print(f"快捷键加载失败: {e}")

    def _fmt_keys(self, keys):
        """把 VK 键码列表格式化成 'Ctrl+Shift+R' 样式（修饰键固定顺序）"""
        names = {160: 'Shift', 161: 'Shift', 162: 'Ctrl', 163: 'Ctrl',
                 164: 'Alt', 165: 'Alt'}
        parts = [n for n in ('Ctrl', 'Alt', 'Shift')
                 if any(names.get(k) == n for k in keys)]
        for k in keys:
            if k in names:
                continue
            if 65 <= k <= 90 or 48 <= k <= 57:
                parts.append(chr(k))
            else:
                parts.append('Key%d' % k)
        return '+'.join(parts)

    def _build_hint_text(self):
        """主窗口提示条文案：快捷键 + 录制时窗口缩小行为"""
        keys = getattr(self, '_hint_keys', {})
        screen_txt = self._fmt_keys(keys['screen']) if 'screen' in keys \
            else 'Ctrl+Shift+R'
        stop_txt = self._fmt_keys(keys['stop']) if 'stop' in keys \
            else 'Ctrl+Shift+S'
        return ('⌨️ 快捷键：{} 开始录制 · {} 停止录制\n'
                '🖥️ 全屏录制开始后，主窗口会自动缩小到屏幕右下角').format(
                    screen_txt, stop_txt)

    def _on_hotkey(self, hid):
        """热键动作（主线程执行）"""
        try:
            if hid == 'screen':
                if self.recording:
                    self.stop_record()
                else:
                    self.rb_fullscreen.setChecked(True)
                    self.start_record()
            elif hid == 'stop':
                if self.recording:
                    self.stop_record()
        except Exception as e:
            print('热键处理失败: %s' % e)
    
    def open_file_dir(self):
        """打开文件目录"""
        try:
            if hasattr(self, 'file_dir') and self.file_dir:
                if os.path.isdir(self.file_dir):
                    os.startfile(self.file_dir)
                else:
                    print('错误的文件目录：%s' % self.file_dir)
            else:
                # 尝试从配置中获取
                rc = RecordConfig()
                file_dir = rc.config.get('record', 'file_dir')
                if os.path.isdir(file_dir):
                    os.startfile(file_dir)
        except Exception as e:
            print(f"打开文件目录失败: {e}")
    
    def open_trim_video(self):
        """打开视频裁剪对话框（默认裁剪最近一次录制的视频）"""
        try:
            from TrimDialog import open_trim_dialog
            last = getattr(self.rv, '_current_filename', None)
            if last and not os.path.exists(last):
                last = None
            open_trim_dialog(last, parent=self)
        except Exception as e:
            print('打开裁剪功能失败: %s' % e)
            QMessageBox.warning(self, '错误', '打开裁剪功能失败：%s' % e)

    def open_current_file_dir(self):
        """打开当前选择的保存目录"""
        try:
            current_dir = self.le_file_path.text()
            if current_dir and os.path.exists(current_dir):
                os.startfile(current_dir)
            else:
                QMessageBox.warning(self, "提示", "保存目录不存在，请先选择有效的目录。")
        except Exception as e:
            print(f"打开当前保存目录失败: {e}")
            QMessageBox.warning(self, "错误", f"打开目录失败: {e}")
    
    def check_save_directory(self):
        """检查保存目录是否有效，如果无效则提示用户选择"""
        current_dir = self.le_file_path.text()
        
        # 如果目录为空或不存在，提示用户选择
        if not current_dir or not os.path.exists(current_dir):
            reply = QMessageBox.question(
                self, 
                "保存目录未设置", 
                "保存目录为空或不存在，是否现在选择保存目录？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 打开目录选择对话框
                self.browse_file_dir()
                # 重新检查目录
                new_dir = self.le_file_path.text()
                if new_dir and os.path.exists(new_dir):
                    return True
                else:
                    QMessageBox.warning(self, "警告", "未选择有效的保存目录，无法开始录制。")
                    return False
            else:
                QMessageBox.information(self, "提示", "请先设置保存目录后再开始录制。")
                return False
        
        return True
    
    def browse_file_dir(self):
        """浏览文件目录"""
        try:
            from PySide6.QtWidgets import QFileDialog
            
            current_dir = self.le_file_path.text()
            if not current_dir or not os.path.exists(current_dir):
                # 尝试从配置中获取默认目录
                rc = RecordConfig()
                current_dir = rc.config.get('record', 'file_dir')
                if not current_dir or not os.path.exists(current_dir):
                    current_dir = default_record_dir()
            
            selected_dir = QFileDialog.getExistingDirectory(
                self, '选择录像保存目录', current_dir, QFileDialog.Option.ShowDirsOnly
            )
            
            if selected_dir and os.path.exists(selected_dir):
                selected_dir = os.path.abspath(selected_dir)
                # 更新界面显示
                self.le_file_path.setText(selected_dir)

                # 自动保存到配置文件
                rc = RecordConfig()
                rc.config.set('record', 'file_dir', selected_dir)
                rc.write()

                # 同步到录制模块与托盘打开目录，无需重启立即生效
                self.rv.file_dir = selected_dir
                if hasattr(self, 'file_dir'):
                    self.file_dir = selected_dir

                print(f"保存目录已自动保存并生效: {selected_dir}")
                
        except Exception as e:
            print(f"浏览文件目录失败: {e}")
            QMessageBox.warning(self, "错误", f"选择目录失败: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 检查是否正在录制
        if self.recording:
            reply = QMessageBox.question(self, "确认退出", 
                                       "正在录制中，确定要退出吗？",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_record()
                self.force_quit()
            else:
                event.ignore()
                return
        
        # 没有录制或用户确认退出
        self.force_quit()
        
    def force_quit(self):
        """强制退出程序"""
        print('软件将退出.')
        
        # 清理资源
        try:
            # 停止计时器
            if hasattr(self, 'timer'):
                self.timer.stop()
            
            # 清理快捷键
            if hasattr(self, 'sc'):
                try:
                    self.sc.clear()
                except:
                    pass
            
            # 清理区域覆盖层
            if hasattr(self, 'area_overlay') and self.area_overlay:
                try:
                    self.area_overlay.hide_overlay()
                    self.area_overlay.close()
                except:
                    pass
            
            # 清理录制模块
            if hasattr(self, 'rv'):
                try:
                    if hasattr(self.rv, 'cleanup'):
                        self.rv.cleanup()
                except:
                    pass
            
            # 清理托盘图标
            if hasattr(self, 'rti') and self.rti:
                try:
                    self.rti.hide()
                    del self.rti
                except:
                    pass
            
        except Exception as e:
            print(f"清理资源时出错: {e}")
        
        # 完全退出应用
        QCoreApplication.instance().quit()
        
        # 额外的退出保障
        import sys
        sys.exit(0)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 单实例锁：避免同时运行两个实例
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

    # 获取屏幕分辨率
    screen = app.primaryScreen().geometry()
    resolution = '{}x{}'.format(screen.width(), screen.height())
    
    # 创建主窗口
    rw = ModernRecordWindow(screen_resolution=resolution)
    rw.monitor_shortcut()
    
    # 显示托盘图标
    if hasattr(rw, 'rti') and rw.rti:
        rw.rti.show()
    
    # 显示主窗口
    rw.show()
    
    sys.exit(app.exec())