"""
Marketing Automation Module - Main Application
Flask REST API for CRM Marketing Automation
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
from contextlib import contextmanager

from segmentation_manager import SegmentationManager
from campaign_manager import CampaignManager
from marketing_analytics import MarketingAnalytics
from event_bus import EventPublisher, EventSubscriber, MarketingEventHandlers, setup_event_handlers

app = Flask(__name__)
CORS(app)

# Swagger configuration
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/api/docs/swagger.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs"
}

swagger_template = {
    "info": {
        "title": "Marketing Automation API",
        "description": "Auto-generated API documentation for Marketing Automation Module",
        "version": "1.0.0"
    }
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# Error handler for bad JSON requests
@app.errorhandler(400)
def handle_bad_request(e):
    """Handle bad request errors, including JSON decode errors"""
    if 'JSON' in str(e) or 'json' in str(e.description if hasattr(e, 'description') else ''):
        # This is a JSON parsing error, but the request might still be valid
        return jsonify({'error': 'Invalid JSON in request body'}), 400
    return jsonify({'error': str(e)}), 400

# Database configuration
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'crm_marketing'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432')
}


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


def get_service_instances(conn):
    """Initialize service instances with database connection"""
    event_publisher = EventPublisher(conn)
    segmentation = SegmentationManager(conn)
    campaign = CampaignManager(conn, event_publisher, segmentation)
    analytics = MarketingAnalytics(conn)
    return segmentation, campaign, analytics, event_publisher


# ============================================================================
# SEGMENTATION API ENDPOINTS
# ============================================================================

@app.route('/api/segments', methods=['GET'])
def get_segments():
    """Get all active customer segments
    ---
    tags:
      - Segments
    responses:
      200:
        description: List of all active segments
    """
    with get_db_connection() as conn:
        segmentation = SegmentationManager(conn)
        segments = segmentation.get_all_segments()
        return jsonify(segments), 200


@app.route('/api/segments', methods=['POST'])
def create_segment():
    """Create a new customer segment
    ---
    tags:
      - Segments
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - segment_name
          properties:
            segment_name:
              type: string
            description:
              type: string
            criteria:
              type: object
    responses:
      201:
        description: Segment created successfully
    """
    data = request.json
    
    with get_db_connection() as conn:
        segmentation = SegmentationManager(conn)
        segment_id = segmentation.create_segment(
            name=data['segment_name'],
            description=data.get('description', ''),
            criteria=data.get('criteria', {})
        )
        return jsonify({'segment_id': segment_id, 'message': 'Segment created successfully'}), 201


@app.route('/api/segments/<int:segment_id>', methods=['GET'])
def get_segment(segment_id):
    """Get segment details"""
    with get_db_connection() as conn:
        segmentation = SegmentationManager(conn)
        segment = segmentation.get_segment_by_id(segment_id)
        
        if not segment:
            return jsonify({'error': 'Segment not found'}), 404
        
        return jsonify(segment), 200


@app.route('/api/segments/<int:segment_id>/customers', methods=['GET'])
def get_segment_customers(segment_id):
    """Get all customers in a segment"""
    with get_db_connection() as conn:
        segmentation = SegmentationManager(conn)
        customers = segmentation.get_customers_by_segment(segment_id)
        return jsonify(customers), 200


@app.route('/api/customers/<int:customer_id>/segments', methods=['GET'])
def get_customer_segments(customer_id):
    """Get all segments a customer belongs to"""
    with get_db_connection() as conn:
        segmentation = SegmentationManager(conn)
        segments = segmentation.get_customer_segments(customer_id)
        return jsonify(segments), 200


@app.route('/api/customers/<int:customer_id>/categorize', methods=['POST'])
def categorize_customer(customer_id):
    """Automatically categorize customer into appropriate segments"""
    with get_db_connection() as conn:
        segmentation = SegmentationManager(conn)
        segments = segmentation.categorize_customer(customer_id)
        return jsonify({'customer_id': customer_id, 'segments': segments}), 200


@app.route('/api/customers/<int:customer_id>/interests', methods=['POST'])
def add_customer_interest(customer_id):
    """Track customer product interest"""
    data = request.json
    
    with get_db_connection() as conn:
        segmentation = SegmentationManager(conn)
        segmentation.add_customer_interest(
            customer_id,
            data['product_category'],
            data.get('interest_level', 'medium')
        )
        return jsonify({'message': 'Interest tracked successfully'}), 201


@app.route('/api/segments/recategorize', methods=['POST'])
def recategorize_all():
    """Batch recategorize all customers (admin function)"""
    with get_db_connection() as conn:
        segmentation = SegmentationManager(conn)
        results = segmentation.recategorize_all_customers()
        return jsonify(results), 200


# ============================================================================
# CUSTOMER API ENDPOINTS
# ============================================================================

@app.route('/api/customers', methods=['GET'])
def get_customers():
    """Get customers with optional filtering
    ---
    tags:
      - Customers
    parameters:
      - in: query
        name: location
        type: string
        description: Filter by location (partial match)
      - in: query
        name: industry
        type: string
        description: Filter by industry (partial match)
      - in: query
        name: company_size
        type: string
        description: Company size (1-10, 10-50, 50-200, 200-500, 500+)
      - in: query
        name: min_age
        type: integer
        description: Minimum age
      - in: query
        name: max_age
        type: integer
        description: Maximum age
      - in: query
        name: min_purchase_value
        type: number
        description: Minimum purchase value
      - in: query
        name: max_purchase_value
        type: number
        description: Maximum purchase value
      - in: query
        name: min_engagement_score
        type: integer
        description: Minimum engagement score (0-100)
      - in: query
        name: max_engagement_score
        type: integer
        description: Maximum engagement score (0-100)
      - in: query
        name: marketing_consent
        type: boolean
        description: Filter by marketing consent
      - in: query
        name: limit
        type: integer
        default: 100
        description: Number of results
      - in: query
        name: offset
        type: integer
        default: 0
        description: Results offset
    responses:
      200:
        description: Filtered customers list
    """
    filters = {}
    
    # Extract filter parameters from query string
    if request.args.get('location'):
        filters['location'] = request.args.get('location')
    
    if request.args.get('industry'):
        filters['industry'] = request.args.get('industry')
    
    if request.args.get('company_size'):
        filters['company_size'] = request.args.get('company_size')
    
    if request.args.get('min_age'):
        filters['min_age'] = int(request.args.get('min_age'))
    
    if request.args.get('max_age'):
        filters['max_age'] = int(request.args.get('max_age'))
    
    if request.args.get('min_purchase_value'):
        filters['min_purchase_value'] = float(request.args.get('min_purchase_value'))
    
    if request.args.get('max_purchase_value'):
        filters['max_purchase_value'] = float(request.args.get('max_purchase_value'))
    
    if request.args.get('min_engagement_score'):
        filters['min_engagement_score'] = int(request.args.get('min_engagement_score'))
    
    if request.args.get('max_engagement_score'):
        filters['max_engagement_score'] = int(request.args.get('max_engagement_score'))
    
    if request.args.get('marketing_consent'):
        filters['marketing_consent'] = request.args.get('marketing_consent').lower() == 'true'
    
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    
    with get_db_connection() as conn:
        segmentation = SegmentationManager(conn)
        customers = segmentation.get_customers_filtered(filters, limit, offset)
        return jsonify({
            'customers': customers,
            'count': len(customers),
            'limit': limit,
            'offset': offset
        }), 200


@app.route('/api/customers/search', methods=['GET'])
def search_customers():
    """Search customers by text across multiple fields
    ---
    tags:
      - Customers
    parameters:
      - in: query
        name: q
        type: string
        required: true
        description: Search term
      - in: query
        name: fields
        type: string
        description: Comma-separated list of fields to search (email, first_name, last_name, location, industry)
    responses:
      200:
        description: Search results
      400:
        description: Missing search term
    """
    search_term = request.args.get('q', '').strip()
    
    if not search_term:
        return jsonify({'error': 'Search term (q) is required'}), 400
    
    search_fields = None
    if request.args.get('fields'):
        search_fields = [f.strip() for f in request.args.get('fields').split(',')]
    
    with get_db_connection() as conn:
        segmentation = SegmentationManager(conn)
        customers = segmentation.search_customers(search_term, search_fields)
        return jsonify({
            'customers': customers,
            'count': len(customers),
            'search_term': search_term
        }), 200


# ============================================================================
# CAMPAIGN API ENDPOINTS
# ============================================================================

@app.route('/api/campaigns', methods=['POST'])
def create_campaign():
    """Create a new marketing campaign"""
    data = request.json
    
    with get_db_connection() as conn:
        _, campaign_mgr, _, _ = get_service_instances(conn)
        
        campaign_id = campaign_mgr.create_campaign(
            name=data['campaign_name'],
            description=data.get('description', ''),
            campaign_type=data['campaign_type'],
            target_segment_id=data['target_segment_id'],
            start_date=datetime.fromisoformat(data['start_date']),
            end_date=datetime.fromisoformat(data['end_date']) if data.get('end_date') else None,
            budget=float(data.get('budget', 0)),
            message_content=data.get('message_content', ''),
            created_by=data.get('created_by', 'system')
        )
        
        return jsonify({'campaign_id': campaign_id, 'message': 'Campaign created successfully'}), 201


@app.route('/api/campaigns/<int:campaign_id>', methods=['GET'])
def get_campaign(campaign_id):
    """Get campaign details"""
    with get_db_connection() as conn:
        _, campaign_mgr, _, _ = get_service_instances(conn)
        campaign = campaign_mgr.get_campaign(campaign_id)
        
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        return jsonify(campaign), 200


@app.route('/api/campaigns/status/<status>', methods=['GET'])
def get_campaigns_by_status(status):
    """Get campaigns by status (draft, scheduled, active, paused, completed)"""
    with get_db_connection() as conn:
        _, campaign_mgr, _, _ = get_service_instances(conn)
        campaigns = campaign_mgr.get_campaigns_by_status(status)
        return jsonify(campaigns), 200


@app.route('/api/campaigns/<int:campaign_id>/status', methods=['PUT'])
def update_campaign_status(campaign_id):
    """Update campaign status"""
    data = request.json
    
    with get_db_connection() as conn:
        _, campaign_mgr, _, _ = get_service_instances(conn)
        campaign_mgr.update_campaign_status(campaign_id, data['status'])
        return jsonify({'message': 'Status updated successfully'}), 200


@app.route('/api/campaigns/<int:campaign_id>/message', methods=['PUT'])
def update_campaign_message(campaign_id):
    """Update campaign message content"""
    data = request.json
    
    with get_db_connection() as conn:
        _, campaign_mgr, _, _ = get_service_instances(conn)
        campaign_mgr.update_campaign_message(campaign_id, data['message_content'])
        return jsonify({'message': 'Message updated successfully'}), 200


@app.route('/api/campaigns/<int:campaign_id>/template', methods=['POST'])
def add_campaign_template(campaign_id):
    """Add content template to campaign"""
    data = request.json
    
    with get_db_connection() as conn:
        _, campaign_mgr, _, _ = get_service_instances(conn)
        
        template_id = campaign_mgr.add_campaign_template(
            campaign_id,
            data['channel'],
            data['subject_line'],
            data['body_content'],
            data.get('personalization_fields', {}),
            data.get('asset_url')
        )
        
        return jsonify({'template_id': template_id, 'message': 'Template added successfully'}), 201


@app.route('/api/campaigns/<int:campaign_id>/workflow', methods=['POST'])
def add_workflow_step(campaign_id):
    """Add workflow automation step to campaign"""
    data = request.json
    
    with get_db_connection() as conn:
        _, campaign_mgr, _, _ = get_service_instances(conn)
        
        campaign_mgr.create_workflow_step(
            campaign_id,
            data['step_number'],
            data['trigger_event'],
            data['action_type'],
            data.get('delay_hours', 0),
            data.get('action_config', {})
        )
        
        return jsonify({'message': 'Workflow step added successfully'}), 201


@app.route('/api/campaigns/<int:campaign_id>/workflow', methods=['GET'])
def get_workflow_steps(campaign_id):
    """Get all workflow steps for campaign"""
    with get_db_connection() as conn:
        _, campaign_mgr, _, _ = get_service_instances(conn)
        workflows = campaign_mgr.get_campaign_workflows(campaign_id)
        return jsonify(workflows), 200


@app.route('/api/campaigns/<int:campaign_id>/execute', methods=['POST'])
def execute_campaign(campaign_id):
    """Execute campaign - send to all customers in target segment
    ---
    tags:
      - Campaigns
    parameters:
      - name: campaign_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        required: false
        schema:
          type: object
          properties:
            check_consent:
              type: boolean
              default: true
    responses:
      200:
        description: Campaign execution results
      400:
        description: Execution error
    """
    try:
        # Get optional parameters from request body if provided
        data = request.get_json(silent=True, force=True) or {}
        check_consent = data.get('check_consent', True)
        
        with get_db_connection() as conn:
            _, campaign_mgr, _, _ = get_service_instances(conn)
            results = campaign_mgr.execute_campaign(campaign_id, check_consent=check_consent)
            
            # Check if there was an error
            if 'error' in results:
                return jsonify(results), 400
            
            return jsonify(results), 200
    except Exception as e:
        print(f"Error in execute_campaign endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/api/campaigns/<int:campaign_id>/preview', methods=['GET'])
def preview_campaign_message(campaign_id):
    """Get campaign message with sample personalization"""
    with get_db_connection() as conn:
        _, campaign_mgr, _, _ = get_service_instances(conn)
        campaign = campaign_mgr.get_campaign(campaign_id)
        
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Create sample personalization
        message_content = campaign.get('message_content', '')
        sample_message = message_content.replace('{name}', 'John Doe')
        sample_message = sample_message.replace('{first_name}', 'John')
        sample_message = sample_message.replace('{last_name}', 'Doe')
        sample_message = sample_message.replace('{email}', 'john.doe@example.com')
        
        return jsonify({
            'campaign_id': campaign_id,
            'message_template': message_content,
            'sample_message': sample_message,
            'available_fields': ['{name}', '{first_name}', '{last_name}', '{email}']
        }), 200


# ============================================================================
# ANALYTICS API ENDPOINTS
# ============================================================================

@app.route('/api/analytics/dashboard', methods=['GET'])
def get_dashboard():
    """Get dashboard data for Marketing Admin PC"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.fromisoformat(start_date)
    if end_date:
        end_date = datetime.fromisoformat(end_date)
    
    with get_db_connection() as conn:
        _, _, analytics, _ = get_service_instances(conn)
        data = analytics.get_dashboard_data(start_date, end_date)
        return jsonify(data), 200


