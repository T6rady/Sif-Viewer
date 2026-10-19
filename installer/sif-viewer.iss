; Build with build-installer.ps1. Source paths are relative to this script.
; AppName and AppId may be overridden only to create an isolated test build.
#ifndef AppName
  #define AppName "SIF Viewer"
#endif
#ifndef AppId
  #define AppId "ORI.SIFViewer"
#endif
#ifndef AppVersion
  #error AppVersion must be supplied by build-installer.ps1
#endif

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=ORI
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ChangesAssociations=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
WizardStyle=modern
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\SIF Viewer.exe
OutputDir=..\dist\installer
OutputBaseFilename=SIF-Viewer-{#AppVersion}-Setup-x64
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
Uninstallable=yes
UninstallDisplayName={#AppName}
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} Setup
VersionInfoCompany=ORI

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[Files]
Source: "..\dist\SIF Viewer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\installer\third-party-notices.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\installer\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\SIF Viewer.exe"; WorkingDir: "{app}"; AppUserModelID: "ORI.SIFViewer"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\SIF Viewer.exe"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "ORI.SIFViewer"

; Register an available handler; Windows retains the user's current default.
; AppId-derived keys keep isolated installer tests separate from the real app.
[Registry]
Root: HKCU; Subkey: "Software\Classes\{#AppId}.SIF"; ValueType: string; ValueData: "SIF document"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\{#AppId}.SIF"; ValueType: string; ValueName: "FriendlyTypeName"; ValueData: "SIF document"
Root: HKCU; Subkey: "Software\Classes\{#AppId}.SIF\DefaultIcon"; ValueType: string; ValueData: """{app}\SIF Viewer.exe"",0"
Root: HKCU; Subkey: "Software\Classes\{#AppId}.SIF\shell\open\command"; ValueType: string; ValueData: """{app}\SIF Viewer.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\.sif\OpenWithProgids"; ValueType: string; ValueName: "{#AppId}.SIF"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\{#AppId}\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#AppId}\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Read-only viewer for contract furniture SIF files."
Root: HKCU; Subkey: "Software\{#AppId}\Capabilities"; ValueType: string; ValueName: "ApplicationIcon"; ValueData: """{app}\SIF Viewer.exe"",0"
Root: HKCU; Subkey: "Software\{#AppId}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".sif"; ValueData: "{#AppId}.SIF"
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#AppName}"; ValueData: "Software\{#AppId}\Capabilities"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\SIF Viewer.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; No recursive uninstall-delete rules: only installed files/shortcuts are removed.
; Users' SIF files and other files they add are left alone.
