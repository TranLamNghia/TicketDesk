from .base import *  # noqa: F403

DEBUG = False

# Tăng cường bảo mật Production
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
