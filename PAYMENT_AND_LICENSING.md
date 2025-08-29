# SRPK Pro Payment and Licensing System

## Overview

SRPK Pro uses a comprehensive payment and licensing system that supports both Stripe and PayPal for payments, secure downloads via AWS S3, and a robust license management system.

## Payment Processing

### Stripe Integration

**Test Keys:**
- Publishable: `pk_test_...` (get from Stripe Dashboard)
- Secret: `sk_test_...` (get from Stripe Dashboard)

**Setup:**
1. Create products in Stripe Dashboard
2. Configure webhook endpoint: `https://api.srpk.io/api/webhook`
3. Update webhook secret in `.env`

**API Endpoints:**
- `POST /api/process-payment` - Process Stripe payment
- `POST /api/webhook` - Stripe webhook handler

### PayPal Integration

**Setup:**
1. Create app in PayPal Developer Dashboard
2. Get Client ID and Secret
3. Configure webhooks

**API Endpoints:**
- `POST /api/create-paypal-payment` - Create PayPal payment
- `POST /api/process-paypal-payment` - Execute PayPal payment

## License Management

### License Types

1. **Starter ($99/month)**
   - 5 devices max
   - 10 repositories max
   - Basic features

2. **Professional ($299/month)**
   - 10 devices max
   - 50 repositories max
   - All features

3. **Enterprise (Custom)**
   - 100 devices max
   - Unlimited repositories
   - Premium features + support

### License Features

```python
{
    "advanced_reports": True,
    "enterprise_connectors": True/False,
    "priority_support": True/False,
    "api_access": True,
    "custom_rules": True/False,
    "team_collaboration": True/False,
    "sso": True/False,  # Enterprise only
    "audit_logs": True/False,  # Enterprise only
}
```

### License API

```python
from license_manager import LicenseManager, LicenseType

# Create license manager
manager = LicenseManager()

# Create a new license
license = manager.create_license(
    customer_email="customer@example.com",
    customer_name="John Doe",
    license_type=LicenseType.PROFESSIONAL,
    payment_info={
        'stripe_customer_id': 'cus_xxx',
        'stripe_subscription_id': 'sub_xxx'
    }
)

# Validate license
result = manager.validate_license(license_key)
if result['valid']:
    print("License is valid")
else:
    print(f"License invalid: {result['error']}")

# Activate device
success = manager.activate_device(
    license_key,
    device_id="device123",
    device_name="John's Laptop"
)

# Check device count
count = manager.get_device_count(license_key)
print(f"Active devices: {count}")
```

## Secure Downloads

### Configuration

Downloads are served via AWS S3 with time-limited presigned URLs.

**Setup:**
1. Create S3 bucket: `srpk-downloads`
2. Upload release files
3. Configure AWS credentials in `.env`

### Download Flow

1. User requests download with license key
2. System validates license
3. Generates JWT token with expiration
4. Creates presigned S3 URL
5. Returns secure download link

### API Endpoints

- `POST /api/generate-download-token` - Get download token
- `GET /api/download/<token>` - Download file

**Example Request:**
```bash
curl -X POST https://downloads.srpk.io/api/generate-download-token \
  -H "Content-Type: application/json" \
  -d '{
    "licenseKey": "XXXX-XXXX-XXXX-XXXX",
    "downloadId": "srpk-pro"
  }'
```

## Database Schema

### Licenses Table
```sql
CREATE TABLE licenses (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(255) UNIQUE NOT NULL,
    customer_email VARCHAR(255) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    license_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    max_devices INTEGER DEFAULT 5,
    max_repositories INTEGER DEFAULT 10,
    features JSONB,
    metadata JSONB,
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    paypal_payment_id VARCHAR(255)
);
```

### License Activations Table
```sql
CREATE TABLE license_activations (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(255) REFERENCES licenses(license_key),
    device_id VARCHAR(255) NOT NULL,
    device_name VARCHAR(255),
    ip_address INET,
    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(license_key, device_id)
);
```

## Integration with SRPK

### License Validation in SRPK

```python
# In srpk_v3_1.py
def validate_license():
    """Validate SRPK Pro license"""
    license_key = get_stored_license_key()
    
    if not license_key:
        return False, "No license key found"
    
    # Call license API
    response = requests.post(
        "http://payment-api:5000/api/validate-license",
        json={"license_key": license_key}
    )
    
    if response.status_code == 200:
        data = response.json()
        return data['valid'], data.get('error')
    
    return False, "License validation failed"
```

### Feature Gating

```python
def check_feature(feature_name):
    """Check if feature is available in current license"""
    license_data = get_current_license()
    
    if not license_data:
        return False
    
    features = license_data.get('features', {})
    return features.get(feature_name, False)

# Usage
if check_feature('enterprise_connectors'):
    # Enable enterprise connectors
    enable_enterprise_features()
```

## Testing

### Test Payment Flow

1. **Stripe Test Cards:**
   - Success: `4242 4242 4242 4242`
   - Decline: `4000 0000 0000 0002`
   - 3D Secure: `4000 0025 0000 3155`

2. **PayPal Sandbox:**
   - Use sandbox accounts from PayPal Developer Dashboard

### Test License Flow

```bash
# Create test license
curl -X POST http://localhost:5000/api/test/create-license \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "name": "Test User",
    "type": "professional"
  }'

# Validate license
curl -X POST http://localhost:5000/api/validate-license \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "XXXX-XXXX-XXXX-XXXX"
  }'
```

## Monitoring

### Key Metrics

1. **Payment Metrics:**
   - Successful payments
   - Failed payments
   - Revenue by product
   - Churn rate

2. **License Metrics:**
   - Active licenses
   - Device activations
   - Feature usage
   - License violations

3. **Download Metrics:**
   - Download attempts
   - Successful downloads
   - Failed downloads
   - Bandwidth usage

### Alerts

Configure alerts for:
- Payment failures > 5%
- License validation errors
- Download service downtime
- Unusual activation patterns

## Security Considerations

1. **API Security:**
   - All endpoints use HTTPS
   - JWT tokens for authentication
   - Rate limiting on all endpoints

2. **License Security:**
   - License keys are hashed in logs
   - Device fingerprinting
   - IP-based restrictions (optional)

3. **Payment Security:**
   - PCI compliance via Stripe/PayPal
   - No card data stored
   - Webhook signature verification

## Troubleshooting

### Common Issues

1. **"License key not found"**
   - Check license exists in database
   - Verify key format (XXXX-XXXX-XXXX-XXXX)

2. **"Device limit exceeded"**
   - Check active devices
   - Deactivate unused devices
   - Upgrade license type

3. **Payment webhook failures**
   - Verify webhook secret
   - Check webhook logs
   - Ensure endpoint is accessible

### Debug Commands

```bash
# Check payment API logs
docker-compose logs payment-api | grep ERROR

# Check license in database
docker-compose exec postgres psql -U srpk_user -d srpk_db \
  -c "SELECT * FROM licenses WHERE license_key = 'XXXX-XXXX-XXXX-XXXX';"

# Check device activations
docker-compose exec postgres psql -U srpk_user -d srpk_db \
  -c "SELECT * FROM license_activations WHERE license_key = 'XXXX-XXXX-XXXX-XXXX';"
```

## Support

For payment and licensing issues:
- Email: support@srpk.io
- Documentation: https://msc-tecnologia.github.io/SRPK/