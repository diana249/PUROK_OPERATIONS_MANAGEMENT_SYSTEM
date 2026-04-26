from html import escape
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.http import HttpResponse, JsonResponse
from django.db.models import Max
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AttendanceForm,
    ClearanceForm,
    FeeForm,
    PaymentTransactionForm,
    ForgotPasswordRequestForm,
    PasswordResetWithCodeForm,
    ProfileForm,
    ResidentForm,
    UserResidentInfoForm,
    VerificationCodeRequestForm,
    UserRegistrationForm,
    UserUpdateForm,
)
from .models import (
    Attendance,
    AuditLog,
    ClearanceType,
    Fee,
    PaymentTransaction,
    Profile,
    LoginActivity,
    PurokClearance,
    Resident,
    VerificationCodeRequest,
    create_unique_verification_code,
    write_audit_log,
)
from .services import account_service, attendance_service, clearance_service, fee_service
from .services.dashboard_service import build_dashboard_context

logger = logging.getLogger(__name__)


def _run_sql(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
    return {"sql": sql, "columns": columns, "rows": rows}


def _run_explain(sql, params=None):
    explain_prefix = "EXPLAIN QUERY PLAN" if connection.vendor == "sqlite" else "EXPLAIN"
    return _run_sql(f"{explain_prefix} {sql}", params=params)


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
                "Request submitted. Please wait for admin to give you a login code.",
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
                "Password reset request submitted. Ask admin for a login code, then reset your password.",
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


staff_required = user_passes_test(lambda user: user.is_staff)


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
    context = {
        "pending_users": pending_users,
        "active_users": active_users,
        "recent_logins": recent_logins,
        "verification_requests": verification_requests,
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
        messages.success(
            request,
            f"Login code for '{req.email}' is {code.code}. Share this code with the user.",
        )
    else:
        messages.error(request, "Invalid login code request action.")

    return redirect("pending-accounts")


@login_required
def dashboard(request):
    context = build_dashboard_context(request.user)
    return render(request, "management/dashboard.html", context)


@login_required
@staff_required
def resident_list(request):
    query = request.GET.get("q", "").strip()
    residents = Resident.objects.all().order_by("last_name", "first_name")

    if query:
        residents = residents.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(purok__name__icontains=query)
        )

    paginator = Paginator(residents, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "management/resident_list.html",
        {"residents": page_obj, "query": query},
    )


@login_required
@staff_required
def resident_export_word(request):
    query = request.GET.get("q", "").strip()
    residents = Resident.objects.select_related("purok").all().order_by("last_name", "first_name")
    if query:
        residents = residents.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(purok__name__icontains=query)
        )

    table_rows = "".join(
        (
            "<tr>"
            f"<td>{escape(resident.first_name)} {escape(resident.last_name)}</td>"
            f"<td>{escape(str(resident.purok))}</td>"
            f"<td>{escape(resident.date_of_birth.strftime('%Y-%m-%d'))}</td>"
            f"<td>{escape(resident.contact_number or '-')}</td>"
            "</tr>"
        )
        for resident in residents
    )
    if not table_rows:
        table_rows = '<tr><td colspan="4">No residents found.</td></tr>'

    html = f"""
    <html>
    <head><meta charset="utf-8"><title>Residents</title></head>
    <body>
        <h2>Residents</h2>
        <table border="1" cellspacing="0" cellpadding="6">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Purok</th>
                    <th>Date of Birth</th>
                    <th>Contact Number</th>
                </tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>
    </body>
    </html>
    """
    response = HttpResponse(html, content_type="application/msword")
    response["Content-Disposition"] = 'attachment; filename="residents.doc"'
    return response


@login_required
@staff_required
def resident_create(request):
    if request.method == "POST":
        form = ResidentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Resident added successfully.")
            return redirect("resident-list")
    else:
        form = ResidentForm()
    return render(request, "management/resident_form.html", {"form": form, "title": "Add Resident"})


@login_required
@staff_required
def resident_edit(request, pk):
    resident = get_object_or_404(Resident, pk=pk)
    if request.method == "POST":
        form = ResidentForm(request.POST, instance=resident)
        if form.is_valid():
            form.save()
            messages.success(request, "Resident updated successfully.")
            return redirect("resident-list")
    else:
        form = ResidentForm(instance=resident)
    return render(request, "management/resident_form.html", {"form": form, "title": "Edit Resident"})


