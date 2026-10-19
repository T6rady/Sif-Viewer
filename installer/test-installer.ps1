param(
    [string]$Compiler = "$PSScriptRoot\..\.tools\innosetup\ISCC.exe"
)

# End-to-end smoke test with unique names, shortcuts and registry identity.
# It never installs over the user's real SIF Viewer or removes their shortcuts.
$ErrorActionPreference = 'Stop'
$projectPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$testId = [guid]::NewGuid().ToString('N')
$testName = "SIF Viewer Installer Test $testId"
# Keep below Inno Setup's uninstall-key truncation threshold.
$testAppId = "ORI.SIFTest.$testId"
$testPath = [IO.Path]::GetFullPath((Join-Path $projectPath "test-artifacts\installer-$testId"))
$installPath = Join-Path $testPath 'installed'
if (-not $testPath.StartsWith($projectPath.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Test files must remain in this project.'
}
New-Item -ItemType Directory -Path $testPath -Force | Out-Null
$versionMatch = [regex]::Match((Get-Content -LiteralPath (Join-Path $projectPath 'main.py') -Raw), 'setApplicationVersion\("([0-9]+\.[0-9]+\.[0-9]+)"\)')
if (-not $versionMatch.Success) { throw 'Application version is missing.' }
$appVersion = $versionMatch.Groups[1].Value
& $Compiler '/Q' "/DAppName=$testName" "/DAppId=$testAppId" "/DAppVersion=$appVersion" "/O$testPath" '/FInstaller-Test' (Join-Path $PSScriptRoot 'sif-viewer.iss')
if ($LASTEXITCODE -ne 0) { throw 'Test installer compilation failed.' }
# A fresh Windows profile may not have created its Desktop directory yet.
# Resolve configured known-folder paths without requiring them to exist first;
# Setup creates the destination when it writes the shortcut.
$desktopDirectory = [Environment]::GetFolderPath('DesktopDirectory', [Environment+SpecialFolderOption]::DoNotVerify)
$programsDirectory = [Environment]::GetFolderPath('Programs', [Environment+SpecialFolderOption]::DoNotVerify)
if (-not $desktopDirectory -or -not $programsDirectory) {
    throw 'Windows did not provide configured Desktop and Programs folder paths.'
}
$desktopLink = Join-Path $desktopDirectory "$testName.lnk"
$startFolder = Join-Path $programsDirectory $testName
$startLink = Join-Path $startFolder "$testName.lnk"
$registryPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\${testAppId}_is1"
$progIdPath = "HKCU:\Software\Classes\${testAppId}.SIF"
$capabilitiesPath = "HKCU:\Software\$testAppId\Capabilities"
$registeredAppsPath = 'HKCU:\Software\RegisteredApplications'
$openWithPath = 'HKCU:\Software\Classes\.sif\OpenWithProgids'

function Get-SifDefaultSnapshot {
    $snapshot = [ordered]@{}
    foreach ($subkey in @('Software\Classes\.sif', 'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.sif\UserChoice')) {
        $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($subkey)
        try {
            $values = [ordered]@{}
            foreach ($name in @('', 'ProgId', 'Hash')) {
                $values[$name] = if ($key) { $key.GetValue($name) } else { $null }
            }
            $snapshot[$subkey] = $values
        } finally { if ($key) { $key.Dispose() } }
    }
    return ($snapshot | ConvertTo-Json -Compress -Depth 4)
}
$sifDefaultBefore = Get-SifDefaultSnapshot
if ((Test-Path -LiteralPath $desktopLink) -or (Test-Path -LiteralPath $startFolder) -or (Test-Path -LiteralPath $registryPath)) {
    throw 'A test identity already exists; stopping without changing it.'
}
$installed = $false
$appProcess = $null
try {
    # Install and repeat once to exercise an in-place reinstall/upgrade.
    foreach ($attempt in 1..2) {
        $parameters = @('/SP-', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/TASKS=desktopicon',
                        ('/DIR="' + $installPath + '"'), ('/GROUP="' + $testName + '"'),
                        ('/LOG="' + (Join-Path $testPath "install-$attempt.log") + '"'))
        $process = Start-Process -FilePath (Join-Path $testPath 'Installer-Test.exe') -ArgumentList $parameters -WindowStyle Hidden -PassThru -Wait
        if ($process.ExitCode -ne 0) { throw "Install attempt $attempt failed: $($process.ExitCode)" }
        $installed = $true
    }
    $appExe = Join-Path $installPath 'SIF Viewer.exe'
    foreach ($file in @($appExe, (Join-Path $installPath '_internal\assets\app.ico'), $desktopLink, $startLink)) {
        if (-not (Test-Path -LiteralPath $file)) { throw "Installed file or shortcut missing: $file" }
    }
    $shell = New-Object -ComObject WScript.Shell
    foreach ($link in @($desktopLink, $startLink)) {
        if ($shell.CreateShortcut($link).TargetPath -ne $appExe) { throw "Incorrect shortcut target: $link" }
    }
    $entry = Get-ItemProperty -LiteralPath $registryPath
    if ($entry.DisplayName -ne $testName -or $entry.DisplayVersion -ne $appVersion) {
        throw 'Uninstall registration is incorrect.'
    }
    $command = (Get-Item -LiteralPath "$progIdPath\shell\open\command").GetValue('')
    if ($command -ne ('"' + $appExe + '" "%1"')) { throw 'SIF open command is not quoted correctly.' }
    $capability = (Get-Item -LiteralPath "$capabilitiesPath\FileAssociations").GetValue('.sif')
    if ($capability -ne "${testAppId}.SIF") { throw 'SIF capability registration is incorrect.' }
    if ((Get-Item -LiteralPath $registeredAppsPath).GetValue($testName) -ne "Software\$testAppId\Capabilities") {
        throw 'Default apps registration is incorrect.'
    }
    if ((Get-Item -LiteralPath $openWithPath).GetValueNames() -notcontains "${testAppId}.SIF") {
        throw 'Open With registration is missing.'
    }
    if ((Get-SifDefaultSnapshot) -ne $sifDefaultBefore) { throw 'Setup changed the existing SIF default.' }
    $oldQtPlatform = $env:QT_QPA_PLATFORM
    try {
        $env:QT_QPA_PLATFORM = 'offscreen'
        $appProcess = Start-Process -FilePath $appExe -WorkingDirectory $installPath -WindowStyle Hidden -PassThru
        Start-Sleep -Milliseconds 1500
        $appProcess.Refresh()
        if ($appProcess.HasExited) { throw "Installed app exited on startup: $($appProcess.ExitCode)" }
        $appProcess.Kill()
        $appProcess.WaitForExit()
        $appProcess = $null
    } finally {
        $env:QT_QPA_PLATFORM = $oldQtPlatform
    }
    # A user-created SIF in the app directory must survive uninstall.
    $userFile = Join-Path $installPath 'keep-user-file.sif'
    $userText = "SF=User-created test data`r`n"
    [IO.File]::WriteAllText($userFile, $userText)
    $uninstaller = Join-Path $installPath 'unins000.exe'
    $process = Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
        ('/LOG="' + (Join-Path $testPath 'uninstall.log') + '"') -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -ne 0) { throw "Uninstall failed: $($process.ExitCode)" }
    $installed = $false
    foreach ($removed in @($appExe, $desktopLink, $startLink, $registryPath, $progIdPath, $capabilitiesPath)) {
        if (Test-Path -LiteralPath $removed) { throw "Uninstall left a registered item: $removed" }
    }
    if ((Get-Item -LiteralPath $registeredAppsPath).GetValue($testName)) { throw 'Default apps entry was not removed.' }
    if (Test-Path -LiteralPath $openWithPath) {
        if ((Get-Item -LiteralPath $openWithPath).GetValueNames() -contains "${testAppId}.SIF") {
            throw 'Open With entry was not removed.'
        }
    }
    if ((Get-SifDefaultSnapshot) -ne $sifDefaultBefore) { throw 'Uninstall changed the existing SIF default.' }
    if ([IO.File]::ReadAllText($userFile) -ne $userText) { throw 'User data was altered during uninstall.' }
    Write-Host 'PASS: install, reinstall, app startup, shortcuts, uninstall registration, SIF handler/Default apps registration and cleanup, existing default preservation, and user SIF preservation.'
    Write-Host "Test logs: $testPath"
} finally {
    if ($appProcess -and -not $appProcess.HasExited) { $appProcess.Kill(); $appProcess.WaitForExit() }
    $uninstaller = Join-Path $installPath 'unins000.exe'
    if ($installed -and (Test-Path -LiteralPath $uninstaller)) {
        Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -WindowStyle Hidden -Wait
    }
}
