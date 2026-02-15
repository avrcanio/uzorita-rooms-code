from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parents[2]


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


SECRET_KEY = env("DJANGO_SECRET_KEY", "change-me")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "config",
    "reception",
    "communications",
    "rooms",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": env("DB_ENGINE", "django.db.backends.postgresql"),
        "NAME": env("DB_NAME", "postgres"),
        "USER": env("DB_USER", "postgres"),
        "PASSWORD": env("DB_PASSWORD", "postgres"),
        "HOST": env("DB_HOST", "host.docker.internal"),
        "PORT": env("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "hr"
TIME_ZONE = "Europe/Zagreb"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# File uploads
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Uzorita Rooms API",
    "DESCRIPTION": "Django REST API za Uzorita Rooms.",
    "VERSION": "1.0.0",
}

# Mail / IMAP configuration (M2)
MAILBOX_EMAIL = env("MAILBOX_EMAIL", "")
MAILBOX_PASSWORD = env("MAILBOX_PASSWORD", "")
IMAP_HOST = env("IMAP_HOST", "")
IMAP_PORT = int(env("IMAP_PORT", "993"))
IMAP_USE_SSL = env_bool("IMAP_USE_SSL", default=True)
IMAP_FOLDER = env("IMAP_FOLDER", "INBOX")

EMAIL_HOST = env("SMTP_HOST", "")
EMAIL_PORT = int(env("SMTP_PORT", "465"))
EMAIL_HOST_USER = env("SMTP_USER", "")
EMAIL_HOST_PASSWORD = env("SMTP_PASSWORD", "")
EMAIL_USE_SSL = env_bool("SMTP_USE_SSL", default=True)
EMAIL_USE_TLS = env_bool("SMTP_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("MAILBOX_EMAIL", "noreply@localhost")
