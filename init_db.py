#!/usr/bin/env python3
"""
Initialize SRPK Pro Crypto Database
Creates tables and initial data
"""
import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_USER = os.getenv('DB_USER', 'srpk')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'srpk_licenses')

def create_database():
    """Create database if it doesn't exist"""
    try:
        # Connect to PostgreSQL server
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        exists = cur.fetchone()
        
        if not exists:
            cur.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"✓ Database '{DB_NAME}' created successfully")
        else:
            print(f"✓ Database '{DB_NAME}' already exists")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Error creating database: {str(e)}")
        return False

def execute_schema():
    """Execute schema SQL file"""
    try:
        # Connect to the database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cur = conn.cursor()
        
        # Read and execute schema
        with open('schema_crypto.sql', 'r') as f:
            schema_sql = f.read()
            cur.execute(schema_sql)
        
        conn.commit()
        print("✓ Database schema created successfully")
        
        # Get table count
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        table_count = cur.fetchone()[0]
        print(f"✓ Created {table_count} tables")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Error executing schema: {str(e)}")
        return False

def insert_initial_data():
    """Insert initial data"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cur = conn.cursor()
        
        # Insert initial blockchain sync status
        cur.execute("""
            INSERT INTO blockchain_sync (network, last_block_number, status)
            VALUES ('bsc', 0, 'active')
            ON CONFLICT DO NOTHING
        """)
        
        # Insert sample token prices (will be updated by the API)
        sample_prices = [
            ('BNB', 300.0, 'initial'),
            ('ETH', 2000.0, 'initial'),
            ('USDT', 1.0, 'initial')
        ]
        
        for token, price, source in sample_prices:
            cur.execute("""
                INSERT INTO token_prices (token, price_usd, source)
                VALUES (%s, %s, %s)
            """, (token, price, source))
        
        conn.commit()
        print("✓ Initial data inserted successfully")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Error inserting initial data: {str(e)}")
        return False

def verify_setup():
    """Verify database setup"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cur = conn.cursor()
        
        # Check tables
        tables = [
            'crypto_payments',
            'licenses',
            'token_prices',
            'webhook_registrations',
            'webhook_logs',
            'api_usage',
            'blockchain_sync',
            'failed_transactions'
        ]
        
        print("\nVerifying tables:")
        for table in tables:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                )
            """, (table,))
            exists = cur.fetchone()[0]
            status = "✓" if exists else "✗"
            print(f"  {status} {table}")
        
        # Check views
        views = ['active_licenses', 'payment_stats', 'webhook_performance']
        
        print("\nVerifying views:")
        for view in views:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.views 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                )
            """, (view,))
            exists = cur.fetchone()[0]
            status = "✓" if exists else "✗"
            print(f"  {status} {view}")
        
        # Check functions
        functions = ['validate_license', 'get_license_stats']
        
        print("\nVerifying functions:")
        for func in functions:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_proc 
                    WHERE proname = %s
                )
            """, (func,))
            exists = cur.fetchone()[0]
            status = "✓" if exists else "✗"
            print(f"  {status} {func}")
        
        cur.close()
        conn.close()
        print("\n✓ Database setup verification complete")
        return True
        
    except Exception as e:
        print(f"\n✗ Error verifying setup: {str(e)}")
        return False

def main():
    """Main initialization function"""
    print("SRPK Pro Crypto Database Initialization")
    print("=" * 40)
    
    # Check environment
    if not DB_PASSWORD:
        print("✗ Error: DB_PASSWORD not set in environment")
        print("Please set database password in .env file")
        sys.exit(1)
    
    # Create database
    if not create_database():
        sys.exit(1)
    
    # Execute schema
    if not execute_schema():
        sys.exit(1)
    
    # Insert initial data
    if not insert_initial_data():
        sys.exit(1)
    
    # Verify setup
    if not verify_setup():
        sys.exit(1)
    
    print("\n✓ Database initialization complete!")
    print(f"\nConnection string: postgresql://{DB_USER}:***@{DB_HOST}:{DB_PORT}/{DB_NAME}")

if __name__ == '__main__':
    main()