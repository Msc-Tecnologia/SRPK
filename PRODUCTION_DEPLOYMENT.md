# SRPK Pro Production Deployment Guide

## Overview

This guide covers the complete deployment process for SRPK Pro, including payment processing (Stripe & PayPal), secure downloads, license management, and monitoring.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Nginx     │────▶│  Payment API │────▶│  PostgreSQL │
│  (Reverse   │     │   (Flask)    │     │  (Database) │
│   Proxy)    │     └──────────────┘     └─────────────┘
└─────────────┘              │                    │
       │                     │                    │
       │              ┌──────────────┐           │
       ├─────────────▶│ Download API │───────────┘
       │              │   (Flask)    │
       │              └──────────────┘
       │                     │
       │              ┌──────────────┐     ┌─────────────┐
       └─────────────▶│   SRPK App   │────▶│    Redis    │
                      │   (Python)    │     │   (Cache)   │
                      └──────────────┘     └─────────────┘
```

## Prerequisites

1. **Server Requirements:**
   - Ubuntu 20.04+ or similar Linux distribution
   - Docker 20.10+ and Docker Compose 2.0+
   - 4+ CPU cores, 8GB+ RAM
   - 50GB+ disk space
   - SSL certificates for domains

2. **Domain Configuration:**
   - `srpk.io` - Main landing page
   - `api.srpk.io` - Payment API
   - `downloads.srpk.io` - Download API
   - `app.srpk.io` - Main application

3. **Third-Party Services:**
   - Stripe account (with API keys)
   - PayPal business account
   - SendGrid account (for emails)
   - AWS S3 bucket (for downloads)
   - Optional: Sentry, New Relic

## Configuration

### 1. Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

**Critical Variables to Update:**

```bash
# Database
DB_PASSWORD=<generate-secure-password>

# Redis
REDIS_PASSWORD=<generate-secure-password>

# Stripe (Production Keys)
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# PayPal (Production)
PAYPAL_CLIENT_ID=<your-live-client-id>
PAYPAL_CLIENT_SECRET=<your-live-secret>
PAYPAL_MODE=live

# Security
JWT_SECRET_KEY=<generate-with-openssl-rand-hex-32>
SECRET_KEY=<generate-with-openssl-rand-hex-32>

# AWS S3 (for downloads)
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
```

### 2. SSL Certificates

Place SSL certificates in the `ssl/` directory:
```bash
mkdir -p ssl
cp /path/to/cert.pem ssl/
cp /path/to/key.pem ssl/
```

### 3. Stripe Configuration

1. Log into Stripe Dashboard
2. Create products and prices:
   - SRPK Pro Starter: $99/month
   - SRPK Pro Professional: $299/month
3. Configure webhooks:
   - Endpoint: `https://api.srpk.io/api/webhook`
   - Events: subscription.*, invoice.*, payment_intent.*
4. Copy webhook secret to `.env`

### 4. PayPal Configuration

1. Log into PayPal Developer Dashboard
2. Create REST API app
3. Copy Client ID and Secret to `.env`
4. Configure webhooks for payment events

## Deployment Steps

### 1. Initial Setup

```bash
# Clone repository
git clone https://github.com/msc-tecnologia/SRPK.git
cd SRPK

# Create required directories
mkdir -p logs/{payment,download,app,nginx,celery}
mkdir -p backups
mkdir -p data

# Set permissions
chmod +x deploy-production.sh
```

### 2. Database Setup

```bash
# Start only database service
docker-compose up -d postgres

# Wait for database to be ready
sleep 10

# Create schema
docker-compose exec postgres psql -U srpk_user -d srpk_db -f /docker-entrypoint-initdb.d/01-schema.sql
```

### 3. Deploy All Services

```bash
# Run deployment script
sudo ./deploy-production.sh

# Or manually:
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 4. Verify Deployment

```bash
# Check service status
docker-compose ps

# Check logs
docker-compose logs -f payment-api
docker-compose logs -f download-api

# Test endpoints
curl https://api.srpk.io/health
curl https://downloads.srpk.io/health
```

## GitHub Actions Setup

### Required Secrets

Add these secrets to your GitHub repository:

```
# Stripe
STRIPE_TEST_PUBLISHABLE_KEY
STRIPE_TEST_SECRET_KEY
STRIPE_TEST_WEBHOOK_SECRET
STRIPE_LIVE_PUBLISHABLE_KEY
STRIPE_LIVE_SECRET_KEY
STRIPE_LIVE_WEBHOOK_SECRET

