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
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Flask, request, jsonify
from flask_cors import CORS
from web3 import Web3
from eth_account import Account
import jwt
from dotenv import load_dotenv
import redis
import psycopg2
from psycopg2.extras import RealDictCursor

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
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS', '')
CONTRACT_ABI = json.loads(os.getenv('CONTRACT_ABI', '[]'))

# Token addresses on BSC
USDT_ADDRESS = '0x55d398326f99059fF775485246999027B3197955'
ETH_ADDRESS = '0x2170Ed0880ac9A755fd29B2688956BD959F933F8'

# ERC20 ABI for token interactions
ERC20_ABI = json.loads('[{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"}]')

# JWT Secret for license tokens
JWT_SECRET = os.getenv('JWT_SECRET', 'change-me-in-production')

# Email Configuration
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASS = os.getenv('SMTP_PASS', '')
EMAIL_FROM = os.getenv('EMAIL_FROM', 'noreply@srpk.io')

# Redis Configuration
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    decode_responses=True
)

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', '')

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

# Price feed APIs
PRICE_APIS = {
    'coingecko': 'https://api.coingecko.com/api/v3/simple/price',
    'binance': 'https://api.binance.com/api/v3/ticker/price'
}

def get_db_connection():
    """Get PostgreSQL database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return None

def get_token_price(token_symbol):
    """Get current token price in USD from multiple sources"""
    cache_key = f"price:{token_symbol}"
    
    # Check Redis cache (5 minute TTL)
    cached_price = redis_client.get(cache_key)
    if cached_price:
        return float(cached_price)
    
    price = None
    
    try:
        # Try CoinGecko first
        token_ids = {
            'BNB': 'binancecoin',
            'ETH': 'ethereum',
            'USDT': 'tether'
        }
        
        if token_symbol in token_ids:
            response = requests.get(
                PRICE_APIS['coingecko'],
                params={
                    'ids': token_ids[token_symbol],
                    'vs_currencies': 'usd'
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                price = data[token_ids[token_symbol]]['usd']
    
    except Exception as e:
        logger.error(f"CoinGecko API error: {str(e)}")
    
    # Fallback to Binance
    if price is None:
        try:
            symbol_map = {
                'BNB': 'BNBUSDT',
                'ETH': 'ETHUSDT',
                'USDT': None  # USDT is always $1
            }
            
            if token_symbol == 'USDT':
                price = 1.0
            elif token_symbol in symbol_map:
                response = requests.get(
                    f"{PRICE_APIS['binance']}",
                    params={'symbol': symbol_map[token_symbol]},
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    price = float(data['price'])
        
        except Exception as e:
            logger.error(f"Binance API error: {str(e)}")
    
    # Cache the price if found
    if price:
        redis_client.setex(cache_key, 300, str(price))  # 5 minute cache
        return price
    
    # Return default prices as fallback
    default_prices = {
        'BNB': 300.0,
        'ETH': 2000.0,
        'USDT': 1.0
    }
    
    return default_prices.get(token_symbol, 0)

def send_license_email_real(email, name, license_key, product_name, tx_hash):
    """Send license key via email using SMTP"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Tu Licencia {product_name} - SRPK Pro'
        msg['From'] = EMAIL_FROM
        msg['To'] = email
        
        # Create the HTML body
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
              <div style="background: linear-gradient(135deg, #4e72ff 0%, #667eea 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0;">
                <h1 style="margin: 0; font-size: 28px;">¡Bienvenido a SRPK Pro!</h1>
              </div>
              
              <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px;">
                <p style="font-size: 16px;">Hola <strong>{name}</strong>,</p>
                
                <p>Gracias por tu compra de <strong>{product_name}</strong>. Tu pago ha sido verificado exitosamente en la blockchain.</p>
                
                <div style="background: white; border: 2px solid #4e72ff; border-radius: 8px; padding: 20px; margin: 20px 0;">
                  <h3 style="color: #4e72ff; margin-top: 0;">Tu Licencia:</h3>
                  <p style="font-family: monospace; font-size: 18px; color: #333; word-break: break-all; background: #f0f0f0; padding: 10px; border-radius: 4px;">
                    {license_key}
                  </p>
                </div>
                
                <div style="background: #e8f4f8; border-left: 4px solid #4e72ff; padding: 15px; margin: 20px 0;">
                  <h4 style="margin-top: 0; color: #4e72ff;">Detalles de la Transacción:</h4>
                  <p style="margin: 5px 0;"><strong>Hash:</strong> <a href="https://bscscan.com/tx/{tx_hash}" style="color: #4e72ff; text-decoration: none;">{tx_hash[:16]}...</a></p>
                  <p style="margin: 5px 0;"><strong>Producto:</strong> {product_name}</p>
                  <p style="margin: 5px 0;"><strong>Duración:</strong> 30 días</p>
                  <p style="margin: 5px 0;"><strong>Válido hasta:</strong> {(datetime.utcnow() + timedelta(days=30)).strftime('%d/%m/%Y')}</p>
                </div>
                
                <h3 style="color: #333; margin-top: 30px;">Próximos Pasos:</h3>
                <ol style="color: #666;">
                  <li>Descarga SRPK Pro desde <a href="https://github.com/srpkio/srpk-pro" style="color: #4e72ff;">nuestro repositorio</a></li>
                  <li>Instala las dependencias con <code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px;">pip install -r requirements.txt</code></li>
                  <li>Activa tu licencia con el comando: <code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px;">srpk activate {license_key}</code></li>
                </ol>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666;">
                  <p>¿Necesitas ayuda? Contáctanos en <a href="mailto:support@srpk.io" style="color: #4e72ff;">support@srpk.io</a></p>
                  <p style="font-size: 12px; margin-top: 10px;">
                    Este email fue enviado porque realizaste una compra en SRPK Pro.<br>
                    Transacción verificada en Binance Smart Chain.
                  </p>
                </div>
              </div>
            </div>
          </body>
        </html>
        """
        
        # Attach HTML
        part = MIMEText(html, 'html')
        msg.attach(part)
        
        # Send email
        if SMTP_USER and SMTP_PASS:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            
            logger.info(f"License email sent to {email}")
            return True
        else:
            logger.warning("SMTP credentials not configured, email not sent")
            return False
            
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False

def verify_token_transfer(tx_hash, token_address, expected_amount):
    """Verify ERC20 token transfer in transaction"""
    try:
        # Get transaction receipt
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        
        if not receipt or receipt['status'] != 1:
            return False
        
        # Check logs for Transfer event
        # Transfer event signature: Transfer(address,address,uint256)
        transfer_event_signature = w3.keccak(text="Transfer(address,address,uint256)").hex()
        
        for log in receipt['logs']:
            if (log['address'].lower() == token_address.lower() and 
                len(log['topics']) > 0 and 
                log['topics'][0].hex() == transfer_event_signature):
                
                # Decode transfer data
                # topics[1] = from address (padded)
                # topics[2] = to address (padded)
                # data = amount
                
                to_address = '0x' + log['topics'][2].hex()[-40:]
                amount = int(log['data'], 16)
                
                # Get token decimals
                token_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=ERC20_ABI
                )
                decimals = token_contract.functions.decimals().call()
                
                # Check if transfer is to our payment wallet
                if (to_address.lower() == PAYMENT_WALLET.lower() and 
                    amount >= expected_amount * (10 ** decimals)):
                    return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error verifying token transfer: {str(e)}")
        return False

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'web3_connected': w3.is_connected(),
        'chain_id': w3.eth.chain_id if w3.is_connected() else None,
        'redis_connected': redis_client.ping(),
        'database_connected': False
    }
    
    # Check database
    conn = get_db_connection()
    if conn:
        health_status['database_connected'] = True
        conn.close()
    
    return jsonify(health_status)

@app.route('/api/crypto/payment-info', methods=['GET'])
def get_payment_info():
    """Get payment wallet and supported tokens info with current prices"""
    prices = {
        'BNB': get_token_price('BNB'),
        'USDT': get_token_price('USDT'),
        'ETH': get_token_price('ETH')
    }
    
    return jsonify({
        'success': True,
        'payment_wallet': PAYMENT_WALLET,
        'supported_tokens': {
            'BNB': {
                'symbol': 'BNB',
                'name': 'Binance Coin',
                'decimals': 18,
                'is_native': True,
                'current_price_usd': prices['BNB']
            },
            'USDT': {
                'symbol': 'USDT',
                'name': 'Tether USD',
                'address': USDT_ADDRESS,
                'decimals': 18,
                'is_native': False,
                'current_price_usd': prices['USDT']
            },
            'ETH': {
                'symbol': 'ETH',
                'name': 'Ethereum',
                'address': ETH_ADDRESS,
                'decimals': 18,
                'is_native': False,
                'current_price_usd': prices['ETH']
            }
        },
        'prices': PRICES,
        'network': {
            'name': 'Binance Smart Chain',
            'chain_id': 56,
            'rpc_url': 'https://bsc-dataseed.binance.org/'
        }
    })

@app.route('/api/crypto/calculate-amount', methods=['POST'])
def calculate_crypto_amount():
    """Calculate crypto amount needed for a product based on current prices"""
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
        token_price = get_token_price(token)
        
        if not token_price:
            return jsonify({
                'success': False,
                'error': 'Unable to fetch token price'
            }), 500
        
        # Calculate amount needed
        if token == 'USDT':
            # USDT is 1:1 with USD
            crypto_amount = usd_price
        else:
            # Calculate based on current price
            crypto_amount = usd_price / token_price
        
        return jsonify({
            'success': True,
            'amount': f"{crypto_amount:.6f}",
            'amount_wei': str(int(crypto_amount * 10**18)),  # For smart contract
            'token': token,
            'usd_price': usd_price,
            'token_price_usd': token_price,
            'decimals': 18,
            'expires_in': 300  # Price valid for 5 minutes
        })
            
    except Exception as e:
        logger.error(f"Error calculating amount: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error calculating amount'
        }), 500

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
        
        # Check if transaction already processed
        cache_key = f"tx:{tx_hash}"
        if redis_client.exists(cache_key):
            return jsonify({
                'success': False,
                'error': 'Transaction already processed'
            }), 400
        
        # Get transaction receipt
        try:
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
            
            # Calculate expected amount
            usd_price = PRICES[product_type]['amount']
            token_price = get_token_price(token)
            expected_amount = usd_price / token_price if token != 'USDT' else usd_price
            
            # Verify payment based on token type
            payment_valid = False
            
            if token == 'BNB':
                # For BNB, check direct transfer
                if (tx['to'].lower() == PAYMENT_WALLET.lower() and 
                    Web3.from_wei(tx['value'], 'ether') >= Decimal(str(expected_amount)) * Decimal('0.95')):  # 5% price tolerance
                    payment_valid = True
            else:
                # For tokens, check Transfer event
                token_address = USDT_ADDRESS if token == 'USDT' else ETH_ADDRESS
                payment_valid = verify_token_transfer(tx_hash, token_address, expected_amount * 0.95)  # 5% price tolerance
            
            if not payment_valid:
                return jsonify({
                    'success': False,
                    'error': 'Invalid payment amount or recipient'
                }), 400
            
            # Generate license
            license_key = generate_license_key(email, tx_hash)
            license_token = generate_license_token(
                email=email,
                license_key=license_key,
                product_name=PRICES[product_type]['name'],
                duration=PRICES[product_type]['duration']
            )
            
            # Save to database
            save_payment_to_db(
                tx_hash=tx_hash,
                email=email,
                name=name,
                product_type=product_type,
                token=token,
                amount=str(expected_amount),
                license_key=license_key
            )
            
            # Mark transaction as processed
            redis_client.setex(cache_key, 86400, "processed")  # 24 hour TTL
            
            # Send license email
            send_license_email_real(email, name, license_key, PRICES[product_type]['name'], tx_hash)
            
            # Log successful payment
            logger.info(f"Payment verified - TxHash: {tx_hash}, Email: {email}, Product: {product_type}, Token: {token}")
            
            return jsonify({
                'success': True,
                'license_key': license_key,
                'license_token': license_token,
                'message': 'Payment verified successfully. Check your email for license details.',
                'transaction': {
                    'hash': tx_hash,
                    'block': tx_receipt['blockNumber'],
                    'from': tx['from'],
                    'token': token,
                    'amount': str(expected_amount)
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

@app.route('/api/licenses/verify', methods=['GET'])
def verify_license():
    """Verify license token validity"""
    token = request.args.get('token') or _extract_bearer_token(request.headers.get('Authorization', ''))
    if not token:
        return jsonify({'valid': False, 'error': 'Missing token'}), 400
    
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        
        # Check if license exists in database
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM licenses WHERE license_key = %s AND expiry_time > NOW()",
                (claims.get('lk'),)
            )
            license_data = cur.fetchone()
            cur.close()
            conn.close()
            
            if license_data:
                return jsonify({
                    'valid': True,
                    'claims': claims,
                    'license': dict(license_data)
                })
        
        return jsonify({
            'valid': True,
            'claims': claims,
            'warning': 'License not found in database'
        })
        
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

def save_payment_to_db(tx_hash, email, name, product_type, token, amount, license_key):
    """Save payment and license information to database"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Could not connect to database")
            return False
        
        cur = conn.cursor()
        
        # Insert payment record
        cur.execute("""
            INSERT INTO crypto_payments 
            (tx_hash, email, name, product_type, token, amount, license_key, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            tx_hash,
            email,
            name,
            product_type,
            token,
            amount,
            license_key,
            datetime.utcnow()
        ))
        
        # Insert license record
        cur.execute("""
            INSERT INTO licenses 
            (license_key, email, product_type, created_at, expiry_time, tx_hash, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            license_key,
            email,
            PRICES[product_type]['name'],
            datetime.utcnow(),
            datetime.utcnow() + timedelta(days=PRICES[product_type]['duration']),
            tx_hash,
            True
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
        return False

@app.route('/api/crypto/webhook/register', methods=['POST'])
def register_webhook():
    """Register a webhook for payment notifications"""
    try:
        data = request.json
        webhook_url = data.get('url')
        events = data.get('events', ['payment.confirmed'])
        
        if not webhook_url:
            return jsonify({
                'success': False,
                'error': 'Missing webhook URL'
            }), 400
        
        # Save webhook to Redis
        webhook_id = hashlib.sha256(webhook_url.encode()).hexdigest()[:16]
        webhook_data = {
            'url': webhook_url,
            'events': events,
            'created_at': datetime.utcnow().isoformat()
        }
        
        redis_client.hset(f"webhook:{webhook_id}", mapping=webhook_data)
        
        return jsonify({
            'success': True,
            'webhook_id': webhook_id,
            'message': 'Webhook registered successfully'
        })
        
    except Exception as e:
        logger.error(f"Error registering webhook: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error registering webhook'
        }), 500

@app.route('/api/crypto/prices/history', methods=['GET'])
def get_price_history():
    """Get historical price data for tokens"""
    token = request.args.get('token', 'BNB')
    days = int(request.args.get('days', 7))
    
    try:
        # This would integrate with a price history API or database
        # For now, return sample data
        history = []
        current_price = get_token_price(token)
        
        for i in range(days):
            date = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
            # Simulate price variations
            price = current_price * (1 + (0.1 * (0.5 - i/days)))
            history.append({
                'date': date,
                'price': round(price, 2)
            })
        
        return jsonify({
            'success': True,
            'token': token,
            'history': list(reversed(history))
        })
        
    except Exception as e:
        logger.error(f"Error getting price history: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error fetching price history'
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')