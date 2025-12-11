# CS411 Project 2 - Marketing Automation Module

## Project Overview

A comprehensive Marketing Automation Module for CRM systems featuring customer segmentation, campaign management, analytics, and event-driven architecture. Built with Python Flask, PostgreSQL, and Docker.

**Course:** CS411 - Database Systems  
**Project:** Project 2 - Marketing Automation Module Implementation  

## Features

### Core Functionality
- ✅ **Customer Segmentation** - Automatic customer categorization based on behavior and demographics
- ✅ **Campaign Management** - Multi-channel marketing campaigns (email, social, SMS)
- ✅ **Marketing Analytics** - Real-time performance metrics, ROI calculation, and conversion tracking
- ✅ **Event-Driven Architecture** - Pub/Sub system for cross-module integration
- ✅ **Workflow Automation** - Automated campaign sequences and triggers
- ✅ **User Authentication** - Login system with optional 2FA support

### Technical Features
- Frontend/Backend separation with containerization
- RESTful API architecture
- PostgreSQL database with comprehensive schema
- Session-based authentication
- Responsive web interface

## Architecture

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Frontend   │────────▶│  Backend    │────────▶│  PostgreSQL │
│  (Flask)    │         │  (Flask)    │         │  Database   │
│  Port 8080  │         │  Port 5001  │         │  Port 5432  │
└─────────────┘         └─────────────┘         └─────────────┘
```

## Quick Start

### Prerequisites
- Docker Desktop installed
- Ports 5001, 5432, and 8080 available

### Installation & Running

1. **Clone the repository**
   ```bash
   cd /Users/boraakoguz/Development/Bilkent/CS411/Project_2
   ```

2. **Build and start all services**
   ```bash
   docker-compose up --build
   ```

3. **Access the application**
   - Frontend UI: http://localhost:8080
   - Backend API: http://localhost:5001
   - Database: localhost:5432

### Default Login Credentials

**Account 1 (with 2FA):**
- Email: `demo@demo.com`
- Password: `demo123`

**Account 2 (without 2FA):**
- Email: `admin@marketing.com`
- Password: `admin123`

## Docker Commands

```bash
# Start all services
docker-compose up -d

# Start with rebuild
docker-compose up --build

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs frontend
docker-compose logs backend
docker-compose logs postgres

# Stop all services
docker-compose down

# Stop and remove all data (fresh start)
docker-compose down -v

