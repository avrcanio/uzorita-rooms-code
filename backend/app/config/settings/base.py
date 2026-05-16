from pathlib import Path
import os

from celery.schedules import crontab


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
# Optional: TCP address for hairpin NAT (e.g. 127.0.0.1) while TLS uses IMAP_TLS_SERVERNAME or IMAP_HOST.
IMAP_CONNECT_HOST = env("IMAP_CONNECT_HOST", "")
IMAP_TLS_SERVERNAME = env("IMAP_TLS_SERVERNAME", "")

EMAIL_HOST = env("SMTP_HOST", "")
EMAIL_PORT = int(env("SMTP_PORT", "465"))
EMAIL_HOST_USER = env("SMTP_USER", "")
EMAIL_HOST_PASSWORD = env("SMTP_PASSWORD", "")
EMAIL_USE_SSL = env_bool("SMTP_USE_SSL", default=True)
EMAIL_USE_TLS = env_bool("SMTP_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("MAILBOX_EMAIL", "noreply@localhost")

# PaddleOCR HTTP service (Docker / internal URL). Empty disables remote calls until configured.
PADDLE_OCR_BASE_URL = env("PADDLE_OCR_BASE_URL", "").rstrip("/")
PADDLE_OCR_PREDICT_PATH = env("PADDLE_OCR_PREDICT_PATH", "/predict")
PADDLE_OCR_FILE_FIELD = env("PADDLE_OCR_FILE_FIELD", "file")
# multipart: raw file upload. json_images: PaddleHub Serving {"images":[base64,...]}.
PADDLE_OCR_REQUEST_FORMAT = env("PADDLE_OCR_REQUEST_FORMAT", "multipart")
PADDLE_OCR_TIMEOUT_SECONDS = float(env("PADDLE_OCR_TIMEOUT_SECONDS", "90"))
PADDLE_OCR_SCAN_MAX_BYTES = int(env("PADDLE_OCR_SCAN_MAX_BYTES", str(8 * 1024 * 1024)))
BOOKING_XLS_IMPORT_MAX_BYTES = int(env("BOOKING_XLS_IMPORT_MAX_BYTES", str(5 * 1024 * 1024)))
# Drugi Paddle prolaz na donjem izrezu (MRZ) — smanjuje ultra-široka OCR polja.
MRZ_OCR_SECOND_PASS = env_bool("MRZ_OCR_SECOND_PASS", default=True)
# Donji izrez za MRZ drugi prolaz (ICAO: MRZ na dnu ID-1); 0.30–0.35.
MRZ_CROP_HEIGHT_RATIO = float(env("MRZ_CROP_HEIGHT_RATIO", "0.325"))
MRZ_CROP_PREPROCESS = env_bool("MRZ_CROP_PREPROCESS", default=True)
MRZ_CROP_MERGE_MARGIN_PX = float(env("MRZ_CROP_MERGE_MARGIN_PX", "8"))
# OpenCV: deskew + CLAHE + threshold + upscale prije drugog Paddle poziva.
MRZ_CROP_UPSCALE = int(env("MRZ_CROP_UPSCALE", "2"))  # 2 ili 3
MRZ_CROP_USE_OTSU = env_bool("MRZ_CROP_USE_OTSU", default=False)
# CLAHE + adaptive threshold na cropu — loše s custom HR rec modelom na MRZ fontu; default deskew+upscale.
MRZ_CROP_BINARIZE = env_bool("MRZ_CROP_BINARIZE", default=False)
MRZ_CROP_DEBUG_IMAGES = env_bool("MRZ_CROP_DEBUG_IMAGES", default=False)
# Nakon geometrijskog izreza: ako je duži rub veći, smanji crop (INTER_AREA) prije deskew/upscale.
# Smanjuje RAM/CPU i timeout na originu (Cloudflare „invalid response“). 0 = isključeno.
MRZ_CROP_MAX_LONG_EDGE = int(env("MRZ_CROP_MAX_LONG_EDGE", "1600"))
# Gornja granica piksela nakon upscale-a (nh*nw*upscale^2); ako je prekoračeno, upscale se snizi.
MRZ_CROP_MAX_PIXELS_AFTER_UPSCALE = int(env("MRZ_CROP_MAX_PIXELS_AFTER_UPSCALE", str(5_000_000)))
# INFO logovi za sken: OCR stavke, MRZ kandidati, ishod (uglavnom reception.scan / mrz_pipeline).
SCAN_OCR_TRACE_LOG = env_bool("SCAN_OCR_TRACE_LOG", default=DEBUG)
# Ulaz za Paddle: pretvori u sive tonove (JPEG RGB, luminantni kanali) prije predict.
SCAN_OCR_GRAYSCALE_BEFORE_PREDICT = env_bool("SCAN_OCR_GRAYSCALE_BEFORE_PREDICT", default=True)
# Prazno = ne spremaj upload. Default: media/id_documents (ispod MEDIA_ROOT, vidi u IDE-u / preko /media/).
# Apsolutna putanja ili relativno na BASE_DIR. Sadrži osobne podatke — u produkciji postavi prazno.
SCAN_OCR_SAMPLE_DIR = env("SCAN_OCR_SAMPLE_DIR", "media/id_documents")
# Uz spremljeni upload pisi <stem>.json (OCR/MRZ/raw za debug). Prazno sample dir = nema ni JSON-a.
SCAN_OCR_DEBUG_JSON = env_bool("SCAN_OCR_DEBUG_JSON", default=True)
# Uz sliku <stem>.paddle.json — isključivo paddle_response (+ crop prolaz ako postoji).
SCAN_OCR_PADDLE_RAW_JSON = env_bool("SCAN_OCR_PADDLE_RAW_JSON", default=True)

if SCAN_OCR_TRACE_LOG:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "scan_trace": {
                "format": "{levelname} {asctime} {name}: {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "scan_trace",
            },
        },
        "loggers": {
            "reception": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }
else:
    LOGGING = {}

# Celery (broker: infra-redis DB 1 on hetzner_net)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://infra-redis:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TIMEZONE = "Europe/Zagreb"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

CELERY_BEAT_SCHEDULE = {
    "booking-email-pipeline": {
        "task": "communications.tasks.run_booking_email_pipeline_task",
        "schedule": crontab(minute="*/2"),
        "kwargs": {"fetch_limit": 50, "process_limit": 50},
    },
    "booking-sync-ical": {
        "task": "reception.tasks.sync_booking_ical_task",
        "schedule": crontab(minute="*/30"),
        "kwargs": {"feed": "all"},
    },
}
