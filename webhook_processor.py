"""
SRPK Pro Webhook Processor
Monitors blockchain events and sends webhook notifications
"""
import os
import json
import time
import logging
import requests
import threading
from datetime import datetime
from queue import Queue
from web3 import Web3
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

# Web3 Configuration
BSC_RPC_URL = os.getenv('BSC_RPC_URL', 'https://bsc-dataseed.binance.org/')
w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))

# Contract addresses and ABIs
PAYMENT_CONTRACT_ADDRESS = os.getenv('PAYMENT_CONTRACT_ADDRESS', '')
WEBHOOK_CONTRACT_ADDRESS = os.getenv('WEBHOOK_CONTRACT_ADDRESS', '')

# Redis Configuration
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    decode_responses=True
)

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', '')

# Event signatures
EVENT_SIGNATURES = {
    'PaymentReceived': w3.keccak(text='PaymentReceived(address,string,uint256,string)').hex(),
    'LicensePurchased': w3.keccak(text='LicensePurchased(address,string,string,string,uint256,string,uint256)').hex(),
    'LicenseRevoked': w3.keccak(text='LicenseRevoked(string,address)').hex(),
    'WebhookTriggered': w3.keccak(text='WebhookTriggered(bytes32,uint8,bytes)').hex()
}

# Event type mapping
EVENT_TYPES = {
    0: 'payment.received',
    1: 'license.created',
    2: 'license.expired',
    3: 'license.revoked',
    4: 'price.updated'
}

