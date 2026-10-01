$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($taskLauncher) {
        & py -3.12 -m venv .venv
    } else {
        & python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or 3.11 is required. Install Python, then try again.' }
}
& $taskPython -m pip install --disable-pip-version-check --timeout 120 -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check network access to PyPI.' }
Write-Output 'Setup complete. Run: .\.venv\Scripts\python.exe main.py'
