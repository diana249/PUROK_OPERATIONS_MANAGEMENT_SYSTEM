import os
import sys
from importlib.util import find_spec
from pathlib import Path

from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    env_file_name = os.getenv("ENV_FILE", ".env").strip() or ".env"
    load_dotenv(BASE_DIR / env_file_name)
except Exception:
    pass

DEBUG = os.getenv("DEBUG", "1") == "1"
SECRET_KEY = os.getenv("SECRET_KEY", get_random_secret_key())
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver,.ngrok-free.dev").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "https://*.ngrok-free.dev,http://127.0.0.1,http://localhost",
    ).split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "management",
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

HAS_WHITENOISE = find_spec("whitenoise") is not None
if HAS_WHITENOISE:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "purok_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "management.context_processors.notification_summary",
            ],
        },
    },
]

WSGI_APPLICATION = "purok_system.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL")
DB_ENGINE = os.getenv("DB_ENGINE", "").strip().lower()

if DATABASE_URL:
    try:
        import dj_database_url

        DATABASES = {
            "default": dj_database_url.parse(
                DATABASE_URL,
                conn_max_age=600,
            )
        }
    except Exception:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }
elif DB_ENGINE == "mysql":
    db_init_command = os.getenv(
        "DB_INIT_COMMAND",
        "SET sql_mode='STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'",
    )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "purok_system"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": db_init_command,
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
if HAS_WHITENOISE:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

if "test" in sys.argv:
    SECURE_SSL_REDIRECT = False

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@puroksystem.local")
EMAIL_FILE_PATH = os.getenv("EMAIL_FILE_PATH", str(BASE_DIR / "emails"))

MANUAL_GCASH_NAME = os.getenv("MANUAL_GCASH_NAME", "Purok Admin")
MANUAL_GCASH_NUMBER = os.getenv("MANUAL_GCASH_NUMBER", "09XXXXXXXXX")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
APP_LOG_FILE = LOG_DIR / "purok_system.log"
ERROR_LOG_FILE = LOG_DIR / "purok_system.error.log"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": LOG_LEVEL,
        },
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(APP_LOG_FILE),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "standard",
            "level": LOG_LEVEL,
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(ERROR_LOG_FILE),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "standard",
            "level": "ERROR",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "app_file", "error_file"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
        "management": {
            "handlers": ["console", "app_file", "error_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

DEFAULT_AUTH_CLASSES = [
    "rest_framework.authentication.SessionAuthentication",
]
if DEBUG:
    DEFAULT_AUTH_CLASSES.append("rest_framework.authentication.BasicAuthentication")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": DEFAULT_AUTH_CLASSES,
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": int(os.getenv("API_PAGE_SIZE", "20")),
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ] if DEBUG else [
        "rest_framework.renderers.JSONRenderer",
    ],
}
