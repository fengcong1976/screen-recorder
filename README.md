# screen-recorder

screen-recorder 源码仓库。

## 运行

```bat
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python main.py
```

构建与安装包脚本见仓库内的 `.spec`、`.iss` 与 `build*.bat`。

## 许可

GPL-3.0，详见 LICENSE。第三方组件声明见 THIRD_PARTY_NOTICES.md。

## 仓库说明

本仓库只包含源码，以下运行时资源体积较大，未纳入仓库：

- ffmpeg-shared/（FFmpeg 共享库）：自行下载 FFmpeg 后放到该目录再运行/打包。
