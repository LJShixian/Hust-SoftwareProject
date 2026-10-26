@echo off
setlocal
pushd "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m mycc --gui %*
) else (
    python -m mycc --gui %*
)
set "mycc_exit=%errorlevel%"
popd
exit /b %mycc_exit%