@app.route('/api/analytics/campaigns/<int:campaign_id>/metrics', methods=['GET'])
def get_campaign_metrics(campaign_id):
    """Get performance metrics for a campaign"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.fromisoformat(start_date)
    if end_date:
        end_date = datetime.fromisoformat(end_date)
    
    with get_db_connection() as conn:
        _, _, analytics, _ = get_service_instances(conn)
        metrics = analytics.get_campaign_metrics(campaign_id, start_date, end_date)
        return jsonify(metrics), 200


@app.route('/api/analytics/campaigns/<int:campaign_id>/summary', methods=['GET'])
def get_campaign_summary(campaign_id):
    """Get aggregated campaign summary"""
    with get_db_connection() as conn:
        _, _, analytics, _ = get_service_instances(conn)
        summary = analytics.get_campaign_summary(campaign_id)
        return jsonify(summary), 200


@app.route('/api/analytics/campaigns/<int:campaign_id>/roi', methods=['POST'])
def calculate_campaign_roi(campaign_id):
    """Calculate and store ROI for campaign"""
    data = request.json
    total_cost = data.get('total_cost')
    
    with get_db_connection() as conn:
        _, _, analytics, _ = get_service_instances(conn)
        roi = analytics.calculate_roi(campaign_id, total_cost)
        return jsonify(roi), 200


@app.route('/api/analytics/campaigns/<int:campaign_id>/roi', methods=['GET'])
def get_campaign_roi(campaign_id):
    """Get calculated ROI for campaign"""
    with get_db_connection() as conn:
        _, _, analytics, _ = get_service_instances(conn)
        roi = analytics.get_campaign_roi(campaign_id)
        
        if not roi:
            return jsonify({'error': 'ROI not calculated yet'}), 404
        
        return jsonify(roi), 200


@app.route('/api/analytics/campaigns/<int:campaign_id>/funnel', methods=['GET'])
def get_conversion_funnel(campaign_id):
    """Get conversion funnel analysis"""
    with get_db_connection() as conn:
        _, _, analytics, _ = get_service_instances(conn)
        funnel = analytics.get_conversion_funnel(campaign_id)
        return jsonify(funnel), 200


@app.route('/api/analytics/attribution', methods=['GET'])
def get_attribution_report():
    """Get revenue attribution report"""
    start_date = datetime.fromisoformat(request.args['start_date'])
    end_date = datetime.fromisoformat(request.args['end_date'])
    
    with get_db_connection() as conn:
        _, _, analytics, _ = get_service_instances(conn)
        report = analytics.generate_attribution_report(start_date, end_date)
        return jsonify(report), 200


@app.route('/api/analytics/segments/<int:segment_id>/performance', methods=['GET'])
def get_segment_performance(segment_id):
    """Get performance of campaigns targeting a segment"""
    with get_db_connection() as conn:
        _, _, analytics, _ = get_service_instances(conn)
        performance = analytics.get_segment_performance(segment_id)
        return jsonify(performance), 200


@app.route('/api/analytics/campaigns/summary', methods=['GET'])
def get_all_campaigns_summary():
    """Get summary of all campaigns with revenue, segment info, and customer counts
    ---
    tags:
      - Analytics
    responses:
      200:
        description: List of all campaigns with performance metrics
    """
    with get_db_connection() as conn:
        segmentation, campaign, analytics, _ = get_service_instances(conn)
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get all campaigns with their metrics and segment info
            cur.execute(
                """
                SELECT 
                    c.campaign_id,
                    c.campaign_name,
                    c.campaign_type,
                    c.status,
                    c.target_segment_id,
                    c.start_date,
                    c.end_date,
                    c.budget,
                    s.segment_name,
                    s.description as segment_description,
                    COALESCE(SUM(cm.emails_sent), 0) as total_emails_sent,
                    COALESCE(SUM(cm.emails_opened), 0) as total_emails_opened,
                    COALESCE(SUM(cm.links_clicked), 0) as total_clicks,
                    COALESCE(SUM(cm.conversions), 0) as total_conversions,
                    COALESCE(SUM(cm.revenue_generated), 0) as total_revenue,
                    COALESCE(SUM(cm.cost_incurred), 0) as total_cost,
                    CASE 
                        WHEN SUM(cm.emails_sent) > 0 
                        THEN ROUND((SUM(cm.emails_opened)::numeric / SUM(cm.emails_sent) * 100), 2)
                        ELSE 0 
                    END as open_rate,
                    CASE 
                        WHEN SUM(cm.emails_sent) > 0 
                        THEN ROUND((SUM(cm.conversions)::numeric / SUM(cm.emails_sent) * 100), 2)
                        ELSE 0 
                    END as conversion_rate
                FROM campaigns c
                LEFT JOIN segments s ON c.target_segment_id = s.segment_id
                LEFT JOIN campaign_metrics cm ON c.campaign_id = cm.campaign_id
                GROUP BY c.campaign_id, c.campaign_name, c.campaign_type, c.status, 
                         c.target_segment_id, c.start_date, c.end_date, c.budget,
                         s.segment_name, s.description
                ORDER BY c.created_at DESC
                """
            )
            campaigns = cur.fetchall()
        
        # Add customer count for each segment
        result = []
        for campaign in campaigns:
            campaign_dict = dict(campaign)
            if campaign_dict['target_segment_id']:
                try:
                    customer_count = segmentation.get_segment_count(campaign_dict['target_segment_id'])
                    campaign_dict['active_customers'] = customer_count
                except:
                    campaign_dict['active_customers'] = 0
            else:
                campaign_dict['active_customers'] = 0
            result.append(campaign_dict)
        
        return jsonify(result), 200


@app.route('/api/analytics/customers/<int:customer_id>/interactions', methods=['POST'])
def track_interaction():
    """Track customer interaction with campaign"""
    customer_id = int(request.view_args['customer_id'])
    data = request.json
    
    with get_db_connection() as conn:
        _, _, analytics, _ = get_service_instances(conn)
        
        analytics.track_interaction(
            customer_id,
            data['campaign_id'],
            data['interaction_type'],
            data.get('metadata', {}),
            data.get('conversion_value')
        )
        
        return jsonify({'message': 'Interaction tracked successfully'}), 201


@app.route('/api/analytics/customers/<int:customer_id>/history', methods=['GET'])
def get_customer_engagement_history(customer_id):
    """Get customer's engagement history across campaigns"""
    limit = int(request.args.get('limit', 50))
    
    with get_db_connection() as conn:
        _, _, analytics, _ = get_service_instances(conn)
        history = analytics.get_customer_engagement_history(customer_id, limit)
        return jsonify(history), 200


