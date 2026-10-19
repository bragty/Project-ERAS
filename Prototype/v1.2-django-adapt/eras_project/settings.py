"""Django settings for the ERAS project.

All environment-specific values come from environment variables (see
``.env.example``). ``DJANGO_ENV`` selects the profile:

- ``development`` (default): local work and the current school VM. Behaviour is
  unchanged from the prototype (DEBUG on, fallback secret key, HTTP allowed).
- ``production``: strict profile for the hospital deployment. Startup fails if
  mandatory values are missing, DEBUG defaults to off and HTTPS hardening is on.

Places that must be adjusted for a concrete hosting are marked with
``ANPASSEN (Hosting)``.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    return int(os.getenv(name, str(default)))


def env_list(name, default=""):
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


DJANGO_ENV = os.getenv("DJANGO_ENV", "development").strip().lower()
if DJANGO_ENV not in {"development", "production"}:
    raise ImproperlyConfigured("DJANGO_ENV muss 'development' oder 'production' sein.")
IS_PRODUCTION = DJANGO_ENV == "production"

# --- Core -------------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", not IS_PRODUCTION)
if IS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG darf in Produktion nicht aktiv sein.")

_DEV_SECRET_KEY = "django-insecure-eras-prototype-development-key"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "" if IS_PRODUCTION else _DEV_SECRET_KEY)
if IS_PRODUCTION and (not SECRET_KEY or SECRET_KEY == _DEV_SECRET_KEY or len(SECRET_KEY) < 50):
    # ANPASSEN (Hosting): eigenen Zufallswert (>= 50 Zeichen) als Secret hinterlegen.
    raise ImproperlyConfigured("DJANGO_SECRET_KEY fehlt oder ist unsicher.")

# ANPASSEN (Hosting): Hostname(s), unter denen die Spital-IT die App erreichbar
# macht, z. B. "eras.ksw.ch". In Produktion gibt es bewusst keinen Default.
ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "" if IS_PRODUCTION else "bene-ksw.init-lab.ch,160.85.252.95,127.0.0.1,localhost",
)
if IS_PRODUCTION and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS muss in Produktion gesetzt sein.")

# ANPASSEN (Hosting): vollständige Origins inkl. Schema, z. B. "https://eras.ksw.ch".
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# auth/sessions/messages exist only for the Django admin backoffice. The clinical
# frontend and the API remain login-free.
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "eras",
    "apps.core.apps.CoreConfig",
    "apps.patients.apps.PatientsConfig",
    "apps.checklist.apps.ChecklistConfig",
    "apps.responses.apps.ResponsesConfig",
    "apps.workflow.apps.WorkflowConfig",
    "apps.audit.apps.AuditConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves collected static files directly from Django/Gunicorn, so the app
    # does not depend on a specific reverse-proxy configuration for /static/.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "eras_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "eras_project.wsgi.application"

# --- Database ---------------------------------------------------------------

# Standard ist SQLite – auch in Produktion (eine Datei, kein eigener DB-Server).
# ANPASSEN (Hosting): Wer lieber PostgreSQL betreibt (z. B. eine andere Klinik mit
# vorhandener DB-Infrastruktur), setzt POSTGRES_DB; dann wird automatisch
# PostgreSQL verwendet. Danach "python manage.py migrate" ausführen.
if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", "eras"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", 60),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                # ANPASSEN (Hosting): "require"/"verify-full", wenn die DB auf
                # einem anderen Server liegt und TLS anbietet.
                "sslmode": os.getenv("POSTGRES_SSLMODE", "prefer"),
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            # ANPASSEN (Hosting): In Produktion einen eigenen Datenordner ausserhalb
            # des Code-Verzeichnisses verwenden, z. B. /opt/eras/data/db.sqlite3.
            # Der App-User braucht Schreibrechte auf den Ordner (nicht nur die
            # Datei), weil SQLite daneben WAL-/Journal-Dateien anlegt.
            "NAME": Path(os.getenv("SQLITE_PATH", BASE_DIR / "db.sqlite3")),
            "OPTIONS": {
                # Several Gunicorn workers write concurrently: wait for locks
                # instead of failing immediately with "database is locked".
                "timeout": env_int("SQLITE_TIMEOUT_SECONDS", 20),
                # Take the write lock at transaction start, which avoids lock
                # upgrade deadlocks between workers.
                "transaction_mode": "IMMEDIATE",
                # WAL lets readers continue while one worker writes.
                "init_command": "PRAGMA journal_mode=WAL;",
            },
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Passwords (Django admin accounts) ---------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalisation ---------------------------------------------------

LANGUAGE_CODE = "de-ch"
TIME_ZONE = "Europe/Zurich"
USE_I18N = True
USE_TZ = True

# --- Static files -------------------------------------------------------------

STATIC_URL = "static/"
# ANPASSEN (Hosting): Zielordner von "collectstatic"; muss für den App-User
# schreib- und lesbar sein.
STATIC_ROOT = Path(os.getenv("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Production: hashed, compressed, long-cacheable files (requires
        # "python manage.py collectstatic" on every deployment).
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if IS_PRODUCTION
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

# --- Security -----------------------------------------------------------------

# The prototype is same-origin only. The API is intentionally unauthenticated,
# but write operations remain protected by Django's CSRF middleware.
# ANPASSEN (Hosting): Vor dem Einsatz mit echten Patientendaten müssen Frontend
# und API hinter eine Authentifizierung (z. B. SSO/Reverse-Proxy-Login der
# Spital-IT oder Django-Login). Das Admin allein schützt die Daten nicht.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# Admin sessions expire after 8 hours and when the browser is closed.
SESSION_COOKIE_AGE = env_int("DJANGO_SESSION_COOKIE_AGE", 8 * 60 * 60)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# HTTPS hardening. On by default in production, off for development and the
# current HTTP-only school VM. Only disable in production for a closed test
# setup without TLS – never with real patient data.
USE_HTTPS = env_bool("DJANGO_HTTPS", IS_PRODUCTION)
if USE_HTTPS:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # ANPASSEN (Hosting): Falls TLS vor Django terminiert (Nginx, Load-Balancer,
    # Ingress), muss der Proxy "X-Forwarded-Proto: https" setzen und eingehende
    # gleichnamige Header von Clients überschreiben. Sonst entstehen
    # Redirect-Schleifen bzw. Django erkennt HTTPS nicht.
    if env_bool("DJANGO_BEHIND_TLS_PROXY", True):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # ANPASSEN (Hosting): auf false setzen, wenn bereits der Proxy auf HTTPS umleitet.
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    # ANPASSEN (Hosting): zuerst klein (3600) testen, danach 31536000 (1 Jahr).
    SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 3600)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = False

# Health endpoint must stay reachable over plain HTTP for internal load-balancer
# probes even when SECURE_SSL_REDIRECT is on.
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]

# Django admin (backoffice). The path is configurable so it can be moved away
# from the well-known "/admin/".
# ANPASSEN (Hosting): in Produktion einen nicht erratbaren Pfad setzen und den
# Pfad zusätzlich per Proxy/Firewall auf das Spitalnetz beschränken.
ADMIN_URL = os.getenv("DJANGO_ADMIN_URL", "admin/").strip("/") + "/"

# --- Uploads ------------------------------------------------------------------

# Laboratory report import. The first prototype processes one file per request
# synchronously and keeps no permanent copy of the uploaded report.
# ANPASSEN (Hosting): Upload-Limit des Proxys (z. B. Nginx client_max_body_size)
# muss mindestens LAB_IMPORT_MAX_BYTES betragen.
LAB_IMPORT_MAX_BYTES = env_int("LAB_IMPORT_MAX_BYTES", 10 * 1024 * 1024)
LAB_IMPORT_MAX_PAGES = env_int("LAB_IMPORT_MAX_PAGES", 10)
LAB_IMPORT_MAX_IMAGE_PIXELS = env_int("LAB_IMPORT_MAX_IMAGE_PIXELS", 25000000)
LAB_IMPORT_OCR_TIMEOUT_SECONDS = env_int("LAB_IMPORT_OCR_TIMEOUT_SECONDS", 30)
LAB_IMPORT_OCR_LANG = os.getenv("LAB_IMPORT_OCR_LANG", "deu+eng")

# --- Logging ------------------------------------------------------------------

# Logs go to stdout/stderr so that systemd (journalctl), Docker or the hospital's
# log collector can pick them up. Patient data must not be logged.
# ANPASSEN (Hosting): Falls die Spital-IT ein zentrales Logsystem (Syslog, ELK,
# Splunk …) vorgibt, hier einen passenden Handler ergänzen.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
