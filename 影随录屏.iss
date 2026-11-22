; 影随录屏 安装包脚本（Inno Setup 6）
; 使用：ISCC.exe 影随录屏.iss
; 前置：先运行 PyInstaller 生成 dist\影随录屏\

#define MyAppName "影随录屏"
#define MyAppVersion "1.1"
#define MyAppPublisher "深圳市创炫互动网络科技有限公司"
#define MyAppURL "https://www.mrheedu.com"
#define MyAppExeName "影随录屏.exe"

[Setup]
RedirectionGuard=no
AppId={{8E4C2A91-6D3B-4F5E-9A7C-1B2D3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
; 免管理员权限，仅安装到当前用户目录
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=影随录屏安装包-v{#MyAppVersion}
SetupIconFile=图标.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; 主程序（PyInstaller 产物）
Source: "dist\影随录屏\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; ffmpeg 与程序资源
Source: "ffmpeg-shared\*"; DestDir: "{app}\ffmpeg-shared"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "resource\*"; DestDir: "{app}\resource"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "图标.png"; DestDir: "{app}"; Flags: ignoreversion
; 配置文件：默认 ini 装入 {app}，应用首次启动会把它迁移到 %LOCALAPPDATA%\影随录屏
Source: "configByLinxiao.ini"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时清理历史版本残留（旧版把录制写到 {app}\recordings；现默认目录为 视频库\影随录屏，不删除）
Type: filesandordirs; Name: "{app}\recordings"
