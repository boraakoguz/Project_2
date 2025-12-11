"""
Marketing Automation Module - Main Application
Flask REST API for CRM Marketing Automation
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
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
    campaign = CampaignManager(conn, event_publisher)
    analytics = MarketingAnalytics(conn)
    return segmentation, campaign, analytics, event_publisher


# ============================================================================
# SEGMENTATION API ENDPOINTS
# ============================================================================

@app.route('/api/segments', methods=['GET'])
def get_segments():
    """Get all active customer segments"""
    with get_db_connection() as conn:
        segmentation = SegmentationManager(conn)
        segments = segmentation.get_all_segments()
        return jsonify(segments), 200


@app.route('/api/segments', methods=['POST'])
def create_segment():
    """Create a new customer segment"""
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
    """Execute campaign - send to all customers in target segment"""
    with get_db_connection() as conn:
        _, campaign_mgr, _, _ = get_service_instances(conn)
        results = campaign_mgr.execute_campaign(campaign_id, check_consent=True)
        return jsonify(results), 200


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
    """API documentation"""
    return jsonify({
        'module': 'Marketing Automation Module',
        'version': '1.0',
        'endpoints': {
            'segments': {
                'GET /api/segments': 'Get all segments',
                'POST /api/segments': 'Create segment',
                'GET /api/segments/<id>': 'Get segment details',
                'GET /api/segments/<id>/customers': 'Get customers in segment'
            },
            'campaigns': {
                'POST /api/campaigns': 'Create campaign',
                'GET /api/campaigns/<id>': 'Get campaign details',
                'GET /api/campaigns/status/<status>': 'Get campaigns by status',
                'PUT /api/campaigns/<id>/status': 'Update campaign status',
                'POST /api/campaigns/<id>/execute': 'Execute campaign'
            },
            'analytics': {
                'GET /api/analytics/dashboard': 'Get dashboard data',
                'GET /api/analytics/campaigns/<id>/summary': 'Get campaign summary',
                'POST /api/analytics/campaigns/<id>/roi': 'Calculate ROI',
                'GET /api/analytics/attribution': 'Get attribution report'
            },
            'events': {
                'POST /api/events/publish': 'Publish event',
                'POST /api/events/process': 'Process events'
            }
        }
    }), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
