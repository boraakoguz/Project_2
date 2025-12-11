#!/bin/bash
# Entrypoint script for backend container
# Runs database seeding on first startup, then starts the application

set -e

echo "=========================================="
echo "Backend Container Starting..."
echo "=========================================="

# Wait for database to be ready
echo "Waiting for database..."
until pg_isready -h $DB_HOST -U $DB_USER; do
  echo "Database is unavailable - sleeping"
  sleep 2
done
echo "✓ Database is ready"

# Check if database needs seeding (only on first run)
# Schema.sql has 8 seed customers, so we check if there are MORE than 8
CUSTOMER_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM customers;" 2>/dev/null | tr -d '[:space:]' || echo "0")

if [ "$CUSTOMER_COUNT" -le "8" ] && [ "$CUSTOMER_COUNT" -ge "0" ]; then
    echo "=========================================="
    echo "First startup detected - seeding database"
    echo "Current customers: $CUSTOMER_COUNT (schema seeds)"
    echo "=========================================="
    
    # Run the seeder script without interactive prompt
    python3 -c "
import os
os.environ['SKIP_PROMPT'] = 'true'

# Load and execute the seeder
exec(open('seed_customers.py').read())
" || echo "Warning: Seeding failed, continuing anyway..."
    
    echo "✓ Seeding complete"
else
    echo "Database already contains $CUSTOMER_COUNT customers - skipping seed"
fi

echo "=========================================="
echo "Starting application..."
echo "=========================================="

# Execute the main command
exec "$@"
