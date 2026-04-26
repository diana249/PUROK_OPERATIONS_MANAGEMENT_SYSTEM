from django.db import transaction

from management.models import VerificationCodeRequest


@transaction.atomic
def create_pending_user(registration_form):
    user = registration_form.save(commit=False)
    user.is_active = False
    user.save()
    verification = registration_form.get_verification_code()
    if verification is not None:
        verification.mark_used()
    return user


@transaction.atomic
def create_verification_request(*, name, email, request_type="login_code"):
    normalized_email = email.strip().lower()
    if request_type == "password_reset":
        existing = VerificationCodeRequest.objects.filter(
            email=normalized_email,
            status="pending",
            request_type=request_type,
        ).first()
        if existing is not None:
            return existing, False

    request_obj = VerificationCodeRequest.objects.create(
        name=name.strip(),
        email=normalized_email,
        status="pending",
        request_type=request_type,
    )
    return request_obj, True


@transaction.atomic
def reset_password_with_code(reset_form):
    user = reset_form.get_user()
    verification = reset_form.get_verification_code()
    user.set_password(reset_form.cleaned_data["new_password1"])
    user.save(update_fields=["password"])
    if verification is not None:
        verification.mark_used()
    return user
