FROM python:3.11-slim

# Install nginx, supervisor, and envsubst (gettext-base)
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

CMD ["/app/start.sh"]
