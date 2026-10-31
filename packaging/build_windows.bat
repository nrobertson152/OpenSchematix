@echo off
rem Build the OpenSchematix Windows application folder and installer.
rem Requirements: Python 3.10+ (python.org build, includes Tkinter), optional Inno Setup 6 (ISCC on PATH).
setlocal
cd /d "%~dp0\.."

if not exist .build-venv (
    py -3 -m venv .build-venv || goto :fail
)
call .build-venv\Scripts\activate.bat || goto :fail
python -m pip install --upgrade pip pyinstaller pytest || goto :fail

echo Running tests...
python -m pytest -q tests || goto :fail

echo Building application...
python -m PyInstaller --noconfirm --clean packaging\openschematix.spec || goto :fail

where iscc >nul 2>&1
if errorlevel 1 (
    echo Inno Setup 6 not found on PATH: skipping installer. The portable app is in dist\OpenSchematix.
) else (
    iscc packaging\installer.iss || goto :fail
    echo Installer written to installer_output\
)
echo Build complete.
exit /b 0

:fail
echo Build FAILED.
exit /b 1
