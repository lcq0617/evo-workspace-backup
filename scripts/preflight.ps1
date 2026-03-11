<#
preflight.ps1
Creates a timestamped ZIP backup of the workspace, computes SHA256, optionally creates a git backup branch/tag and prints a summary manifest.
This script is safe (read-only except for writing the backup ZIP and optional git tag/branch). It does NOT push.
#>
param(
    [string]$WorkspaceRoot = "${PSScriptRoot}/..",
    [string]$BackupsDir = "${PSScriptRoot}/../backups",
    [switch]$CreateGitTag
)

Set-StrictMode -Version Latest
$ts = (Get-Date).ToString('yyyyMMdd-HHmmss')
$backupName = "backup-$ts.zip"
$backupPath = Join-Path -Path (Resolve-Path $BackupsDir).Path -ChildPath $backupName

# Ensure backups dir exists
if(-not (Test-Path -LiteralPath $BackupsDir)){
    New-Item -ItemType Directory -Path $BackupsDir -Force | Out-Null
}

Write-Output "WorkspaceRoot: $WorkspaceRoot"
Write-Output "BackupPath: $backupPath"

# Create zip (uses Compress-Archive)
try{
    Compress-Archive -Path (Join-Path $WorkspaceRoot '*') -DestinationPath $backupPath -Force -ErrorAction Stop
    Write-Output "Backup created: $backupPath"
} catch {
    Write-Error "Failed to create backup: $_"
    exit 1
}

# Compute SHA256
try{
    $h = Get-FileHash -Path $backupPath -Algorithm SHA256
    Write-Output "SHA256: $($h.Hash)"
} catch{
    Write-Warning "Could not compute SHA256: $_"
}

# Create manifest
$manifest = [PSCustomObject]@{
    Timestamp = $ts
    BackupPath = $backupPath
    SHA256 = ($h.Hash -as [string])
    Host = $env:COMPUTERNAME
    User = $env:USERNAME
}
$manifestPath = [System.IO.Path]::ChangeExtension($backupPath, '.json')
$manifest | ConvertTo-Json -Depth 5 | Out-File -FilePath $manifestPath -Encoding UTF8
Write-Output "Manifest written: $manifestPath"

# Optional: create a local git tag/branch (no push)
if($CreateGitTag){
    try{
        $tagName = "backup/$ts"
        Write-Output "Creating git tag: $tagName"
        git rev-parse --is-inside-work-tree 2>$null | Out-Null
        if($LASTEXITCODE -ne 0){ Write-Warning "Not a git repository - skipping tag creation" } else {
            git tag -a $tagName -m "Backup $ts" || Write-Warning "git tag returned non-zero"
            Write-Output "Created local tag: $tagName"
        }
    } catch { Write-Warning "Git tag creation failed: $_" }
}

Write-Output "Preflight complete. Backup: $backupPath; Manifest: $manifestPath"
