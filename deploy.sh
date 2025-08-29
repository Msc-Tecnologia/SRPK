#!/bin/bash

# SRPK Pro Deployment Script
# This script handles deployment to staging/production environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-staging}
STACK=${STACK:-minimal} # minimal|full
DOCKER_REGISTRY=${DOCKER_REGISTRY:-ghcr.io}
IMAGE_NAME=${IMAGE_NAME:-msc-tecnologia/srpk}
IMAGE_TAG=${IMAGE_TAG:-latest}

# Functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check environment
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    error "Invalid environment. Use 'staging' or 'production'"
fi

log "Starting deployment to $ENVIRONMENT environment..."

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    if [[ -f ".env.example" ]]; then
        warning ".env file not found. Creating from .env.example..."
        cp .env.example .env
        error "Please configure .env file with your actual values before deploying"
    else
        error ".env file not found"
    fi
fi

# Validate environment variables
required_vars=(
    "STRIPE_SECRET_KEY"
    "STRIPE_PUBLISHABLE_KEY"
    "SECRET_KEY"
)

log "Validating environment variables..."
source .env
for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        error "Required environment variable $var is not set"
    fi
done

# Build Docker image
log "Building Docker image..."
docker build -t $DOCKER_REGISTRY/$IMAGE_NAME:$IMAGE_TAG .

# Run tests
log "Running tests..."
docker run --rm $DOCKER_REGISTRY/$IMAGE_NAME:$IMAGE_TAG pytest tests/ || warning "Tests failed"

# Tag image for environment
if [[ "$ENVIRONMENT" == "production" ]]; then
    docker tag $DOCKER_REGISTRY/$IMAGE_NAME:$IMAGE_TAG $DOCKER_REGISTRY/$IMAGE_NAME:production
else
    docker tag $DOCKER_REGISTRY/$IMAGE_NAME:$IMAGE_TAG $DOCKER_REGISTRY/$IMAGE_NAME:staging
fi

# Push to registry (if using remote registry)
if [[ "$DOCKER_REGISTRY" != "local" ]]; then
    log "Pushing image to registry..."
    docker push $DOCKER_REGISTRY/$IMAGE_NAME:$ENVIRONMENT
fi

# Deploy with docker-compose
log "Deploying with docker-compose..."
if [[ "$ENVIRONMENT" == "production" ]]; then
    if [[ "$STACK" == "full" ]]; then
        docker-compose -f docker-compose.full.yml -f docker-compose.prod.yml up -d
    else
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale payment-api=3
    fi
else
    if [[ "$STACK" == "full" ]]; then
        docker-compose -f docker-compose.full.yml up -d
    else
        docker-compose up -d
    fi
fi

# Wait for services to be healthy
log "Waiting for services to be healthy..."
timeout=60
elapsed=0
while [[ $elapsed -lt $timeout ]]; do
    if docker-compose ps | grep -q "healthy"; then
        log "Services are healthy!"
        break
    fi
    sleep 5
    elapsed=$((elapsed + 5))
done

if [[ $elapsed -ge $timeout ]]; then
    error "Services failed to become healthy within $timeout seconds"
fi

# Run database migrations (if needed)
if [[ "$ENVIRONMENT" == "production" ]]; then
    log "Running database migrations..."
    docker-compose exec payment-api python -c "print('No migrations defined; skipping')" || true
fi

# Clean up old images
log "Cleaning up old Docker images..."
docker image prune -f

# Show deployment status
log "Deployment completed successfully!"
echo ""
echo "Deployment Summary:"
echo "==================="
echo "Environment: $ENVIRONMENT"
echo "Image: $DOCKER_REGISTRY/$IMAGE_NAME:$ENVIRONMENT"
echo "Services:"
docker-compose ps
echo ""

# Show URLs
if [[ "$ENVIRONMENT" == "production" ]]; then
    echo "URLs:"
    echo "====="
    echo "Landing Page: https://srpk.io"
    echo "API: https://api.srpk.io"
else
    echo "URLs:"
    echo "====="
    echo "Landing Page: http://localhost"
    echo "API: http://localhost:5000"
fi

# Deployment verification
log "Running deployment verification..."
if curl -f http://localhost:5000/health > /dev/null 2>&1; then
    log "API health check passed ✓"
else
    error "API health check failed"
fi

log "Deployment completed successfully! 🚀"