@login_required
@staff_required
def resident_delete(request, pk):
    resident = get_object_or_404(Resident, pk=pk)
    if request.method == "POST":
        resident.delete()
        messages.success(request, "Resident deleted successfully.")
        return redirect("resident-list")
    return render(request, "management/resident_delete_confirm.html", {"resident": resident})


@login_required
def attendance_list(request):
    base_qs = Attendance.objects.select_related("resident").all().order_by("-date", "-id")
    if not request.user.is_staff:
        resident = Resident.objects.filter(user=request.user).first()
        if resident:
            base_qs = base_qs.filter(resident=resident)
        else:
            base_qs = base_qs.none()

    meeting_records = base_qs.filter(attendance_type="Meeting")
    cleaning_records = base_qs.filter(attendance_type="Cleaning")
    all_records = base_qs
    tab = (request.GET.get("tab") or "meeting").strip().lower()
    if tab not in {"meeting", "cleaning", "all"}:
        tab = "meeting"

    return render(
        request,
        "management/attendance_list.html",
        {
            "meeting_records": meeting_records,
            "cleaning_records": cleaning_records,
            "all_records": all_records,
            "attendance_tab": tab,
        },
    )


@login_required
def attendance_export_word(request):
    base_qs = Attendance.objects.select_related("resident").all().order_by("-date", "-id")
    if not request.user.is_staff:
        resident = Resident.objects.filter(user=request.user).first()
        if resident:
            base_qs = base_qs.filter(resident=resident)
        else:
            base_qs = base_qs.none()

    tab = (request.GET.get("tab") or "all").strip().lower()
    if tab == "meeting":
        base_qs = base_qs.filter(attendance_type="Meeting")
    elif tab == "cleaning":
        base_qs = base_qs.filter(attendance_type="Cleaning")
    rows = list(base_qs)

    table_rows = "".join(
        (
            "<tr>"
            f"<td>{escape(record.resident.first_name)} {escape(record.resident.last_name)}</td>"
            f"<td>{escape(record.attendance_type)}</td>"
            f"<td>{escape(record.date.strftime('%Y-%m-%d'))}</td>"
            f"<td>{escape(record.status)}</td>"
            "</tr>"
        )
        for record in rows
    )
    if not table_rows:
        table_rows = '<tr><td colspan="4">No attendance records found.</td></tr>'

    html = f"""
    <html>
    <head><meta charset="utf-8"><title>Attendance Records</title></head>
    <body>
        <h2>Attendance Records</h2>
        <table border="1" cellspacing="0" cellpadding="6">
            <thead>
                <tr>
                    <th>Resident</th>
                    <th>Attendance Type</th>
                    <th>Date</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>
    </body>
    </html>
    """
    response = HttpResponse(html, content_type="application/msword")
    response["Content-Disposition"] = 'attachment; filename="attendance_records.doc"'
    return response

@login_required
@staff_required
def attendance_create(request):
    if request.method == "POST":
        form = AttendanceForm(request.POST)
        if form.is_valid():
            attendance, penalty_fee = attendance_service.create_attendance(form)
            if penalty_fee is not None:
                messages.warning(
                    request,
                    f"Resident {attendance.resident} is absent from {attendance.attendance_type.lower()}. Penalty fee automatically added.",
                )
            else:
                messages.success(request, f"Attendance recorded for {attendance.resident}.")
            return redirect("attendance-list")
    else:
        form = AttendanceForm()
    return render(request, "management/attendance_form.html", {"form": form, "title": "Add Attendance"})


