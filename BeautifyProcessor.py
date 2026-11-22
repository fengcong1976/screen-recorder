# -*- coding: utf-8 -*-
"""自动缩放美化处理器（Screen Studio 风格的核心引擎）

根据 MouseTracker 记录的点击时间线，为录像生成"点击处自动平滑缩放"的
美化视频：
  1. 把点击事件换算到视频坐标系（减去区域录制原点、补偿录制启动延迟）
  2. 构建缩放关键帧时间线（推进 -> 保持 -> 拉回，相邻点击间镜头平移）
  3. 相邻关键帧之间用 smoothstep 缓动，编译为 FFmpeg zoompan 逐帧表达式
  4. zoompan 以 2 倍尺寸渲染抑制抖动，再 lanczos 缩回原尺寸，重编码输出
"""

import json
import os
import subprocess

from RunCMD import get_ffmpeg_path
from RecordConfig import app_data_dir


def _get_logger():
    import logging
    logger = logging.getLogger('BeautifyProcessor')
    if not logger.handlers:
        try:
            handler = logging.FileHandler(os.path.join(app_data_dir(), 'log.txt'))
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        except Exception:
            pass
    return logger


def probe_video(video_path):
    """用 ffprobe 探测视频信息。

    返回 (width, height, fps, duration, has_audio)
    """
    ffmpeg_path = get_ffmpeg_path()
    ffprobe = 'ffprobe'
    if ffmpeg_path:
        candidate = os.path.join(os.path.dirname(ffmpeg_path), 'ffprobe.exe')
        if os.path.isfile(candidate):
            ffprobe = candidate
    cmd = [ffprobe, '-v', 'error', '-show_streams', '-show_format',
           '-of', 'json', video_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode != 0:
        raise RuntimeError('ffprobe失败: %s' % (result.stderr or '')[:500])
    data = json.loads(result.stdout)
    video = next((s for s in data.get('streams', [])
                  if s.get('codec_type') == 'video'), None)
    if not video:
        raise RuntimeError('未找到视频流: %s' % video_path)
    width, height = int(video['width']), int(video['height'])
    num, _, den = (video.get('r_frame_rate') or '24/1').partition('/')
    try:
        fps = float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        fps = 24.0
    if fps <= 0 or fps != fps:  # 处理0/0等异常
        fps = 24.0
    try:
        duration = float(data.get('format', {}).get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0
    has_audio = any(s.get('codec_type') == 'audio'
                    for s in data.get('streams', []))
    return width, height, fps, duration, has_audio


class BeautifyProcessor():
    """点击自动缩放美化"""

    def __init__(self, zoom_in_dur=0.4, hold_dur=1.8, zoom_out_dur=0.5,
                 merge_gap=0.3):
        # 推进时长 / 点击后保持时长 / 拉回时长 / 连点合并间隔（秒）
        self.zoom_in_dur = zoom_in_dur
        self.hold_dur = hold_dur
        self.zoom_out_dur = zoom_out_dur
        self.merge_gap = merge_gap
        self.logger = _get_logger()

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def process(self, video_path, events, zoom=2.0, origin=(0, 0),
                time_offset=0.5, output_path=None):
        """生成美化视频。

        video_path:  录制生成的视频文件
        events:      MouseTracker 的事件列表 [{'t','x','y'}, ...]
        zoom:        缩放倍率（>=1.2）
        origin:      录制区域左上角物理坐标（区域录制时为所选区域原点）
        time_offset: 录制启动延迟补偿（秒），事件时间减去该值对齐视频时间轴
        output_path: 输出文件完整路径（默认为 原名_美化.扩展名）
        返回输出文件路径；无有效点击时返回 None。
        """
        self.logger.info('开始美化处理: %s (点击数=%d, zoom=%.2f)'
                         % (video_path, len(events), zoom))
        width, height, fps, duration, has_audio = probe_video(video_path)

        # 1. 换算到视频坐标系
        clicks = []
        for e in events:
            t = float(e.get('t', 0)) - float(time_offset)
            x = float(e.get('x', 0)) - origin[0]
            y = float(e.get('y', 0)) - origin[1]
            if t <= 0 or x < 0 or y < 0 or x >= width or y >= height:
                continue
            clicks.append((t, x, y))
        clicks.sort()

        # 2. 合并连点（双击等间隔过近的点击保留最后一次）
        merged = []
        for c in clicks:
            if merged and c[0] - merged[-1][0] < self.merge_gap:
                merged[-1] = c
            else:
                merged.append(c)
        if not merged:
            print('视频坐标系内无有效点击，跳过美化')
            self.logger.info('无有效点击，跳过美化: %s' % video_path)
            return None
        print('有效点击 %d 处，缩放倍率 %.2f' % (len(merged), zoom))

        # 3. 关键帧时间线 + 逐帧表达式
        kfs = self._build_keyframes(merged, duration, zoom)
        z_expr, x_expr, y_expr = self._build_expr(kfs, width, height, fps)

        # 4. zoompan 渲染（超采样抑抖 -> 缩回原尺寸）
        base, ext = os.path.splitext(video_path)
        output = output_path or '{}_美化{}'.format(base, ext)
        # 超采样倍率：小视频用 2 倍抑抖；大区域（如全屏 1080p）按 2560 封顶，
        # 避免按 4K 渲染导致耗时成倍增长
        ss = min(2.0, max(1.0, 2560.0 / float(max(width, height))))
        bw = max(2, int(width * ss) & ~1)
        bh = max(2, int(height * ss) & ~1)
        print('美化渲染: %dx%d，超采样 %.2f 倍（工作区 %dx%d）'
              % (width, height, ss, bw, bh))
        vf = ("zoompan=z='{z}':x='{x}':y='{y}':d=1:s={bw}x{bh}:fps={fps},"
              "format=yuv420p,scale={w}:{h}:flags=lanczos").format(
            z=z_expr, x=x_expr, y=y_expr,
            bw=bw, bh=bh,
            fps='%.6f' % fps, w=width, h=height)

        ffmpeg_path = get_ffmpeg_path() or 'ffmpeg'
        cmd = [ffmpeg_path, '-y', '-i', video_path, '-vf', vf,
               '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast',
               '-pix_fmt', 'yuv420p']
        if has_audio:
            cmd += ['-c:a', 'aac', '-b:a', '160k']
        else:
            cmd += ['-an']
        cmd += ['-movflags', '+faststart', output]

        self.logger.info('美化命令: %s' % ' '.join(cmd))
        print('正在生成美化视频（可能需要几十秒）...')
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=1800,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != 0 or not os.path.exists(output):
            tail = (result.stderr or '')[-800:]
            self.logger.error('美化处理失败: %s' % tail)
            raise RuntimeError('美化处理失败: %s' % tail)
        self.logger.info('美化完成: %s' % output)
        print('美化完成: %s' % output)
        return output

    # ------------------------------------------------------------------
    # 时间线与表达式
    # ------------------------------------------------------------------
    def _build_keyframes(self, clicks, duration, zoom):
        """构建关键帧列表 [(t, zoom, cx, cy), ...]

        cx/cy 为镜头中心（物理像素）；None 表示全屏中心。
        相邻关键帧之间做 smoothstep 缓动。
        """
        kfs = [(0.0, 1.0, None, None)]
        for (t, x, y) in clicks:
            cur_t, cur_z, cur_cx, cur_cy = kfs[-1]
            move_start = max(t - self.zoom_in_dur, cur_t)
            if move_start > cur_t + 1e-6:
                kfs.append((move_start, cur_z, cur_cx, cur_cy))
            # 点击时刻推进到位并保持
            kfs.append((t, zoom, x, y))
            kfs.append((t + self.hold_dur, zoom, x, y))
        # 末尾拉回全屏
        last_t, last_z, _, _ = kfs[-1]
        if last_z != 1.0:
            end = last_t + self.zoom_out_dur
            if duration > end:
                end = max(end, duration)  # 有时长信息时保证拉回完成
            kfs.append((end, 1.0, None, None))
        return kfs

    def _build_expr(self, kfs, width, height, fps):
        """把关键帧编译为 zoompan 的 z/x/y 逐帧表达式（变量 t = on/fps）"""
        var = '(on/%.6f)' % fps
        z_points = [(t, z) for (t, z, _, _) in kfs]
        x_points, y_points = [], []
        for (t, z, cx, cy) in kfs:
            cx = width / 2.0 if cx is None else cx
            cy = height / 2.0 if cy is None else cy
            # 镜头中心换算为取景窗口左上角（zoompan 内部会自动裁剪越界）
            x_points.append((t, cx - width / (2.0 * z)))
            y_points.append((t, cy - height / (2.0 * z)))
        return (self._piecewise(z_points, var),
                self._piecewise(x_points, var),
                self._piecewise(y_points, var))

    @staticmethod
    def _piecewise(points, var):
        """生成分段 smoothstep 插值表达式：u=3u^2-2u^3"""
        if len(points) == 1:
            return '%.6f' % points[0][1]
        expr = '%.6f' % points[-1][1]
        # 从后往前嵌套 if，得到 if(t<T1, 段0, if(t<T2, 段1, ...))
        for i in range(len(points) - 2, -1, -1):
            t0, v0 = points[i]
            t1, v1 = points[i + 1]
            if t1 <= t0 + 1e-6:
                continue
            u = "(clip((%s-%.5f)/%.5f,0,1))" % (var, t0, t1 - t0)
            smooth = "(%s*%s*(3-2*%s))" % (u, u, u)
            piece = "(%.6f+(%.6f-%.6f)*%s)" % (v0, v1, v0, smooth)
            expr = "if(lt(%s,%.5f),%s,%s)" % (var, t1, piece, expr)
        return expr


if __name__ == '__main__':
    # 简单自测：对命令行传入的视频做一次演示美化（点击位于画面中心）
    import sys
    if len(sys.argv) < 2:
        print('用法: python BeautifyProcessor.py <video>')
        sys.exit(1)
    w, h, fps, dur, _ = probe_video(sys.argv[1])
    demo_events = [
        {'t': 2.0 + 0.5, 'x': w / 2, 'y': h / 2},
        {'t': 6.0 + 0.5, 'x': w / 4, 'y': h / 3},
    ]
    out = BeautifyProcessor().process(sys.argv[1], demo_events, zoom=2.0)
    print('输出: %s' % out)
