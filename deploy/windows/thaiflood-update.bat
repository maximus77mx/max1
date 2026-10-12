@echo off
rem Collect flood data and rebuild the dashboard. Task Scheduler runs this every 15 minutes.
rem Usage: thaiflood-update.bat [WEB_DIR]   (default C:\inetpub\wwwroot\flood)
setlocal
set "APP_DIR=%~dp0..\.."
set "WEB_DIR=%~1"
if "%WEB_DIR%"=="" set "WEB_DIR=C:\inetpub\wwwroot\flood"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

cd /d "%APP_DIR%" || exit /b 1
if not exist data mkdir data
if not exist "%WEB_DIR%" mkdir "%WEB_DIR%"

rem keep the log small: rotate at ~5 MB
if exist data\update.log for %%A in (data\update.log) do if %%~zA GTR 5000000 move /y data\update.log data\update.old.log >nul

echo ===== %date% %time% =====>> data\update.log
".venv\Scripts\thaiflood.exe" collect --respect-intervals >> data\update.log 2>&1
".venv\Scripts\thaiflood.exe" dashboard "%WEB_DIR%\index.html" --days 7 >> data\update.log 2>&1
set "RC=%errorlevel%"

rem drop data older than 60 days (cheap, safe to run every time)
".venv\Scripts\thaiflood.exe" prune --keep-days 60 >> data\update.log 2>&1

exit /b %RC%
