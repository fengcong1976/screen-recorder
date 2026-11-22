# -*- coding: utf-8 -*-
"""系统声音采集（WASAPI loopback，免驱动）

通过 pyaudiowpatch 捕获默认扬声器的回环数据（无需"立体声混音"设备），
以 PCM(s16le) 形式通过本机 TCP 端口喂给 FFmpeg：
    ffmpeg -f s16le -ar {rate} -ac {ch} -i tcp://127.0.0.1:{port} ...

与分段录制（真实暂停/恢复）天然兼容：FFmpeg 每次启动都会重新连接，
本模块循环 accept，一个连接断开后等待下一个。
"""

import io
import os
import socket
import tempfile
import threading
import time
import wave

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

try:
    import pyaudiowpatch as pyaudio
    HAS_PYAUDIOWPATCH = True
except ImportError:
    try:  # 兼容普通pyaudio（不支持loopback，仅探测时使用）
        import pyaudio
        HAS_PYAUDIOWPATCH = False
    except ImportError:
        HAS_PYAUDIOWPATCH = False


def _make_silence_wav_file(rate=48000, channels=2, seconds=1):
    """生成静音WAV临时文件（winsound的内存模式不支持异步循环播放）"""
    path = os.path.join(tempfile.gettempdir(), 'recorder_silence.wav')
    w = wave.open(path, 'wb')
    w.setnchannels(channels)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(b'\x00\x00' * channels * rate * seconds)
    w.close()
    return path


