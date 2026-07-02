---
name: novena-hub-architecture
description: Use for Novena Hub codebase mapping, Django app placement, tenancy/data model decisions, service-layer design, TimescaleDB telemetry architecture, Redis/Celery/MQTT flows, and deciding where new Hub behavior should live.
---

# Novena Hub Architecture

Read references/hub_architecture.md before adding or moving backend behavior, models, services, telemetry paths, or cross-app integrations.

Default rules:

1. Scope tenant data by request.team or team relations.
2. Put business workflows in apps/{app}/services.py unless the app already has a more specific local pattern.
3. Keep views focused on permissions, request/response handling, and template context.
4. Prefer existing app boundaries over new abstractions.
5. Verify with focused tests plus python manage.py check when touching Django behavior.
