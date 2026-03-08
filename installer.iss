; 爱客服采集客户端 Inno Setup 安装脚本
; 需要先执行 build.py 生成 dist/ 目录

[Setup]
AppName=爱客服采集客户端
AppVersion=1.0.0
AppPublisher=爱客服团队
AppPublisherURL=http://8.145.43.255:6000
DefaultDirName={autopf}\爱客服采集客户端
DefaultGroupName=爱客服
OutputDir=installer_output
OutputBaseFilename=爱客服采集客户端_安装包_v1.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\爱客服采集客户端.exe
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; Flags: checked
Name: "startup"; Description: "开机时自动启动（推荐）"; Flags: unchecked

[Files]
Source: "dist\爱客服采集客户端\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\爱客服采集客户端"; Filename: "{app}\爱客服采集客户端.exe"
Name: "{group}\卸载爱客服采集客户端"; Filename: "{uninstallexe}"
Name: "{autodesktop}\爱客服采集客户端"; Filename: "{app}\爱客服采集客户端.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "AiKeFuClient"; \
  ValueData: """{app}\爱客服采集客户端.exe"""; \
  Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\爱客服采集客户端.exe"; Description: "立即启动爱客服采集客户端"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\.aikefu-client"
