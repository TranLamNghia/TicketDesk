# Test environment settings
# ruff: noqa: F403, F405
from .base import *


PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

DEBUG = False

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

SECRET_KEY = "test-secret-key-ticketdesk-only-for-pytest-runs"
