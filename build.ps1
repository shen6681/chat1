$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Run setup.ps1 first to create the local Python environment.'
}
& $taskPython -m pip install --disable-pip-version-check 'pyinstaller==6.16.0'
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller installation failed.' }
& $taskPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Install Node.js to rebuild the React frontend, or use the portable release.' }
Push-Location -LiteralPath (Join-Path $PSScriptRoot 'web')
try {
    & npm.cmd ci --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    & npm.cmd test
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
& $taskPython -m PyInstaller --noconfirm ChatReplyAssistant.spec
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
& $taskPython .\scripts\package_release.py
if ($LASTEXITCODE -ne 0) { throw 'Release packaging failed.' }
Write-Output 'Ready: dist\ChatReplyAssistant.exe'
