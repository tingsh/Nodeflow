import os

import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "iot_platform.settings")
django.setup()

from apps.devices.models import DeviceTemplate  # noqa: E402


def seed_templates():
    templates = [
        {
            "name": "Eastron SDM630",
            "manufacturer": "Eastron",
            "model_number": "SDM630-Modbus-V2",
            "device_type": "power_meter",
            "protocol": "modbus_tcp",
            "category": "energy",
            "register_map": {"active_power": 12, "voltage": 0, "current": 6, "kwh_total": 342},
        },
        {
            "name": "Schneider PM5110",
            "manufacturer": "Schneider Electric",
            "model_number": "METSEPM5110",
            "device_type": "power_meter",
            "protocol": "modbus_tcp",
            "category": "energy",
            "register_map": {"active_power": 3060, "voltage": 3028, "active_energy": 3204},
        },
        {
            "name": "Generic Temperature Sensor",
            "manufacturer": "Generic",
            "model_number": "TH-01",
            "device_type": "sensor",
            "protocol": "modbus_tcp",
            "category": "cold_chain",
            "register_map": {"temperature": 1, "humidity": 2},
        },
    ]

    for t in templates:
        obj, created = DeviceTemplate.objects.get_or_create(name=t["name"], defaults=t)
        if created:
            print(f"Created template: {obj.name}")
        else:
            print(f"Template already exists: {obj.name}")


if __name__ == "__main__":
    seed_templates()
