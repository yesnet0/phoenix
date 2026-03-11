#!/usr/bin/env bash
set -euo pipefail

# Phoenix Deploy Script — DigitalOcean droplet provisioning
# Usage: Run on a fresh Ubuntu 22.04 droplet as root

DOMAIN="${DOMAIN:-phoenix.disclose.io}"
EMAIL="${EMAIL:-casey@disclose.io}"
REPO="https://github.com/yesnet0/phoenix.git"
APP_DIR="/opt/phoenix"

echo "=== Phoenix Deploy ==="
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"

# --- 1. System updates ---
echo ">>> Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq curl git ufw

# --- 2. Create swap ---
if [ ! -f /swapfile ]; then
    echo ">>> Creating 2GB swap file..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "vm.swappiness=10" >> /etc/sysctl.conf
    sysctl -p
else
    echo ">>> Swap already exists, skipping."
fi

# --- 3. Install Docker ---
if ! command -v docker &>/dev/null; then
    echo ">>> Installing Docker..."
    curl -fsSL https://get.docker.com | sh
else
    echo ">>> Docker already installed."
fi

# --- 4. Firewall ---
echo ">>> Configuring firewall..."
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# --- 5. Clone repo ---
if [ ! -d "$APP_DIR" ]; then
    echo ">>> Cloning repository..."
    git clone "$REPO" "$APP_DIR"
else
    echo ">>> Repository exists, pulling latest..."
    cd "$APP_DIR" && git pull origin main
fi

cd "$APP_DIR"

# --- 6. Create .env if missing ---
if [ ! -f .env ]; then
    echo ">>> Creating .env from template..."
    cp .env.production.example .env
    # Generate a random Neo4j password
    NEO4J_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
    sed -i "s/change_me_to_a_strong_password/$NEO4J_PASS/" .env
    echo ">>> Generated Neo4j password. Review .env before continuing."
    echo ">>> Edit /opt/phoenix/.env if needed, then re-run this script."
fi

# --- 7. SSL certificate ---
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    echo ">>> Obtaining SSL certificate..."
    apt-get install -y -qq certbot

    # Use nginx-initial.conf for ACME challenge
    cp nginx/nginx-initial.conf nginx/nginx-active.conf
    mkdir -p /var/www/certbot

    # Start nginx temporarily for ACME challenge
    docker compose -f docker-compose.prod.yml run -d --name nginx-certbot \
        -p 80:80 \
        -v "$(pwd)/nginx/nginx-active.conf:/etc/nginx/nginx.conf:ro" \
        -v "/var/www/certbot:/var/www/certbot" \
        nginx:alpine

    # Get certificate
    certbot certonly --webroot \
        -w /var/www/certbot \
        -d "$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos \
        --non-interactive

    # Stop temporary nginx
    docker stop nginx-certbot && docker rm nginx-certbot
    rm nginx/nginx-active.conf

    # Set up auto-renewal cron
    echo "0 3 * * * certbot renew --quiet --deploy-hook 'docker compose -f /opt/phoenix/docker-compose.prod.yml restart nginx'" \
        | crontab -
else
    echo ">>> SSL certificate already exists."
fi

# --- 8. Build and start services ---
echo ">>> Building and starting services..."
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "=== Deploy complete ==="
echo "Services starting up. Check with:"
echo "  docker compose -f docker-compose.prod.yml ps"
echo "  docker compose -f docker-compose.prod.yml logs -f"
echo ""
echo "Verify at: https://$DOMAIN/api/health"
