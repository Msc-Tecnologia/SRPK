# SRPK Pro Payment Integration Guide

This guide explains how the payment system works and how to configure it properly.

## Overview

SRPK Pro uses Stripe for payment processing, offering:
- Secure credit card processing
- Subscription management
- Automated billing
- License key generation

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Landing   │────▶│  Payment API │────▶│   Stripe    │
│    Page     │     │   (Flask)    │     │     API     │
└─────────────┘     └──────────────┘     └─────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  PostgreSQL  │
                    │  (Licenses)  │
                    └──────────────┘
```

## Stripe Configuration

### 1. Create Stripe Account

1. Sign up at https://stripe.com
2. Complete account verification
3. Enable live mode when ready

### 2. Create Products and Prices

In Stripe Dashboard:

1. **Create Products:**
   - SRPK Pro Starter
   - SRPK Pro Professional
   - SRPK Pro Enterprise

2. **Create Prices:**
   ```
   Starter: $99/month (price_starter)
   Professional: $299/month (price_professional)
   Enterprise: Custom pricing
   ```

3. **Configure Webhooks:**
   - Endpoint URL: `https://api.srpk.io/api/webhook`
   - Events to listen:
     - `subscription.created`
     - `subscription.updated`
     - `subscription.deleted`
     - `invoice.payment_succeeded`
     - `invoice.payment_failed`

### 3. Get API Keys

From Stripe Dashboard > Developers > API Keys:
- Publishable key: `pk_live_...`
- Secret key: `sk_live_...`
- Webhook secret: `whsec_...`

## Payment Flow

1. **Customer Selection**
   - User selects plan on landing page
   - JavaScript shows payment form

2. **Card Collection**
   - Stripe Elements collects card details
   - Creates secure token

3. **Payment Processing**
   - Frontend sends token to backend
   - Backend creates customer and subscription
   - Stripe processes payment

4. **License Generation**
   - System generates unique license key
   - Stores in database
   - Sends email to customer

5. **Webhook Handling**
   - Stripe sends events
   - System updates subscription status
   - Handles renewals/cancellations

## API Endpoints

### `POST /api/process-payment`

Process a new subscription payment.

**Request:**
```json
{
  "token": "tok_xxxxx",
  "priceId": "price_professional",
  "email": "customer@example.com",
  "name": "John Doe",
  "company": "Acme Corp"
}
```

**Response:**
```json
{
  "success": true,
  "subscription_id": "sub_xxxxx",
  "customer_id": "cus_xxxxx",
  "message": "Payment processed successfully"
}
```

### `POST /api/webhook`

Stripe webhook endpoint for event handling.

**Headers:**
```
Stripe-Signature: t=timestamp,v1=signature
```

## Testing

### Test Cards

Use these test cards in development:
- Success: `4242 4242 4242 4242`
- Decline: `4000 0000 0000 0002`
- Authentication: `4000 0025 0000 3155`

### Stripe CLI

Test webhooks locally:
```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks
stripe listen --forward-to localhost:5000/api/webhook

# Trigger test events
stripe trigger payment_intent.succeeded
```

## License System

### License Key Format
```
XXXX-XXXX-XXXX-XXXX
```

### License Features
```json
{
  "max_repositories": 5,
  "features": {
    "advanced_reports": true,
    "enterprise_connectors": false,
    "priority_support": true,
    "api_access": true
  }
}
```

### License Validation

```python
# Example validation
def validate_license(license_key):
    license = db.query(License).filter_by(
        license_key=license_key,
        is_active=True
    ).first()
    
    if not license:
        return False
    
    if license.expires_at < datetime.utcnow():
        return False
    
    return True
```

## Email Integration

### SendGrid Setup

1. Create SendGrid account
2. Verify sender domain
3. Create API key
4. Update `.env`:
   ```
   SENDGRID_API_KEY=SG.xxxxx
   ```

### Email Templates

- **Welcome Email**: Sent after purchase
- **License Key**: Contains activation instructions
- **Renewal Reminder**: 7 days before expiration
- **Payment Failed**: When renewal fails

## Security Best Practices

1. **API Keys**
   - Never expose secret keys in frontend
   - Use environment variables
   - Rotate keys regularly

2. **HTTPS Only**
   - All payment pages must use HTTPS
   - Redirect HTTP to HTTPS

3. **Input Validation**
   - Validate all input server-side
   - Sanitize data before storage

4. **PCI Compliance**
   - Don't store card details
   - Use Stripe Elements
   - Keep systems updated

## Monitoring

### Key Metrics

- Conversion rate
- Failed payments
- Churn rate
- MRR (Monthly Recurring Revenue)

### Alerts

Set up alerts for:
- Payment failures
- Webhook errors
- API errors
- License abuse

## Troubleshooting

### Common Issues

1. **"Your card was declined"**
   - Check card details
   - Verify billing address
   - Contact bank

2. **Webhook signature verification failed**
   - Check webhook secret
   - Verify endpoint URL
   - Check request headers

3. **License key not received**
   - Check spam folder
   - Verify email address
   - Check email service logs

### Debug Mode

Enable detailed logging:
```python
# In payment_api.py
app.logger.setLevel(logging.DEBUG)
stripe.log = 'debug'
```

## Support

- Stripe Support: https://support.stripe.com
- SRPK Support: support@srpk.io
- Documentation: https://msc-tecnologia.github.io/SRPK/