# Check container status
docker-compose ps
```

## Project Structure

```
Project_2/
├── frontend/                 # Frontend Web Application
│   ├── app.py               # Flask app with authentication
│   ├── templates/           # HTML templates
│   │   ├── login.html       # Login page
│   │   ├── 2fa.html        # Two-factor authentication
│   │   ├── dashboard.html  # Main dashboard
│   │   ├── campaigns.html  # Campaign management
│   │   ├── segments.html   # Segment management
│   │   └── analytics.html  # Analytics dashboard
│   ├── static/             # CSS and JavaScript
│   │   ├── style.css       # Application styles
│   │   └── script.js       # Client-side logic
│   ├── Dockerfile          # Frontend container config
│   └── requirements.txt    # Frontend dependencies
│
├── backend/                 # Backend API Service
│   ├── marketing_automation.py  # Main Flask API
│   ├── event_bus.py            # Event-driven integration
│   ├── campaign_manager.py     # Campaign management logic
│   ├── segmentation_manager.py # Customer segmentation
│   ├── marketing_analytics.py  # Analytics and metrics
│   ├── schema.sql             # Database schema with seed data
│   ├── Dockerfile             # Backend container config
│   └── requirements.txt       # Backend dependencies
│
└── docker-compose.yml       # Container orchestration
```

## Database Schema

The system includes 15 interconnected tables:

### Core Entities
- `customers` - Customer information
- `customer_profiles` - Demographic and behavioral data
- `customer_interests` - Product/category preferences

### Segmentation
- `segments` - Segment definitions
- `customer_segments` - Customer-segment relationships
- `segment_triggers` - Automated segmentation rules

### Campaigns
- `campaigns` - Campaign definitions
- `campaign_templates` - Content templates
- `campaign_workflows` - Automation workflows
- `campaign_executions` - Individual send records

### Analytics
- `campaign_metrics` - Performance metrics
- `customer_interactions` - Interaction tracking
- `campaign_roi` - ROI calculations

### Integration
- `marketing_events` - Event bus for pub/sub
- `external_service_logs` - API integration logs

## API Endpoints

### Segments
- `GET /api/segments` - Get all segments
- `POST /api/segments` - Create new segment
- `GET /api/segments/<id>` - Get segment details
- `GET /api/segments/<id>/customers` - Get customers in segment

### Campaigns
- `POST /api/campaigns` - Create campaign
- `GET /api/campaigns/<id>` - Get campaign details
- `GET /api/campaigns/status/<status>` - Get campaigns by status
- `PUT /api/campaigns/<id>/status` - Update campaign status
- `POST /api/campaigns/<id>/execute` - Execute campaign

### Analytics
- `GET /api/analytics/dashboard` - Get dashboard data
- `GET /api/analytics/campaigns/<id>/summary` - Campaign summary
- `POST /api/analytics/campaigns/<id>/roi` - Calculate ROI
- `GET /api/analytics/attribution` - Attribution report

### Events
- `POST /api/events/publish` - Publish event
- `POST /api/events/process` - Process pending events

## Sample Data

The database is pre-populated with realistic sample data:
- 8 example customers with varied profiles
- 5 customer segments (High Value, At Risk, New Leads, etc.)
- 5 marketing campaigns in various states
- Campaign metrics and customer interactions
- ROI calculations and analytics data

## Key Implementation Details

### Customer Segmentation
Automatic categorization using:
- Purchase history and value
- Engagement scores
- Activity patterns
- Behavioral triggers

### Campaign Workflows
Multi-step automated sequences:
1. Campaign start triggers
2. Customer actions (opens, clicks)
3. Time-based delays
4. Automated follow-ups

### Event-Driven Integration
Pub/Sub system for:
- Campaign events
- Customer interactions
- Cross-module communication
- External service integration

### Analytics & Metrics
Real-time tracking of:
- Email open rates
- Click-through rates
- Conversion rates
- Revenue attribution
- ROI calculations

## Security Features

- Session-based authentication
- Login required for all protected routes
- Optional two-factor authentication (2FA)
- API proxy with authentication checks
- Secure session cookies

## Development

### Running Locally (without Docker)

**Frontend:**
```bash
cd frontend
pip install -r requirements.txt
export BACKEND_API_URL=http://localhost:5001
python app.py
```

**Backend:**
```bash
cd backend
pip install -r requirements.txt
export DB_HOST=localhost
export DB_NAME=crm_marketing
export DB_USER=postgres
export DB_PASSWORD=postgres
python marketing_automation.py
```

### Environment Variables

**Backend:**
- `DB_NAME` - Database name (default: crm_marketing)
- `DB_USER` - Database user (default: postgres)
- `DB_PASSWORD` - Database password (default: postgres)
- `DB_HOST` - Database host (default: localhost)
- `DB_PORT` - Database port (default: 5432)

**Frontend:**
- `BACKEND_API_URL` - Backend API URL (default: http://localhost:5001)

## Troubleshooting

### Port Conflicts
If ports are already in use:
1. Stop other services using those ports, or
2. Modify `docker-compose.yml` to use different ports

### Database Issues
```bash
# Reset database and start fresh
docker-compose down -v
docker-compose up --build
```

### Container Logs
```bash
# View all logs
docker-compose logs -f

# View specific service
docker logs marketing_automation_frontend
docker logs marketing_automation_backend
docker logs crm_postgres
```

## Project Requirements Met

✅ Database design with proper normalization  
✅ Complex queries with joins and aggregations  
✅ Indexes for performance optimization  
✅ Event-driven architecture  
✅ Multi-module integration (CRM, Sales, Support)  
✅ RESTful API implementation  
✅ User interface for data visualization  
✅ Comprehensive seed data  
✅ Documentation and deployment guide  

## Technologies Used

- **Backend:** Python 3.11, Flask, psycopg2
- **Frontend:** Python Flask, HTML, CSS, JavaScript
- **Database:** PostgreSQL 15
- **Containerization:** Docker, Docker Compose
- **Authentication:** Session-based with 2FA support

## Authors

Bora Akoğuz  
CS411 - Database Systems  
Bilkent University  

## License

This project is created for educational purposes as part of CS411 coursework.

---

**Last Updated:** December 11, 2025
