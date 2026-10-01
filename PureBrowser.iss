; PureBrowser.iss
; Inno Setup script for PureBrowser

[Setup]
AppId={{B8F3A2C1-4D5E-6F70-8A9B-C0D1E2F3A4B5}
AppName=PureBrowser
AppVersion=1.0.0
AppPublisher=PureBrowser Project
DefaultDirName={autopf}\PureBrowser
DisableDirPage=no
DisableProgramGroupPage=no
AllowNoIcons=yes
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer\Output
OutputBaseFilename=PureBrowserSetup
SetupIconFile=resources\purebrowser.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\PureBrowser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PureBrowser"; Filename: "{app}\PureBrowser.exe"
Name: "{group}\Uninstall PureBrowser"; Filename: "{uninstallexe}"
Name: "{autodesktop}\PureBrowser"; Filename: "{app}\PureBrowser.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PureBrowser.exe"; Description: "Launch PureBrowser"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"