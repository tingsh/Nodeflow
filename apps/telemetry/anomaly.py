import logging
from django.db.models import Avg, StdDev
from django.utils import timezone
from datetime import timedelta
from .models import TelemetryData

logger = logging.getLogger('iot_platform')

def get_z_score_insight(device, key):
    """
    Calculates if the latest value is a statistical outlier (z-score > 2).
    """
    # Get last 100 points or last 24 hours
    lookback = timezone.now() - timedelta(hours=24)
    stats = TelemetryData.objects.filter(
        device=device,
        key=key,
        timestamp__gte=lookback,
        value_numeric__isnull=False
    ).aggregate(
        avg=Avg('value_numeric'),
        std=StdDev('value_numeric')
    )
    
    avg = stats.get('avg')
    std = stats.get('std')
    
    if avg is None or not std:
        return None
        
    latest_val = TelemetryData.objects.filter(device=device, key=key).first()
    if not latest_val or latest_val.value_numeric is None:
        return None
        
    z_score = abs(latest_val.value_numeric - avg) / std
    
    if z_score > 2.5:
        return {
            "type": "anomaly",
            "severity": "high" if z_score > 4 else "medium",
            "message": f"Significant deviation detected in {key.replace('_', ' ')}. Value is {z_score:.1f}x the standard deviation.",
            "value": latest_val.value_numeric
        }
    return None

def get_weekly_trend_insight(device, key):
    """
    Compares current hour average with same hour last week.
    """
    now = timezone.now()
    hour_ago = now - timedelta(hours=1)
    
    current_avg = TelemetryData.objects.filter(
        device=device,
        key=key,
        timestamp__gte=hour_ago
    ).aggregate(avg=Avg('value_numeric'))['avg']
    
    last_week_start = now - timedelta(days=7, hours=1)
    last_week_end = now - timedelta(days=7)
    
    last_week_avg = TelemetryData.objects.filter(
        device=device,
        key=key,
        timestamp__gte=last_week_start,
        timestamp__lte=last_week_end
    ).aggregate(avg=Avg('value_numeric'))['avg']
    
    if current_avg is None or last_week_avg is None or last_week_avg == 0:
        return None
        
    diff_pct = ((current_avg - last_week_avg) / last_week_avg) * 100
    
    if abs(diff_pct) > 10:
        direction = "higher" if diff_pct > 0 else "lower"
        return {
            "type": "trend",
            "message": f"Power usage is {abs(diff_pct):.1f}% {direction} today compared to the same hour last week.",
            "value": f"{diff_pct:+.1f}%"
        }
    return None

def get_ai_insights(device):
    """
    Aggregates all statistical insights into a human-readable list.
    """
    insights = []
    
    # Check for power-related insights
    z_insight = get_z_score_insight(device, "active_power")
    if z_insight:
        insights.append(z_insight)
        
    trend_insight = get_weekly_trend_insight(device, "active_power")
    if trend_insight:
        insights.append(trend_insight)
        
    # Check for voltage stability
    v_insight = get_z_score_insight(device, "voltage")
    if v_insight:
        insights.append(v_insight)
        
    return insights
