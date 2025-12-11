"""
Event-Driven Integration Layer
Implements Publish-Subscribe pattern for event-driven architecture
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json
from typing import Dict, List, Callable, Optional
from enum import Enum


class EventType(Enum):
    """Standardized event types for pub/sub system"""
    # Campaign events
    CAMPAIGN_STARTED = 'CAMPAIGN_STARTED'
    CAMPAIGN_COMPLETED = 'CAMPAIGN_COMPLETED'
    CAMPAIGN_STATUS_CHANGED = 'CAMPAIGN_STATUS_CHANGED'
    EMAIL_SENT = 'EMAIL_SENT'
    SMS_SENT = 'SMS_SENT'
    
    # Customer interaction events
    EMAIL_OPENED = 'EMAIL_OPENED'
    LINK_CLICKED = 'LINK_CLICKED'
    CUSTOMER_UNSUBSCRIBED = 'CUSTOMER_UNSUBSCRIBED'
    
    # System events (from other modules)
    CUSTOMER_PURCHASE = 'CUSTOMER_PURCHASE'
    TICKET_CREATED = 'TICKET_CREATED'
    CUSTOMER_REGISTERED = 'CUSTOMER_REGISTERED'
    CUSTOMER_UPDATED = 'CUSTOMER_UPDATED'
    
    # Segmentation events
    SEGMENT_CHANGED = 'SEGMENT_CHANGED'
    CUSTOMER_ADDED_TO_SEGMENT = 'CUSTOMER_ADDED_TO_SEGMENT'


class EventPublisher:
    """Publishes events to the event bus"""
    
    def __init__(self, db_connection):
        self.conn = db_connection
    
    def publish(self, event_type: str, payload: Dict, 
                customer_id: int = None, campaign_id: int = None,
                source: str = 'marketing_automation'):
        """
        Publish event to the event bus.
        Other modules can subscribe to these events.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO marketing_events 
                (event_type, event_source, payload_json, customer_id, campaign_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING event_id
                """,
                (event_type, source, json.dumps(payload), customer_id, campaign_id)
            )
            event_id = cur.fetchone()[0]
            self.conn.commit()
            
            return event_id
    
    def publish_batch(self, events: List[Dict]):
        """Publish multiple events efficiently"""
        with self.conn.cursor() as cur:
            for event in events:
                cur.execute(
                    """
                    INSERT INTO marketing_events 
                    (event_type, event_source, payload_json, customer_id, campaign_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        event['event_type'],
                        event.get('source', 'marketing_automation'),
                        json.dumps(event.get('payload', {})),
                        event.get('customer_id'),
                        event.get('campaign_id')
                    )
                )
            self.conn.commit()


