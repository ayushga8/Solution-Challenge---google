"""
Django settings for bias_detector project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-fallback-key-change-me')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = ['*']

# Detect environment
IS_VERCEL = os.getenv('VERCEL') == '1'
IS_GCP = os.getenv('K_SERVICE') is not None  # K_SERVICE is set by Cloud Run

# Vercel proxy configuration for HTTPS and CSRF
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
CSRF_TRUSTED_ORIGINS = [
    'https://*.vercel.app',
    'https://solution-challenge-google-nine.vercel.app',
    'https://*.a.run.app', # Wildcard for Cloud Run
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

if os.getenv('VERCEL') == '1':
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Fix Firebase Google Sign-In popups being disconnected by Django's strict COOP header
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'

ROOT_URLCONF = 'bias_detector.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'bias_detector.wsgi.application'


# Database
# Vercel's serverless environment has a read-only filesystem except for /tmp
if IS_VERCEL:
    tmp_db = '/tmp/db.sqlite3'
    # Copy the pre-populated database to /tmp so tables exist natively
    if not os.path.exists(tmp_db):
        import shutil
        original_db = BASE_DIR / 'db.sqlite3'
        if original_db.exists():
            shutil.copy2(original_db, tmp_db)

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': tmp_db,
        }
    }
    # Store session data in browser cookies instead of ephemeral /tmp database
    SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
    WHITENOISE_USE_FINDERS = True

elif IS_GCP:
    # Google Cloud Run + Cloud SQL (PostgreSQL)
    db_name = os.getenv('DB_NAME', 'bias_db')
    db_user = os.getenv('DB_USER', 'postgres')
    db_pass = os.getenv('DB_PASS', '')
    db_conn = os.getenv('DB_CONNECTION_NAME') # project:region:instance
    
    if db_conn:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': db_name,
                'USER': db_user,
                'PASSWORD': db_pass,
                'HOST': f'/cloudsql/{db_conn}', 
            }
        }
    else:
        # Fallback to local SQLite if connector is missing
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files (Uploaded datasets)
MEDIA_URL = '/media/'
if os.getenv('VERCEL') == '1':
    MEDIA_ROOT = '/tmp/media'
    os.makedirs(MEDIA_ROOT, exist_ok=True)
else:
    MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Max upload size: 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800

# Email Configuration
# Try SMTP first; if it fails, OTP is shown on-screen in DEBUG mode
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    DEFAULT_FROM_EMAIL = f'Unbiased AI <{EMAIL_HOST_USER}>'
else:
    # Fallback: print emails to console
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'Unbiased AI <noreply@unbiasedai.com>'

# OTP Settings
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
