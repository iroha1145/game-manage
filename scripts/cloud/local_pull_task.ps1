# Current-user scheduled task entry point. No passwords, payload logging or elevation.
$ErrorActionPreference = 'Stop'
try {
    $taskRepo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
    $taskPython = Join-Path $taskRepo '.venv/Scripts/python.exe'
    if (!(Test-Path -LiteralPath $taskPython -PathType Leaf)) { exit 2 }
    Push-Location -LiteralPath $taskRepo
    try {
        & $taskPython -m scripts.cloud.local_pull --execute
        $taskExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    exit $taskExitCode
} catch {
    Write-Output 'local_pull_task_failed'
    exit 2
}