class EventSubscriber:
    """Subscribes to and processes events from the event bus"""
    
    def __init__(self, db_connection):
        self.conn = db_connection
        self.handlers = {}  # event_type -> list of handler functions
    
    def subscribe(self, event_type: str, handler: Callable):
        """Register a handler function for a specific event type"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: str, handler: Callable):
        """Remove a handler from event subscriptions"""
        if event_type in self.handlers:
            self.handlers[event_type].remove(handler)
    
    def get_unprocessed_events(self, limit: int = 100) -> List[Dict]:
        """Fetch unprocessed events from the queue"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM marketing_events 
                WHERE processed = FALSE 
                ORDER BY published_at ASC 
                LIMIT %s
                """,
                (limit,)
            )
            return cur.fetchall()
    
    def mark_as_processed(self, event_id: int):
        """Mark event as processed"""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE marketing_events SET processed = TRUE WHERE event_id = %s",
                (event_id,)
            )
            self.conn.commit()
    
    def process_events(self):
        """
        Main event processing loop.
        Fetch unprocessed events and dispatch to registered handlers.
        """
        events = self.get_unprocessed_events()
        
        processed_count = 0
        error_count = 0
        
        for event in events:
            event_type = event['event_type']
            
            if event_type in self.handlers:
                for handler in self.handlers[event_type]:
                    try:
                        handler(event)
                        processed_count += 1
                    except Exception as e:
                        error_count += 1
                        print(f"Error processing event {event['event_id']}: {e}")
                        continue
            
            # Mark as processed even if no handlers
            self.mark_as_processed(event['event_id'])
        
        return {
            'processed': processed_count,
            'errors': error_count,
            'total': len(events)
        }


class MarketingEventHandlers:
    """
    Pre-built event handlers for Marketing Automation Module.
    Responds to events from other CRM modules.
    """
    
    def __init__(self, segmentation_manager, campaign_manager, analytics):
        self.segmentation = segmentation_manager
        self.campaign = campaign_manager
        self.analytics = analytics
    
    def handle_customer_purchase(self, event: Dict):
        """
        When customer makes a purchase (from Sales Automation module),
        update their segment and trigger behavior-based campaigns.
        """
        customer_id = event['customer_id']
        payload = event['payload_json']
        purchase_amount = payload.get('purchase_amount', 0)
        
        # Trigger segmentation update
        self.segmentation.process_behavior_triggers(
            'PURCHASE', 
            customer_id, 
            {'purchase_amount': purchase_amount}
        )
        
        # Record conversion if linked to campaign
        campaign_id = payload.get('campaign_id')
        if campaign_id:
            self.analytics.track_interaction(
                customer_id, 
                campaign_id, 
                'conversion',
                conversion_value=purchase_amount
            )
    
    def handle_ticket_created(self, event: Dict):
        """
        When customer creates support ticket (from Customer Service module),
        pause marketing campaigns to that customer.
        """
        customer_id = event['customer_id']
        
        # Stop sending marketing emails to customers with open tickets
        # This demonstrates cross-module integration
        print(f"Customer {customer_id} has support ticket - pausing marketing")
        
        # Could implement: add customer to "Do Not Contact" segment temporarily
    
    def handle_email_opened(self, event: Dict):
        """Track email open as interaction"""
        customer_id = event['customer_id']
        campaign_id = event['campaign_id']
        
        self.analytics.track_interaction(customer_id, campaign_id, 'email_open')
        
        # Trigger next workflow step
        self.campaign.process_workflow_trigger(campaign_id, 'EMAIL_OPEN', customer_id)
    
    def handle_link_clicked(self, event: Dict):
        """Track link click and trigger workflow"""
        customer_id = event['customer_id']
        campaign_id = event['campaign_id']
        payload = event.get('payload_json', {})
        
        self.analytics.track_interaction(
            customer_id, 
            campaign_id, 
            'click',
            metadata=payload
        )
        
        # Trigger next workflow step
        self.campaign.process_workflow_trigger(campaign_id, 'LINK_CLICK', customer_id)
    
    def handle_customer_unsubscribed(self, event: Dict):
        """
        Handle unsubscribe event - update customer consent.
        Critical for privacy compliance.
        """
        customer_id = event['customer_id']
        campaign_id = event.get('campaign_id')
        
        # Track interaction
        if campaign_id:
            self.analytics.track_interaction(customer_id, campaign_id, 'unsubscribe')
        
        # Remove from all marketing segments
        with self.segmentation.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM customer_segments WHERE customer_id = %s",
                (customer_id,)
            )
            cur.execute(
                "UPDATE customers SET marketing_consent = FALSE WHERE customer_id = %s",
                (customer_id,)
            )
            self.segmentation.conn.commit()
    
    def handle_customer_registered(self, event: Dict):
        """
        When new customer registers, automatically segment them
        and enroll in welcome campaign.
        """
        customer_id = event['customer_id']
        
        # Auto-categorize new customer
        segments = self.segmentation.categorize_customer(customer_id)
        
        # Trigger welcome campaign if applicable
        print(f"New customer {customer_id} added to segments: {segments}")


def setup_event_handlers(subscriber: EventSubscriber, handlers: MarketingEventHandlers):
    """
    Register all event handlers with the subscriber.
    Call this during application initialization.
    """
    # External events from other CRM modules
    subscriber.subscribe(EventType.CUSTOMER_PURCHASE.value, handlers.handle_customer_purchase)
    subscriber.subscribe(EventType.TICKET_CREATED.value, handlers.handle_ticket_created)
    subscriber.subscribe(EventType.CUSTOMER_REGISTERED.value, handlers.handle_customer_registered)
    
    # Internal marketing events
    subscriber.subscribe(EventType.EMAIL_OPENED.value, handlers.handle_email_opened)
    subscriber.subscribe(EventType.LINK_CLICKED.value, handlers.handle_link_clicked)
    subscriber.subscribe(EventType.CUSTOMER_UNSUBSCRIBED.value, handlers.handle_customer_unsubscribed)
    
    print("Event handlers registered successfully")


# Example: Privacy Module Integration
def check_marketing_consent(db_connection, customer_id: int) -> bool:
    """
    Check if customer has given marketing consent.
    Should be called before sending any campaign.
    Integration point with Data Privacy Module.
    """
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT marketing_consent FROM customers WHERE customer_id = %s",
            (customer_id,)
        )
        result = cur.fetchone()
        return result[0] if result else False
