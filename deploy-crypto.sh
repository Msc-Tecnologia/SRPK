#!/bin/bash

# SRPK Pro Crypto Payment Deployment Script
# This script helps deploy the smart contract and set up the crypto payment system

set -e

echo "================================================"
echo "SRPK Pro Crypto Payment System Deployment"
echo "================================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cat > .env << EOF
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)

# Blockchain Configuration
BSC_RPC_URL=https://bsc-dataseed.binance.org/
CONTRACT_ADDRESS=
CONTRACT_ABI=

# Database Configuration
DB_USER=srpk
DB_PASSWORD=$(openssl rand -hex 16)
DB_NAME=srpk_licenses
DATABASE_URL=postgresql://srpk:$(openssl rand -hex 16)@postgres:5432/srpk_licenses

# CORS Configuration
ALLOWED_ORIGINS=http://localhost,https://yourdomain.com

# Email Configuration (optional)
SENDGRID_API_KEY=
EMAIL_FROM=noreply@srpk.io
EOF
    echo "✓ .env file created. Please update with your values."
fi

# Function to deploy smart contract
deploy_contract() {
    echo ""
    echo "Deploying Smart Contract..."
    echo "=========================="
    
    cd contracts
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "Installing contract dependencies..."
        npm install
    fi
    
    # Create .env for contract deployment if not exists
    if [ ! -f .env ]; then
        echo ""
        echo "⚠️  Please create contracts/.env with:"
        echo "PRIVATE_KEY=your_deployer_private_key"
        echo "BSC_RPC_URL=https://bsc-dataseed.binance.org/"
        echo "BSCSCAN_API_KEY=your_bscscan_api_key"
        echo ""
        read -p "Press enter when ready to continue..."
    fi
    
    # Compile contracts
    echo "Compiling contracts..."
    npx hardhat compile
    
    # Run tests
    echo "Running contract tests..."
    npx hardhat test
    
    # Deploy to network
    echo ""
    echo "Select deployment network:"
    echo "1) BSC Testnet"
    echo "2) BSC Mainnet"
    echo "3) Local Hardhat"
    read -p "Enter choice (1-3): " network_choice
    
    case $network_choice in
        1)
            NETWORK="bscTestnet"
            echo "Deploying to BSC Testnet..."
            ;;
        2)
            NETWORK="bsc"
            echo "⚠️  WARNING: Deploying to BSC Mainnet!"
            read -p "Are you sure? (yes/no): " confirm
            if [ "$confirm" != "yes" ]; then
                echo "Deployment cancelled."
                exit 1
            fi
            ;;
        3)
            NETWORK="localhost"
            echo "Deploying to local Hardhat network..."
            ;;
        *)
            echo "Invalid choice. Exiting."
            exit 1
            ;;
    esac
    
    # Create deployments directory
    mkdir -p deployments
    
    # Deploy contract
    npx hardhat run scripts/deploy.js --network $NETWORK
    
    echo ""
    echo "✓ Contract deployed successfully!"
    echo ""
    echo "Please update the root .env file with:"
    echo "- CONTRACT_ADDRESS from deployments/${NETWORK}-deployment.json"
    echo "- CONTRACT_ABI from artifacts/contracts/SRPKPayment.sol/SRPKPayment.json"
    
    cd ..
}

# Function to start crypto payment system
start_crypto_system() {
    echo ""
    echo "Starting Crypto Payment System..."
    echo "================================"
    
    # Build and start services
    docker-compose -f docker-compose.crypto.yml build
    docker-compose -f docker-compose.crypto.yml up -d
    
    echo ""
    echo "✓ Crypto payment system started!"
    echo ""
    echo "Services:"
    echo "- Landing Page: http://localhost"
    echo "- Crypto API: http://localhost:5001/health"
    echo "- PostgreSQL: localhost:5432"
    echo "- Redis: localhost:6379"
}

# Function to stop old Stripe system
stop_stripe_system() {
    echo ""
    echo "Stopping old Stripe payment system..."
    echo "===================================="
    
    if docker-compose ps | grep -q "srpk-payment-api"; then
        docker-compose down
        echo "✓ Old payment system stopped"
    else
        echo "✓ Old payment system not running"
    fi
}

# Main menu
echo ""
echo "What would you like to do?"
echo "1) Deploy smart contract only"
echo "2) Start crypto payment system only"
echo "3) Full deployment (contract + system)"
echo "4) Stop old Stripe system and start crypto system"
echo "5) Generate contract ABI for .env"

read -p "Enter choice (1-5): " choice

case $choice in
    1)
        deploy_contract
        ;;
    2)
        start_crypto_system
        ;;
    3)
        deploy_contract
        echo ""
        read -p "Contract deployed. Update .env and press enter to continue..."
        start_crypto_system
        ;;
    4)
        stop_stripe_system
        start_crypto_system
        ;;
    5)
        if [ -f "contracts/artifacts/contracts/SRPKPayment.sol/SRPKPayment.json" ]; then
            echo ""
            echo "Contract ABI:"
            echo "============="
            cat contracts/artifacts/contracts/SRPKPayment.sol/SRPKPayment.json | jq -c '.abi'
        else
            echo "Contract not compiled. Run 'cd contracts && npx hardhat compile' first."
        fi
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "================================================"
echo "Deployment complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Ensure CONTRACT_ADDRESS and CONTRACT_ABI are set in .env"
echo "2. Visit http://localhost to test the payment system"
echo "3. Monitor logs: docker-compose -f docker-compose.crypto.yml logs -f"
echo ""
echo "To accept payments:"
echo "- BNB: Native token on BSC"
echo "- USDT: 0x55d398326f99059fF775485246999027B3197955"
echo "- ETH: 0x2170Ed0880ac9A755fd29B2688956BD959F933F8"
echo "- Wallet: 0x680c48F49187a2121a25e3F834585a8b82DfdC16"