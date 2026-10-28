@echo off
cd /d "%~dp0"
where pyw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pyw -3.14 "%~dp0run_qtcalendar.pyw"
) else (
    start "" pythonw "%~dp0run_qtcalendar.pyw"
)
