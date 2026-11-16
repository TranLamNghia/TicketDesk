# Test environment settings
# ruff: noqa: F403, F405
from .base import *


PASSWORD_HASHERS = ["django.contrb.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

DEBUG = False

CELERY_TASK_ALWAYS_EAGER = True

SECRET_KEY = "test-secret-key-ticketdesk"
