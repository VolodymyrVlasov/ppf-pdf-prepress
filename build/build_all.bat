@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ======================================================
echo   PDF Pre-Press - Full Build
echo ======================================================
echo.

:: ---------------------------------------------------
:: Step 1 - Check Ghostscript
:: ---------------------------------------------------
echo [1/5] Checking Ghostscript...
if not exist ghostscript\bin\gswin64c.exe (
    echo.
    echo  ERROR: Ghostscript not found at build\ghostscript\bin\gswin64c.exe
    echo  Read: build\ghostscript\README.txt
    echo.
    pause
    exit /b 1
)
echo  [OK] Ghostscript found.

:: ---------------------------------------------------
:: Step 2 - Check / install PyInstaller
:: ---------------------------------------------------
echo.
echo [2/5] Checking PyInstaller...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo  PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo  ERROR: Failed to install PyInstaller.
        pause
        exit /b 1
    )
)
echo  [OK] PyInstaller ready.

:: ---------------------------------------------------
:: Step 3 - Clean previous build
:: ---------------------------------------------------
echo.
echo [3/5] Cleaning previous artifacts...
if exist ..\dist\pdf_prepress  rmdir /s /q ..\dist\pdf_prepress
if exist ..\build_tmp          rmdir /s /q ..\build_tmp
echo  [OK] Cleaned.

:: ---------------------------------------------------
:: Step 4 - PyInstaller
:: ---------------------------------------------------
echo.
echo [4/5] Building app with PyInstaller...
python -m PyInstaller build.spec --distpath ..\dist --workpath ..\build_tmp
if errorlevel 1 (
    echo.
    echo  ERROR: PyInstaller failed.
    echo  Review the output above for details.
    pause
    exit /b 1
)
echo  [OK] PyInstaller done. Output: dist\pdf_prepress\

:: Verify PyInstaller produced the expected output
if not exist ..\dist\pdf_prepress\pdf_prepress.exe (
    echo.
    echo  ERROR: PyInstaller did not produce expected output.
    echo  Expected: dist\pdf_prepress\pdf_prepress.exe
    echo.
    pause
    exit /b 1
)

:: ---------------------------------------------------
:: Step 5 - Inno Setup
:: ---------------------------------------------------
echo.
echo [5/5] Creating installer with Inno Setup...

set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe

if "%ISCC%"=="" (
    echo.
    echo  ERROR: Inno Setup 6 not found.
    echo  Download from: https://jrsoftware.org/isdl.php
    echo  Expected: C:\Program Files (x86)\Inno Setup 6\ISCC.exe
    echo.
    pause
    exit /b 1
)

"%ISCC%" installer.iss
if errorlevel 1 (
    echo.
    echo  ERROR: Inno Setup failed.
    echo  Review the output above for details.
    pause
    exit /b 1
)

:: ---------------------------------------------------
:: Done
:: ---------------------------------------------------
echo.
echo ======================================================
echo   DONE!
echo.
echo   Installer saved to:
echo   dist_installer\setup_pdf_prepress.exe
echo ======================================================
echo.
pause
