# -*- coding: utf-8 -*-
"""通用「关于」对话框：图标 + 应用名 + 版本 + 公司 + 网址。

标准公司信息规范，所有桌面应用共用；信息变更只改这里的常量。
"""

from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from version import VERSION

COMPANY = '深圳市创炫互动网络科技有限公司'
WEBSITE = 'www.mrheedu.com'
WEBSITE_URL = 'https://www.mrheedu.com'


def find_icon(name='图标.png'):
    """找应用图标（约定放在项目根目录）；打包环境下查找 exe 所在目录与 _MEIPASS。"""
    if getattr(sys, 'frozen', False):
        folders = [Path(sys.executable).parent]
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            folders.append(Path(meipass))
    else:
        base = Path.cwd()
        folders = [base, *list(base.parents)[:3]]
    for folder in folders:
        p = folder / name
        if p.exists():
            return p
    return None


def app_icon(name='图标.png'):
    """返回应用图标；找不到时返回 None，调用方跳过 setWindowIcon。"""
    path = find_icon(name)
    if path:
        return QIcon(str(path))
    return None


class AboutDialog(QDialog):
    def __init__(self, app_name, parent=None, icon_path=None):
        super().__init__(parent)
        self.setWindowTitle('关于 %s' % app_name)
        root = QVBoxLayout(self)

        row = QHBoxLayout()
        path = icon_path or find_icon()
        if path:
            pic = QLabel()
            pic.setPixmap(QPixmap(str(path)).scaled(
                72, 72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            row.addWidget(pic)

        info = QLabel(
            '<h2>%s</h2>'
            '<p>版本：%s</p>'
            '<p>公司：%s</p>'
            '<p>更多免费软件：<a href="%s">%s</a></p>'
            % (app_name, VERSION, COMPANY, WEBSITE_URL, WEBSITE))
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setOpenExternalLinks(True)
        row.addWidget(info, stretch=1)
        root.addLayout(row)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(self.accept)
        root.addWidget(btns)


def show_about(app_name, parent=None, icon_path=None):
    """弹出「关于」对话框。"""
    AboutDialog(app_name, parent, icon_path).exec()
