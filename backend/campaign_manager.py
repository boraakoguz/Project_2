"""
CampaignManager Component
Handles campaign creation, workflow automation, and external service integration
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional
import requests


class CampaignManager:
    """Manages marketing campaigns with automated workflows and multi-channel execution"""
    
    def __init__(self, db_connection, event_publisher=None, segmentation_manager=None):
        self.conn = db_connection
        self.event_publisher = event_publisher
        self.segmentation_manager = segmentation_manager
    
    def create_campaign(self, name: str, description: str, campaign_type: str, 
                       target_segment_id: int, start_date: datetime, 
                       end_date: datetime = None, budget: float = 0.0, 
                       message_content: str = None,
                       created_by: str = 'system') -> int:
        """Create a new marketing campaign"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO campaigns 
                (campaign_name, description, campaign_type, target_segment_id, 
                 start_date, end_date, budget, message_content, created_by, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft')
                RETURNING campaign_id
                """,
                (name, description, campaign_type, target_segment_id, 
                 start_date, end_date, budget, message_content, created_by)
            )
            campaign_id = cur.fetchone()[0]
            self.conn.commit()
            return campaign_id
    
    def get_campaign(self, campaign_id: int) -> Optional[Dict]:
        """Retrieve campaign details"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM campaigns WHERE campaign_id = %s", (campaign_id,))
            return cur.fetchone()
    
    def get_campaigns_by_status(self, status: str) -> List[Dict]:
        """Get all campaigns with specific status"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM campaigns WHERE status = %s ORDER BY created_at DESC",
                (status,)
            )
            return cur.fetchall()
    
    def update_campaign_message(self, campaign_id: int, message_content: str):
        """Update campaign message content"""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE campaigns SET message_content = %s, updated_at = CURRENT_TIMESTAMP WHERE campaign_id = %s",
                (message_content, campaign_id)
            )
            self.conn.commit()
    
    def update_campaign_status(self, campaign_id: int, new_status: str):
        """Update campaign status (draft, scheduled, active, paused, completed)"""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE campaigns SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE campaign_id = %s",
                (new_status, campaign_id)
            )
            self.conn.commit()
            
            # Publish event
            if self.event_publisher:
                self.event_publisher.publish('CAMPAIGN_STATUS_CHANGED', {
                    'campaign_id': campaign_id,
                    'new_status': new_status,
                    'timestamp': datetime.now().isoformat()
                })
    
    def add_campaign_template(self, campaign_id: int, channel: str, 
                             subject_line: str, body_content: str,
                             personalization_fields: Dict = None,
                             asset_url: str = None) -> int:
        """Add content template to campaign"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO campaign_templates 
                (campaign_id, channel, subject_line, body_content, personalization_fields, external_asset_url)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING template_id
                """,
                (campaign_id, channel, subject_line, body_content, 
                 json.dumps(personalization_fields or {}), asset_url)
            )
            template_id = cur.fetchone()[0]
            self.conn.commit()
            return template_id
    
    def create_workflow_step(self, campaign_id: int, step_number: int,
                            trigger_event: str, action_type: str,
                            delay_hours: int = 0, action_config: Dict = None):
        """Add automated workflow step to campaign"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO campaign_workflows 
                (campaign_id, step_number, trigger_event, delay_hours, action_type, action_config_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (campaign_id, step_number) 
                DO UPDATE SET 
                    trigger_event = EXCLUDED.trigger_event,
                    action_type = EXCLUDED.action_type,
                    action_config_json = EXCLUDED.action_config_json
                """,
                (campaign_id, step_number, trigger_event, delay_hours, 
                 action_type, json.dumps(action_config or {}))
            )
            self.conn.commit()
    
    def get_campaign_workflows(self, campaign_id: int) -> List[Dict]:
        """Get all workflow steps for a campaign"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM campaign_workflows 
                WHERE campaign_id = %s AND is_active = TRUE 
                ORDER BY step_number
                """,
                (campaign_id,)
            )
            return cur.fetchall()
    
    def execute_campaign(self, campaign_id: int, check_consent: bool = True) -> Dict:
        """
        Execute campaign: send to all customers in target segment.
        Returns execution summary.
        """
        try:
            campaign = self.get_campaign(campaign_id)
            if not campaign:
                return {'error': 'Campaign not found'}
            
            if campaign['status'] not in ['scheduled', 'active', 'draft']:
                return {'error': f'Cannot execute campaign with status: {campaign["status"]}'}
            
            # Get target customers from segment using SegmentationManager
            if not self.segmentation_manager:
                return {'error': 'Segmentation manager not configured'}
            
            try:
                customers = self.segmentation_manager.get_customers_by_segment(campaign['target_segment_id'])
                
                # Filter by consent if required
                if check_consent:
                    customers = [c for c in customers if c.get('marketing_consent', False)]
            except Exception as e:
                print(f"Error getting customers from segment: {e}")
                import traceback
                traceback.print_exc()
                return {'error': f'Failed to get customers from segment: {str(e)}'}
            
            if not customers:
                return {'error': f'No customers found in target segment (segment_id: {campaign["target_segment_id"]}). Try a different segment or check consent settings.'}
            
            results = {
                'campaign_id': campaign_id,
                'total_targeted': len(customers),
                'sent': 0,
                'failed': 0,
                'skipped_no_consent': 0
            }
            
            # Get campaign template
            template = self._get_campaign_template(campaign_id, campaign['campaign_type'])
            if not template:
                return {'error': f'No template found for campaign (type: {campaign["campaign_type"]}). Please create a template first.'}
            
            # Execute for each customer
            for customer in customers:
                try:
                    # Personalize content
                    personalized_content = self._personalize_content(
                        template['body_content'], 
                        customer, 
                        template.get('personalization_fields', {})
                    )
                    
                    # Send via appropriate channel
                    success = self._send_via_channel(
                        campaign['campaign_type'],
                        customer,
                        template['subject_line'],
                        personalized_content,
                        template.get('external_asset_url')
                    )
                    
                    # Log execution
                    self._log_execution(
                        campaign_id, 
                        customer['customer_id'],
                        campaign['campaign_type'],
                        personalized_content,
                        'sent' if success else 'failed'
                    )
                    
                    if success:
                        results['sent'] += 1
                    else:
                        results['failed'] += 1
                        
                except Exception as e:
                    results['failed'] += 1
                    print(f"Error sending to customer {customer['customer_id']}: {e}")
            
            # Update campaign status
            if campaign['status'] in ['scheduled', 'draft']:
                self.update_campaign_status(campaign_id, 'active')
            
            # Record campaign sends in metrics
            if results['sent'] > 0:
                self._record_campaign_sends(campaign_id, results['sent'])
            
            # Publish campaign started event
            if self.event_publisher:
                self.event_publisher.publish('CAMPAIGN_STARTED', {
                    'campaign_id': campaign_id,
                    'campaign_name': campaign['campaign_name'],
                    'results': results
                })
            
            return results
            
        except Exception as e:
            print(f"Critical error in execute_campaign: {e}")
            import traceback
            traceback.print_exc()
            return {'error': f'Campaign execution failed: {str(e)}'}
    
    def _get_campaign_template(self, campaign_id: int, channel: str) -> Optional[Dict]:
        """Get template for specific channel"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM campaign_templates WHERE campaign_id = %s AND channel = %s LIMIT 1",
                (campaign_id, channel)
            )
            return cur.fetchone()
    
    def _personalize_content(self, template: str, customer: Dict, fields: Dict) -> str:
        """Replace personalization tokens with customer data"""
        content = template
        
        # Replace common tokens
        replacements = {
            '{{first_name}}': customer.get('first_name', 'Valued Customer'),
            '{{last_name}}': customer.get('last_name', ''),
            '{{email}}': customer.get('email', ''),
            '{{company}}': customer.get('company', '')
        }
        
        for token, value in replacements.items():
            content = content.replace(token, str(value))
        
        return content
    
    def _send_via_channel(self, channel: str, customer: Dict, 
                         subject: str, content: str, asset_url: str = None) -> bool:
        """
        Send message via specified channel (email, social, SMS).
        Integrates with External Services Module.
        """
        try:
            if channel == 'email':
                return self._send_email(customer['email'], subject, content)
            elif channel == 'sms':
                return self._send_sms(customer.get('phone'), content)
            elif channel == 'social':
                return self._post_social_media(content, asset_url)
            else:
                print(f"Unknown channel: {channel}")
                return False
        except Exception as e:
            print(f"Channel send error: {e}")
            return False
    
    def _send_email(self, email: str, subject: str, body: str) -> bool:
        """Send email via external email provider API"""
        # Simulated external API call
        try:
            self._log_external_service('email_provider', {
                'to': email,
                'subject': subject,
                'body': body
            }, {'status': 'sent'}, 200, True)
            return True
        except Exception as e:
            self._log_external_service('email_provider', {'to': email}, {'error': str(e)}, 500, False)
            return False
    
    def _send_sms(self, phone: str, message: str) -> bool:
        """Send SMS via external SMS gateway"""
        if not phone:
            return False
        
        try:
            self._log_external_service('sms_gateway', {
                'to': phone,
                'message': message
            }, {'status': 'sent'}, 200, True)
            return True
        except Exception as e:
            self._log_external_service('sms_gateway', {'to': phone}, {'error': str(e)}, 500, False)
            return False
    
    def _post_social_media(self, content: str, media_url: str = None) -> bool:
        """Post to social media via external API"""
        try:
            self._log_external_service('social_media_api', {
                'content': content,
                'media_url': media_url
            }, {'status': 'posted'}, 200, True)
            return True
        except Exception as e:
            self._log_external_service('social_media_api', {'content': content}, {'error': str(e)}, 500, False)
            return False
    
    def _log_execution(self, campaign_id: int, customer_id: int, 
                      channel: str, content: str, status: str):
        """Log individual campaign execution"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO campaign_executions 
                (campaign_id, customer_id, channel, delivery_status, personalized_content)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (campaign_id, customer_id, channel, status, content)
            )
            self.conn.commit()
            
            # Publish event
            if self.event_publisher and status == 'sent':
                self.event_publisher.publish('EMAIL_SENT', {
                    'campaign_id': campaign_id,
                    'customer_id': customer_id,
                    'channel': channel
                })
    
    def _record_campaign_sends(self, campaign_id: int, count: int):
        """Record email sends in campaign metrics"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO campaign_metrics (campaign_id, metric_date, emails_sent)
                VALUES (%s, CURRENT_DATE, %s)
                ON CONFLICT (campaign_id, metric_date) 
                DO UPDATE SET emails_sent = campaign_metrics.emails_sent + EXCLUDED.emails_sent,
                              updated_at = CURRENT_TIMESTAMP
                """,
                (campaign_id, count)
            )
            self.conn.commit()
    
    def _log_external_service(self, service_type: str, request: Dict, 
                             response: Dict, status_code: int, success: bool,
                             campaign_id: int = None):
        """Log external service API calls"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO external_service_logs 
                (service_type, campaign_id, request_payload, response_payload, status_code, success)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (service_type, campaign_id, json.dumps(request), 
                 json.dumps(response), status_code, success)
            )
            self.conn.commit()
    
    def process_workflow_trigger(self, campaign_id: int, trigger_event: str, 
                                 customer_id: int, metadata: Dict = None):
        """
        Process workflow automation triggers (e.g., EMAIL_OPEN, LINK_CLICK).
        Execute next step in workflow sequence.
        """
        workflows = self.get_campaign_workflows(campaign_id)
        
        for workflow in workflows:
            if workflow['trigger_event'] == trigger_event:
                # Execute workflow action after delay
                action_type = workflow['action_type']
                action_config = workflow.get('action_config_json', {})
                
                # In production, use task queue for delayed execution
                if workflow['delay_hours'] == 0:
                    self._execute_workflow_action(action_type, customer_id, 
                                                  campaign_id, action_config)
    
    def _execute_workflow_action(self, action_type: str, customer_id: int, 
                                campaign_id: int, config: Dict):
        """Execute automated workflow action"""
        if action_type == 'SEND_EMAIL':
            # Send follow-up email
            pass
        elif action_type == 'POST_SOCIAL':
            # Post on social media
            pass
        elif action_type == 'SEND_SMS':
            # Send SMS
            pass
