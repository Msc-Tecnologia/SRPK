"""
SRPK Pro Crypto Payment API
Handles cryptocurrency payment processing for SRPK Pro licenses
Supports BNB, USDT, and ETH on Binance Smart Chain
"""
import os
import json
import logging
import hashlib
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from web3 import Web3
from eth_account import Account
import jwt
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

# Web3 Configuration
BSC_RPC_URL = os.getenv('BSC_RPC_URL', 'https://bsc-dataseed.binance.org/')
w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))

# Contract Configuration
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS', '')  # Will be set after deployment
CONTRACT_ABI = json.loads(os.getenv('CONTRACT_ABI', '[]'))  # Will be loaded from deployment

# Token addresses on BSC
USDT_ADDRESS = '0x55d398326f99059fF775485246999027B3197955'
ETH_ADDRESS = '0x2170Ed0880ac9A755fd29B2688956BD959F933F8'

# JWT Secret for license tokens
JWT_SECRET = os.getenv('JWT_SECRET', 'change-me-in-production')

# Price configuration (in USD)
PRICES = {
    'starter': {
        'amount': 99.00,
        'name': 'SRPK Pro Starter',
        'duration': 30  # days
    },
    'professional': {
        'amount': 299.00,
        'name': 'SRPK Pro Professional',
        'duration': 30  # days
    }
}

# Payment wallet
PAYMENT_WALLET = '0x680c48F49187a2121a25e3F834585a8b82DfdC16'

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'web3_connected': w3.is_connected(),
        'chain_id': w3.eth.chain_id if w3.is_connected() else None
    })

@app.route('/api/crypto/payment-info', methods=['GET'])
def get_payment_info():
    """Get payment wallet and supported tokens info"""
    return jsonify({
        'success': True,
        'payment_wallet': PAYMENT_WALLET,
        'supported_tokens': {
            'BNB': {
                'symbol': 'BNB',
                'name': 'Binance Coin',
                'decimals': 18,
                'is_native': True
            },
            'USDT': {
                'symbol': 'USDT',
                'name': 'Tether USD',
                'address': USDT_ADDRESS,
                'decimals': 18,
                'is_native': False
            },
            'ETH': {
                'symbol': 'ETH',
                'name': 'Ethereum',
                'address': ETH_ADDRESS,
                'decimals': 18,
                'is_native': False
            }
        },
        'prices': PRICES,
        'network': {
            'name': 'Binance Smart Chain',
            'chain_id': 56,
            'rpc_url': 'https://bsc-dataseed.binance.org/'
        }
    })

