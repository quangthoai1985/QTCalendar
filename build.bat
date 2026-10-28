@echo off
setlocal
cd /d "%~dp0"

set "DIST_DIR=dist"
if not "%~1"=="" set "DIST_DIR=%~1"

echo ========================================================
echo Dang bien dich QT Calendar bang PyInstaller...
echo ========================================================

py -3.14 -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --name QTCalendar ^
    --distpath "%DIST_DIR%" ^
    --icon assets\icon.ico ^
    --paths src ^
    --collect-all qtcalendar ^
    --add-data "src\qtcalendar\data;qtcalendar\data" ^
    --add-data "assets\icon.ico;assets" ^
    --add-data "assets\icon.png;assets" ^
    --exclude-module tkinter ^
    --exclude-module matplotlib ^
    --exclude-module scipy ^
    run_qtcalendar.pyw

if errorlevel 1 (
    echo [LOI] Bien dich PyInstaller that bai!
    exit /b 1
)

copy /y LICENSE "%DIST_DIR%\QTCalendar\LICENSE" >nul 2>&1
echo ========================================================
echo Bien dich thanh cong: "%DIST_DIR%\QTCalendar\QTCalendar.exe"
echo ========================================================
