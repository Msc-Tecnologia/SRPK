"""
SRPK Pro Payment API
Handles Stripe payment processing for SRPK Pro licenses
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import stripe
import paypalrestsdk
from dotenv import load_dotenv

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
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

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
            
            return jsonify({
                'success': True,
                'subscription_id': subscription.id,
                'customer_id': customer.id,
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

@app.route('/api/process-paypal-payment', methods=['POST'])
def process_paypal_payment():
    """Process PayPal payment for SRPK Pro license"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['paymentId', 'payerId', 'priceId', 'email', 'name']
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
        
        # Execute PayPal payment
        payment = paypalrestsdk.Payment.find(data['paymentId'])
        
        if payment.execute({"payer_id": data['payerId']}):
            logger.info(f"PayPal payment executed successfully: {payment.id}")
            
            # Create customer record
            try:
                # Generate license key
                license_key = generate_license_key(data['email'], payment.id)
                
                # Send license email
                send_license_email(
                    data['email'], 
                    data['name'], 
                    license_key, 
                    price_info['product_name']
                )
                
                # Store payment record (implement database storage)
                store_paypal_payment({
                    'payment_id': payment.id,
                    'email': data['email'],
                    'name': data['name'],
                    'product': price_info['product_name'],
                    'amount': price_info['amount'],
                    'license_key': license_key
                })
                
                return jsonify({
                    'success': True,
                    'payment_id': payment.id,
                    'message': 'Payment processed successfully. Check your email for license details.'
                })
            
            except Exception as e:
                logger.error(f"Error processing PayPal payment: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': 'Error creating license. Please contact support.'
                }), 500
        else:
            logger.error(f"PayPal payment execution failed: {payment.error}")
            return jsonify({
                'success': False,
                'error': 'Payment execution failed. Please try again.'
            }), 400
    
    except Exception as e:
        logger.error(f"Unexpected PayPal error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again later.'
        }), 500

@app.route('/api/create-paypal-payment', methods=['POST'])
def create_paypal_payment():
    """Create PayPal payment for approval"""
    try:
        data = request.json
        
        # Validate price ID
        price_id = data.get('priceId')
        if price_id not in PRICE_IDS:
            return jsonify({
                'success': False,
                'error': 'Invalid price ID'
            }), 400
        
        price_info = PRICE_IDS[price_id]
        
        # Create PayPal payment
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {
                "payment_method": "paypal"
            },
            "redirect_urls": {
                "return_url": f"{os.getenv('APP_URL')}/payment/success",
                "cancel_url": f"{os.getenv('APP_URL')}/payment/cancel"
            },
            "transactions": [{
                "item_list": {
                    "items": [{
                        "name": price_info['product_name'],
                        "sku": price_id,
                        "price": str(price_info['amount'] / 100),
                        "currency": price_info['currency'].upper(),
                        "quantity": 1
                    }]
                },
                "amount": {
                    "total": str(price_info['amount'] / 100),
                    "currency": price_info['currency'].upper()
                },
                "description": f"{price_info['product_name']} License"
            }]
        })
        
        if payment.create():
            logger.info(f"PayPal payment created: {payment.id}")
            
            # Find approval URL
            approval_url = None
            for link in payment.links:
                if link.rel == "approval_url":
                    approval_url = link.href
                    break
            
            return jsonify({
                'success': True,
                'paymentId': payment.id,
                'approvalUrl': approval_url
            })
        else:
            logger.error(f"PayPal payment creation failed: {payment.error}")
            return jsonify({
                'success': False,
                'error': 'Failed to create payment. Please try again.'
            }), 400
    
    except Exception as e:
        logger.error(f"Unexpected error creating PayPal payment: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again later.'
        }), 500

def store_paypal_payment(payment_data):
    """Store PayPal payment record in database"""
    # This is a placeholder - implement based on your database schema
    logger.info(f"Would store PayPal payment: {payment_data}")
    # Example implementation:
    # db.session.add(PayPalPayment(**payment_data))
    # db.session.commit()

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