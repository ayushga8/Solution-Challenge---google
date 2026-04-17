import os

# Firebase Configuration for Google Sign-In
# All values read from .env file — no hardcoded secrets
FIREBASE_CONFIG = {
    'apiKey': os.getenv('FIREBASE_API_KEY', ''),
    'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN', ''),
    'projectId': os.getenv('FIREBASE_PROJECT_ID', ''),
    'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', ''),
    'messagingSenderId': os.getenv('FIREBASE_MESSAGING_SENDER_ID', ''),
    'appId': os.getenv('FIREBASE_APP_ID', ''),
    'measurementId': os.getenv('FIREBASE_MEASUREMENT_ID', ''),
}

FIREBASE_PROJECT_ID = FIREBASE_CONFIG.get('projectId', '')
