"""Flush local Redis ingestion queues during hardware tests.

This is a local development helper for machines that are not running Celery.
It periodically invokes the same task functions Celery Beat would run.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "novena_hub.settings")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import django  # noqa: E402

django.setup()

from apps.telemetry.tasks import flush_logs_buffer_task, flush_telemetry_buffer_task  # noqa: E402


if __name__ == "__main__":
    print("dev_flush_redis_queues running", flush=True)
    while True:
        try:
            telemetry_result = flush_telemetry_buffer_task()
            logs_result = flush_logs_buffer_task()
            if telemetry_result != "No telemetry to ingest" or logs_result != "No logs to ingest":
                print(f"{telemetry_result}; {logs_result}", flush=True)
        except Exception as exc:
            print(f"flush error: {exc}", flush=True)
        time.sleep(5)

