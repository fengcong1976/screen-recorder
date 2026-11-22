import datetime,time,sys,os,signal,re,winreg
from datetime import datetime
import subprocess,threading
from subprocess import CalledProcessError
# from multiprocessing import Process
from threading import Thread
import ctypes,inspect
import RecordType
from RecordType import *
import RecordConfig
from RecordConfig import *
import logging
import RunCMD
from RunCMD import get_ffmpeg_path
from winreg import HKEY_CURRENT_USER, OpenKey, QueryInfoKey, EnumValue, SetValueEx, CloseKey, REG_SZ, KEY_READ, KEY_SET_VALUE
from DevicesInfo import DevicesInfo
from SystemAudioCapture import SystemAudioCapture

class RecordVideo():

    r'''
        ffmpeg -f dshow -i video="@device_pnp_\\\\?\usb#vid_04f2&pid_b354&mi_00#7&30d7ad30&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global":audio="@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\wave_{571529B3-7DB3-42A3-ADEF-BBD82925C15D}" -acodec libmp3lame -vcodec libx265 -preset:v ultrafast -tune:v zerolatency -s 1920x1080 -r 7 -y record_camera_20180408_182541.mkv
        
    r'''    
    
    def __init__(self, record_video=True, record_voice=True):
        # print('视频录制初始化中...')
        # self.record_video=record_video
        # self.record_voice=record_voice
        #录制状态
        self.recording = False
        self.paused = False  # 真实暂停状态（FFmpeg进程已停止，等待恢复）
        self.exception_exit = False
        self.gpu_failed = False  # GPU失败标志
        self.gpu_fallbacks = ['h264_qsv']  # GPU编码器降级链：NVENC失败后依次尝试
        self.segments = []  # 分段录制产生的文件列表（暂停时切换分段，停止后无损拼接）
        self._cmd_no_output = None  # 不含输出文件的命令模板（恢复录制时复用）
        self._final_filename = None  # 最终输出文件名
        self.audio_capture = None  # WASAPI loopback系统声音采集器
        self.use_loopback = True  # system音源优先使用WASAPI loopback
        self.record_type=RecordType.Screen
        # 当前录制的区域信息 (x, y, width, height)
        self.current_region = None
        #文件名称
        self.file_name='record'
        #文件后缀
        self.file_suffix='.mp4'
        self.process = None
        self.record_thread_name='record'
        self.record_thread=None
        
        self.file_dir = ''
        self.last_error = ''
        self.load()
        
    def load(self):
        #日志
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level = logging.INFO)
        handler = logging.FileHandler(os.path.join(app_data_dir(), 'log.txt'))
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)    
        
        self.logger.addHandler(handler)
        
        self.load_config()
        
        # 设备信息
        self.devices_info = None
        
    def load_config(self):
  
        rc = RecordConfig()
        self.config = rc.config
        
        #麦克风名称
        self.voice_device_name=rc.config.get('devices','voice_device_name')
        if not self.voice_device_name or self.voice_device_name == 'None':
            # 配置残留空值/None：现场探测第一个麦克风
            try:
                from DevicesInfo import DevicesInfo
                di = DevicesInfo()
                if di.voice_devices:
                    self.voice_device_name = di.voice_devices[0][0]
                    rc.config.set('devices', 'voice_device_name',
                                  self.voice_device_name)
                    rc.write()
            except Exception as _e:
                self.logger.warning('自动探测麦克风失败: %s' % _e)
        #录制屏幕名称
        self.screen_name=rc.config.get('devices','screen_device_name')
        #系统声音设备名称
        self.system_voice_device_name=rc.config.get('devices','system_voice_device_name')
        #视频编码
        self.video_codec=rc.config.get('record','vcodec')
        #分辨率
        self.resolution=rc.config.get('record','resolution')
        #是否自适应屏幕录制分辨率
        self.adaptive_screen_resolution = rc.config.getboolean('record', 'adaptive_screen_resolution')
        #帧率
        self.brate=rc.config.getfloat('record','frame_rate')
        self.auto_frame_rate = rc.config.getboolean('record', 'auto_frame_rate')
        #文件目录
        self.file_dir= os.path.abspath(rc.config.get('record','file_dir'))
        #线程数
        self.threads = rc.config.getint('record','threads')
        #GPU加速选项
        self.gpu_acceleration = rc.config.getboolean('record', 'gpu_acceleration')
        self.gpu_encoder = rc.config.get('record', 'gpu_encoder')
        self.hw_accel = rc.config.get('record', 'hw_accel')
        # 系统声音采集方式（True=WASAPI loopback免驱动，False=回退立体声混音）
        self.use_loopback = rc.config.getboolean('record', 'use_loopback', fallback=True)
        
        self.logger.info('voice device name: %s' % self.voice_device_name)
        self.logger.info('screen device name: %s' % self.screen_name)
        self.logger.info('system voice device name: %s' % self.system_voice_device_name)
        self.logger.info('vcodec: %s' % self.video_codec)
        self.logger.info('resolution: %s' % self.resolution)
        self.logger.info('frame rate: %s' % self.brate)
        self.logger.info('save dir: %s' % self.file_dir)
        self.logger.info('gpu acceleration: %s' % self.gpu_acceleration)
        if self.gpu_acceleration:
            self.logger.info('gpu encoder: %s' % self.gpu_encoder)
            self.logger.info('hw accel: %s' % self.hw_accel)
        self.logger.info('auto frame rate: %s' % self.auto_frame_rate)
        
    
    
    def _setup_audio_input(self, audio_source):
        """准备音频输入。
        返回 (use_audio, audio_device, tcp_port)：
        - system音源：优先WASAPI loopback（tcp_port非None），不可用回退dshow设备
        - mic音源：走dshow设备
        """
        use_audio = True
        audio_device = None
        tcp_port = None
        try:
            if audio_source == 'system' and getattr(self, 'use_loopback', True):
                cap = SystemAudioCapture()
                port = cap.start()
                if port:
                    self.audio_capture = cap
                    tcp_port = port
                    return use_audio, audio_device, tcp_port
                print('WASAPI loopback不可用，回退到DirectShow音频设备')
            from DevicesInfo import DevicesInfo
            device_info = DevicesInfo()
            audio_device = self._resolve_audio_device(audio_source, device_info)
        except Exception as e:
            print(f'获取音频设备失败: {e}')
        if audio_device:
            print(f"使用音频设备: {audio_device}")
        else:
            print("警告: 未检测到音频设备，将仅录制视频")
            use_audio = False
        return use_audio, audio_device, tcp_port

    def record_screen(self, resolution=None, audio_source="system"):
        """录制整个屏幕"""
        self.last_error = ''
        try:
            # 设置录制类型（必须在调用get_file_name之前）
            self.record_type = RecordType.Screen
            
            # 解析屏幕分辨率
            if resolution and 'x' in str(resolution):
                width, height = map(int, resolution.split('x'))
            else:
                # 获取屏幕分辨率作为默认值
                try:
                    import sys
                    if sys.platform == 'win32':
                        import ctypes
                        user32 = ctypes.windll.user32
                        width = user32.GetSystemMetrics(0)
                        height = user32.GetSystemMetrics(1)
                    else:
                        width, height = 1920, 1080  # 默认分辨率
                except:
                    width, height = 1920, 1080  # 默认分辨率
            
            # 准备音频输入（system音源优先WASAPI loopback，mic走DirectShow设备）
            use_audio, audio_device, tcp_port = self._setup_audio_input(audio_source)
            
            # 构建录制命令参数（不包含ffmpeg命令名）
            cmd_list = []
            
            # 如果启用GPU加速，首先添加GPU加速参数（必须在输入文件之前）
            if self.gpu_acceleration and not self.gpu_failed and self.hw_accel:
                cmd_list.extend(['-hwaccel', self.hw_accel])
            
            # 添加视频输入参数
            cmd_list.extend(['-f', 'gdigrab', '-framerate', str(int(self.brate)), '-i', 'desktop'])
            
            # 添加音频参数
            if use_audio and tcp_port:
                cmd_list.extend(['-f', 's16le',
                                 '-ar', str(self.audio_capture.sample_rate),
                                 '-ac', str(self.audio_capture.channels),
                                 '-i', 'tcp://127.0.0.1:%d' % tcp_port])
            elif use_audio and audio_device:
                # 当使用shell=False时，不需要在参数中添加引号
                cmd_list.extend(['-f', 'dshow', '-i', f'audio={audio_device}'])
            
            # 添加视频编码参数
            if self.gpu_acceleration and not self.gpu_failed:
                # 已经添加了hwaccel参数，这里只需要添加编码器
                cmd_list.extend(['-c:v', self.gpu_encoder])
            else:
                cmd_list.extend(['-c:v', self.video_codec])
            
            # 添加音频编码参数
            if use_audio:
                cmd_list.extend(['-c:a', 'aac'])
                # 添加音量增益滤镜，将音量增加一倍（1.0表示原始音量，3.0表示两倍音量）
                cmd_list.extend(['-af', 'volume=3.0'])

            # 添加其他通用参数
            cmd_list.extend(['-preset', 'ultrafast', '-tune', 'zerolatency', '-r', str(int(self.brate))])
            cmd_list.extend(['-s', f'{width}x{height}'])
            
            if use_audio:
                cmd_list.extend(['-ac', '2', '-ar', '44100'])
            
            cmd_list.extend(['-pix_fmt', 'yuv420p', '-f', 'mp4', '-y'])
            
            # 保存文件名避免重复生成（分段录制：暂停时切换分段，停止后拼接）
            self._cmd_no_output = list(cmd_list)
            self._final_filename = self.get_file_name()
            self._current_filename = self._final_filename
            filename = self._start_first_segment()
            
            # 添加输出文件名
            cmd_list.append(filename)
            
            # 将命令列表转换为字符串用于日志记录
            cmd_str = ' '.join(cmd_list)
            
            # 记录日志
            if self.gpu_acceleration and not self.gpu_failed:
                self.logger.info('GPU全屏录制命令参数: %s' % cmd_str)
                print('GPU全屏录制命令参数: %s' % cmd_str)
            else:
                self.logger.info('CPU全屏录制命令参数: %s' % cmd_str)
                print('CPU全屏录制命令参数: %s' % cmd_str)
            
            # 开始录制
            self.record(cmd_list=cmd_list, target=self.start_ffmpeg)
            
            print('开始录制全屏幕: %sx%s' % (width, height))
            if use_audio and audio_device:
                print(f'音频设备: {audio_device}')
            elif use_audio and tcp_port:
                print('音频: WASAPI loopback (tcp://%d)' % tcp_port)
            else:
                print('警告: 仅录制视频，无音频')
            self.logger.info('开始录制全屏幕: %sx%s' % (width, height))
            
        except Exception as e:
            print('录制全屏幕失败: %s' % str(e))
            self.logger.error('录制全屏幕失败: %s' % str(e))
            self.last_error = str(e)
            self.recording = False
    
    def record_screen_region(self, region, audio_source="system"):
        """录制屏幕指定区域 - 使用先录制全屏再裁剪的方式"""
        self.last_error = ''
        try:
            # 设置录制类型（必须在调用get_file_name之前）
            self.record_type = RecordType.Screen
            
            # 解析区域参数
            if isinstance(region, (list, tuple)) and len(region) == 4:
                x, y, width, height = region
            else:
                # 默认区域
                x, y, width, height = 0, 0, 640, 480
            
            # 检查参数有效性
            if width <= 0 or height <= 0:
                raise ValueError("区域宽度和高度必须为正数")
            
            # 记录裁剪信息，用于录制完成后裁剪
            # 向内收缩边框厚度，避免裁剪包含红色边框
            border_thickness = 2  # 与AreaOverlay中的边框厚度保持一致
            crop_x = x + border_thickness
            crop_y = y + border_thickness
            crop_width = width - 2 * border_thickness
            crop_height = height - 2 * border_thickness
            
            # 确保裁剪后的区域有效，且宽高为偶数（libx264要求宽高能被2整除）
            crop_width = max(2, crop_width - crop_width % 2)
            crop_height = max(2, crop_height - crop_height % 2)
              
            # 记录实际录制区域（已收缩边框，供GPU回退重启时使用）
            self.current_region = (crop_x, crop_y, crop_width, crop_height)
            
            # 准备音频输入（system音源优先WASAPI loopback，mic走DirectShow设备）
            use_audio, audio_device, tcp_port = self._setup_audio_input(audio_source)
            
            # 构建区域直录命令参数（使用gdigrab偏移直接录制所选区域，无需后处理裁剪）
            cmd_list = ['-f', 'gdigrab',
                        '-offset_x', str(crop_x), '-offset_y', str(crop_y),
                        '-video_size', f'{crop_width}x{crop_height}',
                        '-framerate', str(int(self.brate)), '-i', 'desktop']
            
            # 添加音频参数
            if use_audio and tcp_port:
                cmd_list.extend(['-thread_queue_size', '1024',
                                 '-f', 's16le',
                                 '-ar', str(self.audio_capture.sample_rate),
                                 '-ac', str(self.audio_capture.channels),
                                 '-i', 'tcp://127.0.0.1:%d' % tcp_port])
            elif use_audio and audio_device:
                cmd_list.extend(['-thread_queue_size', '1024',
                                 '-f', 'dshow', '-i', f'audio={audio_device}'])
            
            # 添加视频编码参数
            if self.gpu_acceleration and not self.gpu_failed:
                # 添加硬件加速参数
                if self.hw_accel:
                    cmd_list.extend(['-hwaccel', self.hw_accel])
                cmd_list.extend(['-c:v', self.gpu_encoder])
            else:
                cmd_list.extend(['-c:v', self.video_codec])
            
            # 添加音频编码参数
            if use_audio:
                cmd_list.extend(['-c:a', 'aac'])
                # 添加音量增益滤镜，将音量增加三倍（1.0表示原始音量，3.0表示三倍音量）
                cmd_list.extend(['-af', 'volume=3.0'])

            # 添加其他通用参数（输出尺寸即区域尺寸，无需缩放）
            cmd_list.extend(['-preset', 'ultrafast', '-tune', 'zerolatency', '-r', str(int(self.brate))])
            
            if use_audio:
                cmd_list.extend(['-ac', '2', '-ar', '44100'])
            
            cmd_list.extend(['-pix_fmt', 'yuv420p', '-f', 'mp4', '-y'])
            
            # 保存文件名避免重复生成（分段录制：暂停时切换分段，停止后拼接）
            self._cmd_no_output = list(cmd_list)
            self._final_filename = self.get_file_name()
            self._current_filename = self._final_filename
            filename = self._start_first_segment()
            
            # 添加输出文件名
            cmd_list.append(filename)
            
            # 将命令列表转换为字符串用于日志记录
            cmd_str = ' '.join(cmd_list)
            
            # 记录日志
            self.logger.info('区域直录命令参数: %s' % cmd_str)
            print('区域直录命令参数: %s' % cmd_str)
            
            # 开始录制
            self.record(cmd_list=cmd_list, target=self.start_ffmpeg)
            
            print('开始录制屏幕区域: %d,%d - %dx%d' % (crop_x, crop_y, crop_width, crop_height))
            if use_audio and audio_device:
                print(f'音频设备: {audio_device}')
            elif use_audio and tcp_port:
                print('音频: WASAPI loopback (tcp://%d)' % tcp_port)
            else:
                print('警告: 仅录制视频，无音频')
            self.logger.info('开始录制屏幕区域: %d,%d - %dx%d' % (x, y, width, height))
            
        except Exception as e:
            print('录制屏幕区域失败: %s' % str(e))
            self.logger.error('录制屏幕区域失败: %s' % str(e))
            self.last_error = str(e)
            self.recording = False
            
    def check_device(self):
        """
        检查录制设备是否可用
        返回: bool - True表示设备可用，False表示设备不可用
        """
        try:
            # 初始化设备信息
            device_info = DevicesInfo()
            
            # 检查视频设备（摄像头）
            if not device_info.video_devices:
                self.logger.warning("未检测到可用的视频设备（摄像头）")
                print("⚠️ 未检测到可用的摄像头设备")
                # 对于屏幕录制，摄像头不是必需的
                return True
            
            # 检查音频设备
            if not device_info.voice_devices:
                self.logger.warning("未检测到可用的音频设备")
                print("⚠️ 未检测到可用的音频设备")
                # 音频设备不是必需的，可以继续录制
                return True
            
            self.logger.info("设备检查通过 - 视频设备: %d个, 音频设备: %d个" % 
                           (len(device_info.video_devices), len(device_info.voice_devices)))
            print("设备检查通过")
            return True
            
        except Exception as e:
            self.logger.error("设备检查失败: %s" % str(e))
            print(f"设备检查失败: {e}")
            return False
        
    def start_ffmpeg(self, cmd, shell=False):
        """启动FFmpeg录制进程"""
        try:
            print('录制中...')
            self.logger.info('录制中...')
            
            start_time = datetime.now()
            
            # 使用命令列表和shell=False执行，添加CREATE_NO_WINDOW参数隐藏控制台窗口
            self.process = subprocess.Popen(
                cmd, 
                shell=shell, 
                stdin=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                stdout=subprocess.PIPE,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW  # 添加这一行来隐藏控制台窗口
            )
            
            line = ''
            while self.recording:
                # 检查录制状态，如果需要停止则立即退出
                if not self.recording:
                    break
                
                # 检查进程状态
                if not self.process or self.process.poll() is not None:
                    txt = 'ffmpeg子进程已终止.'
                    print(txt)
                    self.logger.warning(txt)
                    
                    # 暂停导致的正常退出，直接结束本分段
                    if self.paused:
                        break
                    
                    # 检查进程退出码
                    if self.process:
                        exit_code = self.process.poll()
                        print(f'FFmpeg进程退出码: {exit_code}')
                        self.logger.warning(f'FFmpeg进程退出码: {exit_code}')
                        
                        # GPU失败时自动回退到CPU
                        if not self.gpu_failed and self.gpu_acceleration and exit_code == 1:
                            print("GPU加速失败，自动切换到CPU编码...")
                            self.gpu_failed = True
                            self.exception_exit = True
                            # 重新启动录制使用CPU编码
                            return self.restart_with_cpu()
                    
                    # 如果录制被停止，不要抛出异常
                    if not self.recording:
                        break
                    else:
                        # 如果不是被停止的，抛出异常
                        raise CalledProcessError(self.process.returncode if self.process else -1, cmd)
                
                try:
                    # 读取输出，非阻塞方式
                    output_line = self.process.stdout.readline()
                    if output_line:
                        line += str(output_line)
                except:
                    pass
                
                now = datetime.now()
                if (now - start_time).total_seconds() > 2:
                    # 记录运行状态
                    ffmpeg_running = self.process.poll() is None
                    log_text = 'ffmpeg 运行状态:%s' % ('运行中' if ffmpeg_running else '终止')
                    
                    print(log_text)
                    self.logger.info(log_text) 
                 
                    if not ffmpeg_running:
                        if self.paused:
                            break
                        print(self.process.communicate())
                        raise CalledProcessError(self.process.returncode, cmd)
                    
                    # 打印收集到的输出
                    if line:
                        print(line)
                        # self.logger.info(line)  # 可选：记录详细输出到日志
                        line = ''
                    
                    start_time = now
                    
        except CalledProcessError as e:
            log_txt = 'ffmpeg异常终止:\nreturn code: %d\ncmd:\n%s' % (e.returncode, e.cmd)
            if line:
                # 附带ffmpeg的错误输出，便于定位启动失败原因
                log_txt += '\nffmpeg输出:\n%s' % line
            print(log_txt)
            self.logger.warning(log_txt)      
            
            # GPU失败时自动回退到CPU
            if not self.gpu_failed and self.gpu_acceleration and e.returncode == 1:
                print("GPU加速失败，自动切换到CPU编码...")
                self.gpu_failed = True
                self.exception_exit = True
                # 重新启动录制使用CPU编码
                return self.restart_with_cpu()
            
            self.recording = False
            self.exception_exit = True
            print('process is None?:%s' % (self.process is None))
        except Exception as x:
            print('未捕获的异常：')
            print(x)
        finally:
            # 确保在退出时处理清理工作
            if self.process and not self.recording:
                try:
                    self.process.stdin.write('q')
                    self.process.stdin.flush()
                except:
                    try:
                        self.process.terminate()
                    except:
                        pass
        # self.logger.info(self.process.communicate())
        # print('over')
        
    def record(self, cmd='ffmpeg -h', cmd_list=None, target = None):
        """录制方法"""
        if target:
            # 获取FFmpeg可执行文件的完整路径
            ffmpeg_path = get_ffmpeg_path()
            if not ffmpeg_path:
                # 如果没有找到FFmpeg路径，直接使用命令（依赖环境变量）
                ffmpeg_path = 'ffmpeg'
            
            if cmd_list is None:
                # 如果没有提供命令列表，解析命令字符串
                # 构建命令列表
                cmd_list = [ffmpeg_path]
                
                # 解析命令字符串，保留带引号的参数
                i = 0
                cmd = cmd.strip()
                while i < len(cmd):
                    # 跳过空格
                    while i < len(cmd) and cmd[i] == ' ':
                        i += 1
                    if i >= len(cmd):
                        break
                    
                    # 处理带引号的参数
                    if cmd[i] == '"':
                        i += 1  # 跳过引号
                        arg = ''
                        while i < len(cmd) and cmd[i] != '"':
                            arg += cmd[i]
                            i += 1
                        if i < len(cmd):
                            i += 1  # 跳过结尾引号
                        cmd_list.append(arg)
                    else:
                        # 处理不带引号的参数
                        arg = ''
                        while i < len(cmd) and cmd[i] != ' ':
                            arg += cmd[i]
                            i += 1
                        cmd_list.append(arg)
            else:
                # 如果提供了命令列表，在开头添加ffmpeg路径
                cmd_list = [ffmpeg_path] + cmd_list
            
            # 保留完整命令字符串用于日志记录
            full_cmd = ' '.join(cmd_list)
            print('cmd: \n%s' % full_cmd)
            self.logger.info('record cmd:\n %s' % full_cmd)
            
            # 使用命令列表和shell=False执行
            self.record_thread = Thread(name=self.record_thread_name, target= target, args = (cmd_list,), daemon=True)
            self.record_thread.start()
            self.recording=True
            self.exception_exit = False
            
            print('record thread,ident:%d' % self.record_thread.ident)
            # th.join()
                
    def stop_record(self):
        
        # print('threading active thread count:%d' % threading.active_count())
        try:
            
            self.recording = False
            self.logger.info('录制将停止...')
            
            # 强制终止FFmpeg进程，确保释放麦克风资源
            if self.process:
                try:
                    # 首先尝试优雅停止
                    self.logger.info('尝试优雅停止FFmpeg进程...')
                    if hasattr(self.process, 'stdin') and self.process.stdin:
                        try:
                            self.process.stdin.write('q')
                            self.process.stdin.flush()
                        except:
                            pass
                    
                    # 等待一小段时间让进程优雅退出
                    import time
                    time.sleep(0.5)
                    
                    # 检查进程状态
                    if self.process.poll() is None:
                        self.logger.info('强制终止FFmpeg进程...')
                        # 如果进程还在运行，强制终止
                        self.process.terminate()
                        
                        # 再等待一下
                        time.sleep(0.5)
                        
                        # 如果还没终止，使用kill
                        if self.process.poll() is None:
                            self.logger.info('强制杀死FFmpeg进程...')
                            self.process.kill()
                    
                    self.logger.info('ffmpeg进程状态: %s' % (self.process.poll() is not None))
                    if self.process.returncode:
                        print('ffmpeg异常终止:')
                        print('return code:', self.process.returncode)
                        self.exception_exit = True
                        self.logger.error('ffmpeg异常终止，返回码: %s' % self.process.returncode)
                except Exception as e:
                    print('强制结束进程失败: %s' % e)
                    self.logger.error('强制结束进程失败: %s' % e)
                    # 尝试其他方式终止
                    try:
                        import os
                        if os.name == 'nt':  # Windows
                            os.system('taskkill /f /t /pid %d' % self.process.pid)
                        else:  # Linux/Mac
                            os.system('kill -9 %d' % self.process.pid)
                    except Exception as kill_e:
                        print('kill exception:\n %s' % kill_e)
                        self.logger.warning('kill exception:\n %s' % kill_e)
                finally:
                    # 确保在异常情况下也清理资源
                    try:
                        self.force_cleanup_resources()
                    except:
                        pass
            
            # 如果是区域录制，执行裁剪操作（旧版兼容路径，现已改为区域直录，crop_info不再设置）
            if hasattr(self, 'crop_info') and self.crop_info:
                print("\n🎬 录制完成，开始裁剪区域...")
                self.post_process_crop()
            
            # 分段录制后处理：单段改名 / 多段无损拼接
            self._finalize_segments()
            
            self.logger.info('录制已停止')
            print('停止录制')
            
        except Exception as e:
            print('停止录制时发生错误: %s' % str(e))
            self.logger.error('停止录制时发生错误: %s' % str(e))
            self.recording = False
            self.force_cleanup_resources()
            
    def post_process_crop(self):
        """区域录制完成后处理裁剪"""
        try:
            if not hasattr(self, 'crop_info') or not self.crop_info:
                return
                
            # 获取录制完成的文件路径
            original_file = self._current_filename
            
            # 检查原始文件是否存在
            import os
            if not os.path.exists(original_file):
                print(f"❌ 错误: 原始文件不存在: {original_file}")
                self.logger.error(f"原始文件不存在: {original_file}")
                return
                
            # 生成裁剪后的文件名
            from datetime import datetime
            time_str = datetime.now().strftime('%Y-%m-%d-%H%M%S')
            base_name = os.path.basename(original_file)
            name_parts = os.path.splitext(base_name)
            cropped_file = os.path.join(os.path.dirname(original_file), f"{name_parts[0]}_裁剪_{time_str}{name_parts[1]}")
            
            print(f"🔧 开始区域裁剪后处理...")
            print(f"📁 原始文件: {original_file}")
            print(f"✂️ 裁剪参数: {self.crop_info}")
            print(f"📁 裁剪文件: {cropped_file}")
            
            # 获取FFmpeg可执行文件路径
            from RunCMD import get_ffmpeg_path
            ffmpeg_path = get_ffmpeg_path()
            if not ffmpeg_path:
                ffmpeg_path = 'ffmpeg'
            
            # 构建裁剪命令列表
            cmd_list = [
                ffmpeg_path,
                '-i', original_file,
                '-vf', self.crop_info,
                '-c:v', 'libx264',
                '-c:a', 'copy',
                '-preset', 'ultrafast',
                '-y',
                cropped_file
            ]
            
            # 执行裁剪
            print(f"执行裁剪命令: {' '.join(cmd_list)}")
            result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print(f"✅ 区域裁剪完成: {cropped_file}")
                self.logger.info(f"区域裁剪完成: {cropped_file}")
                
                # 更新当前文件名指向裁剪后的文件
                self._current_filename = cropped_file
                
                # 删除原始的全屏文件
                try:
                    os.remove(original_file)
                    print(f"🗑️  已删除原始全屏文件: {original_file}")
                    self.logger.info(f"已删除原始全屏文件: {original_file}")
                except Exception as e:
                    print(f"⚠️  删除原始文件失败: {e}")
                    self.logger.warning(f"删除原始文件失败: {e}")
            else:
                print(f"❌ 区域裁剪失败: {result.stderr}")
                self.logger.error(f"区域裁剪失败: {result.stderr}")
                
        except Exception as e:
            print(f"区域裁剪过程中发生错误: {e}")
            self.logger.error(f"区域裁剪过程中发生错误: {e}")
        finally:
            # 清理裁剪信息
            if hasattr(self, 'crop_info'):
                self.crop_info = None
            if hasattr(self, 'current_region'):
                self.current_region = None
        
    def force_cleanup_resources(self):
        """强制清理所有录制资源（不重新启动录制）"""
        try:
            self.logger.info('清理录制资源...')

            # 停止系统声音采集（WASAPI loopback）
            if getattr(self, 'audio_capture', None):
                try:
                    self.audio_capture.stop()
                except Exception:
                    pass
                self.audio_capture = None
            
            # 清理FFmpeg进程
            if self.process:
                try:
                    # 创建一个临时引用，避免在清理过程中self.process被修改
                    process = self.process
                    self.process = None  # 先将self.process设置为None，避免其他线程访问
                    
                    if process.poll() is None:
                        try:
                            process.terminate()
                            import time
                            time.sleep(0.2)
                            if process.poll() is None:
                                process.kill()
                        except:
                            pass
                    
                    # 清理文件描述符
                    try:
                        if hasattr(process, 'stdout'):
                            stdout = process.stdout
                            if stdout:
                                try:
                                    stdout.close()
                                except:
                                    pass
                    except:
                        pass
                    
                    try:
                        if hasattr(process, 'stderr'):
                            stderr = process.stderr
                            if stderr:
                                try:
                                    stderr.close()
                                except:
                                    pass
                    except:
                        pass
                    
                    try:
                        if hasattr(process, 'stdin'):
                            stdin = process.stdin
                            if stdin:
                                try:
                                    stdin.close()
                                except:
                                    pass
                    except:
                        pass
                    
                except:
                    pass
            
            # 重置状态
            self.recording = False
            self.exception_exit = False
            self.gpu_failed = False
            self.gpu_fallbacks = ['h264_qsv']  # 重置编码器降级链
            
            self.logger.info('录制资源清理完成')
            print('录制资源已清理，麦克风等设备已释放')
            
        except Exception as e:
            self.logger.error(f'清理资源时出错: {e}')
            print(f'清理资源时出错: {e}')
        finally:
            # 确保self.process最终被设置为None
            try:
                self.process = None
            except:
                pass
    
    def restart_with_cpu(self):
        """GPU失败后降级重新录制：先试降级链里的编码器（QSV），再回CPU"""
        try:
            # 编码器降级链：NVENC失败 -> QSV -> CPU
            if self.gpu_acceleration and getattr(self, 'gpu_fallbacks', None):
                next_encoder = self.gpu_fallbacks.pop(0)
                print('%s 失败，尝试 %s 重新录制...' % (self.gpu_encoder, next_encoder))
                self.logger.info('GPU编码器降级: %s -> %s'
                                 % (self.gpu_encoder, next_encoder))
                self.gpu_encoder = next_encoder
                self.gpu_failed = False  # 继续用GPU模式重建命令
            else:
                print("正在使用CPU重新开始录制...")
                self.gpu_failed = True
                self.logger.info("GPU不可用，切换到CPU模式重新录制")
            
            # 构建命令参数列表（不包含FFmpeg路径，record方法会自动添加）
            cmd_params = []
            
            # 根据录制类型重新构建命令
            if self.record_type == RecordType.Camera:
                # 摄像头录制
                cmd_params.extend(['-f', 'dshow', '-i', 'video=ov9734_azurewave_camera'])
                cmd_params.extend(['-f', 'dshow', '-i', 'audio=麦克风阵列 (Realtek(R) Audio)'])
                cmd_params.extend(['-c:v', self.video_codec, '-c:a', 'aac'])
                cmd_params.extend(['-preset:v', 'ultrafast', '-tune:v', 'zerolatency'])
                cmd_params.extend(['-r', str(int(self.brate)), '-ac', '2', '-ar', '44100'])
                cmd_params.extend(['-ab', '128k', '-f', 'mp4'])
                
            elif self.record_type == RecordType.Screen:
                # 检查音频输入（复用存活的loopback采集，否则用第一个dshow设备）
                use_audio = True
                audio_device = None
                tcp_port = None
                if getattr(self, 'audio_capture', None) and self.audio_capture.started:
                    tcp_port = self.audio_capture.port
                    print('音频: 复用WASAPI loopback (tcp://%d)' % tcp_port)
                else:
                    try:
                        from DevicesInfo import DevicesInfo
                        device_info = DevicesInfo()
                        if device_info.voice_devices:
                            # 使用第一个音频设备
                            audio_device = device_info.voice_devices[0][0]
                            print(f"使用音频设备: {audio_device}")
                        else:
                            print("警告: 未检测到音频设备，将仅录制视频")
                            use_audio = False
                    except Exception as e:
                        print(f"获取音频设备失败: {e}，将仅录制视频")
                        use_audio = False
                
                if self.current_region:
                    # 区域录制
                    x, y, width, height = self.current_region
                    cmd_params.extend(['-f', 'gdigrab', '-offset_x', str(x), '-offset_y', str(y)])
                    cmd_params.extend(['-video_size', f"{width}x{height}", '-framerate', str(int(self.brate))])
                    cmd_params.extend(['-i', 'desktop'])
                    
                    if use_audio:
                        if tcp_port:
                            cmd_params.extend(['-f', 's16le',
                                               '-ar', str(self.audio_capture.sample_rate),
                                               '-ac', str(self.audio_capture.channels),
                                               '-i', 'tcp://127.0.0.1:%d' % tcp_port])
                        else:
                            cmd_params.extend(['-f', 'dshow', '-i', f'audio={audio_device}'])
                        
                    cmd_params.extend(['-c:v', self.video_codec])
                    if use_audio:
                        cmd_params.extend(['-c:a', 'aac'])
                    cmd_params.extend(['-preset', 'ultrafast', '-tune', 'zerolatency'])
                    cmd_params.extend(['-r', str(int(self.brate)), '-s', f"{width}x{height}"])
                    if use_audio:
                        cmd_params.extend(['-ac', '2', '-ar', '44100'])
                    cmd_params.extend(['-pix_fmt', 'yuv420p', '-f', 'mp4'])
                    
                else:
                    # 全屏录制
                    cmd_params.extend(['-f', 'gdigrab', '-framerate', str(int(self.brate)), '-i', 'desktop'])
                    
                    if use_audio:
                        if tcp_port:
                            cmd_params.extend(['-f', 's16le',
                                               '-ar', str(self.audio_capture.sample_rate),
                                               '-ac', str(self.audio_capture.channels),
                                               '-i', 'tcp://127.0.0.1:%d' % tcp_port])
                        else:
                            cmd_params.extend(['-f', 'dshow', '-i', f'audio={audio_device}'])
                        
                    cmd_params.extend(['-c:v', self.video_codec])
                    if use_audio:
                        cmd_params.extend(['-c:a', 'aac'])
                    cmd_params.extend(['-preset', 'ultrafast', '-tune', 'zerolatency'])
                    cmd_params.extend(['-r', str(int(self.brate))])
                    if use_audio:
                        cmd_params.extend(['-ac', '2', '-ar', '44100'])
                    cmd_params.extend(['-pix_fmt', 'yuv420p', '-f', 'mp4'])
            else:
                print("未知的录制类型，无法重新开始")
                return False
            
            # 覆盖写入当前分段文件，避免生成两个文件
            if self.segments:
                current_filename = self.segments[-1]
            else:
                current_filename = self.get_file_name()
                self._current_filename = current_filename
            
            # 添加输出文件名和覆盖参数
            cmd_params.extend(['-y', current_filename])
            
            # 直接使用命令列表重新开始录制
            self.record(cmd_list=cmd_params, target=self.start_ffmpeg)
            return True
            
        except Exception as e:
            print(f"CPU录制失败: {e}")
            self.logger.error(f"CPU录制失败: {e}")
            return False

    def deal_with_device_name(self, device_name):    
        """处理设备名称，使其适合FFmpeg使用"""
        try:
            # 对于DirectShow设备，优先使用友好名称
            if device_name.startswith('@device_cm_') or device_name.startswith('@device_pnp_'):
                # 尝试从设备列表中获取友好名称
                if hasattr(self, 'voice_device_friendly') and self.voice_device_friendly:
                    return self.voice_device_friendly
            
            # 转义特殊字符
            # 不需要转义大括号，保持原始格式
            # 只转义反斜杠
            device_name = device_name.replace('\\', '\\\\')
            return device_name
            
        except Exception as e:
            print(f"设备名称处理失败: {e}")
            self.logger.error(f"设备名称处理失败: {e}")
            return device_name
        
    def _ensure_writable_dir(self, path):
        """确保目录存在且实际可写（写入测试文件验证），返回是否成功"""
        try:
            if not os.path.isdir(path):
                os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, '.write_test')
            with open(probe, 'w') as _f:
                pass
            os.remove(probe)
            return True
        except Exception:
            return False

    def get_file_name(self):
        date_dir = datetime.now().strftime('%Y-%m-%d')
        time_str = datetime.now().strftime('%Y-%m-%d-%H%M%S')
        video_type_name = ''
        if self.record_type == RecordType.Camera:
            # video_type_name = 'camera'
            video_type_name = '摄像头'
        if self.record_type == RecordType.Screen:
            video_type_name = '屏幕'
            # video_type_name = 'screen'

        base_name = '{}_{}{}'.format(video_type_name, time_str, self.file_suffix)
        file_name = None

        # 首选：保存目录\日期\ ；不可写时逐级回退，保证录制不被目录权限卡死
        today_file_dir = os.path.join(self.file_dir, date_dir)
        if self._ensure_writable_dir(today_file_dir):
            file_name = os.path.join(today_file_dir, base_name)
        elif self._ensure_writable_dir(self.file_dir):
            print('日期子目录不可用，改用保存目录根')
            self.logger.warning('日期子目录不可用，改用保存目录根: %s' % self.file_dir)
            file_name = os.path.join(self.file_dir, base_name)

        # 回退：默认视频目录（视频库\影随录屏），不再回退到程序安装目录
        if file_name is None:
            fallback_dir = os.path.join(default_record_dir(), date_dir)
            self._ensure_writable_dir(fallback_dir)
            file_name = os.path.join(fallback_dir, base_name)
            print('保存目录不可写，已回退到默认目录: %s' % fallback_dir)
            self.logger.warning('保存目录不可写，使用回退目录: %s' % fallback_dir)

        print('recording file name: %s' % file_name)
        return file_name

    def _resolve_audio_device(self, audio_source, device_info):
        """根据音源选择解析实际使用的音频设备
        system: 优先立体声混音 -> 配置的系统声音设备 -> 配置的麦克风 -> 第一个设备
        mic:    配置的麦克风 -> 第一个设备
        """
        audio_device = None
        voice_devices = device_info.voice_devices if device_info else []

        def _to_friendly(name):
            """配置里可能存的是alternative name（ffmpeg无法解析），映射回友好名；
            若配置的设备在当前设备列表中不存在（别名随系统更新会过期），
            返回None并走后续回退逻辑，避免把无效设备名传给ffmpeg"""
            if not name:
                return None
            for device in voice_devices:
                if device[0] == name:
                    return device[0]
                if len(device) > 1 and device[1] == name:
                    return device[0]
            print('警告: 配置的音频设备已不存在（设备别名过期）: %s' % name)
            return None

        if audio_source == "system":
            # 优先使用系统声音设备（立体声混音）
            for device in voice_devices:
                if '立体声混音' in device[0] or 'stereo mix' in device[0].lower():
                    audio_device = device[0]
                    break
            if not audio_device and getattr(self, 'system_voice_device_name', ''):
                audio_device = _to_friendly(self.system_voice_device_name)
            if not audio_device and getattr(self, 'voice_device_name', ''):
                audio_device = _to_friendly(self.voice_device_name)
        else:  # mic
            audio_device = _to_friendly(getattr(self, 'voice_device_name', ''))
            if not audio_device and voice_devices:
                audio_device = voice_devices[0][0]
        # 最终回退：第一个音频设备
        if not audio_device and voice_devices:
            audio_device = voice_devices[0][0]
        return audio_device

    def _start_first_segment(self):
        """开始新的录制会话，返回第一个分段文件名"""
        self.segments = []
        return self._next_segment_file()

    def _next_segment_file(self):
        """生成分段文件名并登记到segments"""
        base, ext = os.path.splitext(self._final_filename)
        seg = '{}_part{:03d}{}'.format(base, len(self.segments) + 1, ext)
        self.segments.append(seg)
        return seg

    def pause_record(self):
        """真实暂停：优雅停止当前FFmpeg分段，暂停期间不录制任何画面"""
        if not self.recording or self.paused:
            return False
        process = self.process
        if process and process.poll() is None:
            try:
                process.stdin.write('q')
                process.stdin.flush()
            except Exception:
                pass
            # 等待进程退出（最多3秒）
            for _ in range(30):
                if process.poll() is not None:
                    break
                time.sleep(0.1)
            if process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass
        self.paused = True
        self.logger.info('录制已暂停（当前分段: %s）' % (self.segments[-1] if self.segments else '无'))
        print('录制已暂停')
        return True

    def resume_record(self):
        """恢复录制：用相同参数启动新的分段"""
        if not self.recording or not self.paused:
            return False
        if not self._cmd_no_output or not self._final_filename:
            self.paused = False
            return False
        self.paused = False
        seg = self._next_segment_file()
        self.record(cmd_list=list(self._cmd_no_output) + [seg], target=self.start_ffmpeg)
        self.logger.info('恢复录制，新分段: %s' % seg)
        print('恢复录制')
        return True

    def _finalize_segments(self):
        """停止后处理分段：单段直接改名，多段用concat无损拼接"""
        try:
            if not self.segments:
                return
            final = self._final_filename
            if not final:
                return
            if len(self.segments) == 1:
                seg = self.segments[0]
                if os.path.exists(seg) and os.path.abspath(seg) != os.path.abspath(final):
                    if os.path.exists(final):
                        try:
                            os.remove(final)
                        except Exception:
                            pass
                    os.rename(seg, final)
                self.segments = []
                self._current_filename = final
                return
            # 多段：concat demuxer 无损拼接（各分段编码参数一致）
            list_file = final + '.txt'
            with open(list_file, 'w', encoding='utf-8') as f:
                for seg in self.segments:
                    f.write("file '%s'\n" % seg.replace("\\", "/").replace("'", "'\\''"))
            ffmpeg_path = get_ffmpeg_path() or 'ffmpeg'
            cmd = [ffmpeg_path, '-f', 'concat', '-safe', '0', '-i', list_file,
                   '-c', 'copy', '-y', final]
            print('拼接分段: %s' % ' '.join(cmd))
            self.logger.info('拼接分段: %s' % ' '.join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                print('分段拼接完成: %s' % final)
                self.logger.info('分段拼接完成: %s' % final)
                for seg in self.segments:
                    try:
                        if os.path.exists(seg):
                            os.remove(seg)
                    except Exception:
                        pass
                self._current_filename = final
            else:
                print('分段拼接失败，保留分段文件: %s' % result.stderr)
                self.logger.error('分段拼接失败: %s' % result.stderr)
            try:
                if os.path.exists(list_file):
                    os.remove(list_file)
            except Exception:
                pass
            self.segments = []
        except Exception as e:
            print('分段后处理失败: %s' % e)
            self.logger.error('分段后处理失败: %s' % e)