from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from html import escape

from .forms import FeeForm, PaymentTransactionForm
from .models import Fee, PaymentTransaction, Resident, write_audit_log
from .services import fee_service
from .services import email_service

staff_required = user_passes_test(lambda user: user.is_staff)


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
    tab = (request.GET.get("tab") or "meeting").strip().lower()
    if tab not in {"meeting", "cleaning", "other", "all"}:
        tab = "meeting"

    def _decorate(qs):
        items = list(qs)
        for fee in items:
            fee.payment_transactions_list = list(fee.payment_transactions.all())
            fee.pending_payment = next((tx for tx in fee.payment_transactions_list if tx.status == "pending"), None)
            fee.approved_payment = next((tx for tx in fee.payment_transactions_list if tx.status == "approved"), None)
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
            "fee_tab": tab,
            "manual_gcash_name": "Diana Rose C. Mesa",
            "manual_gcash_number": "09054978275",
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

    payment_transactions = fee.payment_transactions.all()
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
                resident_email = (request.user.email or "").strip()
                if resident_email:
                    email_service.send_payment_submission_email(
                        recipient=resident_email,
                        resident_name=str(fee.resident),
                        fee_type=str(fee.fee_type),
                        amount=fee.amount,
                        gcash_reference=form.cleaned_data["gcash_reference"],
                        payment_date=form.cleaned_data["payment_date"],
                    )
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
        "manual_gcash_name": "Diana Rose C. Mesa",
        "manual_gcash_number": "09054978275",
    }
    return render(request, "management/fee_submit_payment.html", context)


@login_required
def fee_view_payment(request, pk):
    fee = get_object_or_404(
        Fee.objects.select_related("resident", "resident__user", "fee_type").prefetch_related(
            "payment_transactions",
            "payment_transactions__submitted_by",
            "payment_transactions__reviewed_by",
        ),
        pk=pk,
    )

    if not request.user.is_staff:
        resident = Resident.objects.filter(user=request.user).first()
        if resident is None or fee.resident_id != resident.id:
            messages.error(request, "You are not allowed to view payment details for this fee.")
            return redirect("fee-list")

    payment_transactions = list(fee.payment_transactions.all())
    approved_payment = next((tx for tx in payment_transactions if tx.status == "approved"), None)
    pending_payment = next((tx for tx in payment_transactions if tx.status == "pending"), None)

    return render(
        request,
        "management/fee_payment_view.html",
        {
            "fee": fee,
            "payment_transactions": payment_transactions,
            "approved_payment": approved_payment,
            "pending_payment": pending_payment,
        },
    )


@login_required
def fee_payment_receipt(request, tx_id):
    payment = get_object_or_404(
        PaymentTransaction.objects.select_related(
            "fee",
            "fee__resident",
            "fee__fee_type",
            "submitted_by",
            "reviewed_by",
        ),
        pk=tx_id,
    )

    if payment.status != "approved":
        messages.error(request, "Receipt is only available for approved payments.")
        return redirect("fee-view-payment", pk=payment.fee_id)

    if not request.user.is_staff:
        resident = Resident.objects.filter(user=request.user).first()
        if resident is None or payment.fee.resident_id != resident.id:
            messages.error(request, "You are not allowed to download this receipt.")
            return redirect("fee-list")

    reviewer = payment.reviewed_by.username if payment.reviewed_by else "-"
    submitted_by = payment.submitted_by.username if payment.submitted_by else "-"
    html = f"""
    <html>
    <head><meta charset="utf-8"><title>Payment Receipt</title></head>
    <body>
        <h2>Payment Receipt</h2>
        <p><strong>Resident:</strong> {escape(str(payment.fee.resident))}</p>
        <p><strong>Fee Type:</strong> {escape(str(payment.fee.fee_type))}</p>
        <p><strong>Fee Amount:</strong> {escape(str(payment.fee.amount))}</p>
        <p><strong>GCash Reference:</strong> {escape(payment.gcash_reference)}</p>
        <p><strong>Amount Sent:</strong> {escape(str(payment.amount_sent))}</p>
        <p><strong>Payment Date:</strong> {escape(payment.payment_date.strftime('%Y-%m-%d'))}</p>
        <p><strong>Submitted By:</strong> {escape(submitted_by)}</p>
        <p><strong>Status:</strong> Approved</p>
        <p><strong>Reviewed By:</strong> {escape(reviewer)}</p>
        <p><strong>Reviewed At:</strong> {escape(payment.reviewed_at.strftime('%Y-%m-%d %H:%M:%S') if payment.reviewed_at else '-')}</p>
    </body>
    </html>
    """
    response = HttpResponse(html, content_type="application/msword")
    response["Content-Disposition"] = f'attachment; filename="payment_receipt_{payment.pk}.doc"'
    return response


@login_required
@staff_required
@require_POST
def fee_payment_action(request, tx_id, action):
    payment = get_object_or_404(PaymentTransaction.objects.select_related("fee", "fee__resident", "fee__fee_type"), pk=tx_id)

    try:
        if action == "approve":
            payment = fee_service.approve_payment_transaction(payment, reviewer=request.user)
            resident_email = ((payment.fee.resident.user.email if payment.fee.resident.user else "") or "").strip()
            if resident_email:
                email_service.send_payment_review_email(
                    recipient=resident_email,
                    resident_name=str(payment.fee.resident),
                    fee_type=str(payment.fee.fee_type),
                    amount=payment.amount_sent,
                    gcash_reference=payment.gcash_reference,
                    status=payment.status,
                    reviewed_at=payment.reviewed_at,
                    admin_notes=payment.admin_notes,
                )
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
            messages.success(
                request,
                f"Manual GCash payment for {payment.fee.resident} approved. Receipt is now available for the user.",
            )
        elif action == "reject":
            payment = fee_service.reject_payment_transaction(payment, reviewer=request.user)
            resident_email = ((payment.fee.resident.user.email if payment.fee.resident.user else "") or "").strip()
            if resident_email:
                email_service.send_payment_review_email(
                    recipient=resident_email,
                    resident_name=str(payment.fee.resident),
                    fee_type=str(payment.fee.fee_type),
                    amount=payment.amount_sent,
                    gcash_reference=payment.gcash_reference,
                    status=payment.status,
                    reviewed_at=payment.reviewed_at,
                    admin_notes=payment.admin_notes,
                )
            messages.warning(request, f"Manual GCash payment for {payment.fee.resident} was rejected.")
        else:
            messages.error(request, "Invalid payment action.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("fee-list")
