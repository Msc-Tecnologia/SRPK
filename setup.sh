#!/bin/bash

# SRPK Pro Initial Setup Script
# This script helps with the initial setup of SRPK Pro

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}       SRPK Pro - Initial Setup Wizard          ${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}This script should not be run as root!${NC}"
   exit 1
fi

# Function to generate secure random string
generate_secret() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites satisfied${NC}"
echo ""

# Create necessary directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p ssl logs backups data downloads
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Setup environment file
if [[ ! -f .env ]]; then
    echo -e "${YELLOW}Setting up environment configuration...${NC}"
    
    if [[ -f .env.example ]]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env from template${NC}"
    else
        echo -e "${RED}Warning: .env.example not found${NC}"
        exit 1
    fi
    
    # Generate secrets
    echo -e "${YELLOW}Generating secure secrets...${NC}"
    SECRET_KEY=$(generate_secret)
    DB_PASSWORD=$(generate_secret)
    REDIS_PASSWORD=$(generate_secret)
    
    # Update .env with generated values
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/your-secret-key-here/$SECRET_KEY/g" .env
        sed -i '' "s/secure_password_here/$DB_PASSWORD/g" .env
        sed -i '' "s/redis_password_here/$REDIS_PASSWORD/g" .env
    else
        # Linux
        sed -i "s/your-secret-key-here/$SECRET_KEY/g" .env
        sed -i "s/secure_password_here/$DB_PASSWORD/g" .env
        sed -i "s/redis_password_here/$REDIS_PASSWORD/g" .env
    fi
    
    echo -e "${GREEN}✓ Secrets generated${NC}"
    echo ""
    
    # Prompt for Stripe keys
    echo -e "${YELLOW}Stripe Configuration${NC}"
    echo "Please enter your Stripe API keys (get them from https://dashboard.stripe.com/apikeys)"
    echo ""
    
    read -p "Stripe Secret Key (sk_test_...): " STRIPE_SECRET
    read -p "Stripe Publishable Key (pk_test_...): " STRIPE_PUBLIC
    
    if [[ -n "$STRIPE_SECRET" ]] && [[ -n "$STRIPE_PUBLIC" ]]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/sk_test_XXXXXXXXXXXXXXXXXXXXXX/$STRIPE_SECRET/g" .env
            sed -i '' "s/pk_test_XXXXXXXXXXXXXXXXXXXXXX/$STRIPE_PUBLIC/g" .env
        else
            sed -i "s/sk_test_XXXXXXXXXXXXXXXXXXXXXX/$STRIPE_SECRET/g" .env
            sed -i "s/pk_test_XXXXXXXXXXXXXXXXXXXXXX/$STRIPE_PUBLIC/g" .env
        fi
        echo -e "${GREEN}✓ Stripe keys configured${NC}"
    else
        echo -e "${YELLOW}⚠ Stripe keys not provided. Remember to update them in .env${NC}"
    fi
    
    # Prompt for PayPal keys
    echo -e "${YELLOW}PayPal Configuration${NC}"
    echo "Enter your PayPal REST API credentials (https://developer.paypal.com)"
    read -p "PayPal Mode (sandbox/live) [sandbox]: " PAYPAL_MODE
    PAYPAL_MODE=${PAYPAL_MODE:-sandbox}
    read -p "PayPal Client ID: " PAYPAL_CLIENT_ID
    read -p "PayPal Client Secret: " PAYPAL_CLIENT_SECRET

    if [[ -n "$PAYPAL_CLIENT_ID" ]] && [[ -n "$PAYPAL_CLIENT_SECRET" ]]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/PAYPAL_MODE=.*/PAYPAL_MODE=$PAYPAL_MODE/g" .env || echo "PAYPAL_MODE=$PAYPAL_MODE" >> .env
            sed -i '' "s/PAYPAL_CLIENT_ID=.*/PAYPAL_CLIENT_ID=$PAYPAL_CLIENT_ID/g" .env || echo "PAYPAL_CLIENT_ID=$PAYPAL_CLIENT_ID" >> .env
            sed -i '' "s/PAYPAL_CLIENT_SECRET=.*/PAYPAL_CLIENT_SECRET=$PAYPAL_CLIENT_SECRET/g" .env || echo "PAYPAL_CLIENT_SECRET=$PAYPAL_CLIENT_SECRET" >> .env
        else
            sed -i "s/PAYPAL_MODE=.*/PAYPAL_MODE=$PAYPAL_MODE/g" .env || echo "PAYPAL_MODE=$PAYPAL_MODE" >> .env
            sed -i "s/PAYPAL_CLIENT_ID=.*/PAYPAL_CLIENT_ID=$PAYPAL_CLIENT_ID/g" .env || echo "PAYPAL_CLIENT_ID=$PAYPAL_CLIENT_ID" >> .env
            sed -i "s/PAYPAL_CLIENT_SECRET=.*/PAYPAL_CLIENT_SECRET=$PAYPAL_CLIENT_SECRET/g" .env || echo "PAYPAL_CLIENT_SECRET=$PAYPAL_CLIENT_SECRET" >> .env
        fi
        echo -e "${GREEN}✓ PayPal keys configured${NC}"
    else
        echo -e "${YELLOW}⚠ PayPal keys not provided. Remember to update them in .env${NC}"
    fi

    # JWT secret for license tokens
    echo -e "${YELLOW}JWT Secret for License Tokens${NC}"
    read -p "Provide JWT secret (leave empty to auto-generate): " JWT_SECRET
    if [[ -z "$JWT_SECRET" ]]; then
        JWT_SECRET=$(generate_secret)
        echo -e "${YELLOW}Generated JWT secret${NC}"
    fi
    echo "JWT_SECRET=$JWT_SECRET" >> .env

    echo ""
    echo -e "${GREEN}✓ Environment configuration complete${NC}"
