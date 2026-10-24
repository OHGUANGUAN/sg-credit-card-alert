@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "%~dp0CC_PDF_WTS.py"
) else (
    python "%~dp0CC_PDF_WTS.py"
)
exit /b %errorlevel%
