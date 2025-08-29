#!/bin/bash
# SRPK Pro Quick Setup Script

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}SRPK Pro Quick Setup${NC}"
echo "===================="
echo ""

# Check if .env exists
if [[ ! -f .env ]]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    
    # Generate secure passwords
    echo "Generating secure passwords..."
    
    # Database password
    DB_PASS=$(openssl rand -hex 16)
    sed -i "s/generate_secure_password_here/$DB_PASS/g" .env
    
    # Redis password
    REDIS_PASS=$(openssl rand -hex 16)
    sed -i "s/generate_secure_redis_password/$REDIS_PASS/g" .env
    
    # JWT secret
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i "s/generate_jwt_secret_key_here/$JWT_SECRET/g" .env
    
    # App secret
    APP_SECRET=$(openssl rand -hex 32)
    sed -i "s/generate_very_secure_key_here/$APP_SECRET/g" .env
    
    echo -e "${GREEN}✓${NC} Generated secure passwords"
else
    echo -e "${YELLOW}!${NC} .env file already exists, skipping password generation"
fi

# Create required directories
echo "Creating required directories..."
mkdir -p logs/{payment,download,app,nginx,celery}
mkdir -p backups
mkdir -p data
mkdir -p ssl
mkdir -p monitoring/grafana/{dashboards,datasources}

echo -e "${GREEN}✓${NC} Directories created"

# Check for SSL certificates
if [[ ! -f ssl/cert.pem ]] || [[ ! -f ssl/key.pem ]]; then
    echo -e "${YELLOW}!${NC} SSL certificates not found in ssl/ directory"
    echo "   Please copy your SSL certificate files:"
    echo "   - ssl/cert.pem"
    echo "   - ssl/key.pem"
    echo ""
    read -p "Generate self-signed certificates for testing? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout ssl/key.pem -out ssl/cert.pem \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=srpk.io"
        echo -e "${GREEN}✓${NC} Generated self-signed certificates"
    fi
else
    echo -e "${GREEN}✓${NC} SSL certificates found"
fi

# Configure Stripe keys
echo ""
echo "Stripe Configuration"
echo "-------------------"
echo "Current Stripe keys in .env:"
grep "STRIPE_" .env | grep -v "WEBHOOK" | head -2
echo ""
echo -e "${YELLOW}!${NC} Please update these with your actual Stripe keys"
echo "   Get them from: https://dashboard.stripe.com/apikeys"
echo ""

# Configure PayPal
echo "PayPal Configuration"
echo "-------------------"
echo -e "${YELLOW}!${NC} Please update PayPal credentials in .env"
echo "   Get them from: https://developer.paypal.com/dashboard/"
echo ""

# Configure AWS S3
echo "AWS S3 Configuration (for downloads)"
echo "-----------------------------------"
echo -e "${YELLOW}!${NC} Please update AWS credentials in .env"
echo "   1. Create an S3 bucket named 'srpk-downloads'"
echo "   2. Create an IAM user with S3 access"
echo "   3. Update AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
echo ""

# Summary
echo -e "${GREEN}Setup Summary${NC}"
echo "============="
echo ""
echo "✓ Environment file created (.env)"
echo "✓ Required directories created"
echo "✓ Secure passwords generated"
echo ""
echo "Next steps:"
echo "1. Update Stripe API keys in .env"
echo "2. Update PayPal credentials in .env"
echo "3. Update AWS S3 credentials in .env"
echo "4. Configure SendGrid API key in .env"
echo "5. Place SSL certificates in ssl/ directory"
echo "6. Run: docker-compose up -d"
echo ""
echo "For full deployment instructions, see PRODUCTION_DEPLOYMENT.md"