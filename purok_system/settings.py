import os

DJANGO_ENV = os.getenv("DJANGO_ENV", "local").strip().lower()

if DJANGO_ENV == "production":
    from .settings_production import *
else:
    from .settings_local import *
