#!/bin/bash
# Production deployment script for Launch the Nukes

set -e

echo "Deploying Launch the Nukes..."

# Get current directory and user
PROJECT_DIR=$(pwd)
CURRENT_USER=$(whoami)

# Check services
redis-cli ping > /dev/null || { echo "❌ Redis not running. Start with: redis-server"; exit 1; }
curl -s http://localhost:11434/api/tags > /dev/null || { echo "❌ Ollama not running. Start with: ollama serve"; exit 1; }

# Install dependencies
pip install -r requirements.txt

# Update existing myflask service
echo "Updating web service..."
sudo tee /etc/systemd/system/myflask.service > /dev/null << EOF
[Unit]
Description=Gunicorn to serve Flask app
After=network.target redis.service

[Service]
User=$CURRENT_USER
Group=www-data
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin"
Environment="PYTHONPATH=$PROJECT_DIR"
Environment="PYTHONUNBUFFERED=1"
Environment="FLASK_ENV=production"
ExecStart=$PROJECT_DIR/.venv/bin/gunicorn -c gunicorn.conf.py app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Create worker service
echo "Creating worker service..."
sudo tee /etc/systemd/system/launch-nukes-worker.service > /dev/null << EOF
[Unit]
Description=Launch the Nukes Job Worker
After=network.target redis.service

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin"
Environment="PYTHONPATH=$PROJECT_DIR"
Environment="PYTHONUNBUFFERED=1"
ExecStart=$PROJECT_DIR/.venv/bin/python worker.py --workers 2 --redis-url redis://localhost:6379/0
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl enable myflask
sudo systemctl enable launch-nukes-worker
sudo systemctl restart myflask
sudo systemctl restart launch-nukes-worker

# Create nginx config
echo "Creating nginx config..."
sudo tee /etc/nginx/sites-available/myflask > /dev/null << EOF
server {
    server_name launchthenukes.duckdns.org;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;

        # Fix long-running requests
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        send_timeout 300s;    
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/launchthenukes.duckdns.org/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/launchthenukes.duckdns.org/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
}

server {
    if (\$host = launchthenukes.duckdns.org) {
        return 301 https://\$host\$request_uri;
    } # managed by Certbot

    listen 80;
    server_name launchthenukes.duckdns.org;
    return 404; # managed by Certbot
}
EOF

# Enable nginx site and restart
sudo ln -sf /etc/nginx/sites-available/myflask /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

echo "Deployment complete."
