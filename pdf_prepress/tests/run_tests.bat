@echo off
:: Запуск тестів для pdf_prepress
:: Виконувати з папки pdf_prepress\ (де знаходиться main.py)
echo.
echo Запуск pytest...
echo -------------------------------------------------------
cd /d "%~dp0.."
pytest tests/ -v
echo.
pause
