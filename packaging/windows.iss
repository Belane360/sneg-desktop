[Setup]
AppId={{86A1D2D2-93C0-4075-AE1D-C20A39EA5712}
AppName=Sneg
AppVersion=0.4.0
AppPublisher=Sneg
DefaultDirName={localappdata}\Programs\Sneg
DefaultGroupName=Sneg
OutputDir=..\dist
OutputBaseFilename=Sneg-Windows-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Sneg.exe
[Files]
Source: "..\dist\Sneg\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Sneg"; Filename: "{app}\Sneg.exe"
Name: "{autodesktop}\Sneg"; Filename: "{app}\Sneg.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\Sneg.exe"; Description: "Launch Sneg"; Flags: nowait postinstall skipifsilent
