<#
rollback.ps1
Restore workspace from the latest backup ZIP in backups/ or from a specified backup file. Safe by default: supports --WhatIf to preview.
#>
param(
    [string]$BackupsDir = "${PSScriptRoot}/../backups",
    [string]$BackupFile = $null,
    [switch]$WhatIf
)
Set-StrictMode -Version Latest

if(-not $BackupFile){
    $files = Get-ChildItem -Path $BackupsDir -Filter 'backup-*.zip' | Sort-Object LastWriteTime -Descending
    if(-not $files){ Write-Error "No backups found in $BackupsDir"; exit 1 }
    $BackupFile = $files[0].FullName
}
Write-Output "Selected backup: $BackupFile"
if($WhatIf){ Write-Output "WhatIf mode: would extract to workspace (preview only)"; exit 0 }

# Extract to workspace root
$workspaceRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
try{
    # Remove current workspace content except backups and scripts (be careful)
    Get-ChildItem -Path $workspaceRoot -Force | Where-Object { $_.FullName -notlike (Join-Path $BackupsDir '*') -and $_.FullName -notlike (Join-Path $PSScriptRoot '*') } | Remove-Item -Recurse -Force -ErrorAction Stop
    Expand-Archive -Path $BackupFile -DestinationPath $workspaceRoot -Force
    Write-Output "Restored backup to $workspaceRoot"
} catch { Write-Error "Rollback failed: $_"; exit 2 }
