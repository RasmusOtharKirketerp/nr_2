#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy newsreader Docker image to AWS EC2 instance

.DESCRIPTION
    Automates the complete deployment process:
    1. Builds Docker image locally
    2. Exports image to tar file
    3. Uploads tar to EC2 instance via SCP
    4. Loads and runs container on remote instance
    5. Verifies deployment success

.PARAMETER InstanceIP
    Public IP address of the EC2 instance
    
.PARAMETER KeyPath
    Path to the SSH private key (.pem file)
    
.PARAMETER Tag
    Docker image tag (default: latest)
    
.PARAMETER Port
    Host port to expose the service on (default: 8000)
    
.PARAMETER SecretKey
    Flask secret key for the application
    
.PARAMETER Force
    Force rebuild and redeploy even if image exists

.EXAMPLE
    .\scripts\deploy.ps1 -InstanceIP "3.79.167.205" -KeyPath "C:\Users\rasmu\Downloads\ls.pem"
    
.EXAMPLE
    .\scripts\deploy.ps1 -InstanceIP "3.79.167.205" -KeyPath ".\ls.pem" -Port 80 -Force
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$InstanceIP,
    
    [Parameter(Mandatory = $true)]
    [string]$KeyPath,
    
    [string]$Tag = "latest",
    [int]$Port = 8000,
    [string]$SecretKey = "please-change-me-in-production",
    [switch]$Force
)

# Configuration
$ImageName = "newsreader"
$ContainerName = "newsreader-stack"
$RemoteUser = "ubuntu"
$TarFile = "newsreader-$Tag.tar"

# Colors for output
$Red = "`e[31m"
$Green = "`e[32m"
$Yellow = "`e[33m"
$Blue = "`e[34m"
$Reset = "`e[0m"

function Write-Status {
    param([string]$Message, [string]$Color = $Blue)
    Write-Host "$Color[DEPLOY]$Reset $Message"
}

function Write-Error {
    param([string]$Message)
    Write-Host "$Red[ERROR]$Reset $Message"
}

function Write-Success {
    param([string]$Message)
    Write-Host "$Green[SUCCESS]$Reset $Message"
}

function Write-Warning {
    param([string]$Message)
    Write-Host "$Yellow[WARNING]$Reset $Message"
}

# Validate prerequisites
Write-Status "Validating prerequisites..."

if (-not (Test-Path $KeyPath)) {
    Write-Error "SSH key not found at: $KeyPath"
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not found. Please install Docker Desktop."
    exit 1
}

if (-not (Get-Command scp -ErrorAction SilentlyContinue)) {
    Write-Error "SCP not found. Please install OpenSSH client."
    exit 1
}

# Check if we need to build
$ImageExists = docker images --format "table {{.Repository}}:{{.Tag}}" | Select-String "$ImageName`:$Tag"
if ($ImageExists -and -not $Force) {
    Write-Status "Image $ImageName`:$Tag already exists. Use -Force to rebuild."
} else {
    Write-Status "Building Docker image $ImageName`:$Tag..."
    docker build -t "$ImageName`:$Tag" -f docker/Dockerfile .
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed"
        exit 1
    }
    Write-Success "Docker image built successfully"
}

# Export image
Write-Status "Exporting Docker image to $TarFile..."
if (Test-Path $TarFile) {
    Remove-Item $TarFile -Force
}

docker save "$ImageName`:$Tag" -o $TarFile
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to export Docker image"
    exit 1
}

$TarSize = [math]::Round((Get-Item $TarFile).Length / 1MB, 1)
Write-Success "Image exported ($TarSize MB)"

# Upload to EC2
Write-Status "Uploading $TarFile to $InstanceIP..."
scp -i $KeyPath -o StrictHostKeyChecking=no $TarFile "${RemoteUser}@${InstanceIP}:/home/$RemoteUser/"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to upload image to EC2"
    exit 1
}
Write-Success "Image uploaded successfully"

