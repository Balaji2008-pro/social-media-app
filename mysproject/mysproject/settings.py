import dj_database_url

from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv
load_dotenv()
# BASE
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")


DEBUG = False


ALLOWED_HOSTS = os.environ.get(
    "ALLOWED_HOSTS", "social-media-app-18r4.onrender.com"
).split(",")
# -------------------------
# APPLICATIONS
# -------------------------
INSTALLED_APPS = [
    'daphne',  
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",

    "api",
    "channels",
    "storages"
]

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")
AWS_S3_CUSTOM_DOMAIN = os.getenv("CLOUDFRONT_URL")

AWS_QUERYSTRING_AUTH = False
AWS_DEFAULT_ACL = None

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'
# -------------------------
# CUSTOM USER MODEL
# -------------------------
AUTH_USER_MODEL = "api.User"



# -------------------------
# MIDDLEWARE
# -------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# -------------------------
# ROOT URL
# -------------------------
ROOT_URLCONF = "mysproject.urls"

# -------------------------
# WSGI
# -------------------------
WSGI_APPLICATION = "mysproject.wsgi.application"

# ------------------------
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True   # production-ல இது add பண்ணுங்க
    )
}
# -------------------------
# TEMPLATES
# -------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# -------------------------
# REST FRAMEWORK + JWT
# -------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
}

# -------------------------
# CORS
# -------------------------
CORS_ALLOW_ALL_ORIGINS = True

# -------------------------
# STATIC & MEDIA
# -------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# -------------------------
# DEFAULT AUTO FIELD
# -------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ASGI_APPLICATION = 'mysproject.asgi.application'  # change myproject

REDIS_URL = os.environ.get("REDIS_URL")

if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [REDIS_URL],
            },
        },
    }
else:
    # Local development — Redis இல்லாம் work ஆகும்
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
        

import sys
print("CLOUDFRONT_URL:", os.getenv("CLOUDFRONT_URL"), file=sys.stderr)
print("AWS_BUCKET:", os.getenv("AWS_STORAGE_BUCKET_NAME"), file=sys.stderr)


# =========================================
# FIREBASE ADMIN SDK — Push Notification
# =========================================
# =========================================
# FIREBASE ADMIN SDK — Push Notification
# =========================================
import firebase_admin
from firebase_admin import credentials

# ✅ Render-ல secret file இங்க இருக்கும்
RENDER_SECRET_PATH = '/etc/secrets/firebase-credentials.json'
# ✅ Local-ல file இங்க இருக்கும்
LOCAL_CREDENTIALS_PATH = os.path.join(BASE_DIR, 'firebase-credentials.json')

if not firebase_admin._apps:
    if os.path.exists(RENDER_SECRET_PATH):
        # Render production server
        cred = credentials.Certificate(RENDER_SECRET_PATH)
    else:
        # Local development machine
        cred = credentials.Certificate(LOCAL_CREDENTIALS_PATH)

    firebase_admin.initialize_app(cred)