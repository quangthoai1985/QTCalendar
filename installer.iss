; Bộ cài đặt QT Calendar (Inno Setup 6) — Cài đặt theo người dùng, KHÔNG cần quyền quản trị UAC.
; Biên dịch: python tools/build_release.py
; Kết quả: dist\QTCalendar_Setup.exe (Cài đặt im lặng: QTCalendar_Setup.exe /SILENT hoặc /VERYSILENT)

#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "dist\QTCalendar"
#endif

#define AppName "QT Calendar"
#define AppExe "QTCalendar.exe"
#define RegAppName "QTCalendar"
#define CapKey "Software\QTCalendar\Capabilities"
#define AppDesc "Lịch bloc Dương – Âm truyền thống thuần Việt cho Windows."
#define RepoUrl "https://github.com/quangthoai1985/QTCalendar"

[Setup]
; AppId trùng với INNO_APP_ID trong update_check.py để đồng bộ phiên bản tự cập nhật
AppId={{C8E2856F-F57B-4F1D-891E-4B022B8C3A42}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher=Quang Thoại (quangthoai1985)
AppPublisherURL={#RepoUrl}
AppSupportURL={#RepoUrl}/issues
AppUpdatesURL={#RepoUrl}/releases
AppCopyright=MIT License
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoDescription=Bộ cài đặt {#AppName}

; Cài đặt cho người dùng hiện tại: %LOCALAPPDATA%\Programs\QT Calendar
PrivilegesRequired=lowest
UsedUserAreasWarning=no
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
DefaultGroupName={#AppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=dist
OutputBaseFilename=QTCalendar_Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe},0
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

; Mutex nhận diện ứng dụng đang chạy để nhắc đóng khi cài/gỡ
AppMutex=QTCalendar.AppMutex
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.CreateDesktopIcon=Tạo biểu tượng ngoài màn hình nền (Desktop)
english.CreateStartupIcon=Khởi động cùng Windows khi đăng nhập
english.LaunchProgram=Khởi chạy %1 ngay bây giờ

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "Tuỳ chọn bổ sung:"
Name: "startupicon"; Description: "{cm:CreateStartupIcon}"; GroupDescription: "Tuỳ chọn bổ sung:"; Flags: unchecked

[InstallDelete]
; Xoá bộ thư viện cũ khi cài đè phiên bản mới
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "{#AppDesc}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "{#AppDesc}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startupicon

[Registry]
; Cho phép gõ "QTCalendar" trong hộp thoại Run (Win+R)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#AppExe}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#AppExe}"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletekey

; Đăng ký Capabilities cho Windows Settings (Installed apps)
Root: HKCU; Subkey: "Software\{#RegAppName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "{#CapKey}"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#AppName}"
Root: HKCU; Subkey: "{#CapKey}"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "{#AppDesc}"
Root: HKCU; Subkey: "{#CapKey}"; ValueType: string; ValueName: "ApplicationIcon"; ValueData: """{app}\{#AppExe}"",0"
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#RegAppName}"; ValueData: "{#CapKey}"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
