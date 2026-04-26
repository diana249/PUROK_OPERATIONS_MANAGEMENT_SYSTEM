from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from management.models import Attendance, Fee, PurokClearance, Resident


def _last_6_month_labels():
    today = timezone.localdate()
    month_dates = []
    for offset in range(5, -1, -1):
        month_seed = today.replace(day=1)
        year = month_seed.year
        month = month_seed.month - offset
        while month <= 0:
            month += 12
            year -= 1
        month_dates.append(month_seed.replace(year=year, month=month))
    labels = [dt.strftime("%b %Y") for dt in month_dates]
    month_keys = [dt.strftime("%Y-%m") for dt in month_dates]
    return labels, month_keys, month_dates


def build_dashboard_context(user):
    if user.is_staff:
        attendance_qs = Attendance.objects.all()
        fee_qs = Fee.objects.all()
        clearance_qs = PurokClearance.objects.all()
        resident_qs = Resident.objects.all()
    else:
        resident = Resident.objects.filter(user=user).first()
        if resident:
            attendance_qs = Attendance.objects.filter(resident=resident)
            fee_qs = Fee.objects.filter(resident=resident)
            clearance_qs = PurokClearance.objects.filter(resident=resident)
            resident_qs = Resident.objects.filter(pk=resident.pk)
        else:
            attendance_qs = Attendance.objects.none()
            fee_qs = Fee.objects.none()
            clearance_qs = PurokClearance.objects.none()
            resident_qs = Resident.objects.none()

    context = {
        "total_residents": resident_qs.count(),
        "total_attendance": attendance_qs.count(),
        "unpaid_fees": fee_qs.filter(paid=False).count(),
        "clearances_issued": clearance_qs.count(),
    }

    
    if user.is_staff:
        labels, month_keys, month_dates = _last_6_month_labels()
        start_month = month_dates[0]
        end_month = month_dates[-1]
        if end_month.month == 12:
            next_month = end_month.replace(year=end_month.year + 1, month=1)
        else:
            next_month = end_month.replace(month=end_month.month + 1)

        attendance_rows = (
            Attendance.objects.filter(date__gte=start_month, date__lt=next_month)
            .annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(total=Count("id"))
        )
        attendance_map = {
            row["month"].strftime("%Y-%m"): row["total"]
            for row in attendance_rows
            if row["month"] is not None
        }

        unpaid_rows = (
            Fee.objects.filter(paid=False, created_at__gte=start_month, created_at__lt=next_month)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total=Count("id"))
        )
        unpaid_map = {
            row["month"].strftime("%Y-%m"): row["total"]
            for row in unpaid_rows
            if row["month"] is not None
        }

        clearance_rows = (
            PurokClearance.objects.filter(date_issued__gte=start_month, date_issued__lt=next_month)
            .annotate(month=TruncMonth("date_issued"))
            .values("month")
            .annotate(total=Count("id"))
        )
        clearance_map = {
            row["month"].strftime("%Y-%m"): row["total"]
            for row in clearance_rows
            if row["month"] is not None
        }

        attendance_trend = [attendance_map.get(key, 0) for key in month_keys]
        unpaid_fee_trend = [unpaid_map.get(key, 0) for key in month_keys]
        clearance_trend = [clearance_map.get(key, 0) for key in month_keys]

        attendance_max = max(attendance_trend) if attendance_trend else 0
        unpaid_max = max(unpaid_fee_trend) if unpaid_fee_trend else 0
        clearance_max = max(clearance_trend) if clearance_trend else 0

        attendance_points = [
            {
                "label": label,
                "value": value,
                "pct": 0 if attendance_max == 0 else int((value / attendance_max) * 100),
            }
            for label, value in zip(labels, attendance_trend)
        ]
        unpaid_points = [
            {
                "label": label,
                "value": value,
                "pct": 0 if unpaid_max == 0 else int((value / unpaid_max) * 100),
            }
            for label, value in zip(labels, unpaid_fee_trend)
        ]
        clearance_points = [
            {
                "label": label,
                "value": value,
                "pct": 0 if clearance_max == 0 else int((value / clearance_max) * 100),
            }
            for label, value in zip(labels, clearance_trend)
        ]

        context.update(
            {
                "attendance_points": attendance_points,
                "unpaid_points": unpaid_points,
                "clearance_points": clearance_points,
            }
        )
    else:
        context.update(
            {
                "attendance_points": [],
                "unpaid_points": [],
                "clearance_points": [],
            }
        )

    return context
