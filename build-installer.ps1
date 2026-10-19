param(
    [string]$Python = "$PSScriptRoot\.venv\Scripts\python.exe",
    [string]$Compiler = '',
    [switch]$SkipAppBuild
)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not $Compiler) {
        $compilerCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        $candidates = @(
            (Join-Path $PSScriptRoot '.tools\innosetup\ISCC.exe'),
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
        )
        if ($compilerCommand) { $candidates += $compilerCommand.Source }
        $Compiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $Compiler -or -not (Test-Path -LiteralPath $Compiler)) {
        throw 'Inno Setup compiler not found. Install Inno Setup 6.3+ from https://jrsoftware.org/isdl.php or pass -Compiler with the full ISCC.exe path.'
    }
    if (-not $SkipAppBuild) {
        & (Join-Path $PSScriptRoot 'build.ps1') -Python $Python
    }
    if (-not (Test-Path -LiteralPath 'dist\SIF Viewer\SIF Viewer.exe')) {
        throw 'Application build is missing. Run build.ps1 first or omit -SkipAppBuild.'
    }
    # Keep the installer version in sync with the app's existing entry point.
    $versionMatch = [regex]::Match((Get-Content -LiteralPath 'main.py' -Raw), 'setApplicationVersion\("([0-9]+\.[0-9]+\.[0-9]+)"\)')
    if (-not $versionMatch.Success) { throw 'Application version could not be read from main.py.' }
    $appVersion = $versionMatch.Groups[1].Value
    & $Python (Join-Path $PSScriptRoot 'installer\collect_licenses.py')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency license collection failed.' }
    $innoLicense = Join-Path (Split-Path -Parent $Compiler) 'license.txt'
    if (-not (Test-Path -LiteralPath $innoLicense)) { throw 'Inno Setup license.txt is missing.' }
    New-Item -ItemType Directory -Path 'installer\licenses\InnoSetup' -Force | Out-Null
    Copy-Item -LiteralPath $innoLicense -Destination 'installer\licenses\InnoSetup\LICENSE.txt' -Force
    if (-not (Test-Path -LiteralPath 'installer\licenses\QtOpenSource\LGPL-3.0-only.txt')) {
        throw 'Qt open-source license texts are missing from installer/licenses/QtOpenSource.'
    }
    & $Compiler '/Q' "/DAppVersion=$appVersion" (Join-Path $PSScriptRoot 'installer\sif-viewer.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
    $setupPath = Join-Path $PSScriptRoot "dist\installer\SIF-Viewer-$appVersion-Setup-x64.exe"
    $checksum = (Get-FileHash -LiteralPath $setupPath -Algorithm SHA256).Hash.ToLowerInvariant()
    "$checksum  $([IO.Path]::GetFileName($setupPath))" | Set-Content -LiteralPath "$setupPath.sha256" -Encoding ascii
    Write-Host "Installer: $setupPath"
    Write-Host 'Share this one Setup EXE. Recipients do not need Python or Inno Setup.'
} finally {
    Pop-Location
}
