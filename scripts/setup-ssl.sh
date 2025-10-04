#!/bin/bash
# SSL Setup Script for othar.dk
# Run this on the EC2 instance after DNS is updated

set -e

echo "=== SSL Setup for othar.dk ==="

# Update system
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Nginx
echo "Installing Nginx..."
sudo apt install nginx -y

# Install Certbot
echo "Installing Certbot..."
sudo apt install certbot python3-certbot-nginx -y

# Stop Docker container temporarily
echo "Stopping newsreader container..."
sudo docker stop newsreader-stack || true

# Configure Nginx for initial setup
echo "Configuring Nginx..."
sudo tee /etc/nginx/sites-available/othar.dk > /dev/null <<EOF
server {
    listen 80;
    server_name othar.dk www.othar.dk;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/othar.dk /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx config
sudo nginx -t

# Start Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Get SSL certificate
echo "Obtaining SSL certificate..."
sudo certbot --nginx -d othar.dk -d www.othar.dk --non-interactive --agree-tos --email admin@othar.dk

# Start newsreader container again
echo "Starting newsreader container..."
sudo docker start newsreader-stack

echo "=== SSL Setup Complete! ==="
echo "Your site should now be available at:"
echo "  https://othar.dk"
echo "  https://www.othar.dk"