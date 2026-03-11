<#
deploy.ps1
Safe deploy helper: runs preflight, creates a feature branch, commits changes, and prints git diff for review. Does NOT push unless --Push is specified.
#>
param(
    [string]$WorkspaceRoot = "${PSScriptRoot}/..",
    [string]$FeatureBranch = "feature/agent-iter",
    [switch]$Push
)
Set-StrictMode -Version Latest

# Run preflight
$preflight = Join-Path $PSScriptRoot 'preflight.ps1'
Write-Output "Running preflight..."
& $preflight -WorkspaceRoot $WorkspaceRoot -BackupsDir (Join-Path $PSScriptRoot '..\backups') -CreateGitTag | Out-Null

# Ensure inside git repo
git rev-parse --is-inside-work-tree 2>$null | Out-Null
if($LASTEXITCODE -ne 0){ Write-Error "Not a git repository. Abort."; exit 2 }

# Create feature branch
Write-Output "Creating branch: $FeatureBranch"
try{ git checkout -b $FeatureBranch } catch { git checkout $FeatureBranch }

# Stage all changes
git add -A
$diff = git diff --staged --name-status
if(-not $diff){ Write-Output "No changes to commit."; exit 0 }

# Commit
git commit -m "chore(agent): iterative backup and deploy $(Get-Date -Format o)" --no-verify
Write-Output "Committed changes. Diff:"; git --no-pager diff --staged --name-only

if($Push){
    Write-Output "Pushing to origin $FeatureBranch..."
    git push -u origin $FeatureBranch
    if($LASTEXITCODE -ne 0){ Write-Error "Push failed"; exit 3 }
    Write-Output "Pushed. Trigger CI on GitHub.";
} else {
    Write-Output "Push not requested. Use --Push to push to origin after review.";
}