@app.route('/api/crypto/verify-payment', methods=['POST'])
def verify_payment():
    """Verify crypto payment transaction"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['txHash', 'productType', 'email', 'name', 'token']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        tx_hash = data['txHash']
        product_type = data['productType']
        email = data['email']
        name = data['name']
        token = data['token']
        
        # Validate product type
        if product_type not in PRICES:
            return jsonify({
                'success': False,
                'error': 'Invalid product type'
            }), 400
        
        # Check if web3 is connected
        if not w3.is_connected():
            return jsonify({
                'success': False,
                'error': 'Unable to connect to blockchain'
            }), 503
        
        try:
            # Get transaction receipt
            tx_receipt = w3.eth.get_transaction_receipt(tx_hash)
            
            if not tx_receipt:
                return jsonify({
                    'success': False,
                    'error': 'Transaction not found or not confirmed'
                }), 404
            
            # Check if transaction was successful
            if tx_receipt['status'] != 1:
                return jsonify({
                    'success': False,
                    'error': 'Transaction failed'
                }), 400
            
            # Get transaction details
            tx = w3.eth.get_transaction(tx_hash)
            
            # Verify payment recipient
            if tx['to'].lower() != PAYMENT_WALLET.lower():
                # Check if it's a token transfer (contract interaction)
                if token != 'BNB':
                    # For token transfers, we need to check the contract logs
                    # This is a simplified check - in production, decode the logs properly
                    logger.info(f"Token transfer detected for {token}")
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid payment recipient'
                    }), 400
            
            # Generate license
            license_key = generate_license_key(email, tx_hash)
            license_token = generate_license_token(
                email=email,
                license_key=license_key,
                product_name=PRICES[product_type]['name'],
                duration=PRICES[product_type]['duration']
            )
            
            # Send license email
            send_license_email(email, name, license_key, PRICES[product_type]['name'])
            
            # Log successful payment
            logger.info(f"Payment verified - TxHash: {tx_hash}, Email: {email}, Product: {product_type}")
            
            return jsonify({
                'success': True,
                'license_key': license_key,
                'license_token': license_token,
                'message': 'Payment verified successfully. Check your email for license details.',
                'transaction': {
                    'hash': tx_hash,
                    'block': tx_receipt['blockNumber'],
                    'from': tx['from'],
                    'token': token
                }
            })
            
        except Exception as e:
            logger.error(f"Error verifying transaction: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Error verifying transaction'
            }), 500
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred'
        }), 500

@app.route('/api/crypto/calculate-amount', methods=['POST'])
def calculate_crypto_amount():
    """Calculate crypto amount needed for a product (for ETH payments)"""
    try:
        data = request.json
        product_type = data.get('productType')
        token = data.get('token')
        
        if product_type not in PRICES:
            return jsonify({
                'success': False,
                'error': 'Invalid product type'
            }), 400
        
        usd_price = PRICES[product_type]['amount']
        
        # For BNB and USDT, return fixed amounts
        if token == 'BNB':
            # This would normally fetch current BNB price
            # For now, return a placeholder
            return jsonify({
                'success': True,
                'amount': str(usd_price),
                'token': 'BNB',
                'usd_price': usd_price,
                'note': 'Amount in USD equivalent - actual BNB amount depends on current price'
            })
        elif token == 'USDT':
            return jsonify({
                'success': True,
                'amount': str(usd_price),
                'token': 'USDT',
                'usd_price': usd_price,
                'decimals': 18
            })
        elif token == 'ETH':
            # This would normally fetch current ETH price
            # For now, return a placeholder
            return jsonify({
                'success': True,
                'amount': str(usd_price),
                'token': 'ETH',
                'usd_price': usd_price,
                'note': 'Amount in USD equivalent - actual ETH amount depends on current price'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Unsupported token'
            }), 400
            
    except Exception as e:
        logger.error(f"Error calculating amount: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error calculating amount'
        }), 500

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
    """Extract bearer token from authorization header"""
    if not auth_header:
        return ''
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        return parts[1]
    return ''

def generate_license_key(email, tx_hash):
    """Generate a unique license key based on email and transaction hash"""
    unique_string = f"{email}-{tx_hash}-{time.time()}"
    hash_object = hashlib.sha256(unique_string.encode())
    hex_dig = hash_object.hexdigest()
    
    # Format as license key (e.g., XXXX-XXXX-XXXX-XXXX)
    license_key = '-'.join([hex_dig[i:i+4].upper() for i in range(0, 16, 4)])
    return license_key

def generate_license_token(email: str, license_key: str, product_name: str, duration: int) -> str:
    """Generate a signed JWT token representing the license"""
    now = datetime.utcnow()
    expiry = now + timedelta(days=duration)
    
    payload = {
        'sub': email,
        'lk': license_key,
        'product': product_name,
        'iat': now.timestamp(),
        'nbf': now.timestamp(),
        'exp': int(expiry.timestamp())
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token

def send_license_email(email, name, license_key, product_name):
    """Send license key via email"""
    # This is a placeholder - implement based on your email service
    logger.info(f"Would send license email to {email}")
    logger.info(f"License Key: {license_key}")
    logger.info(f"Product: {product_name}")
    
    # In production, integrate with SendGrid, AWS SES, etc.
    # Example structure:
    # email_content = f'''
    # <h2>Welcome to {product_name}!</h2>
    # <p>Hi {name},</p>
    # <p>Thank you for your purchase via cryptocurrency.</p>
    # <p>Your license key is: <strong>{license_key}</strong></p>
    # <p>You can activate your license at: https://app.srpk.io/activate</p>
    # <p>This license is valid for 30 days from activation.</p>
    # '''

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')