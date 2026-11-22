import os,configparser
import sys
import shutil

APP_NAME = '影随录屏'
CONFIG_FILE_NAME = 'configByLinxiao.ini'


def app_data_dir():
    """用户数据目录：%LOCALAPPDATA%\影随录屏（不存在则创建），配置与日志统一落在这里。"""
    d = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), APP_NAME)
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def default_record_dir():
    """录制视频默认保存目录：用户媒体文件放 视频库\影随录屏（不塞 LOCALAPPDATA）。"""
    return os.path.join(os.path.expanduser('~'), 'Videos', APP_NAME)


def _migrate_legacy_ini():
    """首次初始化：新目录无 ini 而旧位置（exe 同级 / 工作目录）有 ini 时，
    复制到新目录完成初始化（旧位置的默认 ini 保留不动）；都没有则由 load() 写默认配置。"""
    target = os.path.join(app_data_dir(), CONFIG_FILE_NAME)
    if os.path.exists(target):
        return
    if getattr(sys, 'frozen', False):
        # 打包版：安装时默认 ini 在 exe 同级（{app}）
        candidates = [os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                                   CONFIG_FILE_NAME)]
    else:
        candidates = [os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   CONFIG_FILE_NAME)]
    candidates.append(os.path.join(os.getcwd(), CONFIG_FILE_NAME))
    for src in candidates:
        if os.path.abspath(src) == os.path.abspath(target):
            continue
        if not os.path.isfile(src):
            continue
        try:
            shutil.copy2(src, target)
        except OSError:
            pass
        return


_migrate_legacy_ini()


class RecordConfig():
    def __init__(self, config_file_name = None):
        # 配置文件唯一确定：%LOCALAPPDATA%\影随录屏\configByLinxiao.ini
        self.file_name = config_file_name or os.path.join(app_data_dir(), CONFIG_FILE_NAME)
        self.encoding = 'utf-8'
        self.load()

    def load(self):

        if os.path.exists(self.file_name):
            if sys.version_info >= (3, 2):
                self.config=configparser.ConfigParser()
            else:
                self.config=configparser.SafeConfigParser()
            self.config.read(self.file_name, encoding = self.encoding)
        else:
            self.write_default_config()
            self.load()

    def write_default_config(self):
        print('初始化配置文件.')
        if sys.version_info >= (3, 2):
            conf = configparser.ConfigParser()
        else:
            conf = configparser.SafeConfigParser()

        # di = DevicesInfo()
        devices_section_name = 'devices'
        conf.add_section(devices_section_name)
        conf.set(devices_section_name,'voice_device_name','')
        conf.set(devices_section_name,'screen_device_name','')
        conf.set(devices_section_name,'system_voice_device_name','')

        shortcut_section_name = 'shortcut'
        conf.add_section(shortcut_section_name)
        conf.set(shortcut_section_name,'camera','160,162,164,65')
        conf.set(shortcut_section_name,'screen','160,162,164,66')
        conf.set(shortcut_section_name,'stop','160,162,164,67')

        record_section_name = 'record'
        conf.add_section(record_section_name)
        conf.set(record_section_name,'resolution','1920x1080')
        conf.set(record_section_name,'adaptive_screen_resolution','1')
        conf.set(record_section_name,'vcodec','libx264')
        conf.set(record_section_name,'frame_rate','24.0')
        conf.set(record_section_name,'auto_frame_rate','1')
        conf.set(record_section_name,'file_dir', default_record_dir())
        conf.set(record_section_name,'threads', '4')
        # GPU加速选项（默认关闭，使用CPU编码）
        conf.set(record_section_name,'gpu_acceleration','0')
        conf.set(record_section_name,'gpu_encoder','h264_nvenc')
        conf.set(record_section_name,'hw_accel','cuda')
        # 系统声音采集方式（1=WASAPI loopback免驱动，0=回退立体声混音）
        conf.set(record_section_name,'use_loopback','1')
        # 自动缩放美化（点击处自动推近镜头，Screen Studio 风格）
        conf.set(record_section_name,'auto_beautify','1')
        conf.set(record_section_name,'beautify_zoom','2.0')

        conf.add_section('author')
        conf.set('author', 'name', 'linxiao')
        conf.set('author', 'mail', '940950943@qqqqqqqqqqqqqqqqqqqqqqqqqqqq.com')

        self.config = conf
        self.write()

    def write(self):
        parent = os.path.dirname(self.file_name)
        if parent:
            try:
                os.makedirs(parent, exist_ok=True)
            except OSError:
                pass
        with open(self.file_name, 'wt', encoding = self.encoding) as configfp:
            self.config.write(configfp)
