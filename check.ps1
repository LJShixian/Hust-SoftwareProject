param([switch]$Full)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $myccPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $myccPython)) { $myccPython = 'python' }
    if ($Full) { & $myccPython -m tools.check --full }
    else { & $myccPython -m tools.check }
    $myccExit = $LASTEXITCODE
} finally { Pop-Location }
exit $myccExit
