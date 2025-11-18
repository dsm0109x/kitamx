"""Gunicorn configuration for Kita production."""
import multiprocessing

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Process naming
proc_name = "kita"

# Logging
accesslog = "/home/kita/logs/gunicorn-access.log"
errorlog = "/home/kita/logs/gunicorn-error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Server mechanics
daemon = False
pidfile = "/home/kita/kita/gunicorn.pid"
user = "kita"
group = "kita"
umask = 0o007
tmp_upload_dir = None

# Preload app for better memory usage
preload_app = True

# Max requests per worker (prevent memory leaks)
max_requests = 1000
max_requests_jitter = 50
