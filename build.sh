#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Optional: create/update an admin account during deploy when env vars are provided.
# Set CREATE_SUPERUSER=1 plus DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD in Render.
if [ "${CREATE_SUPERUSER:-0}" = "1" ]; then
  python manage.py shell -c "
from django.contrib.auth import get_user_model
import os

User = get_user_model()
username = os.getenv('DJANGO_SUPERUSER_USERNAME', '').strip()
email = os.getenv('DJANGO_SUPERUSER_EMAIL', '').strip()
password = os.getenv('DJANGO_SUPERUSER_PASSWORD', '').strip()

if not username or not password:
    raise SystemExit('CREATE_SUPERUSER=1 but DJANGO_SUPERUSER_USERNAME/PASSWORD missing.')

user, _ = User.objects.get_or_create(username=username, defaults={'email': email})
if email and user.email != email:
    user.email = email
user.is_active = True
user.is_staff = True
user.is_superuser = True
user.set_password(password)
user.save()
print(f'Admin user ready: {username}')
"
fi
