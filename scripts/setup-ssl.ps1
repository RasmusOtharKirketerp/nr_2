#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Set up SSL certificate and domain for othar.dk

.DESCRIPTION
    Uploads and runs SSL setup script on EC2 instance

.PARAMETER InstanceIP
    EC2 instance IP address

.PARAMETER KeyPath  
    Path to SSH private key

.PARAMETER Domain
    Domain name to configure (default: othar.dk)
#>

param(
    [string]$InstanceIP = "63.179.143.196",
    [string]$KeyPath = "data\aws_ec2_rex.pem", 
    [string]$Domain = "othar.dk"
)

Write-Host "=== Setting up SSL for $Domain ===" -ForegroundColor Green

# Upload SSL setup script
Write-Host "Uploading SSL setup script..." -ForegroundColor Yellow
scp -i $KeyPath -o StrictHostKeyChecking=no "scripts\setup-ssl.sh" "ubuntu@${InstanceIP}:/home/ubuntu/"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to upload SSL script"
    exit 1
}

# Make script executable and run it
Write-Host "Running SSL setup on remote server..." -ForegroundColor Yellow
ssh -i $KeyPath -o StrictHostKeyChecking=no "ubuntu@$InstanceIP" "chmod +x setup-ssl.sh && ./setup-ssl.sh"

if ($LASTEXITCODE -eq 0) {
    Write-Host "SSL setup completed successfully!" -ForegroundColor Green
    Write-Host "Your site should be available at: https://$Domain" -ForegroundColor Cyan
} else {
    Write-Error "SSL setup failed. Check the output above for details."
}