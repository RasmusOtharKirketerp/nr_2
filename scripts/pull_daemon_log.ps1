#!/usr/bin/env pwsh
<#!
.SYNOPSIS
    Display or follow the Newsreader daemon log.
.DESCRIPTION
    Resolves the daemon log path using NEWSREADER_DAEMON_LOG when set (otherwise
    defaults to var\\logs\\news_daemon.log) and streams the most recent entries.
    Run from anywhere; the script locates the repository root automatically.

.PARAMETER Lines
    How many trailing log lines to show (default: 200).

.PARAMETER Follow
    Continue streaming new log entries (equivalent to tail -f).

.EXAMPLE
    .\scripts\pull_daemon_log.ps1

.EXAMPLE
    .\scripts\pull_daemon_log.ps1 -Lines 500 -Follow
#>
param(
    [int]$Lines = 200,
    [switch]$Follow
)

${ErrorActionPreference} = 'Stop'

function Write-Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Err([string]$Message)  { Write-Host "[FAIL] $Message" -ForegroundColor Red }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir

if (-not (Test-Path (Join-Path $repoRoot 'pyproject.toml'))) {
    Write-Err 'Repository root not found. Run this script from within the repo.'
    exit 1
}

$logPath = $env:NEWSREADER_DAEMON_LOG
if ([string]::IsNullOrWhiteSpace($logPath)) {
    $logPath = Join-Path $repoRoot 'var\\logs\\news_daemon.log'
} elseif (-not [System.IO.Path]::IsPathRooted($logPath)) {
    $logPath = Join-Path $repoRoot $logPath
}

try {
    $resolvedLogPath = [System.IO.Path]::GetFullPath($logPath)
} catch {
    Write-Err "Failed to resolve log path '$logPath': $_"
    exit 1
}

if (-not (Test-Path $resolvedLogPath)) {
    Write-Warn "Log file not found at $resolvedLogPath"
    Write-Warn 'Start the daemon (e.g. .\\run.bat daemon) and try again.'
    exit 2
}

Write-Info "Streaming daemon log from $resolvedLogPath"
Write-Host ''

$commonParams = @{ Path = $resolvedLogPath; Tail = $Lines }
if ($Follow) {
    Get-Content @commonParams -Wait
} else {
    Get-Content @commonParams
}