class SystemAudioCapture():
    """采集系统声音并通过 TCP 发送 PCM 流

    用法:
        cap = SystemAudioCapture()
        port = cap.start()   # 成功返回监听端口（在启动FFmpeg之前调用），失败返回None
        ... 启动FFmpeg (-f s16le -ar cap.sample_rate -ac cap.channels -i tcp://127.0.0.1:port) ...
        cap.stop()
    """

    def __init__(self):
        self.sample_rate = 48000
        self.channels = 2
        self.port = None
        self.started = False
        self._server = None
        self._thread = None
        self._stop_event = threading.Event()
        self._pa = None
        self._stream = None
        self._conn = None

    def start(self):
        """初始化采集并开始监听。成功返回端口号，失败返回None。"""
        if not HAS_PYAUDIOWPATCH:
            print('未安装 pyaudiowpatch，无法采集系统声音')
            return None
        try:
            self._pa = pyaudio.PyAudio()
            device = self._find_loopback_device()
            if device is None:
                print('未找到可用的WASAPI loopback设备')
                self._cleanup_pyaudio()
                return None
            self.sample_rate = int(device.get('defaultSampleRate', 48000))
            self.channels = int(device.get('maxInputChannels', 2))
            if self.channels <= 0 or self.sample_rate <= 0:
                self.sample_rate, self.channels = 48000, 2

            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.bind(('127.0.0.1', 0))
            self._server.listen(1)
            self.port = self._server.getsockname()[1]

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, args=(device,),
                                            name='SystemAudioCapture', daemon=True)

            # 关键：循环播放静音保活音频引擎。部分机器的loopback流
            # 在音频引擎空闲（无任何渲染流）时无法启动/会产生数据断流
            if HAS_WINSOUND:
                try:
                    _silence = _make_silence_wav_file(self.sample_rate, self.channels, 1)
                    winsound.PlaySound(_silence,
                                       winsound.SND_FILENAME | winsound.SND_LOOP | winsound.SND_ASYNC)
                    print('静音保活已开启（防止音频引擎空闲导致loopback断流）')
                except Exception as e:
                    print('静音保活开启失败(不影响尝试): %s' % e)

            self._thread.start()
            self.started = True
            print('系统声音采集已启动: %dHz %dch -> tcp://127.0.0.1:%d'
                  % (self.sample_rate, self.channels, self.port))
            return self.port
        except Exception as e:
            print('系统声音采集启动失败: %s' % e)
            self.stop()
            return None

    def _find_loopback_device(self):
        """定位默认扬声器对应的loopback设备"""
        if not hasattr(self._pa, 'get_loopback_device_info_generator'):
            return None
        try:
            wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self._pa.get_device_info_by_index(
                wasapi['defaultOutputDevice'])
        except Exception:
            return None
        if default_speakers.get('isLoopbackDevice', False):
            return default_speakers
        name = default_speakers.get('name', '')
        for loopback in self._pa.get_loopback_device_info_generator():
            if name and name in loopback.get('name', ''):
                return loopback
        for loopback in self._pa.get_loopback_device_info_generator():
            return loopback  # 兜底：第一个loopback设备
        return None

    def _run(self, device):
        """工作线程：打开采集流 -> 循环等待FFmpeg连接并发送PCM"""
        def callback(in_data, frame_count, time_info, status):
            conn = self._conn
            if conn is not None:
                try:
                    conn.sendall(in_data)
                except OSError:
                    self._conn = None  # 连接断开，外层重新accept
            return (None, pyaudio.paContinue)

        # 依次尝试不同缓冲大小并重试（loopback流在引擎刚被唤醒时可能失败几次）
        stream = None
        for fpb in (1024, 512, 2048, 64):
            for attempt in range(3):
                try:
                    stream = self._pa.open(
                        format=pyaudio.paInt16,
                        channels=self.channels,
                        rate=self.sample_rate,
                        frames_per_buffer=fpb,
                        input=True,
                        input_device_index=device['index'],
                        stream_callback=callback)
                    break
                except Exception as e:
                    print('打开系统声音流失败(fpb=%d 第%d次): %s' % (fpb, attempt + 1, e))
                    time.sleep(0.4)
                if stream is not None:
                    break
            if stream is not None:
                break
        if stream is None:
            print('系统声音流无法打开，放弃本次采集')
            return
        self._stream = stream
        stream.start_stream()
        print('WASAPI loopback采集运行中')

        while not self._stop_event.is_set():
            # 等待FFmpeg连接
            try:
                self._server.settimeout(0.5)
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if self._stop_event.is_set():
                try:
                    conn.close()
                except Exception:
                    pass
                break
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            self._conn = conn
            print('FFmpeg已连接音频通道')
            # 等待连接结束（callback里sendall失败会把_conn置None）
            while not self._stop_event.is_set() and self._conn is not None:
                time.sleep(0.1)
            try:
                conn.close()
            except Exception:
                pass

    def stop(self):
        """停止采集并释放所有资源（可重复调用）"""
        self._stop_event.set()
        self.started = False
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
        except Exception:
            pass
        self._stream = None
        try:
            if self._conn is not None:
                self._conn.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:
            pass
        self._conn = None
        try:
            if self._server is not None:
                self._server.close()
        except Exception:
            pass
        self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self._cleanup_pyaudio()
        # 停止静音保活
        if HAS_WINSOUND:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        print('系统声音采集已停止')

    def _cleanup_pyaudio(self):
        try:
            if self._pa is not None:
                self._pa.terminate()
        except Exception:
            pass
        self._pa = None


if __name__ == '__main__':
    # 自测：启动采集 -> 播放提示音 -> 用socket客户端接收2秒数据验证链路
    import winsound

    cap = SystemAudioCapture()
    port = cap.start()
    if not port:
        print('SELFTEST FAIL: 采集启动失败')
        raise SystemExit(1)

    received = []

    def client():
        try:
            c = socket.create_connection(('127.0.0.1', port), timeout=10)
            c.settimeout(8)
            received.append(c.recv(65536))
            c.close()
        except Exception as e:
            print('客户端接收异常: %s' % e)

    threading.Thread(target=client, daemon=True).start()
    time.sleep(0.5)
    winsound.Beep(880, 2000)  # 播放提示音确保loopback有数据
    time.sleep(1.0)
    cap.stop()
    if received and len(received[0]) > 1000:
        print('SELFTEST PASS: 收到 %d 字节PCM' % len(received[0]))
    else:
        print('SELFTEST FAIL: 未收到音频数据')
        raise SystemExit(1)
