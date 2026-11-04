# Dev environment (Postgres Docker 5433, Redis 6379, DEBUG=True)
from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
