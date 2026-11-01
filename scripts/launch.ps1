$ErrorActionPreference = 'Stop'
$myccRoot = Split-Path -Parent $PSScriptRoot
Push-Location $myccRoot
try {
    $myccPython = Join-Path $myccRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $myccPython) {
        & $myccPython -c "import PySide6" 2>$null
        if ($LASTEXITCODE -ne 0) { $myccPython = 'python' }
    } else { $myccPython = 'python' }
    & $myccPython -m mycc --gui @args
    $myccExit = $LASTEXITCODE
} finally { Pop-Location }
exit $myccExit
