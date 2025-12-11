"""
MarketingAnalytics Component
Provides campaign performance metrics, ROI calculation, and dashboard data
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional
from decimal import Decimal


class MarketingAnalytics:
    """Manages marketing analytics, ROI calculation, and performance reporting"""
    
    def __init__(self, db_connection):
        self.conn = db_connection
    
    def track_interaction(self, customer_id: int, campaign_id: int, 
                         interaction_type: str, metadata: Dict = None,
                         conversion_value: float = None):
        """
        Track customer interactions with campaigns.
        Types: email_open, click, conversion, unsubscribe
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO customer_interactions 
                (customer_id, campaign_id, interaction_type, metadata_json, conversion_value)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (customer_id, campaign_id, interaction_type, 
                 json.dumps(metadata or {}), conversion_value)
            )
            self.conn.commit()
            
            # Update campaign metrics
            self._update_campaign_metrics(campaign_id, interaction_type, conversion_value)
    
    def _update_campaign_metrics(self, campaign_id: int, interaction_type: str, 
                                conversion_value: float = None):
        """Update aggregated campaign metrics based on interaction"""
        with self.conn.cursor() as cur:
            # Get or create today's metrics
            cur.execute(
                """
                INSERT INTO campaign_metrics (campaign_id, metric_date)
                VALUES (%s, CURRENT_DATE)
                ON CONFLICT (campaign_id, metric_date) DO NOTHING
                """,
                (campaign_id,)
            )
            
            # Update specific metric
            if interaction_type == 'email_open':
                cur.execute(
                    """
                    UPDATE campaign_metrics 
                    SET emails_opened = emails_opened + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE campaign_id = %s AND metric_date = CURRENT_DATE
                    """,
                    (campaign_id,)
                )
            elif interaction_type == 'click':
                cur.execute(
                    """
                    UPDATE campaign_metrics 
                    SET links_clicked = links_clicked + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE campaign_id = %s AND metric_date = CURRENT_DATE
                    """,
                    (campaign_id,)
                )
            elif interaction_type == 'conversion':
                cur.execute(
                    """
                    UPDATE campaign_metrics 
                    SET conversions = conversions + 1,
                        revenue_generated = revenue_generated + COALESCE(%s, 0),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE campaign_id = %s AND metric_date = CURRENT_DATE
                    """,
                    (conversion_value or 0, campaign_id)
                )
            
            self.conn.commit()
    
    def record_campaign_send(self, campaign_id: int, count: int = 1):
        """Record that emails/messages were sent for a campaign"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO campaign_metrics (campaign_id, metric_date, emails_sent)
                VALUES (%s, CURRENT_DATE, %s)
                ON CONFLICT (campaign_id, metric_date) 
                DO UPDATE SET emails_sent = campaign_metrics.emails_sent + EXCLUDED.emails_sent
                """,
                (campaign_id, count)
            )
            self.conn.commit()
    
    def get_campaign_metrics(self, campaign_id: int, start_date: datetime = None, 
                            end_date: datetime = None) -> List[Dict]:
        """Get campaign performance metrics for date range"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT * FROM campaign_metrics WHERE campaign_id = %s"
            params = [campaign_id]
            
            if start_date:
                query += " AND metric_date >= %s"
                params.append(start_date.date())
            if end_date:
                query += " AND metric_date <= %s"
                params.append(end_date.date())
            
            query += " ORDER BY metric_date DESC"
            cur.execute(query, params)
            return cur.fetchall()
    
    def get_campaign_summary(self, campaign_id: int) -> Dict:
        """Get aggregated summary of campaign performance"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT 
                    SUM(emails_sent) as total_sent,
                    SUM(emails_opened) as total_opened,
                    SUM(links_clicked) as total_clicks,
                    SUM(conversions) as total_conversions,
                    SUM(revenue_generated) as total_revenue,
                    SUM(cost_incurred) as total_cost,
                    CASE 
                        WHEN SUM(emails_sent) > 0 
                        THEN ROUND((SUM(emails_opened)::numeric / SUM(emails_sent) * 100), 2)
                        ELSE 0 
                    END as open_rate,
                    CASE 
                        WHEN SUM(emails_opened) > 0 
                        THEN ROUND((SUM(links_clicked)::numeric / SUM(emails_opened) * 100), 2)
                        ELSE 0 
                    END as click_through_rate,
                    CASE 
                        WHEN SUM(emails_sent) > 0 
                        THEN ROUND((SUM(conversions)::numeric / SUM(emails_sent) * 100), 2)
                        ELSE 0 
                    END as conversion_rate
                FROM campaign_metrics
                WHERE campaign_id = %s
                """,
                (campaign_id,)
            )
            result = cur.fetchone()
            
            if result:
                return dict(result)
            return {}
    
    def calculate_roi(self, campaign_id: int, total_cost: float = None) -> Dict:
        """
        Calculate and store ROI for a campaign.
        ROI = (Revenue - Cost) / Cost * 100
        """
        summary = self.get_campaign_summary(campaign_id)
        
        # Get cost from summary or parameter
        cost = float(total_cost or summary.get('total_cost', 0) or 0)
        revenue = float(summary.get('total_revenue', 0) or 0)
        
        # Calculate ROI
        if cost > 0:
            roi_percentage = ((revenue - cost) / cost) * 100
        else:
            roi_percentage = 0 if revenue == 0 else float('inf')
        
        # Store in database
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO campaign_roi (campaign_id, total_cost, total_revenue)
                VALUES (%s, %s, %s)
                ON CONFLICT (campaign_id) 
                DO UPDATE SET 
                    total_cost = EXCLUDED.total_cost,
                    total_revenue = EXCLUDED.total_revenue,
                    calculated_at = CURRENT_TIMESTAMP
                """,
                (campaign_id, cost, revenue)
            )
            self.conn.commit()
        
        return {
            'campaign_id': campaign_id,
            'total_cost': cost,
            'total_revenue': revenue,
            'roi_percentage': round(roi_percentage, 2),
            'profit': revenue - cost
        }
    
    def get_campaign_roi(self, campaign_id: int) -> Optional[Dict]:
        """Retrieve calculated ROI for campaign"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM campaign_roi WHERE campaign_id = %s", (campaign_id,))
            return cur.fetchone()
    
    def get_dashboard_data(self, start_date: datetime = None, end_date: datetime = None) -> Dict:
        """
        Get comprehensive dashboard data for Marketing Admin PC.
        Includes active campaigns, top performers, and aggregate metrics.
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Active campaigns count
            cur.execute("SELECT COUNT(*) as active_campaigns FROM campaigns WHERE status = 'active'")
            active_count = cur.fetchone()['active_campaigns']
            
            # Total metrics across all campaigns
            cur.execute(
                """
                SELECT 
                    SUM(emails_sent) as total_emails_sent,
                    SUM(emails_opened) as total_emails_opened,
                    SUM(conversions) as total_conversions,
                    SUM(revenue_generated) as total_revenue
                FROM campaign_metrics
                WHERE metric_date BETWEEN %s AND %s
                """,
                (start_date.date(), end_date.date())
            )
            totals = cur.fetchone()
            
            # Top performing campaigns by conversion rate
            cur.execute(
                """
                SELECT 
                    c.campaign_id,
                    c.campaign_name,
                    c.campaign_type,
                    SUM(cm.conversions) as conversions,
                    SUM(cm.revenue_generated) as revenue,
                    CASE 
                        WHEN SUM(cm.emails_sent) > 0 
                        THEN ROUND((SUM(cm.conversions)::numeric / SUM(cm.emails_sent) * 100), 2)
                        ELSE 0 
                    END as conversion_rate
                FROM campaigns c
                JOIN campaign_metrics cm ON c.campaign_id = cm.campaign_id
                WHERE cm.metric_date BETWEEN %s AND %s
                GROUP BY c.campaign_id, c.campaign_name, c.campaign_type
                ORDER BY conversion_rate DESC
                LIMIT 5
                """,
                (start_date.date(), end_date.date())
            )
            top_campaigns = cur.fetchall()
            
            # Recent customer interactions
            cur.execute(
                """
                SELECT 
                    ci.interaction_type,
                    COUNT(*) as count,
                    SUM(COALESCE(ci.conversion_value, 0)) as total_value
                FROM customer_interactions ci
                WHERE ci.interaction_timestamp BETWEEN %s AND %s
                GROUP BY ci.interaction_type
                ORDER BY count DESC
                """,
                (start_date, end_date)
            )
            interactions = cur.fetchall()
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'active_campaigns': active_count,
            'totals': dict(totals) if totals else {},
            'top_performing_campaigns': [dict(c) for c in top_campaigns],
            'interaction_breakdown': [dict(i) for i in interactions]
        }
    
    def get_segment_performance(self, segment_id: int) -> Dict:
        """Analyze performance of campaigns targeting a specific segment"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT 
                    COUNT(DISTINCT c.campaign_id) as total_campaigns,
                    SUM(cm.emails_sent) as total_sent,
                    SUM(cm.conversions) as total_conversions,
                    SUM(cm.revenue_generated) as total_revenue,
                    AVG(
                        CASE 
                            WHEN cm.emails_sent > 0 
                            THEN (cm.conversions::numeric / cm.emails_sent * 100)
                            ELSE 0 
                        END
                    ) as avg_conversion_rate
                FROM campaigns c
                LEFT JOIN campaign_metrics cm ON c.campaign_id = cm.campaign_id
                WHERE c.target_segment_id = %s
                """,
                (segment_id,)
            )
            return dict(cur.fetchone() or {})
    
    def get_customer_engagement_history(self, customer_id: int, limit: int = 50) -> List[Dict]:
        """Get customer's interaction history across all campaigns"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT 
                    ci.*,
                    c.campaign_name,
                    c.campaign_type
                FROM customer_interactions ci
                JOIN campaigns c ON ci.campaign_id = c.campaign_id
                WHERE ci.customer_id = %s
                ORDER BY ci.interaction_timestamp DESC
                LIMIT %s
                """,
                (customer_id, limit)
            )
            return cur.fetchall()
    
    def generate_attribution_report(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Attribution report: Which campaigns generated revenue.
        Critical for measuring marketing's contribution to sales.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT 
                    c.campaign_id,
                    c.campaign_name,
                    c.campaign_type,
                    COUNT(DISTINCT ci.customer_id) as unique_customers_engaged,
                    SUM(ci.conversion_value) as attributed_revenue,
                    SUM(cm.cost_incurred) as campaign_cost,
                    CASE 
                        WHEN SUM(cm.cost_incurred) > 0 
                        THEN ROUND(((SUM(ci.conversion_value) - SUM(cm.cost_incurred)) / SUM(cm.cost_incurred) * 100), 2)
                        ELSE 0 
                    END as roi_percentage
                FROM campaigns c
                LEFT JOIN customer_interactions ci ON c.campaign_id = ci.campaign_id 
                    AND ci.interaction_type = 'conversion'
                    AND ci.interaction_timestamp BETWEEN %s AND %s
                LEFT JOIN campaign_metrics cm ON c.campaign_id = cm.campaign_id
                    AND cm.metric_date BETWEEN %s AND %s
                GROUP BY c.campaign_id, c.campaign_name, c.campaign_type
                HAVING SUM(ci.conversion_value) > 0
                ORDER BY attributed_revenue DESC
                """,
                (start_date, end_date, start_date.date(), end_date.date())
            )
            return cur.fetchall()
    
    def get_conversion_funnel(self, campaign_id: int) -> Dict:
        """Analyze conversion funnel: sent -> opened -> clicked -> converted"""
        summary = self.get_campaign_summary(campaign_id)
        
        sent = int(summary.get('total_sent', 0) or 0)
        opened = int(summary.get('total_opened', 0) or 0)
        clicked = int(summary.get('total_clicks', 0) or 0)
        converted = int(summary.get('total_conversions', 0) or 0)
        
        return {
            'campaign_id': campaign_id,
            'funnel_stages': {
                'sent': sent,
                'opened': opened,
                'clicked': clicked,
                'converted': converted
            },
            'conversion_rates': {
                'sent_to_open': round((opened / sent * 100), 2) if sent > 0 else 0,
                'open_to_click': round((clicked / opened * 100), 2) if opened > 0 else 0,
                'click_to_conversion': round((converted / clicked * 100), 2) if clicked > 0 else 0,
                'overall': round((converted / sent * 100), 2) if sent > 0 else 0
            },
            'drop_off': {
                'after_send': sent - opened,
                'after_open': opened - clicked,
                'after_click': clicked - converted
            }
        }
