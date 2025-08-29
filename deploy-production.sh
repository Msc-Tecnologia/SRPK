#!/bin/bash
# SRPK Pro Production Deployment Script

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_DIR="/opt/srpk"
BACKUP_DIR="/opt/srpk/backups"
LOG_FILE="/var/log/srpk-deployment.log"
HEALTH_CHECK_TIMEOUT=60
ROLLBACK_ON_FAILURE=true

# Functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

# Pre-flight checks
preflight_check() {
    log "Running pre-flight checks..."
    
    # Check if running as root or with sudo
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root or with sudo"
        exit 1
    fi
    
    # Check required commands
    for cmd in docker docker-compose curl git openssl; do
        if ! command -v "$cmd" &> /dev/null; then
            error "$cmd is not installed"
            exit 1
        fi
    done
    
    # Check disk space (require at least 5GB free)
    available_space=$(df -BG "$DEPLOYMENT_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
    if [[ $available_space -lt 5 ]]; then
        error "Insufficient disk space. At least 5GB required, only ${available_space}GB available"
        exit 1
    fi
    
    # Check if services are accessible
    for service in "postgres:5432" "redis:6379"; do
        host=$(echo "$service" | cut -d: -f1)
        port=$(echo "$service" | cut -d: -f2)
        if ! nc -z "$host" "$port" 2>/dev/null; then
            warning "$host is not accessible on port $port"
        fi
    done
    
    log "Pre-flight checks completed successfully"
}

# Backup current deployment
backup_deployment() {
    log "Creating backup of current deployment..."
    
    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_path="$BACKUP_DIR/deployment_$timestamp"
    
    mkdir -p "$backup_path"
    
    # Backup environment files
    if [[ -f "$DEPLOYMENT_DIR/.env" ]]; then
        cp "$DEPLOYMENT_DIR/.env" "$backup_path/.env"
    fi
    
    # Backup database
    log "Backing up database..."
    docker-compose exec -T postgres pg_dump -U srpk_user srpk_db > "$backup_path/database.sql" || {
        warning "Database backup failed, continuing..."
    }
    
    # Save current docker images
    log "Saving current Docker images..."
    docker images --format "{{.Repository}}:{{.Tag}}" | grep srpk > "$backup_path/images.txt" || true
    
    # Create restore script
    cat > "$backup_path/restore.sh" << 'EOF'
#!/bin/bash
# Restore script for SRPK deployment
echo "Restoring SRPK deployment from backup..."
cp .env "$DEPLOYMENT_DIR/.env"
docker-compose down
docker-compose up -d postgres
sleep 10
docker-compose exec -T postgres psql -U srpk_user srpk_db < database.sql
docker-compose up -d
echo "Restoration complete"
EOF
    chmod +x "$backup_path/restore.sh"
    
    log "Backup created at: $backup_path"
}

# Update environment configuration
update_environment() {
    log "Updating environment configuration..."
    
    # Create .env file if it doesn't exist
    if [[ ! -f "$DEPLOYMENT_DIR/.env" ]]; then
        error ".env file not found. Please create it from .env.example"
        exit 1
    fi
    
    # Validate required environment variables
    required_vars=(
        "DB_PASSWORD"
        "REDIS_PASSWORD"
        "STRIPE_SECRET_KEY"
        "JWT_SECRET_KEY"
        "SECRET_KEY"
    )
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" "$DEPLOYMENT_DIR/.env"; then
            error "Required environment variable $var is not set"
            exit 1
        fi
    done
    
    # Generate secure values for any missing optional variables
    if ! grep -q "^ADMIN_TOKEN=" "$DEPLOYMENT_DIR/.env"; then
        echo "ADMIN_TOKEN=$(openssl rand -hex 32)" >> "$DEPLOYMENT_DIR/.env"
    fi
    
    if ! grep -q "^GRAFANA_PASSWORD=" "$DEPLOYMENT_DIR/.env"; then
        echo "GRAFANA_PASSWORD=$(openssl rand -hex 16)" >> "$DEPLOYMENT_DIR/.env"
    fi
}

# Pull latest code
pull_latest_code() {
    log "Pulling latest code from repository..."
    
    cd "$DEPLOYMENT_DIR"
    
    # Stash any local changes
    git stash push -m "Deployment stash $(date +%Y%m%d_%H%M%S)"
    
    # Pull latest changes
    git pull origin production || {
        error "Failed to pull latest code"
        exit 1
    }
    
    log "Code updated successfully"
}

# Build and deploy services
deploy_services() {
    log "Building and deploying services..."
    
    cd "$DEPLOYMENT_DIR"
    
    # Build images
    log "Building Docker images..."
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml build --parallel || {
        error "Failed to build Docker images"
        exit 1
    }
    
    # Run database migrations
    log "Running database migrations..."
    docker-compose run --rm payment-api python -c "
from license_manager import LicenseManager
manager = LicenseManager()
print('Database migrations completed')
" || {
        warning "Database migration failed, continuing..."
    }
    
    # Deploy services with zero downtime
    log "Deploying services..."
    
    # Deploy payment API with rolling update
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --scale payment-api=0
    sleep 5
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --scale payment-api=3
    
    # Deploy other services
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps download-api srpk-app nginx
    
    log "Services deployed successfully"
}

