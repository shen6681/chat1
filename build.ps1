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
& $taskPython -m PyInstaller --noconfirm --onefile --windowed --name ChatReplyAssistant --icon assets\icon.ico --collect-all rapidocr_onnxruntime --collect-data onnxruntime --collect-binaries onnxruntime main.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
& $taskPython .\package_release.py
if ($LASTEXITCODE -ne 0) { throw 'Release packaging failed.' }
Write-Output 'Ready: dist\ChatReplyAssistant.exe'
