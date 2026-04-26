# MySQL Setup (DMS Course)

This project now supports MySQL through environment variables.

## 1) Create MySQL database

Example:

```sql
CREATE DATABASE purok_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'purok_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON purok_system.* TO 'purok_user'@'localhost';
FLUSH PRIVILEGES;
```

Recommended storage engine and strict mode:

```sql
SET GLOBAL default_storage_engine = InnoDB;
SET GLOBAL sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';
```

## 2) Set environment variables (PowerShell)

Run in terminal before `runserver`:

```powershell
$env:DB_ENGINE="mysql"
$env:DB_NAME="purok_system"
$env:DB_USER="purok_user"
$env:DB_PASSWORD="your_password"
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
```

## 3) Run migrations

```powershell
python manage.py makemigrations
python manage.py migrate
```

## 4) Run server

```powershell
python manage.py runserver
```

## Notes

- If `DB_ENGINE` is not set to `mysql`, system falls back to SQLite.
- PyMySQL is used, so no MySQL C build tools are required for this setup.
- In production, keep `CONN_MAX_AGE` non-zero (already supported via env).
