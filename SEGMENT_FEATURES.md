# New Customer Segmentation & Campaign Features

## Overview
Enhanced the Marketing Automation system with comprehensive customer filtering, demographic-based segmentation, and integrated campaign creation workflow.

## New Features

### 1. **Age Tracking** ✅
- Added `date_of_birth` field to customer profiles
- Automatic age calculation in queries
- All 8 seed customers now have birth dates (ages 30-47)

### 2. **Advanced Customer Filtering API** ✅

#### New Backend Methods in `SegmentationManager`:

**`get_customers_filtered(filters, limit, offset)`**
- Supports filtering by:
  - `location` - partial, case-insensitive match
  - `industry` - partial, case-insensitive match  
  - `company_size` - exact match (1-10, 10-50, 50-200, 200-500, 500+)
  - `min_age` / `max_age` - age range
  - `min_purchase_value` / `max_purchase_value` - purchase history
  - `min_engagement_score` / `max_engagement_score` - engagement (0-100)
  - `marketing_consent` - boolean filter

**`search_customers(search_term, search_fields)`**
- Free-text search across multiple fields
- Configurable search fields

#### New API Endpoints:

```bash
# Filter customers with query parameters
GET /api/customers?location=New%20York&min_age=30&max_age=50&min_purchase_value=10000

# Search customers by text
GET /api/customers/search?q=tech&fields=industry,location
```

### 3. **Enhanced Segment Criteria Evaluation** ✅

The `_evaluate_criteria()` method now supports:
- **Location matching** (case-insensitive, partial)
- **Industry matching** (case-insensitive, partial)
- **Company size** (exact match)
- **Age range** (min_age, max_age)

Example segment criteria:
```json
{
  "segment_name": "Young Tech Professionals",
  "criteria": {
    "industry": "Technology",
    "min_age": 25,
    "max_age": 35,
    "min_engagement_score": 70
  }
}
```

### 4. **Complete Frontend Workflow** ✅

#### Segments Page (`/segments`) - Two Tabs:

**Tab 1: Filter Customers**
- Interactive filter form with 10+ filter options:
  - Location, Industry, Company Size
  - Age range (min/max)
  - Purchase value range
  - Engagement score range
  - Marketing consent
- Real-time customer filtering
- Shows customer count and filtered results table
- "Create Segment from Filters" button

**Tab 2: Manage Segments**
- View all existing segments
- See segment details and criteria
- Customer count per segment
- Direct campaign creation from segment

#### Complete Workflow:

1. **Filter Customers**
   - User applies filters (e.g., "age < 28", "location = CA")
   - System shows matching customers
   
2. **Create Segment**
   - Click "Create Segment from Filters"
   - Enter segment name (e.g., "Young Californians Under 28")
   - Add description
   - System saves criteria automatically
   - Segment created with auto-assignment rules

3. **Create Campaign**
   - Go to "Manage Segments" tab
   - Click "View & Create Campaign" on any segment
   - Fill campaign details:
     - Campaign name
     - Type (email, social, SMS, ad)
     - Start/End dates
     - Budget
   - Campaign automatically linked to segment
   - Redirects to campaigns page

## Example Use Cases

### Use Case 1: Youth Marketing Campaign
```
1. Filter: min_age=18, max_age=28
2. Create Segment: "Young Adults Under 28"
3. Create Campaign: "Youth Product Launch 2025"
   - Type: Social Media
   - Target: Young Adults Under 28 segment
   - Budget: $5,000
```

### Use Case 2: High-Value Tech Companies
```
1. Filter: industry=Technology, min_purchase_value=15000, location=CA
2. Create Segment: "Premium Tech Clients in California"
3. Create Campaign: "Enterprise Software Upgrade"
   - Type: Email
   - Target: Premium Tech Clients segment
   - Budget: $10,000
```

### Use Case 3: Re-engagement for Middle-Aged Professionals
```
1. Filter: min_age=35, max_age=50, min_engagement_score=0, max_engagement_score=40
2. Create Segment: "Disengaged Professionals"
3. Create Campaign: "Win-Back Campaign"
   - Type: Email + SMS
   - Special offers for re-engagement
```

## Database Changes

### Schema Updates:
```sql
-- Added to customer_profiles table
date_of_birth DATE

-- Updated seed data with birth dates
INSERT INTO customer_profiles (..., date_of_birth, ...) VALUES
(1, ..., '1985-03-15', ...), -- Age 40
(2, ..., '1990-07-22', ...), -- Age 35
-- ... etc
```

## API Documentation

### GET /api/customers
Query Parameters:
- `location` (string)
- `industry` (string)
- `company_size` (string)
- `min_age` (integer)
- `max_age` (integer)
- `min_purchase_value` (float)
- `max_purchase_value` (float)
- `min_engagement_score` (integer)
- `max_engagement_score` (integer)
- `marketing_consent` (boolean)
- `limit` (integer, default: 100)
- `offset` (integer, default: 0)

Response:
```json
{
  "customers": [...],
  "count": 5,
  "limit": 100,
  "offset": 0
}
```

### GET /api/customers/search
Query Parameters:
- `q` (string, required) - search term
- `fields` (string) - comma-separated list of fields

Response:
```json
{
  "customers": [...],
  "count": 3,
  "search_term": "tech"
}
```

## Testing

To test the new features:

1. Start the system:
   ```bash
   docker compose up --build
   ```

2. Login to frontend: http://localhost:8080
   - Email: demo@demo.com
   - Password: demo123

3. Navigate to "Segments" page

4. Try filtering customers:
   - Set "Max Age" to 40
   - Set "Industry" to "Technology"
   - Click "Apply Filters"

5. Create a segment:
   - Click "Create Segment from Filters"
   - Name it "Young Tech Professionals"
   - Click "Create Segment"

6. Create a campaign:
   - Switch to "Manage Segments" tab
   - Click "View & Create Campaign"
   - Fill in campaign details
   - Submit

## Files Modified

1. `backend/schema.sql` - Added date_of_birth field and updated seed data
2. `backend/segmentation_manager.py` - Added filtering methods and extended criteria evaluation
3. `backend/marketing_automation.py` - Added customer filter/search API endpoints
4. `frontend/templates/segments.html` - Complete UI redesign with filtering and campaign creation