# Upload data files if they exist
Write-Status "Uploading configuration files..."
if (Test-Path "data/sources.json") {
    scp -i $KeyPath -o StrictHostKeyChecking=no "data/sources.json" "${RemoteUser}@${InstanceIP}:/home/$RemoteUser/"
}
if (Test-Path "data/geo_places.json") {
    scp -i $KeyPath -o StrictHostKeyChecking=no "data/geo_places.json" "${RemoteUser}@${InstanceIP}:/home/$RemoteUser/"
}

# Remote deployment script
$RemoteScript = @"
#!/bin/bash
set -e

echo "[REMOTE] Loading Docker image..."
docker load -i /home/$RemoteUser/$TarFile

echo "[REMOTE] Stopping existing container (if any)..."
docker rm -f $ContainerName 2>/dev/null || true

echo "[REMOTE] Setting up host directories..."
sudo mkdir -p /home/$RemoteUser/data /home/$RemoteUser/config /home/$RemoteUser/var

# Move uploaded config files to data directory
if [ -f /home/$RemoteUser/sources.json ]; then
    sudo mv /home/$RemoteUser/sources.json /home/$RemoteUser/data/
fi
if [ -f /home/$RemoteUser/geo_places.json ]; then
    sudo mv /home/$RemoteUser/geo_places.json /home/$RemoteUser/data/
fi

# Get container user ID for proper ownership
CONTAINER_UID=`$(docker run --rm --entrypoint /usr/bin/id $ImageName`:$Tag | cut -d'(' -f1 | cut -d'=' -f2)
CONTAINER_GID=`$(docker run --rm --entrypoint /usr/bin/id $ImageName`:$Tag | cut -d'(' -f2 | cut -d'=' -f2)

echo "[REMOTE] Setting directory ownership to `$CONTAINER_UID:`$CONTAINER_GID..."
sudo chown -R `$CONTAINER_UID:`$CONTAINER_GID /home/$RemoteUser/data /home/$RemoteUser/config /home/$RemoteUser/var

echo "[REMOTE] Starting new container..."
docker run -d --name $ContainerName \
  -p $Port`:8000 \
  -v /home/$RemoteUser/data:/app/data \
  -v /home/$RemoteUser/config:/app/config \
  -v /home/$RemoteUser/var:/var/newsreader \
  -e FLASK_SECRET_KEY="$SecretKey" \
  --restart unless-stopped \
  $ImageName`:$Tag fetch-then-web

echo "[REMOTE] Waiting for container to start..."
sleep 5

echo "[REMOTE] Container status:"
docker ps --filter name=$ContainerName --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo "[REMOTE] Recent logs:"
docker logs --tail 10 $ContainerName

echo "[REMOTE] Cleanup..."
rm -f /home/$RemoteUser/$TarFile

echo "[REMOTE] Deployment complete!"
echo "[REMOTE] Service should be available at: http://$InstanceIP`:$Port"
"@

# Execute remote deployment
Write-Status "Executing remote deployment on $InstanceIP..."
# Convert Windows line endings to Unix for remote execution
$RemoteScriptUnix = $RemoteScript -replace "`r`n", "`n" -replace "`r", "`n"
$RemoteScriptUnix | ssh -i $KeyPath -o StrictHostKeyChecking=no "${RemoteUser}@${InstanceIP}" 'bash -s'

if ($LASTEXITCODE -ne 0) {
    Write-Error "Remote deployment failed"
    exit 1
}

# Cleanup local tar file
Write-Status "Cleaning up local tar file..."
Remove-Item $TarFile -Force

# Final verification
Write-Status "Verifying deployment..."
try {
    $Response = Invoke-WebRequest -Uri "http://$InstanceIP`:$Port" -TimeoutSec 10 -UseBasicParsing
    if ($Response.StatusCode -eq 200) {
        Write-Success "Deployment successful! Service is responding at http://$InstanceIP`:$Port"
    } else {
        Write-Warning "Service deployed but returned status code: $($Response.StatusCode)"
    }
} catch {
    Write-Warning "Service deployed but health check failed: $($_.Exception.Message)"
    Write-Status "You may need to open port $Port in the EC2 security group"
}

Write-Success "Deployment process completed!"