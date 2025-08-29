"""
SRPK Pro Payment API
Handles Stripe payment processing for SRPK Pro licenses
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import stripe
from dotenv import load_dotenv
import paypalrestsdk
import jwt

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, origins=os.getenv('ALLOWED_ORIGINS', '*').split(','))

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Configure PayPal
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),  # sandbox or live
    "client_id": os.getenv('PAYPAL_CLIENT_ID', ''),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET', '')
})

# JWT Secret for license tokens
JWT_SECRET = os.getenv('JWT_SECRET', 'change-me-in-production')

# Price IDs mapping
PRICE_IDS = {
    'price_starter': {
        'amount': 9900,  # $99.00 in cents
        'currency': 'usd',
        'interval': 'month',
        'product_name': 'SRPK Pro Starter'
    },
    'price_professional': {
        'amount': 29900,  # $299.00 in cents
        'currency': 'usd',
        'interval': 'month',
        'product_name': 'SRPK Pro Professional'
    }
}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/process-payment', methods=['POST'])
def process_payment():
    """Process Stripe payment for SRPK Pro license"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['token', 'priceId', 'email', 'name']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Validate price ID
        price_id = data['priceId']
        if price_id not in PRICE_IDS:
            return jsonify({
                'success': False,
                'error': 'Invalid price ID'
            }), 400
        
        price_info = PRICE_IDS[price_id]
        
        # Create or retrieve customer
        try:
            # Check if customer exists
            customers = stripe.Customer.list(email=data['email'], limit=1)
            
            if customers.data:
                customer = customers.data[0]
                logger.info(f"Retrieved existing customer: {customer.id}")
            else:
                # Create new customer
                customer = stripe.Customer.create(
                    email=data['email'],
                    name=data['name'],
                    source=data['token'],
                    metadata={
                        'company': data.get('company', ''),
                        'product': price_info['product_name']
                    }
                )
                logger.info(f"Created new customer: {customer.id}")
        
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Error creating customer account'
            }), 400
        
        # Create subscription
        try:
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{
                    'price': price_id,
                }],
                metadata={
                    'product': price_info['product_name'],
                    'customer_name': data['name'],
                    'company': data.get('company', '')
                }
            )
            
            logger.info(f"Created subscription: {subscription.id}")
            
            # Send license key email (implement this based on your email service)
            license_key = generate_license_key(customer.id, subscription.id)
            send_license_email(data['email'], data['name'], license_key, price_info['product_name'])
            license_token = generate_license_token(email=data['email'], license_key=license_key, product_name=price_info['product_name'])
            
            return jsonify({
                'success': True,
                'subscription_id': subscription.id,
                'customer_id': customer.id,
                'license_key': license_key,
                'license_token': license_token,
                'message': 'Payment processed successfully. Check your email for license details.'
            })
        
        except stripe.error.CardError as e:
            logger.error(f"Card error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Your card was declined. Please check your card details and try again.'
            }), 400
        
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Error processing subscription. Please try again.'
            }), 400
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again later.'
        }), 500

@app.route('/api/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        logger.error("Invalid payload")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature")
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    if event['type'] == 'subscription.created':
        subscription = event['data']['object']
        logger.info(f"Subscription created: {subscription['id']}")
        
    elif event['type'] == 'subscription.updated':
        subscription = event['data']['object']
        logger.info(f"Subscription updated: {subscription['id']}")
        
    elif event['type'] == 'subscription.deleted':
        subscription = event['data']['object']
        logger.info(f"Subscription cancelled: {subscription['id']}")
        # Handle license deactivation
        
    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        logger.info(f"Payment succeeded for invoice: {invoice['id']}")
        
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        logger.info(f"Payment failed for invoice: {invoice['id']}")
        # Send payment failure notification
    
    return jsonify({'received': True})

@app.route('/api/paypal/create-payment', methods=['POST'])
def paypal_create_payment():
    """Create PayPal payment and return approval URL"""
    try:
        data = request.json or {}
        required_fields = ['priceId', 'email', 'name', 'returnUrl', 'cancelUrl']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

        price_id = data['priceId']
        if price_id not in PRICE_IDS:
            return jsonify({'success': False, 'error': 'Invalid price ID'}), 400

        price_info = PRICE_IDS[price_id]

        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "redirect_urls": {
                "return_url": data['returnUrl'],
                "cancel_url": data['cancelUrl']
            },
            "transactions": [{
                "item_list": {
                    "items": [{
                        "name": price_info['product_name'],
                        "sku": price_id,
                        "price": f"{price_info['amount'] / 100:.2f}",
                        "currency": price_info['currency'].upper(),
                        "quantity": 1
                    }]
                },
                "amount": {
                    "total": f"{price_info['amount'] / 100:.2f}",
                    "currency": price_info['currency'].upper()
                },
                "description": f"Subscription to {price_info['product_name']}"
            }]
        })

        if payment.create():
            approval_url = next((link.href for link in payment.links if link.rel == "approval_url"), None)
            return jsonify({
                'success': True,
                'payment_id': payment.id,
                'approval_url': approval_url
            })
        else:
            logger.error(f"PayPal create payment error: {payment.error}")
            return jsonify({'success': False, 'error': 'Error creating PayPal payment'}), 400

    except Exception as e:
        logger.error(f"Unexpected error (PayPal create): {str(e)}")
        return jsonify({'success': False, 'error': 'Unexpected error'}), 500


