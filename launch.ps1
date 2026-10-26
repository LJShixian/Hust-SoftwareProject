$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $myccPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $myccPython)) { $myccPython = 'python' }
    & $myccPython -m mycc --gui @args
    $myccExit = $LASTEXITCODE
} finally { Pop-Location }
exit $myccExit
