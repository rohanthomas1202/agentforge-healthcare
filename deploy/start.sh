#!/bin/bash
set -e

# Railway provides $PORT — default to 8080 for local testing
export PORT="${PORT:-8080}"

# Substitute PORT into nginx config
envsubst '$PORT' < /etc/nginx/nginx.conf > /etc/nginx/nginx.conf.tmp
mv /etc/nginx/nginx.conf.tmp /etc/nginx/nginx.conf

# Start supervisord (runs nginx + uvicorn + streamlit)
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
