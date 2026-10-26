param([switch]$Full)
$ErrorActionPreference = 'Stop'
$myccRoot = Split-Path -Parent $PSScriptRoot
Push-Location $myccRoot
try {
    $myccPython = Join-Path $myccRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $myccPython)) { $myccPython = 'python' }
    if ($Full) { & $myccPython -m tools.check --full }
    else { & $myccPython -m tools.check }
    $myccExit = $LASTEXITCODE
} finally { Pop-Location }
exit $myccExit
