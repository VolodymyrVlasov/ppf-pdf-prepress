@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ======================================================
echo   PDF Pre-Press - Perevirka instrumentiv zbirky
echo ======================================================
echo.

set "ERRORS=0"

:: ---------------------------------------------------
:: Python
:: ---------------------------------------------------
echo --- Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo  [-] Python: NE ZNAIDENO
    echo      Zavantazhte z: https://www.python.org/downloads/
    set /a ERRORS+=1
) else (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do (
        echo  [+] Python: %%v
    )
)

:: ---------------------------------------------------
:: pip packages
:: ---------------------------------------------------
echo.
echo --- pip packages ---

python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo  [-] pyinstaller: not installed   (pip install pyinstaller)
    set /a ERRORS+=1
) else (
    echo  [+] pyinstaller: installed
)

python -m pip show pywebview >nul 2>&1
if errorlevel 1 (
    echo  [-] pywebview: not installed   (pip install pywebview)
    set /a ERRORS+=1
) else (
    echo  [+] pywebview: installed
)

python -m pip show pymupdf >nul 2>&1
if errorlevel 1 (
    echo  [-] pymupdf: not installed   (pip install pymupdf)
    set /a ERRORS+=1
) else (
    echo  [+] pymupdf: installed
)

python -m pip show opencv-python >nul 2>&1
if errorlevel 1 (
    echo  [-] opencv-python: not installed   (pip install opencv-python)
    set /a ERRORS+=1
) else (
    echo  [+] opencv-python: installed
)

python -m pip show img2pdf >nul 2>&1
if errorlevel 1 (
    echo  [-] img2pdf: not installed   (pip install img2pdf)
    set /a ERRORS+=1
) else (
    echo  [+] img2pdf: installed
)

python -m pip show Pillow >nul 2>&1
if errorlevel 1 (
    echo  [-] Pillow: not installed   (pip install Pillow)
    set /a ERRORS+=1
) else (
    echo  [+] Pillow: installed
)

python -m pip show pikepdf >nul 2>&1
if errorlevel 1 (
    echo  [-] pikepdf: not installed   (pip install pikepdf)
    set /a ERRORS+=1
) else (
    echo  [+] pikepdf: installed
)

:: ---------------------------------------------------
:: Ghostscript
:: ---------------------------------------------------
echo.
echo --- Ghostscript ---

if exist "ghostscript\bin\gswin64c.exe" (
    echo  [+] Ghostscript: znaideno u build\ghostscript\bin\gswin64c.exe
) else (
    echo  [-] Ghostscript: NE ZNAIDENO u build\ghostscript\
    echo      Prochytaite build\ghostscript\README.txt
    set /a ERRORS+=1
)

:: ---------------------------------------------------
:: Inno Setup 6
:: ---------------------------------------------------
echo.
echo --- Inno Setup 6 ---

set "ISCC_FOUND=0"
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_FOUND=1"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set "ISCC_FOUND=1"

if "%ISCC_FOUND%"=="1" (
    echo  [+] Inno Setup 6: znaideno
) else (
    echo  [-] Inno Setup 6: NE ZNAIDENO
    echo      Zavantazhte z: https://jrsoftware.org/isdl.php
    set /a ERRORS+=1
)

:: ---------------------------------------------------
:: WebView2 Runtime
:: ---------------------------------------------------
echo.
echo --- WebView2 Runtime ---

set "WV2_FOUND=0"
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>&1
if not errorlevel 1 set "WV2_FOUND=1"
reg query "HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>&1
if not errorlevel 1 set "WV2_FOUND=1"

if "%WV2_FOUND%"=="1" (
    echo  [+] WebView2 Runtime: vstanovleno
) else (
    echo  [-] WebView2 Runtime: NE ZNAIDENO
    echo      Vstanovit z: https://developer.microsoft.com/microsoft-edge/webview2/
    set /a ERRORS+=1
)

:: ---------------------------------------------------
:: icon.ico
:: ---------------------------------------------------
echo.
echo --- icon.ico ---

if exist "..\icon.ico" (
    echo  [+] icon.ico: znaideno ^(..\icon.ico^)
) else (
    echo  [-] icon.ico: NE ZNAIDENO
    echo      Pomistit icon.ico u korin proektu
    set /a ERRORS+=1
)

:: ---------------------------------------------------
:: Pidsumok
:: ---------------------------------------------------
echo.
echo ======================================================
if %ERRORS%==0 (
    echo   [+] Vsi perevirky proideno. Mozhna zapuskaty build_all.bat
) else (
    echo   [-] Znaideno problem: %ERRORS%. Vypravte ikh pered zbirkoju.
)
echo ======================================================
echo.
pause
