# Customer Database Seeder

## Overview
This script generates large amounts of realistic customer data for testing and development purposes. It populates the `customers`, `customer_profiles`, and `customer_interests` tables with synthetic data.

**AUTOMATIC SEEDING**: The database is automatically seeded with 5,000 customers on first startup when using Docker Compose. No manual intervention required!

## Features
- **Automatic seeding on first startup** (Docker only)
- Generates realistic customer data using the Faker library
- Creates 5,000 customers by default on auto-seed (configurable)
- Includes customer profiles with purchase history, engagement scores, demographics
- Generates 1-5 product interests per customer
- Batch processing for performance
- Progress reporting and statistics
- Data validation and verification

## Requirements
- Python 3.7+
- psycopg2-binary
- Faker

Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Automatic Seeding (Recommended)
When you start the application with Docker Compose, the database will automatically be seeded with customer data on first startup:

```bash
# Clean start (removes old data and volumes)
docker compose down -v
docker compose up --build
```

The backend container will:
1. Wait for the database to be ready
2. Check if customers already exist
3. If empty, automatically seed 5,000 customers (no prompt required)
4. Start the application

**Configure the number of customers** by setting the environment variable in `docker-compose.yml`:
```yaml
environment:
  SEED_NUM_CUSTOMERS: 10000  # Seed 10,000 customers instead
```

### Manual Seeding
### Manual Seeding
Run the seeder manually with default settings:
```bash
# Inside Docker container
docker compose exec backend python seed_customers.py

# Or locally (after pip install -r requirements.txt)
python seed_customers.py
```

To run in auto mode without confirmation prompt:
```bash
SKIP_PROMPT=true python seed_customers.py
```

### Configuration
Edit the script or use environment variables to customize:
- `SEED_NUM_CUSTOMERS`: Number of customers to generate (default: 5,000)
- `SKIP_PROMPT`: Set to 'true' to skip confirmation prompt
- Database connection parameters via DB_* environment variables

### Environment Variables
You can configure database connection using environment variables:
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=marketing_db
export DB_USER=postgres
export DB_PASSWORD=postgres
```

Or using Docker Compose environment:
```bash
docker compose exec backend python seed_customers.py
```

### Inside Docker Container
If running in the Docker environment:
```bash
# Enter the backend container
docker compose exec backend bash

# Run the seeder
python seed_customers.py
```

## Generated Data

### Customers Table
- **Email**: Unique, realistic email addresses
- **Name**: Random first and last names
- **Phone**: Phone numbers (80% of customers)
- **Created Date**: Random dates within last 3 years
- **Marketing Consent**: Random true/false (realistic distribution)
- **Last Activity**: 90% of customers have recent activity

### Customer Profiles Table
- **Purchase History**: 70% of customers have purchase history
- **Total Purchases**: 1-50 purchases per customer
- **Purchase Value**: $50 - $10,000 range
- **Engagement Score**: 0-100 scale
- **Demographics**: Date of birth, location (20 major US cities)
- **Business Info**: Industry and company size

### Customer Interests Table
- **Product Categories**: 12 different categories (Electronics, Clothing, etc.)
- **Interest Level**: High, medium, or low
- **Interaction Count**: 1-100 interactions per interest
- **Last Interaction**: Random dates within last year

## Data Statistics
After seeding, the script displays:
- Total records inserted
- Marketing consent percentage
- Active customer percentage
- Average purchase value
- Average engagement score

## Safety Features
- **Confirmation prompt**: Asks for confirmation before seeding
- **Data clearing**: Clears existing customer data before seeding (optional)
- **Batch commits**: Commits data in batches to prevent data loss
- **Error handling**: Rolls back on errors

## Customization

### Automatic Startup Behavior
The seeder automatically runs when:
- The backend container starts
- The database is ready
- The `customers` table is empty (no existing data)

To prevent automatic seeding, you can:
1. Pre-populate the database manually
2. Remove the entrypoint script from the Dockerfile
3. Set `SEED_NUM_CUSTOMERS` to 0 in docker-compose.yml

### Adjusting Volume
To generate more or fewer customers, edit the `NUM_CUSTOMERS` constant:
```python
NUM_CUSTOMERS = 50000  # Generate 50,000 customers
```

### Modifying Data Distribution
Edit the probability values in the generation functions:
```python
# Example: Change percentage of customers with purchases
has_purchases = random.random() > 0.3  # 70% have purchases
```

### Adding New Categories
Add to the lists in the script:
```python
PRODUCT_CATEGORIES = [
    'Electronics', 'Clothing', 'Your New Category', ...
]
```

## Performance
- Typical performance: ~1,000 customers per second
- 10,000 customers: ~10-15 seconds
- 100,000 customers: ~2-3 minutes

## Troubleshooting

### Connection Errors
Ensure the database is running and connection parameters are correct:
```bash
docker compose ps  # Check if database is running
```

### Permission Errors
Make the script executable:
```bash
chmod +x seed_customers.py
```

### Unique Constraint Violations
If re-running, the script clears existing data. If you want to append instead, comment out the DELETE statements.

### Memory Issues
For very large datasets (>100K), consider:
- Reducing `BATCH_SIZE`
- Running in smaller chunks
- Increasing available memory

## Example Output
```
============================================================
CUSTOMER DATABASE SEEDER
============================================================

This will seed 10,000 customers. Continue? (yes/no): yes
Starting customer database seeding...
Target: 10,000 customers
Database: marketing_db at localhost
✓ Connected to database

Clearing existing customer data...
✓ Existing data cleared

Processing batch 1-1000...
  ✓ Inserted 1000 customers
  ✓ Inserted 1000 customer profiles
  ✓ Inserted 3245 customer interests
  ✓ Batch committed

[... more batches ...]

============================================================
SEEDING COMPLETE!
============================================================
Total customers inserted:       10,000
Total profiles inserted:        10,000
Total interests inserted:       32,458

Database verification:
Customers in database:          10,000
Profiles in database:           10,000
Interests in database:          32,458
============================================================

Customer statistics:
  Marketing consent:            5,234 (52.3%)
  Active customers:             9,012 (90.1%)
  Avg purchase value:           $2,456.78
  Avg number of purchases:      15.3
  Avg engagement score:         48.7

✓ Database connection closed
```
