# Container image for ERAS – for hospital IT setups based on Docker/Podman/Kubernetes.
#
# Build:  docker build -t eras:latest .
# Run:    docker run --env-file .env -v eras-data:/app/data -p 8000:8000 eras:latest
#
# Database: SQLite in the volume /app/data by default. The volume must persist,
# otherwise all data is lost when the container is replaced.
# For PostgreSQL set POSTGRES_DB etc. in .env; the volume is then not needed.
#
# The container does not run migrations automatically; run them once per release
# (with the same volume):
#   docker run --rm --env-file .env -v eras-data:/app/data eras:latest python manage.py migrate

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GUNICORN_BIND=0.0.0.0:8000 \
    SQLITE_PATH=/app/data/db.sqlite3 \
    # ANPASSEN (Hosting): IP/Netz des vorgeschalteten Proxys/Ingress statt "*".
    GUNICORN_FORWARDED_ALLOW_IPS=*

# Tesseract is required for OCR of scanned lab reports.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --system --create-home --uid 10001 eras
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# collectstatic needs settings to import; dummy values are used only at build time.
RUN DJANGO_ENV=production \
    DJANGO_SECRET_KEY=build-only-build-only-build-only-build-only-build-only \
    DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput \
    && mkdir -p /app/data \
    && chown -R eras:eras /app

USER eras
VOLUME ["/app/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/', timeout=4)"

CMD ["gunicorn", "-c", "deploy/gunicorn.conf.py", "eras_project.wsgi:application"]
