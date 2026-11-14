#define MyAppName    "Orion ERP Desktop"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Orion ERP"
#define MyAppExeName "OrionERP-Desktop.exe"

[Setup]
AppId={{4C8F2A1D-7B3E-4F90-A2C5-ORIONERPUSER02}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\OrionERPDesktop
DefaultGroupName=Orion ERP
DisableProgramGroupPage=no
OutputDir=..\output\installers
OutputBaseFilename=OrionERP-Desktop-User-Setup
SetupIconFile=..\assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau";         GroupDescription: "Raccourcis :"; Flags: checkedonce
Name: "autostart";   Description: "Lancer Orion ERP au démarrage de Windows"; GroupDescription: "Démarrage :"; Flags: unchecked

[Files]
Source: "..\dist\OrionERP-Desktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Orion ERP Desktop";             Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Désinstaller Orion ERP Desktop"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Orion ERP Desktop";        Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Orion ERP Desktop"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "Orion ERP Desktop"; Flags: deletevalue; Check: not WizardIsTaskSelected('autostart')

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer Orion ERP Desktop"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
