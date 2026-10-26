@echo off
setlocal
pushd "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m tools.check %*
) else (
    python -m tools.check %*
)
set "mycc_exit=%errorlevel%"
popd
exit /b %mycc_exit%
