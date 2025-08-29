"""
SRPK Pro Secure Download API
Handles secure file downloads with license validation
"""

import os
import hashlib
import time
import jwt
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import boto3
from botocore.exceptions import ClientError
import logging
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

# Configure AWS S3
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_S3_REGION', 'us-east-1')
)

# Download configuration
DOWNLOAD_TOKEN_EXPIRY = int(os.getenv('DOWNLOAD_TOKEN_EXPIRY_HOURS', 24))
MAX_DOWNLOAD_ATTEMPTS = int(os.getenv('MAX_DOWNLOAD_ATTEMPTS', 3))
S3_BUCKET = os.getenv('AWS_S3_BUCKET', 'srpk-downloads')

# Available downloads
DOWNLOADS = {
    'srpk-pro': {
        'name': 'SRPK Pro',
        'filename': 'srpk-pro-latest.zip',
        's3_key': 'releases/srpk-pro-latest.zip',
        'size': '45.3 MB',
        'version': '3.1.0',
        'checksum': 'sha256:abcdef123456...'
    },
    'srpk-cli': {
        'name': 'SRPK CLI Tools',
        'filename': 'srpk-cli-latest.tar.gz',
        's3_key': 'releases/srpk-cli-latest.tar.gz',
        'size': '12.1 MB',
        'version': '3.1.0',
        'checksum': 'sha256:fedcba654321...'
    }
}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/generate-download-token', methods=['POST'])
def generate_download_token():
    """Generate secure download token after license validation"""
    try:
        data = request.json
        
        # Validate required fields
        if 'licenseKey' not in data or 'downloadId' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        license_key = data['licenseKey']
        download_id = data['downloadId']
        
        # Validate download ID
        if download_id not in DOWNLOADS:
            return jsonify({
                'success': False,
                'error': 'Invalid download ID'
            }), 400
        
        # Validate license key (implement your license validation logic)
        if not validate_license_key(license_key):
            return jsonify({
                'success': False,
                'error': 'Invalid or expired license key'
            }), 403
        
        # Check download attempts (implement rate limiting)
        if not check_download_attempts(license_key, download_id):
            return jsonify({
                'success': False,
                'error': 'Maximum download attempts exceeded'
            }), 429
        
        # Generate JWT token
        token_payload = {
            'license_key': license_key,
            'download_id': download_id,
            'exp': datetime.utcnow() + timedelta(hours=DOWNLOAD_TOKEN_EXPIRY),
            'iat': datetime.utcnow(),
            'download_info': DOWNLOADS[download_id]
        }
        
        token = jwt.encode(
            token_payload,
            os.getenv('JWT_SECRET_KEY'),
            algorithm='HS256'
        )
        
        # Generate presigned S3 URL
        download_info = DOWNLOADS[download_id]
        presigned_url = generate_presigned_url(download_info['s3_key'])
        
        logger.info(f"Download token generated for license: {license_key[:8]}...")
        
        return jsonify({
            'success': True,
            'token': token,
            'downloadUrl': presigned_url,
            'expiresIn': DOWNLOAD_TOKEN_EXPIRY * 3600,
            'downloadInfo': {
                'name': download_info['name'],
                'filename': download_info['filename'],
                'size': download_info['size'],
                'version': download_info['version'],
                'checksum': download_info['checksum']
            }
        })
    
    except Exception as e:
        logger.error(f"Error generating download token: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate download token'
        }), 500

@app.route('/api/download/<token>', methods=['GET'])
def secure_download(token):
    """Handle secure file download with token validation"""
    try:
        # Decode and validate token
        try:
            payload = jwt.decode(
                token,
                os.getenv('JWT_SECRET_KEY'),
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': 'Download token has expired'
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'error': 'Invalid download token'
            }), 401
        
        download_id = payload['download_id']
        license_key = payload['license_key']
        
        # Log download attempt
        log_download_attempt(license_key, download_id)
        
        # Get download info
        download_info = DOWNLOADS[download_id]
        
        # Generate new presigned URL (for security)
        presigned_url = generate_presigned_url(download_info['s3_key'])
        
        # Redirect to presigned URL
        return jsonify({
            'success': True,
            'downloadUrl': presigned_url,
            'message': 'Download starting...'
        }), 200
    
    except Exception as e:
        logger.error(f"Error processing download: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to process download'
        }), 500

def generate_presigned_url(s3_key):
    """Generate presigned S3 URL for secure download"""
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': S3_BUCKET,
                'Key': s3_key
            },
            ExpiresIn=3600  # 1 hour
        )
        return presigned_url
    except ClientError as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        raise

def validate_license_key(license_key):
    """Validate license key against database"""
    # This is a placeholder - implement your actual validation logic
    # Should check:
    # 1. License exists in database
    # 2. License is active
    # 3. License hasn't expired
    # 4. Device/IP restrictions
    
    # Example implementation:
    # license = db.query(License).filter_by(
    #     license_key=license_key,
    #     is_active=True
    # ).first()
    # 
    # if not license:
    #     return False
    # 
    # if license.expires_at < datetime.utcnow():
    #     return False
    # 
    # return True
    
    # For now, just check format
    return len(license_key) == 19 and license_key.count('-') == 3

def check_download_attempts(license_key, download_id):
    """Check if download attempts are within limits"""
    # This is a placeholder - implement rate limiting
    # Should track download attempts per license/time period
    
    # Example implementation:
    # attempts = redis_client.get(f"downloads:{license_key}:{download_id}")
    # if attempts and int(attempts) >= MAX_DOWNLOAD_ATTEMPTS:
    #     return False
    # return True
    
    return True

def log_download_attempt(license_key, download_id):
    """Log download attempt for auditing"""
    logger.info(f"Download attempt - License: {license_key[:8]}..., Download: {download_id}")
    
    # Example implementation:
    # db.session.add(DownloadLog(
    #     license_key=license_key,
    #     download_id=download_id,
    #     ip_address=request.remote_addr,
    #     user_agent=request.headers.get('User-Agent'),
    #     timestamp=datetime.utcnow()
    # ))
    # db.session.commit()

@app.route('/api/download-stats', methods=['GET'])
def download_stats():
    """Get download statistics (admin endpoint)"""
    # Validate admin token
    auth_header = request.headers.get('Authorization')
    if not auth_header or not validate_admin_token(auth_header):
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Return download statistics
    return jsonify({
        'totalDownloads': 1234,
        'uniqueLicenses': 456,
        'downloadsByProduct': {
            'srpk-pro': 890,
            'srpk-cli': 344
        },
        'recentDownloads': [
            # List of recent downloads
        ]
    })

def validate_admin_token(auth_header):
    """Validate admin authentication token"""
    # Implement your admin authentication logic
    return auth_header == f"Bearer {os.getenv('ADMIN_TOKEN')}"

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')