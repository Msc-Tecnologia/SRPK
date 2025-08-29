# SRPK Pro Deployment Guide

This guide covers the complete deployment process for SRPK Pro, including payment integration with Stripe.

## Prerequisites

- Docker and Docker Compose installed
- Domain name configured (e.g., srpk.io)
- SSL certificates (for HTTPS)
- Stripe account with API keys
- Server with at least 2GB RAM

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/Msc-Tecnologia/SRPK.git
   cd SRPK
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

3. **Deploy to staging**
   ```bash
   ./deploy.sh staging
   ```

4. **Deploy to production**
   ```bash
   ./deploy.sh production
   ```

## Configuration

### 1. Stripe Setup

1. Create a Stripe account at https://stripe.com
2. Get your API keys from the Stripe Dashboard
3. Create products and prices in Stripe
4. Update the `.env` file:
   ```env
   STRIPE_SECRET_KEY=sk_live_xxxxx
   STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx
   STRIPE_WEBHOOK_SECRET=whsec_xxxxx
   ```

### 2. Environment Variables

Required environment variables in `.env`:

```env
# Stripe Configuration
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# CORS Configuration
ALLOWED_ORIGINS=https://srpk.io,https://www.srpk.io

# Database
DB_USER=srpk
DB_PASSWORD=secure_password_here
DB_NAME=srpk_licenses

# Redis
REDIS_PASSWORD=redis_password_here

# Email Service (choose one)
SENDGRID_API_KEY=SG.xxxxx
```

### 3. SSL Certificates

For production deployment with HTTPS:

1. **Option A: Let's Encrypt (recommended)**
   ```bash
   # Install certbot
   sudo apt-get install certbot
   
   # Generate certificates
   sudo certbot certonly --standalone -d srpk.io -d www.srpk.io
   
   # Copy certificates
   cp /etc/letsencrypt/live/srpk.io/fullchain.pem ./ssl/cert.pem
   cp /etc/letsencrypt/live/srpk.io/privkey.pem ./ssl/key.pem
   ```

2. **Option B: Commercial SSL**
   - Purchase SSL certificate
   - Place certificate files in `./ssl/` directory

### 4. Domain Configuration

Configure your DNS records:

```
A     @      YOUR_SERVER_IP
A     www    YOUR_SERVER_IP
A     api    YOUR_SERVER_IP
```

## Deployment Steps

### Manual Deployment

1. **Prepare the server**
   ```bash
   # Update system
   sudo apt-get update && sudo apt-get upgrade
   
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   
   # Install Docker Compose
   sudo apt-get install docker-compose
   ```

2. **Deploy the application**
   ```bash
   # Clone repository
   git clone https://github.com/Msc-Tecnologia/SRPK.git
   cd SRPK
   
   # Configure environment
   cp .env.example .env
   nano .env  # Edit with your values
   
   # Deploy
   ./deploy.sh production
   ```

### Automated Deployment (GitHub Actions)

1. **Configure GitHub Secrets**
   - Go to Settings > Secrets in your GitHub repository
   - Add the following secrets:
     ```
     STAGING_HOST
     STAGING_USER
     STAGING_SSH_KEY
     PRODUCTION_HOST
     PRODUCTION_USER
     PRODUCTION_SSH_KEY
     SLACK_WEBHOOK (optional)
     ```

2. **Deploy**
   - Push to `main` branch for staging deployment
   - Push to `production` branch for production deployment

## Monitoring

### Health Checks

- API Health: `https://api.srpk.io/health`
- Nginx Health: `https://srpk.io/health`

### Logs

View logs for different services:

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f payment-api
docker-compose logs -f nginx

# Last 100 lines
docker-compose logs --tail=100 payment-api
```

### Metrics

Monitor system resources:

```bash
# Container stats
docker stats

# Disk usage
df -h

# Memory usage
free -m
```

## Maintenance

### Backup

1. **Database backup**
   ```bash
   # Manual backup
   docker-compose exec postgres pg_dump -U srpk srpk_licenses > backup_$(date +%Y%m%d_%H%M%S).sql
   
   # Automated backup (add to crontab)
   0 2 * * * /opt/srpk/scripts/backup.sh
   ```

2. **File backup**
   ```bash
   # Backup configuration and data
   tar -czf srpk_backup_$(date +%Y%m%d).tar.gz .env docker-compose.yml ssl/ logs/
   ```

### Updates

1. **Update application**
   ```bash
   git pull origin production
   ./deploy.sh production
   ```

2. **Update dependencies**
   ```bash
   # Update Python packages
   pip install -r requirements.txt --upgrade
   
   # Rebuild Docker images
   docker-compose build --no-cache
   ```

### Scaling

Scale the payment API for high traffic:

```bash
# Scale to 5 instances
docker-compose up -d --scale payment-api=5

# Scale down
docker-compose up -d --scale payment-api=3
```

## Troubleshooting

### Common Issues

1. **Payment API not accessible**
   - Check if container is running: `docker-compose ps`
   - Check logs: `docker-compose logs payment-api`
   - Verify port binding: `netstat -tlnp | grep 5000`

2. **Stripe webhook failures**
   - Verify webhook secret in `.env`
   - Check webhook URL in Stripe Dashboard
   - Test webhook: `stripe trigger payment_intent.succeeded`

3. **SSL certificate issues**
   - Verify certificate files exist in `./ssl/`
   - Check certificate validity: `openssl x509 -in ssl/cert.pem -text -noout`
   - Renew if expired: `sudo certbot renew`

### Debug Mode

Enable debug mode for troubleshooting:

```bash
# Edit .env
FLASK_ENV=development

# Restart services
docker-compose restart payment-api
```

## Security Best Practices

1. **Environment Variables**
   - Never commit `.env` to version control
   - Use strong, unique passwords
   - Rotate keys regularly

2. **Network Security**
   - Use firewall (ufw or iptables)
   - Limit SSH access
   - Enable fail2ban

3. **Updates**
   - Keep system packages updated
   - Update Docker regularly
   - Monitor security advisories

4. **Monitoring**
   - Set up alerts for failures
   - Monitor resource usage
   - Track API errors

## Support

- Documentation: https://msc-tecnologia.github.io/SRPK/
- Issues: https://github.com/Msc-Tecnologia/SRPK/issues
- Email: support@srpk.io

## License

See LICENSE file for details.