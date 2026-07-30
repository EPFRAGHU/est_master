@echo off
REM ============================================================
REM  Build Establishment Master Search as a standalone .exe
REM  Just double-click this file. Requires Python installed
REM  once (from python.org) - after that, no Python needed to
REM  RUN the app, only to BUILD it this one time.
REM ============================================================

echo Installing required packages (one-time)...
pip install pyinstaller pandas openpyxl

echo.
echo Building EstablishmentMasterSearch.exe ...
pyinstaller --onefile --windowed --name EstablishmentMasterSearch establishment_search.py

echo.
echo ============================================================
echo   DONE.
echo   Your app is at:  dist\EstablishmentMasterSearch.exe
echo.
echo   Copy EstablishmentMasterSearch.exe and
echo   establishment_master.csv into the SAME folder together,
echo   then just double-click the .exe to run it - no Python
echo   or VS Code needed after this.
echo ============================================================
pause
