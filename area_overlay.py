import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton
from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QBrush

class AreaOverlay(QWidget):
    """区域覆盖层 - 显示录制区域边框，支持拖动"""
    
    def __init__(self, region, simple_corners=False):
        super().__init__()
        self.recording_region = region  # 实际录制区域 (x, y, width, height)
        self.is_paused = False
        self.is_recording = False  # 录制状态
        self.is_dragging = False    # 是否正在拖动
        self.drag_offset = None      # 拖动偏移量
        self.simple_corners = simple_corners  # 是否使用简化角落
        self.border_thickness = 2    # 边框厚度（边框在录制区域外部）
        self.init_ui()
        
    def init_ui(self):
        # 设置窗口属性 - 覆盖层比录制区域大，边框在外部
        x, y, width, height = self.recording_region
        
        # 覆盖层边界包含边框厚度
        overlay_x = x - self.border_thickness
        overlay_y = y - self.border_thickness  
        overlay_width = width + 2 * self.border_thickness
        overlay_height = height + 2 * self.border_thickness
        
        self.setGeometry(overlay_x, overlay_y, overlay_width, overlay_height)
        
        # 设置窗口属性 - 始终不允许鼠标交互
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool | 
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        
        # 设置窗口背景透明
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    
    def set_paused(self, is_paused):
        """设置暂停状态"""
        self.is_paused = is_paused
        self.update()
    
    def set_recording(self, is_recording):
        """设置录制状态并更新窗口属性"""
        self.is_recording = is_recording
        
        # 保持窗口属性不变 - 始终不允许鼠标交互
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool | 
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        
        self.update()
        self.show()  # 更新窗口属性后需要重新显示
    
    def mousePressEvent(self, event):
        """鼠标按下事件 - 禁用拖动"""
        pass  # 禁用拖动功能
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 禁用拖动"""
        pass  # 禁用拖动功能
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件 - 禁用拖动"""
        pass  # 禁用拖动功能
    
    def enterEvent(self, event):
        """鼠标进入事件 - 不显示移动光标"""
        pass  # 禁用光标变化
    
    def leaveEvent(self, event):
        """鼠标离开事件 - 不显示正常光标"""
        pass  # 禁用光标变化
    
    def _draw_recording_border(self, painter, overlay_rect, recording_rect):
        """绘制录制状态的边框 - 使用透明红色"""
        try:
            # 使用不透明红色边框
            border_color = QColor(255, 0, 0, 255)  # 不透明红色
            border_pen = QPen(border_color, self.border_thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(border_pen)
            painter.drawRect(recording_rect)
            
        except Exception as e:
            print(f"绘制录制边框失败: {e}")
    
    def _draw_idle_border(self, painter, overlay_rect, recording_rect):
        """绘制非录制状态的边框 - 使用透明红色"""
        try:
            # 使用不透明红色边框
            border_color = QColor(255, 0, 0, 255)  # 不透明红色
            border_pen = QPen(border_color, self.border_thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(border_pen)
            painter.drawRect(recording_rect)
            
        except Exception as e:
            print(f"绘制空闲边框失败: {e}")
    
    def _draw_drag_hint(self, painter, overlay_rect):
        """绘制拖动提示 - 已禁用"""
        pass  # 禁用拖动提示
    
    def _draw_simple_corners(self, painter, rect, color, size):
        """简单角落标记"""
        painter.setPen(QPen(color, 3))
        corners = [
            (0, 0),
            (rect.width() - size, 0),
            (0, rect.height() - size),
            (rect.width() - size, rect.height() - size)
        ]
        
        for cx, cy in corners:
            painter.drawLine(cx, cy, cx + size//2, cy)
            painter.drawLine(cx, cy, cx, cy + size//2)
    
    def _draw_detailed_corners(self, painter, rect, outer_color, inner_color, size):
        """详细角落标记 - 双色"""
        # 外层角落
        painter.setPen(QPen(outer_color, 3))
        corners = [
            (0, 0),
            (rect.width() - size, 0),
            (0, rect.height() - size),
            (rect.width() - size, rect.height() - size)
        ]
        
        for cx, cy in corners:
            painter.drawLine(cx, cy, cx + size, cy)
            painter.drawLine(cx, cy, cx, cy + size)
        
        # 内层角落 - 对比色
        inner_size = size // 2
        inner_pen = QPen(inner_color, 2)
        painter.setPen(inner_pen)
        
        inner_corners = [
            (size, size),
            (rect.width() - size - inner_size, size),
            (size, rect.height() - size - inner_size),
            (rect.width() - size - inner_size, rect.height() - size - inner_size)
        ]
        
        for cx, cy in inner_corners:
            painter.drawLine(cx, cy, cx + inner_size, cy)
            painter.drawLine(cx, cy, cx, cy + inner_size)
    
    def _draw_drag_hint(self, painter, overlay_rect):
        """绘制拖动提示"""
        # 提示文本
        hint_text = "拖动选框调整位置"
        
        # 设置文本样式
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        
        # 计算文本位置（在窗口底部）
        text_width = painter.fontMetrics().width(hint_text)
        text_height = painter.fontMetrics().height()
        text_x = (overlay_rect.width() - text_width) // 2
        text_y = overlay_rect.height() - 10
        
        # 绘制文本背景
        padding = 5
        text_bg_rect = QRect(
            text_x - padding, 
            text_y - text_height - padding, 
            text_width + 2 * padding, 
            text_height + 2 * padding
        )
        painter.fillRect(text_bg_rect, QColor(0, 0, 0, 150))
        
        # 绘制文本
        painter.drawText(text_x, text_y, hint_text)
    
    def _draw_recording_area_hint(self, painter, recording_rect):
        """绘制录制区域指示 - 用于调试"""
        # 绘制内部区域的轮廓
        hint_pen = QPen(QColor(255, 255, 0, 150), 1, Qt.PenStyle.DashLine)
        painter.setPen(hint_pen)
        painter.drawRect(recording_rect.adjusted(1, 1, -1, -1))
        
        # 显示录制区域的坐标和尺寸
        size_text = f"录制区域: {recording_rect.width()} x {recording_rect.height()}"
        coord_text = f"坐标: ({recording_rect.x()}, {recording_rect.y()})"
        
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        font = painter.font()
        font.setPointSize(7)
        painter.setFont(font)
        
        # 绘制文本
        painter.drawText(recording_rect.x() + 5, recording_rect.y() - 15, size_text)
        painter.drawText(recording_rect.x() + 5, recording_rect.y() - 5, coord_text)
    
    def show_overlay(self):
        """显示覆盖层"""
        try:
            # 确保窗口在最上层
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            self.show()
            self.raise_()
            self.activateWindow()
            
            # 强制重绘
            self.update()
            
            print(f"覆盖层显示成功，录制区域: {self.recording_region}")
            print(f"覆盖层几何: {self.geometry()}")
            print(f"边框厚度: {self.border_thickness}")
            
        except Exception as e:
            print(f"显示覆盖层失败: {e}")
    
    def hide_overlay(self):
        """隐藏覆盖层"""
        try:
            self.hide()
            print("覆盖层已隐藏")
            
        except Exception as e:
            print(f"隐藏覆盖层失败: {e}")
    
    def get_recording_region(self):
        """获取当前录制区域"""
        return self.recording_region
    
    def closeEvent(self, event):
        """关闭事件处理"""
        self.hide_overlay()
        event.accept()
    
    def paintEvent(self, event):
        """绘制事件 - 调用相应的绘制方法"""
        print("paintEvent被调用")
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 获取窗口矩形
            overlay_rect = self.rect()
            print(f"覆盖层矩形: {overlay_rect}")
            
            # 计算录制区域在覆盖层内的相对位置
            # 覆盖层包含了边框厚度，所以录制区域在内部
            recording_rect = QRect(
                self.border_thickness,  # x 从边框厚度开始
                self.border_thickness,  # y 从边框厚度开始
                overlay_rect.width() - 2 * self.border_thickness,  # 宽度减去两倍边框厚度
                overlay_rect.height() - 2 * self.border_thickness  # 高度减去两倍边框厚度
            )
            print(f"录制区域矩形: {recording_rect}")
            
            # 不绘制背景，保持全透明
            
            # 根据录制状态绘制边框
            if self.is_recording:
                self._draw_recording_border(painter, overlay_rect, recording_rect)
                print("绘制录制边框")
            else:
                self._draw_idle_border(painter, overlay_rect, recording_rect)
                print("绘制空闲边框")
                
        except Exception as e:
            print(f"绘制覆盖层失败: {e}")
            import traceback
            traceback.print_exc()

class RecordingIndicator(QWidget):
    """录制指示器 - 显示录制状态"""
    
    def __init__(self, is_fullscreen=False, parent=None, main_window=None):
        super().__init__(parent)
        self.is_fullscreen = is_fullscreen
        self.main_window = main_window
        self.init_ui()
    
    def init_ui(self):
        """初始化录制指示器界面"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 设置指示器大小和位置
        indicator_size = 24
        margin = 10
        
        if self.is_fullscreen:
            # 全屏录制时，指示器放在屏幕左上角
            self.setGeometry(margin, margin, indicator_size, indicator_size)
        else:
            # 窗口录制时，指示器放在窗口内
            self.setGeometry(margin, margin, indicator_size, indicator_size)
        
        # 创建停止按钮
        self.btn_stop = QPushButton("", self)
        self.btn_stop.setGeometry(0, 0, indicator_size, indicator_size)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #FF3333;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #FF0000;
            }
        """)
        
        # 连接停止按钮信号
        self.btn_stop.clicked.connect(self.on_stop_recording)
    
    def on_stop_recording(self):
        """停止录制事件处理"""
        # 通知主窗口停止录制
        if self.main_window and hasattr(self.main_window, 'stop_record'):
            self.main_window.stop_record()
        
        # 关闭指示器
        self.close()