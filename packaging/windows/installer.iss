; Inno Setup script for the Transcribe-HTR Windows installer.
; Built by scripts/build_desktop.py, which passes:
;   /DAppVersion=<VERSION>  /DSourceDir=<PyInstaller onedir>  /DOutputDir=<dir>
;   /DWebView2Bootstrapper=<MicrosoftEdgeWebview2Setup.exe>   (optional)
;
; Install modes (DESKTOP_PLAN.md, "Multi-user computers"):
;   default, no admin    -> per-user, %LOCALAPPDATA%\Programs\Transcribe-HTR
;   "Install for all users" (or /ALLUSERS) -> C:\Program Files\Transcribe-HTR
;   IT deployment        -> Setup.exe /ALLUSERS /VERYSILENT /SUPPRESSMSGBOXES
; User data is never written under the install folder; it lives in each
; user's %LOCALAPPDATA%\Transcribe-HTR.

#define AppName "Transcribe-HTR"
#define AppExe "Transcribe-HTR.exe"
#ifndef AppVersion
  #error AppVersion must be defined (/DAppVersion=x.y.z)
#endif
#ifndef SourceDir
  #error SourceDir must be defined (/DSourceDir=path\to\dist\Transcribe-HTR)
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

[Setup]
; PERMANENT: identifies the product for upgrades and uninstall. Never change it.
AppId={{3B228E44-1F43-4EFF-8DB4-CF0BA7179BD1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Transcribe-HTR project
AppPublisherURL=https://github.com/gtw2i/Transcribe-HTR
AppSupportURL=https://github.com/gtw2i/Transcribe-HTR/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Windows 10 1809+, the oldest release WebView2 supports.
MinVersion=10.0.17763
OutputDir={#OutputDir}
OutputBaseFilename=Transcribe-HTR-{#AppVersion}-windows-x64-setup
SetupIconFile=..\icons\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
LicenseFile=..\..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#ifdef WebView2Bootstrapper
Source: "{#WebView2Bootstrapper}"; DestDir: "{tmp}"; DestName: "MicrosoftEdgeWebview2Setup.exe"; Flags: deleteafterinstall; Check: NeedsWebView2
#endif

[InstallDelete]
; An upgrade replaces the whole program folder, so files dropped by an older
; version cannot shadow the new ones.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
#ifdef WebView2Bootstrapper
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing the Microsoft Edge WebView2 Runtime..."; Check: NeedsWebView2; Flags: waituntilterminated
#endif
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2Client = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasWebView2Key(RootKey: Integer; SubKey: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

// Same check as desktop/launcher.py (_webview2_available).
function NeedsWebView2: Boolean;
begin
  Result := not (HasWebView2Key(HKLM, 'SOFTWARE\WOW6432Node\' + WebView2Client)
              or HasWebView2Key(HKLM, 'SOFTWARE\' + WebView2Client)
              or HasWebView2Key(HKCU, 'Software\' + WebView2Client));
end;

var
  RemoveUserData: Boolean;

// Uninstalling removes the program only. Each user's documents stay in their
// own profile unless THIS user asks to remove theirs; other accounts on the
// computer are never touched.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    RemoveUserData := (not UninstallSilent) and (MsgBox(
      'Also delete YOUR Transcribe-HTR documents, results, settings and remembered API keys?' + #13#10 + #13#10 +
      'Choose No to keep them (for example, to reinstall later). Other users of this computer are not affected.',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES);
    if RemoveUserData then
      // Keys live in Windows Credential Manager; the app removes its own entries.
      Exec(ExpandConstant('{app}\{#AppExe}'), '--forget-keys', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
  if (CurUninstallStep = usPostUninstall) and RemoveUserData then
    DelTree(ExpandConstant('{localappdata}\{#AppName}'), True, True, True);
end;
