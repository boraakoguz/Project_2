#!/usr/bin/env python3
"""
Customer Database Seeder Script
Generates large amounts of realistic customer data for testing and development.
"""

import psycopg2
import random
import os
from datetime import datetime, timedelta
from faker import Faker

# Initialize Faker for generating realistic data
fake = Faker()

# Database connection parameters (from environment or defaults)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'marketing_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

# Configuration for data generation
NUM_CUSTOMERS = int(os.getenv('SEED_NUM_CUSTOMERS', '5000'))  # Default 5000 for faster startup
BATCH_SIZE = 500  # Insert in batches for performance

# Constants for realistic data generation
PRODUCT_CATEGORIES = [
    'Electronics', 'Clothing', 'Home & Garden', 'Sports & Outdoors',
    'Books', 'Toys & Games', 'Beauty & Health', 'Automotive',
    'Food & Beverage', 'Pet Supplies', 'Office Supplies', 'Jewelry'
]

LOCATIONS = [
    'New York, NY', 'Los Angeles, CA', 'Chicago, IL', 'Houston, TX',
    'Phoenix, AZ', 'Philadelphia, PA', 'San Antonio, TX', 'San Diego, CA',
    'Dallas, TX', 'San Jose, CA', 'Austin, TX', 'Jacksonville, FL',
    'Seattle, WA', 'Denver, CO', 'Boston, MA', 'Portland, OR',
    'Atlanta, GA', 'Miami, FL', 'San Francisco, CA', 'Detroit, MI'
]

INDUSTRIES = [
    'Technology', 'Healthcare', 'Finance', 'Retail', 'Manufacturing',
    'Education', 'Real Estate', 'Entertainment', 'Hospitality',
    'Consulting', 'Legal', 'Non-Profit', 'Government', 'Agriculture'
]

COMPANY_SIZES = [
    '1-10', '11-50', '51-200', '201-500', '501-1000', '1000+'
]

INTEREST_LEVELS = ['high', 'medium', 'low']


def generate_customer():
    """Generate a single customer record with realistic data."""
    created_date = fake.date_time_between(start_date='-3y', end_date='now')
    has_activity = random.random() > 0.1  # 90% have some activity
    
    # Generate phone number and truncate to fit varchar(20)
    phone = None
    if random.random() > 0.2:
        phone = fake.phone_number()[:20]  # Truncate to 20 chars
    
    customer = {
        'email': fake.unique.email(),
        'first_name': fake.first_name(),
        'last_name': fake.last_name(),
        'phone': phone,
        'created_at': created_date,
        'last_activity_at': fake.date_time_between(
            start_date=created_date, end_date='now'
        ) if has_activity else None,
        'marketing_consent': random.choice([True, False]),
        'consent_date': created_date if random.random() > 0.3 else None
    }
    
    return customer


def generate_customer_profile(customer_id, created_at):
    """Generate customer profile data for segmentation."""
    has_purchases = random.random() > 0.3  # 70% have made purchases
    
    if has_purchases:
        total_purchases = random.randint(1, 50)
        purchase_value = round(random.uniform(50, 10000), 2)
        avg_order = round(purchase_value / total_purchases, 2)
        last_purchase = fake.date_time_between(
            start_date=created_at, end_date='now'
        )
    else:
        total_purchases = 0
        purchase_value = 0.00
        avg_order = None
        last_purchase = None
    
    profile = {
        'customer_id': customer_id,
        'purchase_history_value': purchase_value,
        'total_purchases': total_purchases,
        'last_purchase_date': last_purchase,
        'avg_order_value': avg_order,
        'engagement_score': random.randint(0, 100),
        'date_of_birth': fake.date_of_birth(minimum_age=18, maximum_age=80),
        'location': random.choice(LOCATIONS),
        'industry': random.choice(INDUSTRIES),
        'company_size': random.choice(COMPANY_SIZES),
        'updated_at': datetime.now()
    }
    
    return profile


def generate_customer_interests(customer_id):
    """Generate 1-5 product interests per customer."""
    num_interests = random.randint(1, 5)
    categories = random.sample(PRODUCT_CATEGORIES, num_interests)
    
    interests = []
    for category in categories:
        interest = {
            'customer_id': customer_id,
            'product_category': category,
            'interest_level': random.choice(INTEREST_LEVELS),
            'last_interaction_date': fake.date_time_between(
                start_date='-1y', end_date='now'
            ),
            'interaction_count': random.randint(1, 100)
        }
        interests.append(interest)
    
    return interests


def insert_customers_batch(cursor, customers):
    """Insert a batch of customers and return their IDs."""
    sql = """
        INSERT INTO customers (
            email, first_name, last_name, phone, created_at, 
            last_activity_at, marketing_consent, consent_date
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING customer_id, created_at
    """
    
    customer_ids = []
    for customer in customers:
        cursor.execute(sql, (
            customer['email'],
            customer['first_name'],
            customer['last_name'],
            customer['phone'],
            customer['created_at'],
            customer['last_activity_at'],
            customer['marketing_consent'],
            customer['consent_date']
        ))
        result = cursor.fetchone()
        customer_ids.append(result)
    
    return customer_ids


def insert_profiles_batch(cursor, profiles):
    """Insert a batch of customer profiles."""
    sql = """
        INSERT INTO customer_profiles (
            customer_id, purchase_history_value, total_purchases,
            last_purchase_date, avg_order_value, engagement_score,
            date_of_birth, location, industry, company_size, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """
    
    for profile in profiles:
        cursor.execute(sql, (
            profile['customer_id'],
            profile['purchase_history_value'],
            profile['total_purchases'],
            profile['last_purchase_date'],
            profile['avg_order_value'],
            profile['engagement_score'],
            profile['date_of_birth'],
            profile['location'],
            profile['industry'],
            profile['company_size'],
            profile['updated_at']
        ))