@login_required
def fee_list(request):
    base_qs = (
        Fee.objects.select_related("resident", "fee_type")
        .prefetch_related(
            "payment_transactions",
            "payment_transactions__submitted_by",
            "payment_transactions__reviewed_by",
        )
        .all()
        .order_by("-id")
    )

    if not request.user.is_staff:
        resident = Resident.objects.filter(user=request.user).first()
        if resident:
            base_qs = base_qs.filter(resident=resident)
        else:
            base_qs = base_qs.none()

    meeting_qs = base_qs.filter(fee_type__name="Penalty for Missed Meeting")
    cleaning_qs = base_qs.filter(fee_type__name="Penalty for Missed Cleaning")
    other_qs = base_qs.exclude(fee_type__name__in=["Penalty for Missed Meeting", "Penalty for Missed Cleaning"])

    def _decorate(qs):
        items = list(qs)
        for fee in items:
            fee.payment_transactions_list = list(fee.payment_transactions.all())
            fee.pending_payment = next((tx for tx in fee.payment_transactions_list if tx.status == "pending"), None)
            fee.manual_payment_form = None
            if not request.user.is_staff and not fee.paid and fee.pending_payment is None:
                fee.manual_payment_form = PaymentTransactionForm(
                    prefix=f"fee-{fee.pk}",
                    initial={"amount_sent": fee.amount, "payment_date": timezone.localdate()},
                )
        return items

    return render(
        request,
        "management/fee_list.html",
        {
            "meeting_fees": _decorate(meeting_qs),
            "cleaning_fees": _decorate(cleaning_qs),
            "other_fees": _decorate(other_qs),
            "manual_gcash_name": settings.MANUAL_GCASH_NAME,
            "manual_gcash_number": settings.MANUAL_GCASH_NUMBER,
        },
    )

@login_required
@staff_required
def fee_create(request):
    if request.method == "POST":
        form = FeeForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                form.save()
            messages.success(request, "Fee added successfully.")
            return redirect("fee-list")
    else:
        form = FeeForm()
    return render(request, "management/fee_form.html", {"form": form, "title": "Add Fee"})


@login_required
@staff_required
@require_POST
def fee_mark_paid(request, pk):
    fee = get_object_or_404(Fee, pk=pk)
    fee_service.mark_fee_paid(fee)
    write_audit_log(
        "mark_fee_paid",
        f"Marked fee paid for resident '{fee.resident}'.",
        actor=request.user,
        target=fee,
        metadata={"amount": str(fee.amount), "fee_type": fee.fee_type.name},
    )
    messages.success(request, f"Fee for {fee.resident} has been marked as paid.")
    return redirect("fee-list")


@login_required
def fee_submit_payment(request, pk):
    if request.user.is_staff:
        messages.error(request, "Staff accounts cannot submit manual GCash payments from this page.")
        return redirect("fee-list")

    fee = get_object_or_404(Fee.objects.select_related("resident", "fee_type"), pk=pk)
    resident = Resident.objects.filter(user=request.user).first()
    if resident is None or fee.resident_id != resident.id:
        messages.error(request, "You are not allowed to submit payment for this fee.")
        return redirect("fee-list")

    # Get payment transactions for this fee
    payment_transactions = fee.payment_transactions.all()
    
    # Check if there's a pending payment
    pending_payment = next((tx for tx in payment_transactions if tx.status == "pending"), None)
    is_viewing_payment = fee.paid or pending_payment is not None

    if request.method == "POST":
        form = PaymentTransactionForm(request.POST, prefix=f"fee-{fee.pk}")
        if form.is_valid():
            try:
                fee_service.submit_manual_payment(
                    fee=fee,
                    submitted_by=request.user,
                    **form.cleaned_data,
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    "Payment transaction submitted. Please wait for admin approval before the fee is marked as paid.",
                )
                return redirect("fee-list")
        else:
            first_error = next(iter(form.errors.values()))[0] if form.errors else "Please check your payment details."
            messages.error(request, first_error)
    else:
        form = PaymentTransactionForm(prefix=f"fee-{fee.pk}")

    context = {
        "fee": fee,
        "form": form,
        "payment_transactions": payment_transactions,
        "is_viewing_payment": is_viewing_payment,
        "manual_gcash_name": settings.MANUAL_GCASH_NAME,
        "manual_gcash_number": settings.MANUAL_GCASH_NUMBER,
    }
    return render(request, "management/fee_submit_payment.html", context)