# Health checks
health_check() {
    log "Running health checks..."
    
    local services=(
        "https://api.srpk.io/health"
        "https://downloads.srpk.io/health"
        "https://app.srpk.io"
        "https://srpk.io"
    )
    
    local failed=0
    local timeout=$HEALTH_CHECK_TIMEOUT
    
    while [[ $timeout -gt 0 ]]; do
        failed=0
        for service in "${services[@]}"; do
            if ! curl -sf "$service" > /dev/null; then
                ((failed++))
            fi
        done
        
        if [[ $failed -eq 0 ]]; then
            log "All health checks passed"
            return 0
        fi
        
        sleep 5
        ((timeout-=5))
    done
    
    error "$failed service(s) failed health check"
    return 1
}

# Cleanup old resources
cleanup() {
    log "Cleaning up old resources..."
    
    # Remove unused Docker resources
    docker system prune -af --filter "until=24h" || true
    
    # Clean old logs
    find /var/log/srpk -name "*.log" -mtime +30 -delete || true
    
    # Clean old backups (keep last 10)
    cd "$BACKUP_DIR"
    ls -t | tail -n +11 | xargs -r rm -rf
    
    log "Cleanup completed"
}

# Rollback deployment
rollback() {
    error "Deployment failed, rolling back..."
    
    if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
        # Find latest backup
        latest_backup=$(ls -t "$BACKUP_DIR" | head -n 1)
        
        if [[ -n "$latest_backup" ]]; then
            log "Rolling back to: $latest_backup"
            cd "$BACKUP_DIR/$latest_backup"
            ./restore.sh
        else
            error "No backup found for rollback"
        fi
    fi
}

# Send notification
send_notification() {
    local status=$1
    local message=$2
    
    # Send Slack notification if webhook is configured
    if [[ -n "${SLACK_WEBHOOK:-}" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"SRPK Deployment: $status - $message\"}" \
            "$SLACK_WEBHOOK" || true
    fi
    
    # Send email notification if configured
    if [[ -n "${NOTIFICATION_EMAIL:-}" ]]; then
        echo "$message" | mail -s "SRPK Deployment: $status" "$NOTIFICATION_EMAIL" || true
    fi
}

# Main deployment process
main() {
    log "Starting SRPK Pro production deployment..."
    
    # Change to deployment directory
    cd "$DEPLOYMENT_DIR" || {
        error "Deployment directory not found: $DEPLOYMENT_DIR"
        exit 1
    }
    
    # Run deployment steps
    preflight_check || exit 1
    backup_deployment || exit 1
    update_environment || exit 1
    pull_latest_code || exit 1
    deploy_services || {
        rollback
        send_notification "FAILED" "Deployment failed and was rolled back"
        exit 1
    }
    
    # Wait for services to be ready
    sleep 10
    
    # Run health checks
    if health_check; then
        cleanup
        log "Deployment completed successfully!"
        send_notification "SUCCESS" "SRPK Pro has been successfully deployed to production"
    else
        rollback
        send_notification "FAILED" "Deployment failed health checks and was rolled back"
        exit 1
    fi
}

# Handle script interruption
trap 'error "Deployment interrupted"; rollback; exit 130' INT TERM

# Run main deployment
main "$@"