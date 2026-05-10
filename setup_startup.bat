@echo off
echo ================================
echo   !nvest - Configuration Startup
echo ================================

set "PROJECT_DIR=%~dp0"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_DIR%\nvest.lnk"

echo Création du raccourci dans : %STARTUP_DIR%

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $sc = $ws.CreateShortcut('%SHORTCUT_PATH%'); ^
   $sc.TargetPath = '%PROJECT_DIR%start.bat'; ^
   $sc.WorkingDirectory = '%PROJECT_DIR%'; ^
   $sc.WindowStyle = 7; ^
   $sc.Description = '!nvest Trading Dashboard'; ^
   $sc.Save()"

if exist "%SHORTCUT_PATH%" (
  echo.
  echo  Raccourci créé avec succes !
  echo  !nvest démarrera automatiquement à la prochaine connexion Windows.
  echo.
  echo  Pour supprimer : supprimer %SHORTCUT_PATH%
) else (
  echo.
  echo  ERREUR : Le raccourci n'a pas pu être créé.
  echo  Vérifiez les permissions PowerShell.
)

pause
