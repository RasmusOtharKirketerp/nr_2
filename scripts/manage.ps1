#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Manage remote EC2 containers

.DESCRIPTION
    Utility script for common container management tasks on EC2

.PARAMETER InstanceIP
    Public IP address of the EC2 instance (default: 63.179.143.196)
    
.PARAMETER KeyPath
    Path to the SSH private key (.pem file) (default: data\\aws_ec2_rex.pem)
    
.PARAMETER Action
    Action to perform: status, logs, restart, stop, shell, health

.PARAMETER Lines
    Number of log lines to show (for logs action)

.PARAMETER Port
    Host port serving HTTP traffic (default: 80)

.EXAMPLE
    .\scripts\manage.ps1 -Action status          # uses defaults (IP 63.179.143.196, key data\aws_ec2_rex.pem)
    
.EXAMPLE
    .\scripts\manage.ps1 -Action health -Port 80 # curl http://127.0.0.1:8000 from EC2 and host URL
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$InstanceIP = "63.179.143.196",
    
    [Parameter(Mandatory = $false)]
    [string]$KeyPath = "data\\aws_ec2_rex.pem",
    
    [Parameter(Mandatory = $true)]
    [ValidateSet("status", "logs", "restart", "stop", "shell", "health")]
    [string]$Action,
    
    [int]$Lines = 20,
    [int]$Port = 80
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

    "health" {
        Write-Host "Running remote health check..." -ForegroundColor Cyan
    Invoke-RemoteCommand "curl -fsS --max-time 5 http://127.0.0.1:$Port/ >/dev/null && echo '[HEALTH] Container responded on localhost:$Port'"
    Invoke-RemoteCommand "curl -I --max-time 5 http://127.0.0.1:$Port/ | head -n 1"
    Invoke-RemoteCommand "curl -I --max-time 5 http://${InstanceIP}:$Port/ | head -n 1 || true"
        Invoke-RemoteCommand "docker ps --filter name=$ContainerName --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
    }
}