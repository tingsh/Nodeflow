import json
from django.db.models import Avg, Max, Min, Q
from django.utils import timezone
from datetime import timedelta, datetime
from apps.devices.models import Device
from apps.telemetry.models import TelemetryData
from apps.alerts.models import Alert

class NodeflowToolExecutor:
    def __init__(self, team):
        self.team = team

    def execute(self, tool_name, kwargs):
        """
        Execute a tool by name with provided arguments.
        """
        method = getattr(self, tool_name, None)
        if method:
            try:
                return method(**kwargs)
            except Exception as e:
                return {"error": str(e)}
        return {"error": f"Tool {tool_name} not found."}

    def get_device_status(self, device_ids=None):
        devices = self.team.device_set.all()
        if device_ids:
            devices = devices.filter(id__in=device_ids)

        results = []
        for device in devices:
            latest = TelemetryData.objects.filter(device=device).order_by('-timestamp').first()
            recent_readings = []
            if latest:
                # get all readings from the same timestamp (roughly)
                readings = TelemetryData.objects.filter(
                    device=device, 
                    timestamp__gte=latest.timestamp - timedelta(seconds=10)
                )
                for r in readings:
                    recent_readings.append({
                        "key": r.key,
                        "value": r.value_numeric or r.value_string or r.value_bool,
                        "timestamp": r.timestamp.isoformat()
                    })
            
            results.append({
                "id": device.id,
                "name": device.name,
                "status": device.status,
                "last_seen": device.last_telemetry_at.isoformat() if device.last_telemetry_at else None,
                "readings": recent_readings
            })
        return results

    def get_energy_data(self, device_ids, keys, start_date, end_date, aggregation='hour'):
        try:
            from datetime import timezone as dt_timezone
            start = datetime.fromisoformat(start_date).replace(tzinfo=dt_timezone.utc)
            end = datetime.fromisoformat(end_date).replace(tzinfo=dt_timezone.utc)
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD."}

        # Ensure devices belong to the team
        devices = self.team.device_set.filter(id__in=device_ids)
        
        qs = TelemetryData.objects.filter(
            device__in=devices,
            key__in=keys,
            timestamp__range=(start, end),
            value_numeric__isnull=False
        )

        from django.db.models.functions import TruncHour, TruncDay, TruncWeek
        trunc_func = {
            'hour': TruncHour,
            'day': TruncDay,
            'week': TruncWeek
        }.get(aggregation, TruncHour)

        data = qs.annotate(bucket=trunc_func('timestamp')).values('bucket', 'device__name', 'key').annotate(
            avg_value=Avg('value_numeric'),
            max_value=Max('value_numeric'),
            min_value=Min('value_numeric')
        ).order_by('bucket')

        results = []
        for item in data:
            results.append({
                "time": item['bucket'].isoformat(),
                "device": item['device__name'],
                "key": item['key'],
                "avg": round(item['avg_value'], 2),
                "max": round(item['max_value'], 2),
                "min": round(item['min_value'], 2)
            })

        return results

    def get_alerts_summary(self, days=7, status=None):
        start_date = timezone.now() - timedelta(days=days)
        qs = Alert.objects.filter(team=self.team, triggered_at__gte=start_date)
        if status:
            qs = qs.filter(status=status)
        
        alerts = qs.select_related('rule', 'device').order_by('-triggered_at')[:50]
        
        results = []
        for a in alerts:
            results.append({
                "id": a.id,
                "rule": a.rule.name,
                "device": a.device.name,
                "triggered_at": a.triggered_at.isoformat(),
                "status": a.status,
                "severity": a.rule.get_severity_display(),
                "value": a.trigger_value
            })
        return results