@login_required
@staff_required
@require_POST
def fee_payment_action(request, tx_id, action):
    payment = get_object_or_404(PaymentTransaction.objects.select_related("fee", "fee__resident", "fee__fee_type"), pk=tx_id)

    try:
        if action == "approve":
            fee_service.approve_payment_transaction(payment, reviewer=request.user)
            write_audit_log(
                "mark_fee_paid",
                f"Approved manual GCash payment for resident '{payment.fee.resident}'.",
                actor=request.user,
                target=payment.fee,
                metadata={
                    "amount": str(payment.amount_sent),
                    "fee_type": payment.fee.fee_type.name,
                    "payment_reference": payment.gcash_reference,
                    "payment_channel": "manual_gcash",
                },
            )
            messages.success(request, f"Manual GCash payment for {payment.fee.resident} approved.")
        elif action == "reject":
            fee_service.reject_payment_transaction(payment, reviewer=request.user)
            messages.warning(request, f"Manual GCash payment for {payment.fee.resident} was rejected.")
        else:
            messages.error(request, "Invalid payment action.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("fee-list")


@login_required
def clearance_list(request):
    clearances = PurokClearance.objects.select_related("resident").all().order_by("-date_issued", "-id")
    if not request.user.is_staff:
        resident = Resident.objects.filter(user=request.user).first()
        if resident:
            clearances = clearances.filter(resident=resident)
        else:
            clearances = clearances.none()
    return render(request, "management/clearance_list.html", {"clearances": clearances})


@login_required
def clearance_download(request, pk):
    clearance = get_object_or_404(PurokClearance.objects.select_related("resident", "resident__user"), pk=pk)
    if not request.user.is_staff:
        resident = Resident.objects.filter(user=request.user).first()
        if resident is None or clearance.resident_id != resident.id:
            messages.error(request, "You are not allowed to download this clearance.")
            return redirect("clearance-list")

    resident_name = escape(f"{clearance.resident.first_name} {clearance.resident.last_name}")
    clearance_type = escape(clearance.clearance_type.name)
    if clearance_type.strip().lower() == "barangay":
        clearance_type = "Purok Clearance"
    date_issued = escape(clearance.date_issued.strftime("%B %d, %Y"))
    remarks = escape(clearance.remarks or "-")

    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Purok Clearance</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 36px; color: #1a2b33; }}
            .content {{ border: 1px solid #c8d7de; padding: 18px; border-radius: 8px; }}
            .line {{ margin-bottom: 12px; }}
            .label {{ font-weight: bold; }}
            .footer {{ margin-top: 44px; }}
            .sign {{ margin-top: 52px; border-top: 1px solid #6b7c86; width: 260px; padding-top: 6px; }}
        </style>
    </head>
    <body>
        <div class="content">
            <div class="line"><span class="label">Resident Name:</span> {resident_name}</div>
            <div class="line"><span class="label">Clearance Type:</span> {clearance_type}</div>
            <div class="line"><span class="label">Date Issued:</span> {date_issued}</div>
        </div>

        <p style="margin-top:28px;">This certifies that the person named above is issued this clearance based on the current records.</p>

        <div class="footer">
            <div class="sign">Authorized Signature</div>
        </div>
    </body>
    </html>
    """
    response = HttpResponse(html, content_type="application/msword")
    response["Content-Disposition"] = f'attachment; filename="purok_clearance_{clearance.pk}.doc"'
    return response


@login_required
@staff_required
def clearance_create(request):
    if request.method == "POST":
        form = ClearanceForm(request.POST)
        if form.is_valid():
            clearance = form.save(commit=False)
            if clearance.can_issue():
                clearance = clearance_service.issue_clearance_from_form(form)
                write_audit_log(
                    "issue_clearance",
                    f"Issued {clearance.clearance_type.name} clearance for '{clearance.resident}'.",
                    actor=request.user,
                    target=clearance,
                    metadata={"clearance_type": clearance.clearance_type.name},
                )
                messages.success(request, f"Clearance issued for {clearance.resident}.")
            else:
                messages.error(request, f"Cannot issue clearance. {clearance.resident} has unpaid fees.")
            return redirect("clearance-list")
    else:
        form = ClearanceForm()
    return render(request, "management/clearance_form.html", {"form": form, "title": "Issue Clearance"})


@login_required
def user_settings(request):
    resident = Resident.objects.filter(user=request.user).first()
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=request.user)
        resident_form = UserResidentInfoForm(request.POST, instance=resident)
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
        if user_form.is_valid() and resident_form.is_valid() and profile_form.is_valid():
            user_form.save()
            resident_obj = resident_form.save(commit=False)
            resident_obj.user = request.user
            resident_obj.save()
            profile_form.save()
            messages.success(request, "Your account information has been updated successfully.")
            return redirect("user-settings")
        messages.error(request, "Some information is invalid. Please correct the fields and save again.")
    else:
        user_form = UserUpdateForm(instance=request.user)
        resident_form = UserResidentInfoForm(instance=resident)
        profile_form = ProfileForm(instance=profile)

    context = {
        "user_form": user_form,
        "resident_form": resident_form,
        "profile_form": profile_form,
    }
    return render(request, "management/user_setting.html", context)


@login_required
@staff_required
def pending_tasks(request):
    pending_users_count = User.objects.filter(is_staff=False, is_superuser=False, is_active=False).count()
    verification_pending_count = VerificationCodeRequest.objects.filter(status="pending").count()
    unpaid_fees_count = Fee.objects.filter(paid=False).count()
    clearances_today_count = PurokClearance.objects.filter(date_issued=timezone.localdate()).count()

    tasks = [
        {
            "task": "Review pending account approvals",
            "count": pending_users_count,
            "priority": "High" if pending_users_count else "Low",
            "target": "Pending Accounts",
            "url": "/pending-accounts/",
        },
        {
            "task": "Generate login codes",
            "count": verification_pending_count,
            "priority": "High" if verification_pending_count else "Low",
            "target": "Pending Accounts",
            "url": "/pending-accounts/",
        },
        {
            "task": "Follow up unpaid fees",
            "count": unpaid_fees_count,
            "priority": "Medium" if unpaid_fees_count else "Low",
            "target": "Fees",
            "url": "/fees/",
        },
        {
            "task": "Review clearance issuances today",
            "count": clearances_today_count,
            "priority": "Low",
            "target": "Clearances",
            "url": "/clearances/",
        },
    ]
    return render(request, "management/pending_tasks.html", {"tasks": tasks})


@login_required
@staff_required
def pending_tasks_export_word(request):
    pending_users_count = User.objects.filter(is_staff=False, is_superuser=False, is_active=False).count()
    verification_pending_count = VerificationCodeRequest.objects.filter(status="pending").count()
    unpaid_fees_count = Fee.objects.filter(paid=False).count()
    clearances_today_count = PurokClearance.objects.filter(date_issued=timezone.localdate()).count()

    rows = [
        ("Review pending account approvals", pending_users_count, "Pending Accounts", "/pending-accounts/"),
        ("Generate login codes", verification_pending_count, "Pending Accounts", "/pending-accounts/"),
        ("Follow up unpaid fees", unpaid_fees_count, "Fees", "/fees/"),
        ("Review clearance issuances today", clearances_today_count, "Clearances", "/clearances/"),
    ]

    html_rows = "".join(
        f"<tr><td>{task}</td><td>{count}</td><td>{target}</td><td>{url}</td></tr>"
        for task, count, target, url in rows
    )
    html = f"""
    <html>
    <head><meta charset="utf-8"><title>Pending Tasks</title></head>
    <body>
        <h2>Pending Tasks</h2>
        <table border="1" cellspacing="0" cellpadding="6">
            <thead>
                <tr>
                    <th>Task</th>
                    <th>Count</th>
                    <th>Target</th>
                    <th>URL</th>
                </tr>
            </thead>
            <tbody>{html_rows}</tbody>
        </table>
    </body>
    </html>
    """
    response = HttpResponse(html, content_type="application/msword")
    response["Content-Disposition"] = 'attachment; filename="pending_tasks.doc"'
    return response


@login_required
@staff_required
def dbms_lab(request):
    join_group_having_sql = """
        SELECT
            r.id,
            r.first_name,
            r.last_name,
            COUNT(a.id) AS absent_count
        FROM management_resident r
        LEFT JOIN management_attendance a
            ON a.resident_id = r.id
            AND a.status = %s
        GROUP BY r.id, r.first_name, r.last_name
        HAVING COUNT(a.id) >= %s
        ORDER BY absent_count DESC, r.last_name ASC, r.first_name ASC
        LIMIT 20
    """
    subquery_sql = """
        SELECT
            f.id,
            f.resident_id,
            f.amount,
            f.paid,
            (
                SELECT COUNT(*)
                FROM management_fee f2
                WHERE f2.resident_id = f.resident_id
                  AND f2.paid = 0
            ) AS resident_unpaid_count
        FROM management_fee f
        ORDER BY f.id DESC
        LIMIT 20
    """
    aggregate_sql = """
        SELECT
            p.resident_id,
            COUNT(p.id) AS clearance_count
        FROM management_purokclearance p
        GROUP BY p.resident_id
        HAVING COUNT(p.id) >= %s
        ORDER BY clearance_count DESC, p.resident_id ASC
        LIMIT 20
    """

    join_result = _run_sql(join_group_having_sql, params=["Absent", 0])
    subquery_result = _run_sql(subquery_sql)
    aggregate_result = _run_sql(aggregate_sql, params=[1])
    explain_result = _run_explain(join_group_having_sql, params=["Absent", 0])

    return render(
        request,
        "management/dbms_lab.html",
        {
            "db_vendor": connection.vendor,
            "join_result": join_result,
            "subquery_result": subquery_result,
            "aggregate_result": aggregate_result,
            "explain_result": explain_result,
        },
    )


@login_required
@staff_required
def audit_logs(request):
    logs = _attach_audit_log_resident_names(
        list(AuditLog.objects.select_related("actor").all().order_by("-created_at"))
    )
    paginator = Paginator(logs, 30)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "management/audit_logs.html", {"audit_logs": page_obj})


def _attach_audit_log_resident_names(logs):
    request_ids = [log.target_id for log in logs if log.target_type == "VerificationCodeRequest" and log.target_id]
    fee_ids = [log.target_id for log in logs if log.target_type == "Fee" and log.target_id]
    clearance_ids = [log.target_id for log in logs if log.target_type == "PurokClearance" and log.target_id]
    user_ids = [log.target_id for log in logs if log.target_type == "User" and log.target_id]

    req_map = {r.pk: r.name for r in VerificationCodeRequest.objects.filter(pk__in=request_ids).only("id", "name")}
    fee_map = {
        f.pk: str(f.resident)
        for f in Fee.objects.select_related("resident").filter(pk__in=fee_ids)
    }
    clearance_map = {
        c.pk: str(c.resident)
        for c in PurokClearance.objects.select_related("resident").filter(pk__in=clearance_ids)
    }
    user_map = {}
    for user in User.objects.filter(pk__in=user_ids).select_related("resident_profile"):
        resident = getattr(user, "resident_profile", None)
        user_map[user.pk] = str(resident) if resident else user.username

    for log in logs:
        resident_name = "-"
        if log.target_type == "VerificationCodeRequest":
            resident_name = req_map.get(log.target_id, "-")
        elif log.target_type == "Fee":
            resident_name = fee_map.get(log.target_id, "-")
        elif log.target_type == "PurokClearance":
            resident_name = clearance_map.get(log.target_id, "-")
        elif log.target_type == "User":
            resident_name = user_map.get(log.target_id, "-")
        log.resident_name = resident_name

    return logs


@login_required
@staff_required
def audit_logs_export_word(request):
    logs = _attach_audit_log_resident_names(
        list(AuditLog.objects.select_related("actor").all().order_by("-created_at"))
    )
    html_rows = "".join(
        (
            "<tr>"
            f"<td>{escape(timezone.localtime(log.created_at).strftime('%Y-%m-%d %H:%M:%S'))}</td>"
            f"<td>{escape(log.action)}</td>"
            f"<td>{escape(getattr(log, 'resident_name', '-'))}</td>"
            f"<td>{escape(log.target_type)}</td>"
            f"<td>{escape(str(log.target_id or ''))}</td>"
            f"<td>{escape(log.description)}</td>"
            "</tr>"
        )
        for log in logs
    )
    html = f"""
    <html>
    <head><meta charset="utf-8"><title>Audit Logs</title></head>
    <body>
        <h2>Audit Logs</h2>
        <table border="1" cellspacing="0" cellpadding="6">
            <thead>
                <tr>
                    <th>Created At</th>
                    <th>Action</th>
                    <th>Resident Name</th>
                    <th>Target Type</th>
                    <th>Target ID</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>{html_rows}</tbody>
        </table>
    </body>
    </html>
    """
    response = HttpResponse(html, content_type="application/msword")
    response["Content-Disposition"] = 'attachment; filename="audit_logs.doc"'
    return response