else
    echo -e "${YELLOW}ℹ .env file already exists, skipping configuration${NC}"
fi

echo ""

# SSL Certificate setup
echo -e "${YELLOW}SSL Certificate Setup${NC}"
echo "Choose an option:"
echo "1) Generate self-signed certificate (development only)"
echo "2) I'll provide my own certificates later"
echo "3) Use Let's Encrypt (requires domain)"
read -p "Option (1-3): " SSL_OPTION

case $SSL_OPTION in
    1)
        echo -e "${YELLOW}Generating self-signed certificate...${NC}"
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout ssl/key.pem \
            -out ssl/cert.pem \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
        echo -e "${GREEN}✓ Self-signed certificate generated${NC}"
        ;;
    2)
        echo -e "${YELLOW}ℹ Remember to place your certificates in:${NC}"
        echo "  - ssl/cert.pem (certificate)"
        echo "  - ssl/key.pem (private key)"
        ;;
    3)
        echo -e "${YELLOW}Let's Encrypt setup requires a domain name.${NC}"
        read -p "Enter your domain (e.g., srpk.io): " DOMAIN
        echo -e "${YELLOW}ℹ Run this command after DNS is configured:${NC}"
        echo "sudo certbot certonly --standalone -d $DOMAIN -d www.$DOMAIN"
        ;;
esac

echo ""

# Build Docker images
echo -e "${YELLOW}Building Docker images...${NC}"
docker-compose build
echo -e "${GREEN}✓ Docker images built${NC}"
echo ""

# Database setup
echo -e "${YELLOW}Setting up database...${NC}"
docker-compose up -d postgres
sleep 5  # Wait for PostgreSQL to start

# Create database schema
docker-compose exec -T postgres psql -U srpk -d srpk_licenses < schema.sql 2>/dev/null || echo "ℹ Schema may already exist"
echo -e "${GREEN}✓ Database configured${NC}"
echo ""

# Summary
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}          Setup Complete! 🎉                    ${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Update .env with your production values"
echo "2. Update landing/index.html with your Stripe public key"
echo "3. Configure your domain DNS"
echo "4. Run: ./deploy.sh staging"
echo ""
echo -e "${YELLOW}Important files to review:${NC}"
echo "- .env (environment configuration)"
echo "- DEPLOYMENT.md (deployment guide)"
echo "- PAYMENT_INTEGRATION.md (payment setup)"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"