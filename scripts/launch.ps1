$ErrorActionPreference = 'Stop'
$myccRoot = Split-Path -Parent $PSScriptRoot
Push-Location $myccRoot
try {
    $myccPython = Join-Path $myccRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $myccPython)) { $myccPython = 'python' }
    & $myccPython -m mycc --gui @args
    $myccExit = $LASTEXITCODE
} finally { Pop-Location }
exit $myccExit
