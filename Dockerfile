FROM python:3.11-slim

# Install nginx, supervisor, and envsubst (for dynamic PORT)
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx supervisor gettext-base && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY frontend/ ./frontend/

# Copy deployment configuration
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Create data directory for SQLite persistence
RUN mkdir -p /app/data

EXPOSE 80

# Use start.sh to substitute PORT into nginx.conf, then run supervisord
CMD ["/bin/bash", "/app/start.sh"]