class WebhookProcessor:
    def __init__(self):
        self.webhook_queue = Queue()
        self.processing = False
        self.last_block = self.get_last_processed_block()
        
    def get_db_connection(self):
        """Get PostgreSQL database connection"""
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return conn
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            return None
    
    def get_last_processed_block(self):
        """Get the last processed block from Redis or database"""
        last_block = redis_client.get('last_processed_block')
        if last_block:
            return int(last_block)
        
        # Default to current block minus 100
        return w3.eth.block_number - 100
    
    def save_last_processed_block(self, block_number):
        """Save the last processed block"""
        redis_client.set('last_processed_block', str(block_number))
    
    def process_webhook_event(self, event):
        """Process a webhook event from the blockchain"""
        try:
            # Decode event data
            webhook_id = event['args']['webhookId']
            event_type = event['args']['eventType']
            event_data = event['args']['data']
            
            # Get webhook details from Redis
            webhook_key = f"webhook:{webhook_id.hex()}"
            webhook_data = redis_client.hgetall(webhook_key)
            
            if not webhook_data or not webhook_data.get('url'):
                logger.warning(f"Webhook not found: {webhook_id.hex()}")
                return
            
            # Prepare notification payload
            payload = {
                'event': EVENT_TYPES.get(event_type, 'unknown'),
                'timestamp': datetime.utcnow().isoformat(),
                'block_number': event['blockNumber'],
                'transaction_hash': event['transactionHash'].hex(),
                'data': self.decode_event_data(event_type, event_data)
            }
            
            # Add to webhook queue
            self.webhook_queue.put({
                'url': webhook_data['url'],
                'payload': payload,
                'webhook_id': webhook_id.hex(),
                'retry_count': 0
            })
            
        except Exception as e:
            logger.error(f"Error processing webhook event: {str(e)}")
    
    def decode_event_data(self, event_type, data):
        """Decode event data based on event type"""
        try:
            if event_type == 0:  # PaymentReceived
                decoded = w3.codec.decode_abi(
                    ['address', 'string', 'uint256', 'string', 'uint256'],
                    data
                )
                return {
                    'buyer': decoded[0],
                    'product_type': decoded[1],
                    'amount': str(decoded[2]),
                    'token': decoded[3],
                    'timestamp': decoded[4]
                }
            
            elif event_type == 1:  # LicenseCreated
                decoded = w3.codec.decode_abi(
                    ['address', 'string', 'string', 'string', 'uint256', 'string'],
                    data
                )
                return {
                    'buyer': decoded[0],
                    'email': decoded[1],
                    'product_type': decoded[2],
                    'payment_token': decoded[3],
                    'amount': str(decoded[4]),
                    'license_key': decoded[5]
                }
            
            elif event_type == 3:  # LicenseRevoked
                decoded = w3.codec.decode_abi(['string', 'address'], data)
                return {
                    'license_key': decoded[0],
                    'buyer': decoded[1]
                }
            
            else:
                return {'raw_data': data.hex()}
                
        except Exception as e:
            logger.error(f"Error decoding event data: {str(e)}")
            return {'raw_data': data.hex()}
    
    def send_webhook(self, webhook_data):
        """Send webhook notification"""
        max_retries = 3
        retry_delay = 5
        
        url = webhook_data['url']
        payload = webhook_data['payload']
        webhook_id = webhook_data['webhook_id']
        retry_count = webhook_data['retry_count']
        
        try:
            # Add signature for security
            signature = self.generate_webhook_signature(payload)
            
            headers = {
                'Content-Type': 'application/json',
                'X-SRPK-Signature': signature,
                'X-SRPK-Webhook-ID': webhook_id
            }
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Webhook sent successfully to {url}")
                self.log_webhook_delivery(webhook_id, True, response.status_code)
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"Error sending webhook to {url}: {str(e)}")
            
            # Retry logic
            if retry_count < max_retries:
                webhook_data['retry_count'] += 1
                time.sleep(retry_delay * (retry_count + 1))
                self.webhook_queue.put(webhook_data)
            else:
                self.log_webhook_delivery(webhook_id, False, str(e))
    
    def generate_webhook_signature(self, payload):
        """Generate HMAC signature for webhook payload"""
        import hmac
        import hashlib
        
        secret = os.getenv('WEBHOOK_SECRET', 'default-secret')
        payload_str = json.dumps(payload, sort_keys=True)
        
        signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def log_webhook_delivery(self, webhook_id, success, details):
        """Log webhook delivery attempt"""
        try:
            conn = self.get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO webhook_logs 
                    (webhook_id, success, details, created_at)
                    VALUES (%s, %s, %s, %s)
                """, (webhook_id, success, str(details), datetime.utcnow()))
                conn.commit()
                cur.close()
                conn.close()
        except Exception as e:
            logger.error(f"Error logging webhook delivery: {str(e)}")
    
    def process_webhook_queue(self):
        """Process webhooks from the queue"""
        while self.processing:
            try:
                if not self.webhook_queue.empty():
                    webhook_data = self.webhook_queue.get(timeout=1)
                    self.send_webhook(webhook_data)
                else:
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Error processing webhook queue: {str(e)}")
    
    def monitor_events(self):
        """Monitor blockchain for webhook events"""
        logger.info("Starting blockchain event monitoring...")
        
        while self.processing:
            try:
                current_block = w3.eth.block_number
                
                if current_block > self.last_block:
                    # Process blocks in batches
                    to_block = min(self.last_block + 100, current_block)
                    
                    # Get webhook events
                    if WEBHOOK_CONTRACT_ADDRESS:
                        webhook_filter = w3.eth.filter({
                            'fromBlock': self.last_block + 1,
                            'toBlock': to_block,
                            'address': WEBHOOK_CONTRACT_ADDRESS,
                            'topics': [EVENT_SIGNATURES['WebhookTriggered']]
                        })
                        
                        events = webhook_filter.get_all_entries()
                        for event in events:
                            self.process_webhook_event(event)
                    
                    # Update last processed block
                    self.last_block = to_block
                    self.save_last_processed_block(to_block)
                
                # Wait before next check
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error monitoring events: {str(e)}")
                time.sleep(10)
    
    def start(self):
        """Start the webhook processor"""
        self.processing = True
        
        # Start webhook queue processor
        queue_thread = threading.Thread(target=self.process_webhook_queue)
        queue_thread.daemon = True
        queue_thread.start()
        
        # Start blockchain monitor
        monitor_thread = threading.Thread(target=self.monitor_events)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        logger.info("Webhook processor started")
        
        # Keep main thread alive
        try:
            while self.processing:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop the webhook processor"""
        logger.info("Stopping webhook processor...")
        self.processing = False

def main():
    """Main entry point"""
    processor = WebhookProcessor()
    processor.start()

if __name__ == '__main__':
    main()