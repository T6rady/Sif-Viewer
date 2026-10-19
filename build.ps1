param([string]$Python = "$PSScriptRoot\.venv\Scripts\python.exe")

$ErrorActionPreference = 'Stop'
$originalPath = $env:Path
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath $Python)) {
        throw "Python not found: $Python. Create .venv and install requirements.txt first."
    }
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
    # Prevent unrelated tools on PATH (e.g. Poppler's ICU DLL) from shadowing
    # Windows libraries during dependency collection. Restore PATH on exit.
    $env:Path = "$(Split-Path -Parent $Python);$([Environment]::SystemDirectory);$env:SystemRoot"
    # OneDrive may mark generated directories read-only; native forced removal
    # handles those flags. Delete only this project's exact generated output.
    $outputPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'dist\SIF Viewer'))
    $workspacePath = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
    if (-not $outputPath.StartsWith($workspacePath, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Generated output must remain within the project directory.'
    }
    if (Test-Path -LiteralPath $outputPath) {
        Remove-Item -LiteralPath $outputPath -Recurse -Force
    }
    $workPath = Join-Path $env:TEMP 'sif-viewer-pyinstaller'
    & $Python -m PyInstaller --noconfirm --clean --windowed --onedir --workpath $workPath --icon 'assets\app.ico' --add-data 'assets:assets' --name 'SIF Viewer' main.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    Write-Host 'Built: dist\SIF Viewer\SIF Viewer.exe'
    Write-Host 'Distribute the entire dist\SIF Viewer folder, including _internal.'
} finally {
    $env:Path = $originalPath
    Pop-Location
}
