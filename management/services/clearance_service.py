from django.db import transaction

from management.models import ClearanceType


@transaction.atomic
def issue_clearance_from_form(clearance_form):
    clearance = clearance_form.save(commit=False)
    clearance_type, _ = ClearanceType.objects.get_or_create(name="Barangay")
    clearance.clearance_type = clearance_type
    clearance.save()
    return clearance
