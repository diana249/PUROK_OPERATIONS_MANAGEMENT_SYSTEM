from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import Fee, PaymentTransaction


def mark_fee_paid(fee):
    with transaction.atomic():
        fee.paid = True
        fee.date_paid = timezone.localdate()
        fee.save(update_fields=["paid", "date_paid"])
    return fee


def submit_manual_payment(*, fee, submitted_by, gcash_reference, amount_sent, payment_date, notes=""):
    with transaction.atomic():
        locked_fee = Fee.objects.select_for_update().get(pk=fee.pk)
        if locked_fee.paid:
            raise ValueError("This fee is already marked as paid.")
        if locked_fee.payment_transactions.filter(status="pending").exists():
            raise ValueError("A payment transaction for this fee is already waiting for admin approval.")
        if amount_sent != locked_fee.amount:
            raise ValueError("The submitted amount must exactly match the fee amount.")

        try:
            payment = PaymentTransaction.objects.create(
                fee=locked_fee,
                submitted_by=submitted_by,
                gcash_reference=gcash_reference.strip(),
                amount_sent=amount_sent,
                payment_date=payment_date,
                notes=notes.strip(),
                status="pending",
            )
        except IntegrityError as exc:
            raise ValueError("A payment transaction for this fee is already waiting for admin approval.") from exc
    return payment


def approve_payment_transaction(payment, *, reviewer, admin_notes=""):
    with transaction.atomic():
        locked_payment = PaymentTransaction.objects.select_for_update().select_related("fee").get(pk=payment.pk)
        if locked_payment.status != "pending":
            raise ValueError("Only pending payment transactions can be approved.")

        locked_payment.status = "approved"
        locked_payment.admin_notes = admin_notes.strip()
        locked_payment.reviewed_by = reviewer
        locked_payment.reviewed_at = timezone.now()
        locked_payment.save(update_fields=["status", "admin_notes", "reviewed_by", "reviewed_at"])
        mark_fee_paid(locked_payment.fee)
    return locked_payment


def reject_payment_transaction(payment, *, reviewer, admin_notes=""):
    with transaction.atomic():
        locked_payment = PaymentTransaction.objects.select_for_update().get(pk=payment.pk)
        if locked_payment.status != "pending":
            raise ValueError("Only pending payment transactions can be rejected.")

        locked_payment.status = "rejected"
        locked_payment.admin_notes = admin_notes.strip()
        locked_payment.reviewed_by = reviewer
        locked_payment.reviewed_at = timezone.now()
        locked_payment.save(update_fields=["status", "admin_notes", "reviewed_by", "reviewed_at"])
    return locked_payment
