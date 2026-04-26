# Backup and Restore Strategy

## 1) Manual Backup
Run from project root (`purok_system` folder):

```powershell
python manage.py backup_db
```

Optional:

```powershell
python manage.py backup_db --output-dir backups --keep 30
```

## 2) Scheduled Backup (Windows Task Scheduler)

Use this command in task action:

```powershell
cd C:\Users\USER\MyProject\purok_system; .\.venv\Scripts\python.exe manage.py backup_db --output-dir backups --keep 30
```

Recommended schedule:
- Daily at 10:00 PM
- Run whether user is logged in or not

## 3) Restore Procedure (SQLite)

1. Stop the Django server.
2. Choose backup file from `backups\` (for example `db_backup_20260307_220000.sqlite3`).
3. Replace current DB:

```powershell
Copy-Item .\backups\db_backup_YYYYMMDD_HHMMSS.sqlite3 .\db.sqlite3 -Force
```

4. Start server and validate:

```powershell
python manage.py check
python manage.py runserver
```

## 4) Verification Checklist
- Admin login works.
- Resident, attendance, fee, and clearance data visible.
- Latest notifications and audit logs load.

## 5) MySQL backup and restore (production)

Backup:

```powershell
mysqldump -u purok_user -p --single-transaction --routines --triggers purok_system > backups\purok_system_YYYYMMDD_HHMMSS.sql
```

Restore:

```powershell
mysql -u purok_user -p purok_system < backups\purok_system_YYYYMMDD_HHMMSS.sql
```

## 6) Restore drill (required)

At least once per month:
- Restore latest backup into a test database.
- Run:

```powershell
python manage.py check
python manage.py test management
```

- Validate login, pending accounts, fee mark-paid, and clearance download.
