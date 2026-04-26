# Production Readiness Checklist

Use this before every deployment.

## 1) Environment and secrets
- `DEBUG=0`
- Strong `SECRET_KEY`
- Correct `ALLOWED_HOSTS`
- Correct `CSRF_TRUSTED_ORIGINS`
- MySQL variables set (`DB_ENGINE=mysql`, `DB_*`)
- If loading from a file, set `ENV_FILE=.env.production`
- SMTP email variables set for real delivery:
  - `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
  - `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`
  - `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
  - `DEFAULT_FROM_EMAIL`

## 2) Dependencies
```powershell
pip install -r requirements.txt
```

## 3) Database
```powershell
python manage.py migrate
```

## 4) Static files
```powershell
python manage.py collectstatic --no-input
```

## 5) Production checks
```powershell
python manage.py check
python manage.py check --deploy
python manage.py test management
```

## 6) Admin user
```powershell
python manage.py createsuperuser
```

## 7) Backup before deploy
```powershell
python manage.py backup_db
```

## 8) Smoke test after deploy
- Login page works
- Register page works
- Dashboard loads
- Attendance, Fees, Clearance pages load
- Clearance download works
- Admin panel works
- Health check works (`/healthz/` returns status ok)

## 9) Logs and monitoring
- Review application logs in `logs/purok_system.log`
- Review error logs in `logs/purok_system.error.log`
- Configure host alerting for:
  - `/healthz/` non-200 response
  - repeated HTTP 5xx errors
