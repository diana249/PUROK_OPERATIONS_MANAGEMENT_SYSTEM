import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import connection, transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    ForgotPasswordRequestForm,
    PasswordResetWithCodeForm,
    UserRegistrationForm,
    VerificationCodeRequestForm,
)
from .models import (
    LoginActivity,
    VerificationCodeRequest,
    create_unique_verification_code,
    write_audit_log,
)
from .services import account_service
from .services import email_service

logger = logging.getLogger(__name__)
staff_required = user_passes_test(lambda user: user.is_staff)


def welcome(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "management/welcome.html")


def healthz(request):
    db_ok = True
    db_error = ""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        db_ok = False
        db_error = str(exc)
        logger.exception("Health check failed.")

    payload = {"status": "ok" if db_ok else "error", "database": "ok" if db_ok else "error"}
    if db_error and request.user.is_superuser:
        payload["detail"] = db_error
    status = 200 if db_ok else 503
    return JsonResponse(payload, status=status)


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            account_service.create_pending_user(form)
            messages.success(
                request,
                "Account created. Please wait for admin approval before logging in.",
            )
            return redirect("login")
    else:
        form = UserRegistrationForm()

    return render(request, "management/register.html", {"form": form})


def request_verification_code(request):
    if request.method == "POST":
        form = VerificationCodeRequestForm(request.POST)
        if form.is_valid():
            account_service.create_verification_request(
                name=form.cleaned_data["name"],
                email=form.cleaned_data["email"],
                request_type="login_code",
            )
            messages.success(
                request,
                "Request submitted. Once admin generates your login code, it will be sent to your email.",
            )
            return redirect("register")
    else:
        form = VerificationCodeRequestForm()

    return render(request, "management/request_verification_code.html", {"form": form})


def forgot_password_request(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = ForgotPasswordRequestForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            account_service.create_verification_request(
                name=user.username,
                email=user.email,
                request_type="password_reset",
            )
            messages.success(
                request,
                "Password reset request submitted. Once admin generates your reset code, it will be sent to your email.",
            )
            return redirect("password-reset-with-code")
    else:
        form = ForgotPasswordRequestForm()

    return render(request, "management/forgot_password_request.html", {"form": form})


def password_reset_with_code(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = PasswordResetWithCodeForm(request.POST)
        if form.is_valid():
            account_service.reset_password_with_code(form)
            messages.success(request, "Password reset successful. You can now log in.")
            return redirect("login")
    else:
        form = PasswordResetWithCodeForm()

    return render(request, "management/password_reset_with_code.html", {"form": form})


@login_required
@staff_required
def pending_accounts(request):
    pending_users = (
        User.objects.filter(is_staff=False, is_superuser=False, is_active=False)
        .annotate(last_login_activity_at=Max("login_activities__login_at"))
        .order_by("date_joined")
    )
    active_users = (
        User.objects.filter(is_staff=False, is_superuser=False, is_active=True)
        .annotate(last_login_activity_at=Max("login_activities__login_at"))
        .order_by("username")
    )
    recent_logins = LoginActivity.objects.select_related("user").all()[:25]
    verification_requests = VerificationCodeRequest.objects.all()[:25]
    tab = (request.GET.get("tab") or "pending").strip().lower()
    if tab not in {"pending", "approved", "requests", "recent"}:
        tab = "pending"
    context = {
        "pending_users": pending_users,
        "active_users": active_users,
        "recent_logins": recent_logins,
        "verification_requests": verification_requests,
        "accounts_tab": tab,
    }
    return render(request, "management/pending_accounts.html", context)


@login_required
@staff_required
@require_POST
def pending_account_action(request, user_id):
    action = (request.POST.get("action") or "").strip().lower()
    target_user = get_object_or_404(User, pk=user_id, is_staff=False, is_superuser=False)

    if target_user.pk == request.user.pk and action in {"deactivate", "delete"}:
        messages.error(request, "You cannot deactivate or delete your own account here.")
        return redirect("pending-accounts")

    if action == "approve":
        with transaction.atomic():
            target_user.is_active = True
            target_user.save(update_fields=["is_active"])
            write_audit_log(
                "approve_user",
                f"Approved user '{target_user.username}'.",
                actor=request.user,
                target=target_user,
                metadata={"channel": "web", "source": "pending_accounts"},
            )
        messages.success(request, f"User '{target_user.username}' has been approved.")
    elif action == "deactivate":
        with transaction.atomic():
            target_user.is_active = False
            target_user.save(update_fields=["is_active"])
        messages.warning(request, f"User '{target_user.username}' has been deactivated.")
    elif action == "delete":
        with transaction.atomic():
            username = target_user.username
            target_user.delete()
        messages.success(request, f"User '{username}' has been deleted.")
    else:
        messages.error(request, "Invalid account action.")

    return redirect("pending-accounts")


@login_required
@staff_required
@require_POST
def verification_request_action(request, request_id):
    action = (request.POST.get("action") or "").strip().lower()
    req = get_object_or_404(VerificationCodeRequest, pk=request_id)

    if action == "resolve":
        with transaction.atomic():
            req.status = "resolved"
            req.save(update_fields=["status"])
        messages.success(request, f"Verification request for '{req.email}' marked as resolved.")
    elif action == "pending":
        with transaction.atomic():
            req.status = "pending"
            req.save(update_fields=["status"])
        messages.info(request, f"Verification request for '{req.email}' moved to pending.")
    elif action == "generate_code":
        if req.verification_code and req.verification_code.is_usable():
            code = req.verification_code
        else:
            try:
                code = create_unique_verification_code(max_uses=1, attempts=10)
            except RuntimeError:
                messages.error(request, "Could not generate a unique login code. Try again.")
                return redirect("pending-accounts")

        with transaction.atomic():
            req.verification_code = code
            req.status = "resolved"
            req.save(update_fields=["verification_code", "status"])
            write_audit_log(
                "create_code",
                f"Generated login code for '{req.email}'.",
                actor=request.user,
                target=req,
                metadata={"verification_code": code.code, "request_id": req.pk},
            )
        email_sent = email_service.send_verification_code_email(
            recipient=req.email,
            name=req.name,
            verification_code=code.code,
            expires_at=code.expires_at,
        )
        if email_sent:
            messages.success(
                request,
                f"Login code for '{req.email}' was emailed successfully. Code: {code.code}",
            )
        else:
            messages.warning(
                request,
                f"Login code for '{req.email}' is {code.code}, but email could not be sent. Check SMTP settings.",
            )
    else:
        messages.error(request, "Invalid login code request action.")

    return redirect("pending-accounts")
