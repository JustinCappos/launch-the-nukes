# Gunicorn configuration for GCP Cloud Run deployment
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
backlog = 2048

# Worker processes - Cloud Run can handle scaling
workers = int(os.environ.get('GUNICORN_WORKERS', '4'))
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeouts for Cloud Run
timeout = 0  # Cloud Run manages timeouts
keepalive = 30
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get('LOG_LEVEL', 'info')

# Process naming
proc_name = 'launch-the-nukes-gcp'

# Server mechanics
daemon = False
preload_app = True

# Memory management for Cloud Run
worker_tmp_dir = "/dev/shm"

# Enable healthcheck endpoint
def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal")
