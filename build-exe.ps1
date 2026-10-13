# Builds dist\ImgScaleAndExport.exe with PyInstaller (run from anywhere).
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    uv run --group build pyinstaller --noconfirm --distpath dist --workpath build packaging/ImgScaleAndExport.spec
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Built: $PSScriptRoot\dist\ImgScaleAndExport.exe"
}
finally { Pop-Location }
