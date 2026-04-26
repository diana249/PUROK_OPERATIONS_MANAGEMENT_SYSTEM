import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _send_text_email(*, subject, recipient, template_name, context):
    if not recipient:
        return False

    message = render_to_string(template_name, context)
    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send email. recipient=%s subject=%s", recipient, subject)
        return False
    return sent_count > 0


def send_verification_code_email(*, recipient, name, verification_code, expires_at):
    return _send_text_email(
        subject="Your Purok verification code",
        recipient=recipient,
        template_name="management/email_verification_code.txt",
        context={
            "name": name,
            "verification_code": verification_code,
            "expires_at": expires_at,
        },
    )


def send_payment_submission_email(*, recipient, resident_name, fee_type, amount, gcash_reference, payment_date):
    return _send_text_email(
        subject="Payment submission received",
        recipient=recipient,
        template_name="management/email_payment_submitted.txt",
        context={
            "resident_name": resident_name,
            "fee_type": fee_type,
            "amount": amount,
            "gcash_reference": gcash_reference,
            "payment_date": payment_date,
        },
    )


def send_payment_review_email(
    *,
    recipient,
    resident_name,
    fee_type,
    amount,
    gcash_reference,
    status,
    reviewed_at,
    admin_notes,
):
    return _send_text_email(
        subject=f"Payment {status}: {fee_type}",
        recipient=recipient,
        template_name="management/email_payment_reviewed.txt",
        context={
            "resident_name": resident_name,
            "fee_type": fee_type,
            "amount": amount,
            "gcash_reference": gcash_reference,
            "status": status,
            "reviewed_at": reviewed_at,
            "admin_notes": admin_notes,
        },
    )
