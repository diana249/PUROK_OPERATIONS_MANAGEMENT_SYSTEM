# Deployment Stack Reference

## Option A: Render (no Nginx required)
- App server: `gunicorn purok_system.wsgi:application`
- Static files: WhiteNoise
- Health check: `/healthz/`
- Config file: `render.yaml`

## Option B: VPS (Gunicorn + Nginx)

### Gunicorn service example
```bash
gunicorn --workers 3 --bind 127.0.0.1:8000 purok_system.wsgi:application
```

### Nginx reverse proxy (minimal)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /static/ {
        alias /path/to/purok_system/staticfiles/;
    }

    location /media/ {
        alias /path/to/purok_system/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Required post-deploy checks
- `/healthz/` returns `{"status":"ok","database":"ok"}`
- admin login works
- register/reset/approve flows work
- logs are being written to `logs/`
