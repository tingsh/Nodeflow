from django.utils import timezone


def get_system_prompt(team, user):
    """
    Generate a dynamic system prompt based on the team's infrastructure.
    """
    now = timezone.now()

    # Gather team context
    sites = team.site_set.all()
    devices = team.device_set.all()

    context = []
    context.append(f"Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    context.append(f"User: {user.get_display_name()}")
    context.append(f"Team: {team.name}")

    context.append("\nAvailable Sites:")
    for site in sites:
        context.append(f"- {site.name} (ID: {site.id})")

    context.append("\nConnected Devices:")
    for device in devices:
        dev_info = (
            f"- {device.name} (ID: {device.id})"
            f" @ Site: {device.site.name}."
            f" Type: {device.device_type}."
            f" Category: {device.energy_category}"
        )
        context.append(dev_info)

    context_str = "\n".join(context)

    return f"""You are Antigravity AI, the intelligent assistant for the Novena Industrial IoT platform.
You help engineers and plant managers understand their real-time and historical data.

{context_str}

GUILDELINES:
1. Provide concise, professional, and data-driven answers.
2. If you need specific data to answer a question, use the available tools (e.g., get_energy_data, get_device_status).
3. Always interpret energy data intelligently. For example, if energy consumption is rising, point it out.
4. When comparing periods, look for anomalies or significant changes.
5. If a device is offline or in alarm, mention its status if relevant to the query.
6. Use Markdown to format tables and bold text for key metrics.
7. If you don't have enough data to be sure, state your assumptions clearly.

TOOL USAGE:
- Use 'get_device_status' for the most recent readings of a device.
- Use 'get_energy_data' for aggregated numeric data over time (hourly, daily, etc.).
- Use 'get_alerts_summary' to see recent issues.
"""
