# Gunicorn configuration for production deployment
# Usage: gunicorn -c gunicorn.conf.py app_v2:app

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
# For 10 concurrent users, use 4 workers
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 2000
max_requests_jitter = 100

# Timeouts
timeout = 30
keepalive = 2
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = 'launch-the-nukes'

# Server mechanics
daemon = False
pidfile = '/tmp/launch-the-nukes.pid'

# Memory management
preload_app = True

# Environment variables
raw_env = [
    'REDIS_URL=redis://localhost:6379/0',
    'NUM_WORKERS=0',  # Don't start job workers in web processes
]