# ============================================================================
# EVENT BUS API ENDPOINTS
# ============================================================================

@app.route('/api/events/publish', methods=['POST'])
def publish_event():
    """Publish event to event bus"""
    data = request.json
    
    with get_db_connection() as conn:
        publisher = EventPublisher(conn)
        event_id = publisher.publish(
            data['event_type'],
            data.get('payload', {}),
            data.get('customer_id'),
            data.get('campaign_id'),
            data.get('source', 'marketing_automation')
        )
        
        return jsonify({'event_id': event_id, 'message': 'Event published successfully'}), 201


@app.route('/api/events/process', methods=['POST'])
def process_events():
    """Process pending events (admin/cron endpoint)"""
    with get_db_connection() as conn:
        segmentation, campaign, analytics, _ = get_service_instances(conn)
        
        subscriber = EventSubscriber(conn)
        handlers = MarketingEventHandlers(segmentation, campaign, analytics)
        setup_event_handlers(subscriber, handlers)
        
        results = subscriber.process_events()
        return jsonify(results), 200


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return jsonify({'status': 'healthy', 'module': 'Marketing Automation'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503


@app.route('/', methods=['GET'])
def index():
    """API documentation - redirect to Swagger UI
    ---
    tags:
      - Documentation
    responses:
      200:
        description: API info with link to Swagger docs
    """
    return jsonify({
        'module': 'Marketing Automation Module',
        'version': '1.0',
        'documentation': '/api/docs',
        'openapi_spec': '/api/docs/swagger.json'
    }), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
