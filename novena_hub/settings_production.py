# flake8: noqa: F405
from .settings import *  # noqa F401

# Note: it is recommended to use the "DEBUG" environment variable to override this value in your main settings.py file.
# A future release may remove it from here.
DEBUG = False

# fix ssl mixed content issues
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Django security checklist settings.
# More details here: https://docs.djangoproject.com/en/stable/howto/deployment/checklist/
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HTTP Strict Transport Security settings
# Without uncommenting the lines below, you will get security warnings when running ./manage.py check --deploy
# https://docs.djangoproject.com/en/stable/ref/middleware/#http-strict-transport-security

# Increase this number once you're confident everything works https://stackoverflow.com/a/49168623/8207
SECURE_HSTS_SECONDS = 31536000
# Uncomment these two lines if you are sure that you don't host any subdomains over HTTP.
# You will get security warnings if you don't do this.
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

USE_HTTPS_IN_ABSOLUTE_URLS = True

# If you don't want to use environment variables to set production hosts you can add them here
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["yourdomain.com"])

# Production email is sent through Amazon SES via django-anymail.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="anymail.backends.amazon_ses.EmailBackend")

ADMINS = [
    ("Your Name", "tingshouheng@gmail.com"),
]
