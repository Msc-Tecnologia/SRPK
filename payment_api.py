"""
SRPK Pro Crypto Payment API
Accepts payments in native ETH/BNB and USDT via smart contract and verifies them.
"""
import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import jwt
from web3 import Web3

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

# JWT Secret for license tokens
JWT_SECRET = os.getenv('JWT_SECRET', 'change-me-in-production')

# Merchant address (recipient)
MERCHANT_ADDRESS = Web3.to_checksum_address(
    os.getenv('MERCHANT_ADDRESS', '0x680c48F49187a2121a25e3F834585a8b82DfdC16')
)

# RPC URLs (set in environment)
ETH_RPC_URL = os.getenv('ETH_RPC_URL', '')
BSC_RPC_URL = os.getenv('BSC_RPC_URL', '')

web3_clients = {
    'ethereum': Web3(Web3.HTTPProvider(ETH_RPC_URL)) if ETH_RPC_URL else None,
    'bsc': Web3(Web3.HTTPProvider(BSC_RPC_URL)) if BSC_RPC_URL else None,
}

# Contract deployment addresses (set after deploy)
CONTRACT_ADDRESS_ETH = os.getenv('CONTRACT_ADDRESS_ETH', '')
CONTRACT_ADDRESS_BSC = os.getenv('CONTRACT_ADDRESS_BSC', '')

# Token addresses
USDT_ETH_ADDRESS = os.getenv('USDT_ETH_ADDRESS', '0xdAC17F958D2ee523a2206206994597C13D831ec7')
USDT_BSC_ADDRESS = os.getenv('USDT_BSC_ADDRESS', '0x55d398326f99059fF775485246999027B3197955')

# Load ABI if available
ABI_PATH = os.getenv('PAYMENT_CONTRACT_ABI', os.path.join(os.getcwd(), 'build', 'SRPKPayments.json'))
CONTRACT_ABI = None
if os.path.exists(ABI_PATH):
    try:
        with open(ABI_PATH, 'r') as f:
            artifact = json.load(f)
            CONTRACT_ABI = artifact.get('abi') or artifact.get('ABI') or artifact
    except Exception as e:
        logger.warning(f"Could not load ABI from {ABI_PATH}: {e}")


# Price IDs mapping (USD cents for reference/display)
PRICE_IDS = {
    'price_starter': {
        'amount_usd_cents': 9900,
        'product_name': 'SRPK Pro Starter'
    },
    'price_professional': {
        'amount_usd_cents': 29900,
        'product_name': 'SRPK Pro Professional'
    }
}


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})


@app.route('/api/crypto/config', methods=['GET'])
def crypto_config():
    """Return chain and payment configuration to the frontend."""
    config = {
        'merchantAddress': MERCHANT_ADDRESS,
        'priceIds': PRICE_IDS,
        'contract': {
            'abi': CONTRACT_ABI,
            'ethereum': {
                'contractAddress': CONTRACT_ADDRESS_ETH,
                'chainId': 1,
                'nativeSymbol': 'ETH',
                'usdt': USDT_ETH_ADDRESS
            },
            'bsc': {
                'contractAddress': CONTRACT_ADDRESS_BSC,
                'chainId': 56,
                'nativeSymbol': 'BNB',
                'usdt': USDT_BSC_ADDRESS
            }
        }
    }
    return jsonify(config)


@app.route('/api/crypto/verify', methods=['POST'])
def verify_crypto_payment():
    """Verify a transaction against our payment contract events and issue license."""
    data = request.json or {}
    required_fields = ['chain', 'txHash', 'priceId', 'email']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

    chain = data['chain']
    tx_hash = data['txHash']
    price_id = data['priceId']
    email = data['email']
    name = data.get('name', '')

    if price_id not in PRICE_IDS:
        return jsonify({'success': False, 'error': 'Invalid price ID'}), 400

    if chain not in web3_clients or web3_clients[chain] is None:
        return jsonify({'success': False, 'error': f'RPC for {chain} not configured on server'}), 500

    w3 = web3_clients[chain]
    contract_address = CONTRACT_ADDRESS_ETH if chain == 'ethereum' else CONTRACT_ADDRESS_BSC

    if not contract_address:
        return jsonify({'success': False, 'error': 'Payment contract address not configured'}), 500

    if not CONTRACT_ABI:
        return jsonify({'success': False, 'error': 'Payment contract ABI not available'}), 500

    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as e:
        logger.error(f"Error fetching receipt: {e}")
        return jsonify({'success': False, 'error': 'Transaction not found yet. Try again shortly.'}), 404

    if receipt.status != 1:
        return jsonify({'success': False, 'error': 'Transaction failed'}), 400

    contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=CONTRACT_ABI)

    # Parse PaymentReceived event
    event_abi = next((e for e in CONTRACT_ABI if e.get('type') == 'event' and e.get('name') == 'PaymentReceived'), None)
    if not event_abi:
        return jsonify({'success': False, 'error': 'PaymentReceived event ABI missing'}), 500

    logs_for_contract = [log for log in receipt.logs if log.address.lower() == contract.address.lower()]
    matched = None
    for log in logs_for_contract:
        try:
            decoded = contract.events.PaymentReceived().process_log(log)
            matched = decoded
            break
        except Exception:
            continue

    if not matched:
        return jsonify({'success': False, 'error': 'No matching payment event found in transaction'}), 400

    args = matched['args']
    payer = args.get('payer')
    token = args.get('token')
    amount = args.get('amount')
    product_id_onchain = args.get('productId')

    if product_id_onchain != price_id:
        return jsonify({'success': False, 'error': 'Product mismatch'}), 400

    # Basic sanity: ensure tokens routed to merchant via contract
    if receipt.to and receipt.to.lower() != contract.address.lower():
        return jsonify({'success': False, 'error': 'Transaction not sent to payment contract'}), 400

    # Issue license
    product_name = PRICE_IDS[price_id]['product_name']
    license_key = generate_license_key(payer, tx_hash)
    send_license_email(email, name or email, license_key, product_name)
    license_token = generate_license_token(email=email, license_key=license_key, product_name=product_name)

    return jsonify({
        'success': True,
        'payer': payer,
        'token': token,
        'amount': str(amount),
        'license_key': license_key,
        'license_token': license_token
    })


def generate_license_token(email: str, license_key: str, product_name: str) -> str:
    payload = {
        'sub': email,
        'lk': license_key,
        'product': product_name,
        'iat': datetime.utcnow().timestamp(),
        'nbf': datetime.utcnow().timestamp(),
        'exp': int(datetime.utcnow().timestamp()) + 60 * 60 * 24 * 30
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token


@app.route('/api/licenses/verify', methods=['GET'])
def verify_license():
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
    import hashlib
    import time
    unique_string = f"{customer_id}-{subscription_id}-{time.time()}"
    hex_dig = hashlib.sha256(unique_string.encode()).hexdigest()
    license_key = '-'.join([hex_dig[i:i+4].upper() for i in range(0, 16, 4)])
    return license_key


def send_license_email(email, name, license_key, product_name):
    logger.info(f"Would send license email to {email}")
    logger.info(f"License Key: {license_key}")
    logger.info(f"Product: {product_name}")


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')