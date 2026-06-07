; =============================================================================
; PicSimProcess CPU Installer Script for Inno Setup 7.x
;
; Result: CPU-only image/video similarity tool (smaller package, no GPU needed)
;
; Prerequisites:
;   1. Install Inno Setup 7: https://jrsoftware.org/isdl.php
;   2. Run PyInstaller first: python build\build-cpu.py
;   3. Compile this script with Inno Setup Compiler (ISCC.exe)
;
; To compile from command line:
;   "C:\Program Files\Inno Setup 7\ISCC.exe" build\installer-cpu.iss
;
; Output: Output\PicSimProcess_CPU_Setup_v{VERSION}.exe
; =============================================================================

#define AppName "PicSimProcess CPU"
#define AppVersion "1.0.1"
#define AppPublisher "PicSimProcess"
#define AppURL ""
#define AppExeName "PicSimProcess.exe"

[Setup]
AppId={{C3D4E5F6-A7B8-4C9D-0E1F-2A3B4C5D6E8F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE.txt
OutputDir=..\Output
OutputBaseFilename=PicSimProcess_CPU_Setup_v{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog

; Prevent running the app during installation
AppMutex=PicSimProcess_Mutex

; Architectures (Inno Setup 7 supports x64 natively)
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Version info
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Image and Video Similarity Detection Tool (CPU Edition)
VersionInfoTextVersion={#AppVersion}
VersionInfoCopyright=Copyright (C) 2024

; Modern UI settings (Inno Setup 7)
WizardSizePercent=120
WizardResizable=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
; Create writable directory for user data (blocklist, etc.)
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\data\input"; Permissions: users-modify
Name: "{app}\data\output"; Permissions: users-modify

[Files]
; Main executable
Source: "..\dist-cpu\PicSimProcess\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; PyInstaller _internal folder (binaries, Python runtime, bundled packages)
Source: "..\dist-cpu\PicSimProcess\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; Seed an empty blocklist.json only when one does not already exist.
; This protects user data during upgrades/reinstalls.
Source: "..\data\blocklist.json"; DestDir: "{app}\data"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Optional: launch after installation
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up generated user data on uninstall (optional - comment out to keep)
Type: filesandordirs; Name: "{app}\data\input"
Type: filesandordirs; Name: "{app}\data\output"

[Code]
// Installation complete callback
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Installation complete
  end;
end;
