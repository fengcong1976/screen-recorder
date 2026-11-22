import subprocess,os,sys

def run_cmd(cmd, shell = True, universal_newlines = False):
    output_info=[]
    output_err=[]
    
    # 获取FFmpeg路径
    ffmpeg_path = get_ffmpeg_path()
    
    # 如果找到了FFmpeg可执行文件路径
    if ffmpeg_path:
        cmd = '"' + ffmpeg_path + '" ' + cmd
    
    print('执行cmd：\n%s' % cmd)
    
    with subprocess.Popen(cmd, 
                                                 shell = shell, 
                                                 universal_newlines = universal_newlines, 
                                                 stdout = subprocess.PIPE,
                                                 stdin = subprocess.PIPE,
                                                 stderr = subprocess.PIPE,
                                                 creationflags=subprocess.CREATE_NO_WINDOW  # 添加这一行来隐藏控制台窗口
                                                ) as p:
        while True:
            info=p.stdout.read()
            err=p.stderr.read()
            
            if info == b'' and err == b'':
                if p.poll() is not None:  
                    break
            else:
                output_info.append(info)
                output_err.append(err)
                
    return output_err, output_info
    
        
def get_ffmpeg_path():
    
    ffmpeg_path = ''
    
    # 检查FFmpeg-shared目录
    subdir = os.path.join('ffmpeg-shared','bin','ffmpeg.exe')
    
    if getattr(sys, 'frozen', False):
        # The application is frozen
        datadir = os.path.dirname(sys.executable)
    else:
        # The application is not frozen
        datadir = os.path.dirname(__file__)
    
    ffmpeg_path = os.path.join(datadir, subdir)
    ffmpeg_path = os.path.abspath(ffmpeg_path)
    
    # 如果存在ffmpeg.exe，返回完整的可执行文件路径
    if os.path.isfile(ffmpeg_path):
        return ffmpeg_path
    
    # 检查环境变量
    try:
        env_ffmpeg = subprocess.check_output(['where', 'ffmpeg'], shell=True).decode().strip()
        if os.path.isfile(env_ffmpeg):
            return env_ffmpeg
    except:
        pass
    
    # 兼容环境变量设置
    return ''

