import sys
from PySide6.QtWidgets import QApplication, QLabel, QDialog
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QMouseEvent
import pyautogui

class AreaSelector(QDialog):
    area_selected = Signal(int, int, int, int)  # x, y, width, height
    
    def __init__(self):
        super().__init__()
        self.setModal(True)  # 设置为模态对话框
        
        self.screen = QApplication.primaryScreen()
        self.screen_geometry = self.screen.geometry()
        
        # 检测DPI缩放比例
        self.detect_dpi_scaling()
        
        # 设置窗口标志 - 确保全屏且位置正确
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")
        
        # 设置窗口大小和位置 - 确保从屏幕(0,0)开始
        self.setGeometry(0, 0, self.screen_geometry.width(), self.screen_geometry.height())
        
        self.selection_start = None
        self.selection_end = None
        self.selecting = False
        self.selection_result = None
        
        # 提示标签
        self.hint_label = QLabel("拖动鼠标选择录制区域", self)
        self.hint_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold; background-color: rgba(0, 0, 0, 150); padding: 10px;")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setGeometry(0, 0, 400, 40)
        self.hint_label.move((self.width() - 400) // 2, 50)
        
        # 直接显示窗口 - 已经设置了正确的几何
        self.show()
    
    def detect_dpi_scaling(self):
        """检测DPI缩放比例"""
        try:
            # 获取PyAutoGUI报告的屏幕尺寸
            pyautogui_size = pyautogui.size()
            
            # 获取实际截图尺寸
            screenshot = pyautogui.screenshot()
            actual_size = screenshot.size
            
            # 计算缩放比例
            self.scale_x = actual_size[0] / pyautogui_size.width()
            self.scale_y = actual_size[1] / pyautogui_size.height()
            
            print(f"DPI检测 - PyAutoGUI尺寸: {pyautogui_size}")
            print(f"DPI检测 - 实际截图尺寸: {actual_size}")
            print(f"DPI检测 - 缩放比例: {self.scale_x:.3f}x, {self.scale_y:.3f}x")
            
            # 如果检测到缩放，调整窗口几何
            if self.scale_x != 1.0 or self.scale_y != 1.0:
                print("检测到DPI缩放，调整窗口尺寸")
                self.actual_screen_width = int(self.screen_geometry.width() * self.scale_x)
                self.actual_screen_height = int(self.screen_geometry.height() * self.scale_y)
                self.setGeometry(0, 0, self.actual_screen_width, self.actual_screen_height)
            else:
                self.scale_x = 1.0
                self.scale_y = 1.0
                self.actual_screen_width = self.screen_geometry.width()
                self.actual_screen_height = self.screen_geometry.height()
                
        except Exception as e:
            print(f"DPI检测失败，使用默认值: {e}")
            self.scale_x = 1.0
            self.scale_y = 1.0
            self.actual_screen_width = self.screen_geometry.width()
            self.actual_screen_height = self.screen_geometry.height()
    
    def fix_coordinates_for_recording(self, x, y, width, height):
        """将选择区域坐标转换为录制区域坐标"""
        if self.scale_x != 1.0 or self.scale_y != 1.0:
            # 从UI坐标转换到实际录制坐标
            fixed_x = int(x * self.scale_x)
            fixed_y = int(y * self.scale_y)
            fixed_width = int(width * self.scale_x)
            fixed_height = int(height * self.scale_y)
            print(f"坐标转换: ({x},{y},{width},{height}) -> ({fixed_x},{fixed_y},{fixed_width},{fixed_height})")
            return (fixed_x, fixed_y, fixed_width, fixed_height)
        else:
            return (x, y, width, height)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        if self.selection_start and self.selection_end:
            selection_rect = QRect(self.selection_start, self.selection_end).normalized()
            
            # 绘制选中区域
            painter.fillRect(selection_rect, QColor(0, 0, 0, 0))
            
            # 绘制边框 - 使用鲜艳的深红色
            pen = QPen(QColor(220, 20, 60), 3, Qt.PenStyle.SolidLine)  # 鲜艳的深红色 (Crimson)，增加线宽
            painter.setPen(pen)
            painter.drawRect(selection_rect)
            
            # 显示尺寸信息
            width = selection_rect.width()
            height = selection_rect.height()
            size_text = f"{width} x {height}"
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawText(selection_rect.x(), selection_rect.y() - 5, size_text)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.selecting = True
            self.hint_label.hide()
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.reject()  # 右键取消选择
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.selecting:
            self.selection_end = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        try:
            print(f"鼠标释放事件: {event.button()}, 选择状态: {self.selecting}")
            if event.button() == Qt.MouseButton.LeftButton and self.selecting:
                self.selection_end = event.pos()
                self.selecting = False
                
                # 计算最终选中区域
                selection_rect = QRect(self.selection_start, self.selection_end).normalized()
                x = selection_rect.x()
                y = selection_rect.y()
                width = selection_rect.width()
                height = selection_rect.height()
                
                print(f"选中区域: x={x}, y={y}, width={width}, height={height}")
                print(f"选择起始点: {self.selection_start}")
                print(f"选择结束点: {self.selection_end}")
                print(f"选择矩形: {selection_rect}")
                print(f"窗口几何: {self.geometry()}")
                
                # 最小尺寸限制
                if width < 10 or height < 10:
                    print("区域太小，取消选择")
                    self.reject()  # 区域太小时取消选择
                    return
                
                # 将结果存储在对话框中，应用DPI缩放修复
                self.selection_result = self.fix_coordinates_for_recording(x, y, width, height)
                print("设置结果并关闭窗口")
                self.accept()  # 使用accept而不是close
            else:
                print(f"不触发选择: 按钮={event.button()}, 选择状态={self.selecting}")
        except Exception as e:
            print(f"区域选择错误: {e}")
            self.reject()  # 发生错误时拒绝对话框

def select_area():
    app = QApplication.instance()
    created_new_app = False
    
    if app is None:
        app = QApplication(sys.argv)
        created_new_app = True
    
    selector = AreaSelector()
    
    # 初始化结果存储
    selector.selection_result = None
    
    print("显示区域选择对话框...")
    dialog_result = selector.exec()
    print(f"对话框结果: {dialog_result}")
    
    # 直接从对话框获取结果
    result = selector.selection_result
    print(f"返回的区域结果: {result}")
    
    # 只有当我们创建了新应用时才退出
    if created_new_app:
        app.quit()
    
    return result

if __name__ == "__main__":
    area = select_area()
    if area:
        print(f"选中的区域: {area}")