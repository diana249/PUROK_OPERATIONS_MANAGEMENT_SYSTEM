from django.db import transaction

from management.models import Fee, FeeType


def _get_penalty_fee_type(attendance):
    mapping = {
        "Meeting": "Penalty for Missed Meeting",
        "Cleaning": "Penalty for Missed Cleaning",
    }
    penalty_name = mapping.get(attendance.attendance_type, "Penalty")
    fee_type, _ = FeeType.objects.get_or_create(name=penalty_name)
    return fee_type


def _create_penalty_fee(attendance):
    penalty_fee_type = _get_penalty_fee_type(attendance)
    return Fee.objects.create(
        resident=attendance.resident,
        amount=100.00,
        fee_type=penalty_fee_type,
        paid=False,
    )


@transaction.atomic
def create_attendance(attendance_form):
    attendance = attendance_form.save()
    penalty_fee = None
    if attendance.status == "Absent":
        penalty_fee = _create_penalty_fee(attendance)
    return attendance, penalty_fee


@transaction.atomic
def update_attendance_status(attendance, new_status):
    previous_status = attendance.status
    attendance.status = new_status
    attendance.save(update_fields=["status"])
    penalty_fee = None
    if new_status == "Absent" and previous_status != "Absent":
        penalty_fee = _create_penalty_fee(attendance)
    return attendance, penalty_fee
