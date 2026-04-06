@echo off
:: ============================================================
:: build.bat — збирання pdf_prepress.exe за допомогою PyInstaller
:: ============================================================
setlocal

set EXE_NAME=pdf_prepress
set DEST_DIR=%USERPROFILE%\pdf_prepress

echo.
echo [1/3] Збирання %EXE_NAME%.exe через PyInstaller...
echo -------------------------------------------------------

:: Перевіряємо наявність icon.ico (не обов'язково, але бажано)
if not exist icon.ico (
    echo  УВАГА: файл icon.ico не знайдено.
    echo         Збирання продовжиться без іконки.
    echo         Помістіть icon.ico поряд із build.bat, щоб задати іконку програми.
    echo.
    pyinstaller --onefile --windowed --name %EXE_NAME% main.py
) else (
    pyinstaller --onefile --windowed --name %EXE_NAME% --icon=icon.ico main.py
)

if errorlevel 1 (
    echo.
    echo [ПОМИЛКА] PyInstaller завершився з помилкою. Перевірте вивід вище.
    pause
    exit /b 1
)

echo.
echo [2/3] Копіювання %EXE_NAME%.exe до %DEST_DIR%\...
echo -------------------------------------------------------

if not exist "%DEST_DIR%" (
    mkdir "%DEST_DIR%"
    echo  Створено папку: %DEST_DIR%
)

copy /Y "dist\%EXE_NAME%.exe" "%DEST_DIR%\%EXE_NAME%.exe"

if errorlevel 1 (
    echo.
    echo [ПОМИЛКА] Не вдалось скопіювати файл. Перевірте права доступу.
    pause
    exit /b 1
)

echo  Скопійовано: %DEST_DIR%\%EXE_NAME%.exe

echo.
echo [3/3] Готово!
echo -------------------------------------------------------
echo.
echo  Щоб додати пункт "PDF Pre-Press" до контекстного меню .pdf:
echo.
echo    1. Відкрийте папку context_menu\
echo    2. Двічі клацніть install_context_menu.reg
echo    3. Підтвердьте імпорт у реєстр
echo.
echo  Щоб видалити пункт меню — використайте remove_context_menu.reg
echo.

pause
endlocal
