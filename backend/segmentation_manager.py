"""
SegmentationManager Component
Handles customer segmentation, behavior triggers, and dynamic categorization
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional


class SegmentationManager:
    """Manages customer segmentation with automated behavior-based triggers"""
    
    def __init__(self, db_connection):
        self.conn = db_connection
    
    def get_segment_by_id(self, segment_id: int) -> Optional[Dict]:
        """Retrieve segment definition by ID"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM segments WHERE segment_id = %s AND is_active = TRUE",
                (segment_id,)
            )
            return cur.fetchone()
    
    def get_all_segments(self) -> List[Dict]:
        """Get all active segments"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM segments WHERE is_active = TRUE ORDER BY segment_name")
            return cur.fetchall()
    
    def create_segment(self, name: str, description: str, criteria: Dict) -> int:
        """Create a new customer segment with criteria"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO segments (segment_name, description, criteria_json)
                VALUES (%s, %s, %s)
                RETURNING segment_id
                """,
                (name, description, json.dumps(criteria))
            )
            self.conn.commit()
            return cur.fetchone()[0]
    
    def get_customers_by_segment(self, segment_id: int) -> List[Dict]:
        """Retrieve all customers in a specific segment"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.*, cs.assigned_at, cs.auto_assigned
                FROM customers c
                JOIN customer_segments cs ON c.customer_id = cs.customer_id
                WHERE cs.segment_id = %s
                ORDER BY cs.assigned_at DESC
                """,
                (segment_id,)
            )
            return cur.fetchall()
    
    def get_customers_filtered(self, filters: Dict = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Retrieve customers with advanced filtering by demographics and behavior.
        
        Supported filters:
        - location: str (partial match)
        - industry: str (partial match)
        - company_size: str (exact match)
        - min_age: int
        - max_age: int
        - min_purchase_value: float
        - max_purchase_value: float
        - min_engagement_score: int
        - max_engagement_score: int
        - marketing_consent: bool
        """
        filters = filters or {}
        
        query = """
            SELECT c.*, cp.purchase_history_value, cp.total_purchases, 
                   cp.last_purchase_date, cp.avg_order_value, cp.engagement_score,
                   cp.date_of_birth, cp.location, cp.industry, cp.company_size,
                   EXTRACT(YEAR FROM AGE(CURRENT_DATE, cp.date_of_birth))::INTEGER as age
            FROM customers c
            LEFT JOIN customer_profiles cp ON c.customer_id = cp.customer_id
            WHERE 1=1
        """
        
        params = []
        
        # Location filter (case-insensitive partial match)
        if filters.get('location'):
            query += " AND cp.location ILIKE %s"
            params.append(f"%{filters['location']}%")
        
        # Industry filter (case-insensitive partial match)
        if filters.get('industry'):
            query += " AND cp.industry ILIKE %s"
            params.append(f"%{filters['industry']}%")
        
        # Company size filter (exact match)
        if filters.get('company_size'):
            query += " AND cp.company_size = %s"
            params.append(filters['company_size'])
        
        # Age filters
        if filters.get('min_age') is not None:
            query += " AND EXTRACT(YEAR FROM AGE(CURRENT_DATE, cp.date_of_birth)) >= %s"
            params.append(filters['min_age'])
        
        if filters.get('max_age') is not None:
            query += " AND EXTRACT(YEAR FROM AGE(CURRENT_DATE, cp.date_of_birth)) <= %s"
            params.append(filters['max_age'])
        
        # Purchase value filters
        if filters.get('min_purchase_value') is not None:
            query += " AND cp.purchase_history_value >= %s"
            params.append(filters['min_purchase_value'])
        
        if filters.get('max_purchase_value') is not None:
            query += " AND cp.purchase_history_value <= %s"
            params.append(filters['max_purchase_value'])
        
        # Engagement score filters
        if filters.get('min_engagement_score') is not None:
            query += " AND cp.engagement_score >= %s"
            params.append(filters['min_engagement_score'])
        
        if filters.get('max_engagement_score') is not None:
            query += " AND cp.engagement_score <= %s"
            params.append(filters['max_engagement_score'])
        
        # Marketing consent filter
        if filters.get('marketing_consent') is not None:
            query += " AND c.marketing_consent = %s"
            params.append(filters['marketing_consent'])
        
        # Add ordering, limit, and offset
        query += " ORDER BY c.customer_id LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchall()
    
    def search_customers(self, search_term: str, search_fields: List[str] = None) -> List[Dict]:
        """
        Search customers by text across multiple fields.
        
        Args:
            search_term: Text to search for
            search_fields: List of fields to search in (email, first_name, last_name, location, industry)
        """
        search_fields = search_fields or ['email', 'first_name', 'last_name', 'location', 'industry']
        
        conditions = []
        params = []
        
        for field in search_fields:
            if field in ['email', 'first_name', 'last_name']:
                conditions.append(f"c.{field} ILIKE %s")
                params.append(f"%{search_term}%")
            elif field in ['location', 'industry']:
                conditions.append(f"cp.{field} ILIKE %s")
                params.append(f"%{search_term}%")
        
        if not conditions:
            return []
        
        query = f"""
            SELECT c.*, cp.purchase_history_value, cp.total_purchases, 
                   cp.engagement_score, cp.date_of_birth, cp.location, 
                   cp.industry, cp.company_size,
                   EXTRACT(YEAR FROM AGE(CURRENT_DATE, cp.date_of_birth))::INTEGER as age
            FROM customers c
            LEFT JOIN customer_profiles cp ON c.customer_id = cp.customer_id
            WHERE ({' OR '.join(conditions)})
            ORDER BY c.last_activity_at DESC NULLS LAST
            LIMIT 50
        """
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchall()
    
    def assign_customer_to_segment(self, customer_id: int, segment_id: int, auto_assigned: bool = False):
        """Manually or automatically assign customer to segment"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO customer_segments (customer_id, segment_id, auto_assigned)
                VALUES (%s, %s, %s)
                ON CONFLICT (customer_id, segment_id) DO NOTHING
                """,
                (customer_id, segment_id, auto_assigned)
            )
            self.conn.commit()
    
    def remove_customer_from_segment(self, customer_id: int, segment_id: int):
        """Remove customer from a segment"""
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM customer_segments WHERE customer_id = %s AND segment_id = %s",
                (customer_id, segment_id)
            )
            self.conn.commit()
    
    def categorize_customer(self, customer_id: int) -> List[str]:
        """
        Automatically categorize customer based on their profile and behavior.
        Returns list of segment names they qualify for.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get customer profile
            cur.execute(
                """
                SELECT c.*, cp.* 
                FROM customers c
                LEFT JOIN customer_profiles cp ON c.customer_id = cp.customer_id
                WHERE c.customer_id = %s
                """,
                (customer_id,)
            )
            customer = cur.fetchone()
            
            if not customer:
                return []
            
            # Get all active segments
            segments = self.get_all_segments()
            qualifying_segments = []
            
            for segment in segments:
                criteria = segment.get('criteria_json', {})
                if self._evaluate_criteria(customer, criteria):
                    qualifying_segments.append(segment['segment_name'])
                    self.assign_customer_to_segment(customer_id, segment['segment_id'], auto_assigned=True)
            
            return qualifying_segments
    
    def _evaluate_criteria(self, customer: Dict, criteria: Dict) -> bool:
        """Evaluate if customer meets segment criteria"""
        if not criteria:
            return False
        
        # Check minimum purchase value
        if 'min_purchase_value' in criteria:
            purchase_value = customer.get('purchase_history_value', 0) or 0
            if purchase_value < criteria['min_purchase_value']:
                return False
        
        # Check engagement score
        if 'min_engagement_score' in criteria:
            engagement = customer.get('engagement_score', 0) or 0
            if engagement < criteria['min_engagement_score']:
                return False
        
        # Check days since last activity (for "At Risk" segment)
        if 'days_since_last_activity' in criteria:
            last_activity = customer.get('last_activity_at')
            if last_activity:
                days_inactive = (datetime.now() - last_activity).days
                if days_inactive < criteria['days_since_last_activity']:
                    return False
            else:
                return False
        
        # Check total purchases (for "New Leads")
        if 'total_purchases' in criteria:
            total = customer.get('total_purchases', 0) or 0
            if total != criteria['total_purchases']:
                return False
        
        # Check account age
        if 'created_within_days' in criteria:
            created_at = customer.get('created_at')
            if created_at:
                days_old = (datetime.now() - created_at).days
                if days_old > criteria['created_within_days']:
                    return False
        
        # Check location (case-insensitive partial match)
        if 'location' in criteria:
            customer_location = (customer.get('location') or '').lower()
            criteria_location = criteria['location'].lower()
            if criteria_location not in customer_location:
                return False
        
        # Check industry (case-insensitive partial match)
        if 'industry' in criteria:
            customer_industry = (customer.get('industry') or '').lower()
            criteria_industry = criteria['industry'].lower()
            if criteria_industry not in customer_industry:
                return False
        
        # Check company size (exact match)
        if 'company_size' in criteria:
            if customer.get('company_size') != criteria['company_size']:
                return False
        
        # Check age range
        if 'min_age' in criteria or 'max_age' in criteria:
            date_of_birth = customer.get('date_of_birth')
            if date_of_birth:
                age = (datetime.now().date() - date_of_birth).days // 365
                
                if 'min_age' in criteria and age < criteria['min_age']:
                    return False
                
                if 'max_age' in criteria and age > criteria['max_age']:
                    return False
            else:
                # If age criteria exists but no date_of_birth, exclude customer
                return False
        
        return True
    
    def process_behavior_triggers(self, event_type: str, customer_id: int, metadata: Dict = None):
        """
        Process behavior triggers to automatically move customers between segments.
        Called when events like PURCHASE, PAGE_VIEW, EMAIL_OPEN occur.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT st.*, s.segment_id, s.segment_name
                FROM segment_triggers st
                JOIN segments s ON st.segment_id = s.segment_id
                WHERE st.trigger_type = %s AND st.is_active = TRUE
                """,
                (event_type,)
            )
            triggers = cur.fetchall()
            
            for trigger in triggers:
                condition = trigger.get('condition_json', {})
                if self._evaluate_trigger_condition(customer_id, condition, metadata):
                    if trigger['action'] == 'ADD':
                        self.assign_customer_to_segment(customer_id, trigger['segment_id'], auto_assigned=True)
                    elif trigger['action'] == 'REMOVE':
                        self.remove_customer_from_segment(customer_id, trigger['segment_id'])
    
    def _evaluate_trigger_condition(self, customer_id: int, condition: Dict, metadata: Dict) -> bool:
        """Evaluate if trigger condition is met"""
        if not condition:
            return True  # No condition means always trigger
        
        # Example: Check if purchase amount exceeds threshold
        if 'min_purchase_amount' in condition and metadata:
            amount = metadata.get('purchase_amount', 0)
            return amount >= condition['min_purchase_amount']
        
        return True
    
    def recategorize_all_customers(self):
        """Batch process: recategorize all customers (run periodically)"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT customer_id FROM customers WHERE marketing_consent = TRUE")
            customers = cur.fetchall()
            
            results = {
                'processed': 0,
                'errors': 0
            }
            
            for customer in customers:
                try:
                    self.categorize_customer(customer['customer_id'])
                    results['processed'] += 1
                except Exception as e:
                    results['errors'] += 1
                    print(f"Error categorizing customer {customer['customer_id']}: {e}")
            
            return results
    
    def get_customer_segments(self, customer_id: int) -> List[Dict]:
        """Get all segments a customer belongs to"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT s.*, cs.assigned_at, cs.auto_assigned
                FROM segments s
                JOIN customer_segments cs ON s.segment_id = cs.segment_id
                WHERE cs.customer_id = %s AND s.is_active = TRUE
                ORDER BY cs.assigned_at DESC
                """,
                (customer_id,)
            )
            return cur.fetchall()
    
    def add_customer_interest(self, customer_id: int, product_category: str, interest_level: str = 'medium'):
        """Track customer product interests for personalization"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO customer_interests (customer_id, product_category, interest_level)
                VALUES (%s, %s, %s)
                ON CONFLICT (customer_id, product_category) 
                DO UPDATE SET 
                    interest_level = EXCLUDED.interest_level,
                    interaction_count = customer_interests.interaction_count + 1,
                    last_interaction_date = CURRENT_TIMESTAMP
                """,
                (customer_id, product_category, interest_level)
            )
            self.conn.commit()
    
    def get_customer_interests(self, customer_id: int) -> List[Dict]:
        """Get customer interests for personalized campaigns"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM customer_interests 
                WHERE customer_id = %s 
                ORDER BY interest_level DESC, interaction_count DESC
                """,
                (customer_id,)
            )
            return cur.fetchall()
