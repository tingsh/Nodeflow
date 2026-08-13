#!/usr/bin/env bash
set -euo pipefail

ROOT="${NOVENA_HUB_ROOT:-/home/shouheng/Novena-Platform/Novena-Hub}"
cd "$ROOT"

start_service() {
  local name="$1"
  shift

  mkdir -p "$ROOT/.dev-pids"
  if [[ -f "$ROOT/.dev-pids/$name.pid" ]]; then
    local old_pid
    old_pid="$(cat "$ROOT/.dev-pids/$name.pid")"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
      kill "$old_pid" 2>/dev/null || true
      sleep 1
    fi
  fi

  setsid "$@" > "$ROOT/$name.log" 2> "$ROOT/$name.err.log" < /dev/null &
  echo "$!" > "$ROOT/.dev-pids/$name.pid"
  echo "$name pid $(cat "$ROOT/.dev-pids/$name.pid")"
}

start_service "mosquitto-wsl" /usr/sbin/mosquitto -c "$ROOT/mosquitto/wsl-lan-test.conf" -v
start_service "django-wsl" "/home/shouheng/.venvs/novena/bin/python" manage.py runserver 0.0.0.0:8000 --noreload
start_service "celery-wsl" "/home/shouheng/.venvs/novena/bin/celery" -A novena_hub worker -l INFO -B --pool=solo
start_service "mqtt-consumer-wsl" "/home/shouheng/.venvs/novena/bin/python" manage.py mqtt_consumer
start_service "vite-wsl" npm run dev -- --host 0.0.0.0 --force
