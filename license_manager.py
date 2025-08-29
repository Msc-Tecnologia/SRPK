"""
SRPK Pro License Management System
Handles license generation, validation, and management
"""

import os
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
import logging
from dataclasses import dataclass, asdict
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LicenseType(Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

class LicenseStatus(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"

@dataclass
class License:
    """License data model"""
    license_key: str
    customer_email: str
    customer_name: str
    license_type: LicenseType
    status: LicenseStatus
    created_at: datetime
    expires_at: datetime
    max_devices: int = 5
    max_repositories: int = 10
    features: Dict = None
    metadata: Dict = None

class LicenseManager:
    """Manages SRPK Pro licenses"""
    
    def __init__(self):
        self.db_conn = self._get_db_connection()
        self.redis_client = self._get_redis_client()
        self._create_tables()
    
    def _get_db_connection(self):
        """Get PostgreSQL connection"""
        return psycopg2.connect(
            os.getenv('DATABASE_URL'),
            cursor_factory=RealDictCursor
        )
    
    def _get_redis_client(self):
        """Get Redis client for caching"""
        return redis.from_url(
            os.getenv('REDIS_URL'),
            decode_responses=True
        )
    
    def _create_tables(self):
        """Create license tables if they don't exist"""
        with self.db_conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
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
                
                CREATE INDEX IF NOT EXISTS idx_license_key ON licenses(license_key);
                CREATE INDEX IF NOT EXISTS idx_customer_email ON licenses(customer_email);
                CREATE INDEX IF NOT EXISTS idx_status ON licenses(status);
                
                CREATE TABLE IF NOT EXISTS license_activations (
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
                
                CREATE TABLE IF NOT EXISTS license_usage (
                    id SERIAL PRIMARY KEY,
                    license_key VARCHAR(255) REFERENCES licenses(license_key),
                    action VARCHAR(100) NOT NULL,
                    repository_count INTEGER,
                    device_count INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                );
            """)
            self.db_conn.commit()
    
    def generate_license_key(self) -> str:
        """Generate a unique license key"""
        # Generate 16 random bytes
        random_bytes = secrets.token_bytes(16)
        
        # Create hash
        hash_obj = hashlib.sha256(random_bytes)
        hex_dig = hash_obj.hexdigest()
        
        # Format as XXXX-XXXX-XXXX-XXXX
        parts = [hex_dig[i:i+4].upper() for i in range(0, 16, 4)]
        return '-'.join(parts)
    
    def create_license(
        self,
        customer_email: str,
        customer_name: str,
        license_type: LicenseType,
        payment_info: Dict = None
    ) -> License:
        """Create a new license"""
        # Generate unique license key
        license_key = self.generate_license_key()
        
        # Ensure uniqueness
        while self.get_license(license_key):
            license_key = self.generate_license_key()
        
        # Set expiration based on license type
        if license_type == LicenseType.ENTERPRISE:
            expires_at = datetime.utcnow() + timedelta(days=365)
        else:
            expires_at = datetime.utcnow() + timedelta(days=30)  # Monthly subscription
        
        # Set features based on license type
        features = self._get_features_for_type(license_type)
        
        # Set limits based on license type
        max_devices = 5 if license_type == LicenseType.STARTER else 10
        max_repositories = 10 if license_type == LicenseType.STARTER else 50
        
        if license_type == LicenseType.ENTERPRISE:
            max_devices = 100
            max_repositories = -1  # Unlimited
        
        # Create license object
        license = License(
            license_key=license_key,
            customer_email=customer_email,
            customer_name=customer_name,
            license_type=license_type,
            status=LicenseStatus.ACTIVE,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            max_devices=max_devices,
            max_repositories=max_repositories,
            features=features,
            metadata=payment_info or {}
        )
        
        # Save to database
        with self.db_conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO licenses (
                    license_key, customer_email, customer_name,
                    license_type, status, expires_at,
                    max_devices, max_repositories, features, metadata,
                    stripe_customer_id, stripe_subscription_id, paypal_payment_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                license.license_key,
                license.customer_email,
                license.customer_name,
                license.license_type.value,
                license.status.value,
                license.expires_at,
                license.max_devices,
                license.max_repositories,
                json.dumps(license.features),
                json.dumps(license.metadata),
                payment_info.get('stripe_customer_id') if payment_info else None,
                payment_info.get('stripe_subscription_id') if payment_info else None,
                payment_info.get('paypal_payment_id') if payment_info else None
            ))
            self.db_conn.commit()
        
        # Cache license
        self._cache_license(license)
        
        logger.info(f"Created license: {license_key} for {customer_email}")
        
        return license
    
    def get_license(self, license_key: str) -> Optional[License]:
        """Get license by key"""
        # Check cache first
        cached = self.redis_client.get(f"license:{license_key}")
        if cached:
            return self._deserialize_license(json.loads(cached))
        
        # Query database
        with self.db_conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM licenses WHERE license_key = %s
            """, (license_key,))
            
            row = cursor.fetchone()
            if row:
                license = self._row_to_license(row)
                self._cache_license(license)
                return license
        
        return None
    
    def validate_license(
        self,
        license_key: str,
        device_id: Optional[str] = None,
        check_device_limit: bool = True
    ) -> Dict:
        """Validate license key"""
        result = {
            'valid': False,
            'error': None,
            'license': None
        }
        
        # Get license
        license = self.get_license(license_key)
        if not license:
            result['error'] = 'Invalid license key'
            return result
        
        # Check status
        if license.status != LicenseStatus.ACTIVE:
            result['error'] = f'License is {license.status.value}'
            return result
        
        # Check expiration
        if license.expires_at < datetime.utcnow():
            # Update status
            self.update_license_status(license_key, LicenseStatus.EXPIRED)
            result['error'] = 'License has expired'
            return result
        
        # Check device limit if device_id provided
        if device_id and check_device_limit:
            device_count = self.get_device_count(license_key)
            if device_count >= license.max_devices:
                # Check if this device is already activated
                if not self.is_device_activated(license_key, device_id):
                    result['error'] = f'Device limit exceeded ({device_count}/{license.max_devices})'
                    return result
        
        result['valid'] = True
        result['license'] = license
        
        # Log validation
        self._log_usage(license_key, 'validation', {'device_id': device_id})
        
        return result
    
    def activate_device(
        self,
        license_key: str,
        device_id: str,
        device_name: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """Activate a device for a license"""
        # Validate license first
        validation = self.validate_license(license_key, device_id)
        if not validation['valid']:
            logger.error(f"Device activation failed: {validation['error']}")
            return False
        
        with self.db_conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO license_activations (
                    license_key, device_id, device_name, ip_address
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (license_key, device_id) 
                DO UPDATE SET 
                    last_seen = CURRENT_TIMESTAMP,
                    is_active = TRUE
            """, (license_key, device_id, device_name, ip_address))
            self.db_conn.commit()
        
        # Clear cache
        self.redis_client.delete(f"devices:{license_key}")
        
        logger.info(f"Activated device {device_id} for license {license_key}")
        return True
    
    def deactivate_device(self, license_key: str, device_id: str) -> bool:
        """Deactivate a device"""
        with self.db_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE license_activations 
                SET is_active = FALSE 
                WHERE license_key = %s AND device_id = %s
            """, (license_key, device_id))
            self.db_conn.commit()
        
        # Clear cache
        self.redis_client.delete(f"devices:{license_key}")
        
        return True
    
    def get_device_count(self, license_key: str) -> int:
        """Get active device count for a license"""
        # Check cache
        cached = self.redis_client.get(f"devices:{license_key}")
        if cached:
            return int(cached)
        
        with self.db_conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM license_activations 
                WHERE license_key = %s AND is_active = TRUE
            """, (license_key,))
            
            count = cursor.fetchone()['count']
            
            # Cache for 5 minutes
            self.redis_client.setex(f"devices:{license_key}", 300, count)
            
            return count
    
    def is_device_activated(self, license_key: str, device_id: str) -> bool:
        """Check if device is activated"""
        with self.db_conn.cursor() as cursor:
            cursor.execute("""
                SELECT is_active 
                FROM license_activations 
                WHERE license_key = %s AND device_id = %s
            """, (license_key, device_id))
            
            row = cursor.fetchone()
            return row and row['is_active']
    
    def update_license_status(self, license_key: str, status: LicenseStatus):
        """Update license status"""
        with self.db_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE licenses 
                SET status = %s 
                WHERE license_key = %s
            """, (status.value, license_key))
            self.db_conn.commit()
        
        # Clear cache
        self.redis_client.delete(f"license:{license_key}")
    
    def revoke_license(self, license_key: str, reason: str = None):
        """Revoke a license"""
        self.update_license_status(license_key, LicenseStatus.REVOKED)
        
        # Log revocation
        self._log_usage(license_key, 'revocation', {'reason': reason})
        
        logger.info(f"Revoked license: {license_key}, reason: {reason}")
    
    def get_customer_licenses(self, customer_email: str) -> List[License]:
        """Get all licenses for a customer"""
        with self.db_conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM licenses 
                WHERE customer_email = %s 
                ORDER BY created_at DESC
            """, (customer_email,))
            
            rows = cursor.fetchall()
            return [self._row_to_license(row) for row in rows]
    
    def renew_license(self, license_key: str, days: int = 30):
        """Renew a license"""
        license = self.get_license(license_key)
        if not license:
            raise ValueError("License not found")
        
        # Calculate new expiration
        if license.expires_at > datetime.utcnow():
            # Extend from current expiration
            new_expires = license.expires_at + timedelta(days=days)
        else:
            # Extend from now
            new_expires = datetime.utcnow() + timedelta(days=days)
        
        with self.db_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE licenses 
                SET expires_at = %s, status = %s 
                WHERE license_key = %s
            """, (new_expires, LicenseStatus.ACTIVE.value, license_key))
            self.db_conn.commit()
        
        # Clear cache
        self.redis_client.delete(f"license:{license_key}")
        
        logger.info(f"Renewed license: {license_key} until {new_expires}")
    
    def _get_features_for_type(self, license_type: LicenseType) -> Dict:
        """Get features for license type"""
        features = {
            LicenseType.STARTER: {
                "advanced_reports": True,
                "enterprise_connectors": False,
                "priority_support": False,
                "api_access": True,
                "custom_rules": False,
                "team_collaboration": False
            },
            LicenseType.PROFESSIONAL: {
                "advanced_reports": True,
                "enterprise_connectors": True,
                "priority_support": True,
                "api_access": True,
                "custom_rules": True,
                "team_collaboration": True
            },
            LicenseType.ENTERPRISE: {
                "advanced_reports": True,
                "enterprise_connectors": True,
                "priority_support": True,
                "api_access": True,
                "custom_rules": True,
                "team_collaboration": True,
                "sso": True,
                "audit_logs": True,
                "dedicated_support": True
            }
        }
        return features.get(license_type, {})
    
    def _cache_license(self, license: License):
        """Cache license in Redis"""
        serialized = json.dumps(asdict(license), default=str)
        self.redis_client.setex(
            f"license:{license.license_key}",
            3600,  # 1 hour
            serialized
        )
    
    def _deserialize_license(self, data: Dict) -> License:
        """Deserialize license from dict"""
        data['license_type'] = LicenseType(data['license_type'])
        data['status'] = LicenseStatus(data['status'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        return License(**data)
    
    def _row_to_license(self, row: Dict) -> License:
        """Convert database row to License object"""
        return License(
            license_key=row['license_key'],
            customer_email=row['customer_email'],
            customer_name=row['customer_name'],
            license_type=LicenseType(row['license_type']),
            status=LicenseStatus(row['status']),
            created_at=row['created_at'],
            expires_at=row['expires_at'],
            max_devices=row['max_devices'],
            max_repositories=row['max_repositories'],
            features=row['features'] or {},
            metadata=row['metadata'] or {}
        )
    
    def _log_usage(self, license_key: str, action: str, metadata: Dict = None):
        """Log license usage"""
        with self.db_conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO license_usage (
                    license_key, action, metadata
                ) VALUES (%s, %s, %s)
            """, (license_key, action, json.dumps(metadata or {})))
            self.db_conn.commit()
    
    def get_usage_stats(self, license_key: str) -> Dict:
        """Get usage statistics for a license"""
        with self.db_conn.cursor() as cursor:
            # Get activation count
            cursor.execute("""
                SELECT COUNT(*) as device_count 
                FROM license_activations 
                WHERE license_key = %s AND is_active = TRUE
            """, (license_key,))
            device_count = cursor.fetchone()['device_count']
            
            # Get usage history
            cursor.execute("""
                SELECT action, COUNT(*) as count 
                FROM license_usage 
                WHERE license_key = %s 
                GROUP BY action
            """, (license_key,))
            usage_counts = {row['action']: row['count'] for row in cursor.fetchall()}
            
            return {
                'device_count': device_count,
                'usage_counts': usage_counts
            }

# Example usage
if __name__ == "__main__":
    # Initialize manager
    manager = LicenseManager()
    
    # Create a license
    license = manager.create_license(
        customer_email="test@example.com",
        customer_name="Test User",
        license_type=LicenseType.PROFESSIONAL,
        payment_info={
            'stripe_customer_id': 'cus_test123',
            'stripe_subscription_id': 'sub_test456'
        }
    )
    
    print(f"Created license: {license.license_key}")
    
    # Validate license
    validation = manager.validate_license(license.license_key)
    print(f"License valid: {validation['valid']}")
    
    # Activate device
    success = manager.activate_device(
        license.license_key,
        device_id="device123",
        device_name="Test Device"
    )
    print(f"Device activation: {success}")