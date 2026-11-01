; Offleak installer for Windows 10/11 x64 and OBS Studio 28+ (built on macOS/Linux with makensis).
; Build: installers/build_windows.sh  ->  dist/Offleak-Setup-<version>.exe
Unicode true
!include "MUI2.nsh"

!ifndef VERSION
  !error "pass -DVERSION=x.y.z"
!endif
!ifndef PAYLOAD
  !error "pass -DPAYLOAD=<staged app folder>"
!endif
!ifndef OUTFILE
  !error "pass -DOUTFILE=<installer path>"
!endif

!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Offleak"
!define PLUGIN_DIR "obs-studio\plugins\offleak-direct"

Name "Offleak"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\Offleak"
RequestExecutionLevel admin  ; the OBS plugin goes into the machine-wide ProgramData plugin folder
SetCompressor /SOLID lzma
BrandingText "Offleak ${VERSION}"
VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "Offleak"
VIAddVersionKey "FileDescription" "Offleak installer"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "AGPL-3.0"

!define MUI_ICON "${PAYLOAD}\offleak.ico"
!define MUI_UNICON "${PAYLOAD}\offleak.ico"
!define MUI_WELCOMEPAGE_TITLE "Install Offleak"
!define MUI_WELCOMEPAGE_TEXT "Offleak blurs bystanders' faces, QR codes and phone numbers in your OBS video, on your own computer.$\r$\n$\r$\nSetup installs a private Python, the GPU libraries for your graphics card, the detector models and the OBS filter. It downloads about 1-3 GB and takes several minutes.$\r$\n$\r$\nClose OBS before continuing."
!define MUI_FINISHPAGE_TITLE "Offleak is installed"
!define MUI_FINISHPAGE_TEXT "In OBS, right-click your camera source > Filters > + > Offleak direct filter. Start Offleak to process video and open its setup page."
!define MUI_FINISHPAGE_RUN "$INSTDIR\Start Offleak.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Start Offleak now"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${PAYLOAD}\LICENSE"
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Offleak"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${PAYLOAD}\*.*"

  ; OBS 28+ loads plugins from C:\ProgramData\obs-studio\plugins\<name>\bin\64bit
  SetShellVarContext all
  SetOutPath "$APPDATA\${PLUGIN_DIR}\bin\64bit"
  File "${PAYLOAD}\native\offleak-direct.dll"
  CreateDirectory "$APPDATA\${PLUGIN_DIR}\data"
  SetShellVarContext current

  DetailPrint "Setting up Python, GPU libraries and models (this takes several minutes)..."
  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\installers\windows\setup.ps1" -AppDir "$INSTDIR"'
  Pop $0
  StrCmp $0 "0" setup_ok
    MessageBox MB_ICONEXCLAMATION "Setup could not finish (code $0). Check your internet connection and $INSTDIR\setup.log, then run this installer again."
  setup_ok:

  CreateDirectory "$SMPROGRAMS\Offleak"
  CreateShortcut "$SMPROGRAMS\Offleak\Offleak.lnk" "$INSTDIR\Start Offleak.bat" "" "$INSTDIR\offleak.ico"
  CreateShortcut "$SMPROGRAMS\Offleak\Uninstall Offleak.lnk" "$INSTDIR\Uninstall Offleak.exe"
  CreateShortcut "$DESKTOP\Offleak.lnk" "$INSTDIR\Start Offleak.bat" "" "$INSTDIR\offleak.ico"

  WriteUninstaller "$INSTDIR\Uninstall Offleak.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "Offleak"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "Offleak"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\offleak.ico"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall Offleak.exe"'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext all
  RMDir /r "$APPDATA\${PLUGIN_DIR}"
  SetShellVarContext current
  Delete "$DESKTOP\Offleak.lnk"
  RMDir /r "$SMPROGRAMS\Offleak"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
SectionEnd
