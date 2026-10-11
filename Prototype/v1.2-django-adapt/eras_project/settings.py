import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-eras-prototype-development-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() in {"1", "true", "yes"}

ALLOWED_HOSTS = [
    value.strip()
    for value in os.getenv(
        "DJANGO_ALLOWED_HOSTS",
        "bene-ksw.init-lab.ch,160.85.252.95,127.0.0.1,localhost",
    ).split(",")
    if value.strip()
]

# Deliberately no django.contrib.auth/admin/sessions: the prototype has no login/user system.
INSTALLED_APPS = [
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
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "eras_project.wsgi.application"

if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", "eras"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

LANGUAGE_CODE = "de-ch"
TIME_ZONE = "Europe/Zurich"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CSRF_TRUSTED_ORIGINS = [
    value.strip()
    for value in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if value.strip()
]

# The prototype is same-origin only. The API is intentionally unauthenticated,
# but write operations remain protected by Django's CSRF middleware.
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Laboratory report import. The first prototype processes one file per request
# synchronously and keeps no permanent copy of the uploaded report.
LAB_IMPORT_MAX_BYTES = int(os.getenv("LAB_IMPORT_MAX_BYTES", str(10 * 1024 * 1024)))
LAB_IMPORT_MAX_PAGES = int(os.getenv("LAB_IMPORT_MAX_PAGES", "10"))
LAB_IMPORT_MAX_IMAGE_PIXELS = int(os.getenv("LAB_IMPORT_MAX_IMAGE_PIXELS", "25000000"))
LAB_IMPORT_OCR_TIMEOUT_SECONDS = int(os.getenv("LAB_IMPORT_OCR_TIMEOUT_SECONDS", "30"))
LAB_IMPORT_OCR_LANG = os.getenv("LAB_IMPORT_OCR_LANG", "deu+eng")
