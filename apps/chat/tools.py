def get_tools_definition():
    """
    Returns the list of tool definitions for OpenAI/LiteLLM.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "get_device_status",
                "description": "Get the current status and most recent telemetry readings for one or more devices.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Optional list of device IDs. If omitted, returns status for all devices in the team."
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_energy_data",
                "description": "Fetch aggregated telemetry data (numeric) for specific keys over a time period.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "List of device IDs to query."
                        },
                        "keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of telemetry keys (e.g., ['active_power', 'voltage', 'temp'])."
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date in ISO format (YYYY-MM-DD)."
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date in ISO format (YYYY-MM-DD)."
                        },
                        "aggregation": {
                            "type": "string",
                            "enum": ["hour", "day", "week"],
                            "description": "Aggregation bucket size. Use 'hour' for detailed look, 'day' for trends."
                        }
                    },
                    "required": ["device_ids", "keys", "start_date", "end_date"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_alerts_summary",
                "description": "Get a summary of triggered alerts over a period of time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Number of past days to look back. Default is 7."
                        },
                        "status": {
                            "type": "string",
                            "enum": ["active", "acknowledged", "resolved"],
                            "description": "Filter by alert status."
                        }
                    }
                }
            }
        }
    ]
