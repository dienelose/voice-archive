@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 goto folder_error
if not exist "scripts\run.py" goto missing_files
if not exist ".venv\Scripts\python.exe" goto missing_python
".venv\Scripts\python.exe" "scripts\run.py"
set "VOICE_ARCHIVE_EXIT_CODE=%ERRORLEVEL%"
popd
if not "%VOICE_ARCHIVE_EXIT_CODE%"=="0" pause
exit /b %VOICE_ARCHIVE_EXIT_CODE%

:missing_python
echo Python environment not found.
echo Open PowerShell in this extracted folder and run:
echo   py -3.12 -m venv .venv
echo   .\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
echo See README.md for model installation instructions.
popd
pause
exit /b 1

:missing_files
echo Application files were not found.
echo Extract the entire ZIP before running start.bat.
echo Keep start.bat and the scripts folder in the same directory.
popd
pause
exit /b 1

:folder_error
echo Could not open the application folder.
echo Extract the ZIP to a local writable folder and try again.
pause
exit /b 1
