#!/bin/bash
cd /www/wwwroot/aikefu
source /www/wwwroot/aikefu/venv/bin/activate
exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 2 \
  --threads 4 \
  --timeout 120 \
  --access-logfile /www/wwwroot/aikefu/logs/access.log \
  --error-logfile /www/wwwroot/aikefu/logs/error.log \
  --log-level info \
  "app:create_app()"
