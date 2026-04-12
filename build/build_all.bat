@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ======================================================
echo   PDF Pre-Press - Zbirka instaliatora
echo ======================================================
echo.

:: ---------------------------------------------------
:: Krok 1 - Perevirka naiavnosti Ghostscript
:: ---------------------------------------------------
echo [1/5] Perevirka Ghostscript...
if not exist "ghostscript\bin\gswin64c.exe" (
    echo.
    echo  POMYLKA: Ghostscript ne znaideno u build\ghostscript\bin\gswin64c.exe
    echo.
    echo  Prochytaite instrukciiu: build\ghostscript\README.txt
    echo  Pidhotuite faily GS i povtority zapusk build_all.bat
    echo.
    pause
    exit /b 1
)
echo  [OK] Ghostscript znaideno.

:: ---------------------------------------------------
:: Krok 2 - Perevirka / vstanovlennia PyInstaller
:: ---------------------------------------------------
echo.
echo [2/5] Perevirka PyInstaller...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo  PyInstaller ne znaideno. Vstanovlennia...
    pip install pyinstaller
    if errorlevel 1 (
        echo  POMYLKA: ne vdalos vstanovyty PyInstaller.
        pause
        exit /b 1
    )
)
echo  [OK] PyInstaller hotovyi.

:: ---------------------------------------------------
:: Krok 3 - Ochyshchennia poperednoi zbirky
:: ---------------------------------------------------
echo.
echo [3/5] Ochyshchennia poperednih artefaktiv...
if exist "..\dist\pdf_prepress"  rmdir /s /q "..\dist\pdf_prepress"
if exist "..\build_tmp"          rmdir /s /q "..\build_tmp"
echo  [OK] Ochyshcheno.

:: ---------------------------------------------------
:: Krok 4 - PyInstaller
:: ---------------------------------------------------
echo.
echo [4/5] Zbirka dodatku cherez PyInstaller...
python -m PyInstaller build.spec --distpath ..\dist --workpath ..\build_tmp
if errorlevel 1 (
    echo.
    echo  POMYLKA: PyInstaller zavershyvsia z pomylkoiu.
    echo  Perehliante vyvid vyshche dlia detalei.
    pause
    exit /b 1
)
echo  [OK] PyInstaller zaversheno. Rezultat: dist\pdf_prepress\

:: ---------------------------------------------------
:: Krok 5 - Inno Setup
:: ---------------------------------------------------
echo.
echo [5/5] Stvorennia instaliatora cherez Inno Setup...

set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo.
    echo  POMYLKA: Inno Setup 6 ne znaideno.
    echo  Zavantazhte ta vstanovit z: https://jrsoftware.org/isdl.php
    echo  Ochikuvanyi shliakh: C:\Program Files (x86)\Inno Setup 6\ISCC.exe
    echo.
    pause
    exit /b 1
)

"%ISCC%" installer.iss
if errorlevel 1 (
    echo.
    echo  POMYLKA: Inno Setup zavershyvsia z pomylkoiu.
    echo  Perehliante vyvid vyshche dlia detalei.
    pause
    exit /b 1
)

:: ---------------------------------------------------
:: Hotovo
:: ---------------------------------------------------
echo.
echo ======================================================
echo   HOTOVO!
echo.
echo   Instaliatora zberezheno u:
echo   dist_installer\setup_pdf_prepress.exe
echo ======================================================
echo.
pause
