#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Manage remote EC2 containers

.DESCRIPTION
    Utility script for common container management tasks on EC2

.PARAMETER InstanceIP
    Public IP address of the EC2 instance
    
.PARAMETER KeyPath
    Path to the SSH private key (.pem file)
    
.PARAMETER Action
    Action to perform: status, logs, restart, stop, shell

.PARAMETER Lines
    Number of log lines to show (for logs action)

.EXAMPLE
    .\scripts\manage.ps1 -InstanceIP "3.79.167.205" -KeyPath ".\ls.pem" -Action status
    
.EXAMPLE
    .\scripts\manage.ps1 -InstanceIP "3.79.167.205" -KeyPath ".\ls.pem" -Action logs -Lines 50
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$InstanceIP,
    
    [Parameter(Mandatory = $true)]
    [string]$KeyPath,
    
    [Parameter(Mandatory = $true)]
    [ValidateSet("status", "logs", "restart", "stop", "shell")]
    [string]$Action,
    
    [int]$Lines = 20
)

$RemoteUser = "ubuntu"
$ContainerName = "newsreader-stack"

function Invoke-RemoteCommand {
    param([string]$Command)
    ssh -i $KeyPath -o StrictHostKeyChecking=no "${RemoteUser}@${InstanceIP}" $Command
}

switch ($Action) {
    "status" {
        Write-Host "Container Status:" -ForegroundColor Cyan
        Invoke-RemoteCommand "docker ps --filter name=$ContainerName --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
        
        Write-Host "`nSystem Resources:" -ForegroundColor Cyan
        Invoke-RemoteCommand "free -h && df -h /"
    }
    
    "logs" {
        Write-Host "Container Logs (last $Lines lines):" -ForegroundColor Cyan
        Invoke-RemoteCommand "docker logs --tail $Lines $ContainerName"
    }
    
    "restart" {
        Write-Host "Restarting container..." -ForegroundColor Yellow
        Invoke-RemoteCommand "docker restart $ContainerName"
        Start-Sleep 3
        Invoke-RemoteCommand "docker ps --filter name=$ContainerName"
    }
    
    "stop" {
        Write-Host "Stopping container..." -ForegroundColor Red
        Invoke-RemoteCommand "docker stop $ContainerName"
    }
    
    "shell" {
        Write-Host "Opening shell in container..." -ForegroundColor Green
        ssh -i $KeyPath -t "${RemoteUser}@${InstanceIP}" "docker exec -it $ContainerName /bin/sh"
    }
}