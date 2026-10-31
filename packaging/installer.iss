; Inno Setup 6 script for OpenSchematix (Windows x64).
; Run packaging\build_windows.bat first; it compiles this script if ISCC is on PATH.
#define MyAppName "OpenSchematix"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Nate Robertson"
#define MyAppURL "https://ko-fi.com/nr270343"
#define MyAppExeName "OpenSchematix.exe"

[Setup]
; Independent application identity for OpenSchematix.
AppId={{6C3B0E9A-3F7D-4C55-9B57-2E0D4A8F9C21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL={#MyAppURL}
AppCopyright=Copyright (C) 2026 Nate Robertson
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
LicenseFile=..\LICENSE
OutputDir=..\installer_output
OutputBaseFilename=OpenSchematix-{#MyAppVersion}-Setup-x64
SetupIconFile=..\openschematix\resources\openschematix.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "assoc"; Description: "Open .schematix projects and .osch drawings with OpenSchematix"; GroupDescription: "File associations:"

[Files]
Source: "..\dist\OpenSchematix\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
Root: HKA; Subkey: "Software\Classes\.schematix"; ValueType: string; ValueName: ""; ValueData: "OpenSchematix.Project"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\OpenSchematix.Project"; ValueType: string; ValueName: ""; ValueData: "OpenSchematix project"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\OpenSchematix.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\OpenSchematix.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.osch"; ValueType: string; ValueName: ""; ValueData: "OpenSchematix.Drawing"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\OpenSchematix.Drawing"; ValueType: string; ValueName: ""; ValueData: "OpenSchematix drawing"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\OpenSchematix.Drawing\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\OpenSchematix.Drawing\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: assoc

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