# PayPal
PAYPAL_SANDBOX_CLIENT_ID
PAYPAL_SANDBOX_CLIENT_SECRET
PAYPAL_LIVE_CLIENT_ID
PAYPAL_LIVE_CLIENT_SECRET

# Database
STAGING_DATABASE_URL
PRODUCTION_DATABASE_URL
STAGING_DB_PASSWORD
PRODUCTION_DB_PASSWORD

# Redis
STAGING_REDIS_URL
PRODUCTION_REDIS_URL
STAGING_REDIS_PASSWORD
PRODUCTION_REDIS_PASSWORD

# Security
JWT_SECRET_KEY
SECRET_KEY

# Email
SENDGRID_API_KEY

# AWS
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY

# Deployment
STAGING_HOST
STAGING_USER
STAGING_SSH_KEY
PRODUCTION_HOST
PRODUCTION_USER
PRODUCTION_SSH_KEY

# Monitoring
SLACK_WEBHOOK
SENTRY_DSN
NEW_RELIC_LICENSE_KEY
```

### Deployment Workflow

The GitHub Actions workflow automatically:
1. Runs tests and security checks
2. Builds Docker images
3. Pushes to GitHub Container Registry
4. Deploys to staging (on main branch)
5. Deploys to production (on production branch)

## Monitoring

### 1. Prometheus & Grafana

Access monitoring dashboards:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

### 2. Application Logs

```bash
# View real-time logs
docker-compose logs -f payment-api
docker-compose logs -f download-api

# Check log files
tail -f logs/payment/*.log
tail -f logs/download/*.log
```

### 3. Health Checks

Monitor service health:
```bash
# Check all services
curl https://api.srpk.io/health
curl https://downloads.srpk.io/health

# Database health
docker-compose exec postgres pg_isready
```

## Backup & Recovery

### Automated Backups

The deployment script automatically creates backups before each deployment.

### Manual Backup

```bash
# Backup database
docker-compose exec postgres pg_dump -U srpk_user srpk_db > backup-$(date +%Y%m%d).sql

# Backup files and configuration
tar -czf srpk-backup-$(date +%Y%m%d).tar.gz .env logs/ data/
```

### Recovery

```bash
# Restore database
docker-compose exec -T postgres psql -U srpk_user srpk_db < backup.sql

# Restore from deployment backup
cd backups/deployment_YYYYMMDD_HHMMSS
./restore.sh
```

## Troubleshooting

### Common Issues

1. **Payment API not responding**
   ```bash
   docker-compose restart payment-api
   docker-compose logs payment-api
   ```

2. **Database connection issues**
   ```bash
   docker-compose exec postgres pg_isready
   docker-compose logs postgres
   ```

3. **SSL certificate errors**
   - Verify certificate files exist in `ssl/`
   - Check certificate validity
   - Ensure proper permissions

4. **Stripe webhook failures**
   - Verify webhook secret in `.env`
   - Check Stripe dashboard for errors
   - Review payment API logs

### Debug Mode

Enable debug logging:
```bash
# In .env
APP_DEBUG=true
LOG_LEVEL=DEBUG

# Restart services
docker-compose restart
```

## Security Checklist

- [ ] Strong passwords for all services
- [ ] SSL certificates configured
- [ ] Firewall rules configured
- [ ] Database backups automated
- [ ] Monitoring alerts configured
- [ ] Rate limiting enabled
- [ ] CORS properly configured
- [ ] Environment variables secured
- [ ] Regular security updates

## Maintenance

### Regular Tasks

1. **Daily:**
   - Check service health
   - Review error logs
   - Monitor disk space

2. **Weekly:**
   - Update Docker images
   - Review security alerts
   - Check backup integrity

3. **Monthly:**
   - Update dependencies
   - Review access logs
   - Performance optimization

### Updating Services

```bash
# Pull latest changes
git pull origin production

# Update specific service
docker-compose build payment-api
docker-compose up -d payment-api

# Update all services
./deploy-production.sh
```

## Support

- Technical Support: support@srpk.io
- Documentation: https://msc-tecnologia.github.io/SRPK/
- GitHub Issues: https://github.com/msc-tecnologia/SRPK/issues