def insert_interests_batch(cursor, all_interests):
    """Insert a batch of customer interests."""
    sql = """
        INSERT INTO customer_interests (
            customer_id, product_category, interest_level,
            last_interaction_date, interaction_count
        ) VALUES (
            %s, %s, %s, %s, %s
        )
    """
    
    for interest in all_interests:
        cursor.execute(sql, (
            interest['customer_id'],
            interest['product_category'],
            interest['interest_level'],
            interest['last_interaction_date'],
            interest['interaction_count']
        ))


def seed_database():
    """Main seeding function."""
    print(f"Starting customer database seeding...")
    print(f"Target: {NUM_CUSTOMERS} customers")
    print(f"Database: {DB_CONFIG['database']} at {DB_CONFIG['host']}")
    
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("✓ Connected to database")
        
        # Clear existing data (optional - comment out if you want to append)
        print("\nClearing existing customer data...")
        cursor.execute("DELETE FROM customer_interests")
        cursor.execute("DELETE FROM customer_profiles")
        cursor.execute("DELETE FROM customers")
        cursor.execute("ALTER SEQUENCE customers_customer_id_seq RESTART WITH 1")
        cursor.execute("ALTER SEQUENCE customer_profiles_profile_id_seq RESTART WITH 1")
        cursor.execute("ALTER SEQUENCE customer_interests_interest_id_seq RESTART WITH 1")
        conn.commit()
        print("✓ Existing data cleared")
        
        # Generate and insert data in batches
        total_inserted = 0
        total_profiles = 0
        total_interests = 0
        
        for batch_start in range(0, NUM_CUSTOMERS, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, NUM_CUSTOMERS)
            batch_size = batch_end - batch_start
            
            print(f"\nProcessing batch {batch_start + 1}-{batch_end}...")
            
            # Generate customers
            customers = [generate_customer() for _ in range(batch_size)]
            
            # Insert customers and get their IDs
            customer_data = insert_customers_batch(cursor, customers)
            total_inserted += len(customer_data)
            print(f"  ✓ Inserted {len(customer_data)} customers")
            
            # Generate and insert profiles
            profiles = [
                generate_customer_profile(cid, created_at) 
                for cid, created_at in customer_data
            ]
            insert_profiles_batch(cursor, profiles)
            total_profiles += len(profiles)
            print(f"  ✓ Inserted {len(profiles)} customer profiles")
            
            # Generate and insert interests
            all_interests = []
            for customer_id, _ in customer_data:
                interests = generate_customer_interests(customer_id)
                all_interests.extend(interests)
            
            insert_interests_batch(cursor, all_interests)
            total_interests += len(all_interests)
            print(f"  ✓ Inserted {len(all_interests)} customer interests")
            
            # Commit batch
            conn.commit()
            print(f"  ✓ Batch committed")
        
        # Print summary
        print("\n" + "="*60)
        print("SEEDING COMPLETE!")
        print("="*60)
        print(f"Total customers inserted:       {total_inserted:,}")
        print(f"Total profiles inserted:        {total_profiles:,}")
        print(f"Total interests inserted:       {total_interests:,}")
        
        # Verify counts
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM customer_profiles")
        profile_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM customer_interests")
        interest_count = cursor.fetchone()[0]
        
        print("\nDatabase verification:")
        print(f"Customers in database:          {customer_count:,}")
        print(f"Profiles in database:           {profile_count:,}")
        print(f"Interests in database:          {interest_count:,}")
        print("="*60)
        
        # Show sample statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN marketing_consent = TRUE THEN 1 END) as consented,
                COUNT(CASE WHEN last_activity_at IS NOT NULL THEN 1 END) as active
            FROM customers
        """)
        stats = cursor.fetchone()
        print("\nCustomer statistics:")
        print(f"  Marketing consent:            {stats[1]:,} ({stats[1]/stats[0]*100:.1f}%)")
        print(f"  Active customers:             {stats[2]:,} ({stats[2]/stats[0]*100:.1f}%)")
        
        cursor.execute("""
            SELECT 
                AVG(purchase_history_value) as avg_value,
                AVG(total_purchases) as avg_purchases,
                AVG(engagement_score) as avg_engagement
            FROM customer_profiles
        """)
        prof_stats = cursor.fetchone()
        print(f"  Avg purchase value:           ${prof_stats[0]:.2f}")
        print(f"  Avg number of purchases:      {prof_stats[1]:.1f}")
        print(f"  Avg engagement score:         {prof_stats[2]:.1f}")
        
        cursor.close()
        conn.close()
        print("\n✓ Database connection closed")
        
    except psycopg2.Error as e:
        print(f"\n✗ Database error: {e}")
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    print("="*60)
    print("CUSTOMER DATABASE SEEDER")
    print("="*60)
    
    # Check if running in auto mode (from entrypoint script)
    skip_prompt = os.getenv('SKIP_PROMPT', 'false').lower() == 'true'
    
    if skip_prompt:
        print(f"\nAuto-mode: Seeding {NUM_CUSTOMERS:,} customers...")
        seed_database()
    else:
        # Confirm before proceeding
        response = input(f"\nThis will seed {NUM_CUSTOMERS:,} customers. Continue? (yes/no): ")
        if response.lower() in ['yes', 'y']:
            seed_database()
        else:
            print("Seeding cancelled.")
