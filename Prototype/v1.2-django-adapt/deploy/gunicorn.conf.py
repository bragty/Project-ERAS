"""Gunicorn configuration for the ERAS backend.

Start: gunicorn -c deploy/gunicorn.conf.py eras_project.wsgi:application
All values can be overridden via environment variables.
"""

import multiprocessing
import os

# ANPASSEN (Hosting): Adresse/Port, auf die der Reverse-Proxy der Spital-IT
# weiterleitet. 127.0.0.1 = nur lokal erreichbar (Proxy auf demselben Server);
# im Container "0.0.0.0:8000".
bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")

# ANPASSEN (Hosting): an CPU/RAM des Servers anpassen (Faustregel 2 × CPU + 1).
workers = int(os.getenv("GUNICORN_WORKERS", str(multiprocessing.cpu_count() * 2 + 1)))
threads = int(os.getenv("GUNICORN_THREADS", "2"))

# Lab import runs OCR synchronously (LAB_IMPORT_OCR_TIMEOUT_SECONDS, default 30 s),
# so the worker timeout must be clearly larger.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "90"))
graceful_timeout = 30
keepalive = 5

# Recycle workers regularly to contain memory growth from PDF/OCR processing.
max_requests = 1000
max_requests_jitter = 100

# Logs to stdout/stderr (journalctl / docker logs). Access logs contain URLs with
# case numbers but no patient names or medical content.
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Only trust X-Forwarded-* headers from the local reverse proxy.
# ANPASSEN (Hosting): IP des Proxys/Load-Balancers, falls er nicht lokal läuft.
forwarded_allow_ips = os.getenv("GUNICORN_FORWARDED_ALLOW_IPS", "127.0.0.1")