@app.route('/api/paypal/execute-payment', methods=['POST'])
def paypal_execute_payment():
    """Execute PayPal payment after approval and issue license"""
    try:
        data = request.json or {}
        required_fields = ['paymentId', 'PayerID', 'priceId', 'email', 'name']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

        payment = paypalrestsdk.Payment.find(data['paymentId'])
        if payment.execute({"payer_id": data['PayerID']}):
            price_info = PRICE_IDS.get(data['priceId'])
            if not price_info:
                return jsonify({'success': False, 'error': 'Invalid price ID'}), 400

            # Generate license and token
            customer_id = payment.payer.payer_info.payer_id if hasattr(payment, 'payer') else data['email']
            subscription_id = payment.id
            license_key = generate_license_key(customer_id, subscription_id)
            send_license_email(data['email'], data['name'], license_key, price_info['product_name'])
            license_token = generate_license_token(email=data['email'], license_key=license_key, product_name=price_info['product_name'])

            return jsonify({
                'success': True,
                'payment_id': payment.id,
                'license_key': license_key,
                'license_token': license_token,
                'message': 'Payment processed successfully. Check your email for license details.'
            })
        else:
            logger.error(f"PayPal execute error: {payment.error}")
            return jsonify({'success': False, 'error': 'Error executing PayPal payment'}), 400

    except Exception as e:
        logger.error(f"Unexpected error (PayPal execute): {str(e)}")
        return jsonify({'success': False, 'error': 'Unexpected error'}), 500


def generate_license_token(email: str, license_key: str, product_name: str) -> str:
    """Generate a signed JWT token representing the license"""
    payload = {
        'sub': email,
        'lk': license_key,
        'product': product_name,
        'iat': datetime.utcnow().timestamp(),
        'nbf': datetime.utcnow().timestamp(),
        'exp': int(datetime.utcnow().timestamp()) + 60 * 60 * 24 * 30  # 30 days
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token


@app.route('/api/licenses/verify', methods=['GET'])
def verify_license():
    """Verify license token validity"""
    token = request.args.get('token') or _extract_bearer_token(request.headers.get('Authorization', ''))
    if not token:
        return jsonify({'valid': False, 'error': 'Missing token'}), 400
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return jsonify({'valid': True, 'claims': claims})
    except jwt.ExpiredSignatureError:
        return jsonify({'valid': False, 'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'valid': False, 'error': 'Invalid token'}), 401


def _extract_bearer_token(auth_header: str) -> str:
    if not auth_header:
        return ''
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        return parts[1]
    return ''


ALLOWED_DOWNLOADS = {
    'SRPK Pro Starter': ['srpk-starter.zip'],
    'SRPK Pro Professional': ['srpk-professional.zip']
}


@app.route('/api/downloads', methods=['GET'])
def secure_download():
    """Serve product downloads if token is valid and file allowed"""
    token = request.args.get('token') or _extract_bearer_token(request.headers.get('Authorization', ''))
    filename = request.args.get('file')
    if not token or not filename:
        return jsonify({'success': False, 'error': 'Missing token or file parameter'}), 400
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        product = claims.get('product')
        allowed = ALLOWED_DOWNLOADS.get(product, [])
        if filename not in allowed:
            return jsonify({'success': False, 'error': 'File not allowed for this license'}), 403
        downloads_dir = os.getenv('DOWNLOADS_DIR', os.path.join(os.getcwd(), 'downloads'))
        return send_from_directory(directory=downloads_dir, path=filename, as_attachment=True)
    except jwt.ExpiredSignatureError:
        return jsonify({'success': False, 'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'success': False, 'error': 'Invalid token'}), 401

def generate_license_key(customer_id, subscription_id):
    """Generate a unique license key"""
    import hashlib
    import time
    
    # Create a unique string based on customer and subscription
    unique_string = f"{customer_id}-{subscription_id}-{time.time()}"
    
    # Generate hash
    hash_object = hashlib.sha256(unique_string.encode())
    hex_dig = hash_object.hexdigest()
    
    # Format as license key (e.g., XXXX-XXXX-XXXX-XXXX)
    license_key = '-'.join([hex_dig[i:i+4].upper() for i in range(0, 16, 4)])
    
    return license_key

def send_license_email(email, name, license_key, product_name):
    """Send license key via email"""
    # This is a placeholder - implement based on your email service
    # Options: SendGrid, AWS SES, Mailgun, etc.
    logger.info(f"Would send license email to {email}")
    logger.info(f"License Key: {license_key}")
    logger.info(f"Product: {product_name}")
    
    # Example implementation with SendGrid:
    # import sendgrid
    # sg = sendgrid.SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))
    # message = Mail(
    #     from_email='licenses@srpk.io',
    #     to_emails=email,
    #     subject=f'Your {product_name} License',
    #     html_content=f'''
    #     <h2>Welcome to {product_name}!</h2>
    #     <p>Hi {name},</p>
    #     <p>Thank you for your purchase. Your license key is:</p>
    #     <h3>{license_key}</h3>
    #     <p>You can activate your license at: https://app.srpk.io/activate</p>
    #     '''
    # )
    # sg.send(message)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')