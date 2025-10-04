<#!
.SYNOPSIS
    Provision a reliable development environment for the Newsreader project.
.DESCRIPTION
    Creates (or recreates) a Python 3.11 virtual environment, installs project dependencies,
    downloads required spaCy & NLTK models, and performs a quick import sanity check.

    Run from repository root:
        powershell -ExecutionPolicy Bypass -File .\scripts\setup_env.ps1

.PARAMETER Force
    If set, removes any existing .venv directory before creating a new one.

.PARAMETER Python
    Explicit path or launcher spec for Python 3.11 (default: 'py -3.11').

.EXAMPLE
    .\scripts\setup_env.ps1

.EXAMPLE
    .\scripts\setup_env.ps1 -Force

.EXAMPLE
    .\scripts\setup_env.ps1 -Python "C:\\Python311\\python.exe"
#>
param(
    [switch]$Force,
    [string]$Python = 'py -3.11'
)

${ErrorActionPreference} = 'Stop'

function Write-Step($msg) { Write-Host "[STEP] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[FAIL] $msg" -ForegroundColor Red }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

if (-not (Test-Path 'pyproject.toml')) {
    Write-Err 'Run this script from repository root (pyproject.toml not found).'
    exit 1
}

Write-Step 'Ensuring Python 3.11 availability'
try {
    $pyVer = & $Python -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")'
} catch {
    Write-Err "Failed to execute specified Python interpreter: $Python"
    exit 1
}
if ($pyVer -ne '3.11') {
    Write-Err "Python 3.11 required, but got $pyVer from '$Python'"
    exit 1
}

$venvDir = Join-Path $repoRoot '.venv'
if ($Force -and (Test-Path $venvDir)) {
    Write-Step 'Removing existing virtual environment (.venv)'
    Remove-Item -Recurse -Force $venvDir
}

if (Test-Path $venvDir) {
    Write-Warn '.venv already exists. Use -Force to recreate or delete manually.'
} else {
    Write-Step 'Creating Python 3.11 virtual environment (.venv)'
    & $Python -m venv .venv
}

$activate = Join-Path $venvDir 'Scripts/Activate.ps1'
if (-not (Test-Path $activate)) {
    Write-Err 'Activation script not found; virtual environment creation failed.'
    exit 1
}

Write-Step 'Activating virtual environment'
. $activate

Write-Step 'Upgrading pip/build tooling'
python -m pip install --upgrade pip setuptools wheel > $null

Write-Step 'Installing project dependencies'
python -m pip install -r requirements.txt

Write-Step 'Downloading spaCy models (da_core_news_lg, en_core_web_sm)'
python -m spacy download da_core_news_lg
python -m spacy download en_core_web_sm

Write-Step 'Downloading NLTK corpora (punkt, stopwords)'
python -m nltk.downloader punkt stopwords

Write-Step 'Sanity check: import critical packages'
$sanity2 = @'
import sys, importlib
print('Python:', sys.version)
for name in ['spacy','blis','nltk','requests']:
    try:
        mod = importlib.import_module(name)
        print(f"{name}: OK (version=" + getattr(mod,'__version__','n/a') + ")")
    except Exception as e:
        print(f"{name}: FAILED -> {e}")
'@
$tmp2 = Join-Path $env:TEMP ('nr_env_sanity2_' + [System.Guid]::NewGuid().ToString() + '.py')
Set-Content -Path $tmp2 -Value $sanity2 -Encoding UTF8
python $tmp2
Remove-Item $tmp2 -ErrorAction SilentlyContinue

Write-Step 'Done.'
Write-Ok 'Environment ready. Activate with:  .\.venv\Scripts\Activate.ps1'
