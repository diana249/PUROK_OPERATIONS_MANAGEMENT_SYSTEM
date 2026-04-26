# System Architecture And Deployment Notes

## Modules
- `management.models`: core database entities such as residents, attendance, fees, clearances, verification requests, logs, and notifications.
- `management.views`: HTML page flow for the web interface.
- `management.services`: business rules for account requests, attendance handling, fee payment, clearances, and dashboard summaries.
- `management.api_views`: DRF-powered read-only API endpoints for residents, attendance, fees, clearances, and dashboard totals.

## API Plan
- `GET /api/dashboard/`: dashboard summary counts for the authenticated user.
- `GET /api/residents/`: staff sees all residents, regular users only see their own resident profile.
- `GET /api/attendance/`: staff sees all attendance, regular users only see their own records.
- `GET /api/fees/`: staff sees all fees, regular users only see their own fees.
- `GET /api/clearances/`: staff sees all clearances, regular users only see their own clearances.

## Deployment Notes
- Local development defaults to `purok_system.settings_local` through `purok_system.settings`.
- Production can be enabled by setting `DJANGO_ENV=production`.
- Database settings are read from environment variables and support MySQL or SQLite fallback.
- Static files are ready for WhiteNoise in production.
- Before deployment, run `python manage.py migrate` and `python manage.py collectstatic`.

## Database Notes
- `Purok`, `FeeType`, and `ClearanceType` are normalized lookup tables.
- `VerificationCodeRequest.request_type` separates login-code requests from password-reset requests.
- Audit logging remains flexible by design using `target_type` and `target_id`.
