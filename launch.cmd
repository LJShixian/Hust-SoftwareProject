@echo off
setlocal
pushd "%~dp0"
set "mycc_python=python"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import PySide6" >nul 2>nul
    if not errorlevel 1 set "mycc_python=.venv\Scripts\python.exe"
)
"%mycc_python%" -m mycc --gui %*
set "mycc_exit=%errorlevel%"
popd
exit /b %mycc_exit%
