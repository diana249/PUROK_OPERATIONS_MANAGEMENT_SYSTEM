# Free Deployment Guide (Render)

This guide uses Render free tier.

## 1) Push project to GitHub

From `purok_system` folder:

```powershell
git init
git add .
git commit -m "Prepare for free Render deployment"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## 2) Create Web Service on Render

1. Go to `https://render.com/`
2. Sign in with GitHub.
3. Click `New +` -> `Web Service`.
4. Select your repository.
5. Render will read `render.yaml`.
6. Click `Create Web Service`.

## 3) Optional but recommended: add free PostgreSQL

SQLite on free hosting is not persistent/reliable for production.

1. `New +` -> `PostgreSQL` (free plan).
2. After creation, copy `Internal Database URL`.
3. Open your web service -> `Environment`.
4. Add variable:
   - `DATABASE_URL=<internal database url>`
5. Redeploy service.

## 4) Create admin user (one-time)

Open Render Shell for the web service and run:

```bash
python manage.py createsuperuser
```

## 5) Open your live site

Render gives a URL like:

`https://your-service-name.onrender.com`

## Notes

- Free tier sleeps when inactive; first load can take a while.
- Email SMTP still needs environment variables if you want real email sending.
