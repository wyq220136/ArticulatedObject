param(
    [Parameter(Position = 0)]
    [string]$ConfigPath = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$entrypoint = Join-Path $scriptDir "run.py"

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $scriptDir "..\config.yml"
}

$python = if ([string]::IsNullOrWhiteSpace($env:PYTHON_BIN)) {
    "python"
} else {
    $env:PYTHON_BIN
}

& $python $entrypoint $ConfigPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
