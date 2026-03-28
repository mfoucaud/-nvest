@echo off
echo ================================
echo   !nvest - Demarrage complet
echo ================================

cd /d "%~dp0"

:: Lancer le backend dans une nouvelle fenetre
start "Backend FastAPI" cmd /k "python -m uvicorn backend.main:app --reload --port 8000"

:: Attendre que le backend soit pret
echo Demarrage du backend...
timeout /t 3 /nobreak >nul

:: Lancer le frontend dans une nouvelle fenetre
start "Frontend React" cmd /k "cd /d \"%~dp0frontend\" && npm run dev"

:: Attendre que le frontend soit pret
echo Demarrage du frontend...
timeout /t 4 /nobreak >nul

:: Ouvrir le navigateur
echo Ouverture du navigateur...
start "" "http://localhost:5173"

echo.
echo  Backend  : http://localhost:8000
echo  Frontend : http://localhost:5173
echo  API docs : http://localhost:8000/docs
echo.
echo Les deux serveurs tournent dans leurs fenetres respectives.
echo Ferme ces fenetres pour arreter l'application.
