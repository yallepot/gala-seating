# gunicorn_config.py
bind = "0.0.0.0:10000"
workers = 1
worker_class = "gevent"
timeout = 120
keepalive = 5
