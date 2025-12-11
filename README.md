# CS411 Project 2 - Marketing Automation Module

Marketing Automation CRM with customer segmentation, campaign management, and analytics.

## How to Run

```bash
docker-compose up --build
```

**Access:**
- Frontend: http://localhost:8080
- Backend API: http://localhost:5001
- API Docs: http://localhost:5001/api/docs

**Login:**
- Email: `demo@demo.com` | Password: `demo123`

## Source Code

```
backend/
├── marketing_automation.py  # Main API endpoints
├── campaign_manager.py      # Campaign logic
├── segmentation_manager.py  # Segmentation logic
├── marketing_analytics.py   # Analytics logic
├── event_bus.py            # Event system
├── schema.sql              # Database schema
frontend/
├── app.py                  # Frontend server
├── templates/              # HTML pages
└── static/                 # CSS/JS
```

## API Endpoints

**Not-complete documentation:** http://localhost:5001/api/docs

### Segments
- `GET /api/segments` - List all segments
- `POST /api/segments` - Create segment
- `GET /api/segments/<id>/customers` - Get segment customers

### Campaigns
- `POST /api/campaigns` - Create campaign
- `GET /api/campaigns/<id>` - Get campaign
- `POST /api/campaigns/<id>/execute` - Execute campaign

### Analytics
- `GET /api/analytics/dashboard` - Dashboard data
- `GET /api/analytics/campaigns/<id>/summary` - Campaign summary
- `POST /api/analytics/campaigns/<id>/roi` - Calculate ROI

### Customers
- `GET /api/customers?location=...&min_age=...` - Filter customers
- `GET /api/customers/search?q=...` - Search customers