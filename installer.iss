; Inno Setup — instalador do Fifine AM8 Control
; Build:  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=1.0.0 installer.iss
; (o build.py injeta a versão automaticamente a partir de fifine_version.py)

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppName "Fifine AM8 Control"
#define MyAppExe "FifineAM8Control.exe"
#define MyPublisher "DZK"
#define MyAppURL "https://github.com/VictorRobert0/fifine-am8"

[Setup]
AppId={{B7F3A1C2-AM8C-4E5D-9F10-FIFINECONTROL}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\Fifine AM8 Control
DefaultGroupName=Fifine AM8 Control
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=FifineAM8-Setup-{#MyAppVersion}
SetupIconFile=fifine.ico
UninstallDisplayIcon={app}\{#MyAppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; não exige admin se instalar na pasta do usuário; autopf escolhe conforme privilégio
PrivilegesRequiredOverridesAllowed=dialog commandline

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; conteúdo do build onedir do PyInstaller
Source: "dist\FifineAM8Control\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; instalador do VB-Cable é opcional — incluído só se você tiver direito de redistribuir
; coloque VBCABLE_Setup_x64.exe em vendor\ antes de compilar para empacotá-lo
Source: "vendor\VBCABLE_Setup_x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist; Check: VendorCableExists

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
; oferece abrir o app ao final
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
function VbCableInstalled(): Boolean;
begin
  { detecta o driver do VB-Audio Virtual Cable pelo serviço WDM }
  Result := RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\VBAudioVACWDM')
         or RegKeyExists(HKLM, 'SOFTWARE\VB-Audio\Cable');
end;

function VendorCableExists(): Boolean;
begin
  Result := FileExists(ExpandConstant('{src}\vendor\VBCABLE_Setup_x64.exe'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if not VbCableInstalled() then
    begin
      if VendorCableExists() then
      begin
        { instala o VB-Cable empacotado (requer sua licença de redistribuição) }
        if MsgBox('O microfone virtual precisa do VB-Audio Virtual Cable, que não foi '
          + 'encontrado. Deseja instalá-lo agora?', mbConfirmation, MB_YESNO) = IDYES then
          Exec(ExpandConstant('{tmp}\VBCABLE_Setup_x64.exe'), '', '', SW_SHOW,
               ewWaitUntilTerminated, ResultCode);
      end
      else
      begin
        { sem o binário empacotado: abre a página oficial de download }
        if MsgBox('O recurso de ganho++ e supressão de ruído (microfone virtual) '
          + 'precisa do VB-Audio Virtual Cable (gratuito). Abrir a página oficial '
          + 'para baixá-lo agora?', mbConfirmation, MB_YESNO) = IDYES then
          ShellExec('open', 'https://vb-audio.com/Cable/', '', '', SW_SHOW, ewNoWait, ResultCode);
      end;
    end;
  end;
end;
