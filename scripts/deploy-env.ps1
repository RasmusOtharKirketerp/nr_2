#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Enhanced deploy script with configuration file support

.DESCRIPTION
    Deploys using environment-specific configuration from deploy-config.json

.PARAMETER Environment
    Environment name from config file (production, staging, development)
    
.PARAMETER ConfigPath
    Path to configuration file (default: scripts/deploy-config.json)

.EXAMPLE
    .\scripts\deploy-env.ps1 -Environment production
    
.EXAMPLE
    .\scripts\deploy-env.ps1 -Environment staging -ConfigPath .\my-config.json
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Environment,
    
    [string]$ConfigPath = "scripts/deploy-config.json"
)

# Load configuration
if (-not (Test-Path $ConfigPath)) {
    Write-Host "Configuration file not found: $ConfigPath" -ForegroundColor Red
    Write-Host "Copy scripts/deploy-config.example.json to $ConfigPath and customize it" -ForegroundColor Yellow
    exit 1
}

try {
    $Config = Get-Content $ConfigPath | ConvertFrom-Json
    $EnvConfig = $Config.environments.$Environment
    
    if (-not $EnvConfig) {
        Write-Host "Environment '$Environment' not found in $ConfigPath" -ForegroundColor Red
        Write-Host "Available environments: $($Config.environments.PSObject.Properties.Name -join ', ')" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "Failed to parse configuration file: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Call main deploy script with environment-specific parameters
$DeployArgs = @{
    InstanceIP = $EnvConfig.instanceIP
    KeyPath = $EnvConfig.keyPath
    Port = $EnvConfig.port
    SecretKey = $EnvConfig.secretKey
    Tag = $EnvConfig.tag
}

Write-Host "Deploying to $Environment environment..." -ForegroundColor Cyan
Write-Host "Instance: $($EnvConfig.instanceIP):$($EnvConfig.port)" -ForegroundColor Gray

& .\scripts\deploy.ps1 @DeployArgs