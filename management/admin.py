from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
import logging
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .forms import FeeForm
from .models import (
    Attendance,
    AuditLog,
    ClearanceType,
    Fee,
    PaymentTransaction,
    FeeType,
    LoginActivity,
    Profile,
    Purok,
    PurokClearance,
    Resident,
    VerificationCode,
    VerificationCodeRequest,
    create_unique_verification_code,
    write_audit_log,
)
from .services import email_service, fee_service

logger = logging.getLogger(__name__)


class LoginActivityInline(admin.TabularInline):
    model = LoginActivity
    extra = 0
    can_delete = False
    readonly_fields = ("login_at", "ip_address", "user_agent")
    fields = ("login_at", "ip_address", "user_agent")
    ordering = ("-login_at",)
    max_num = 10

    def has_add_permission(self, request, obj=None):
        return False


@admin.action(description="Approve selected users (set active)")
def approve_users(modeladmin, request, queryset):
    updated = 0
    for target_user in queryset:
        if not target_user.is_active:
            target_user.is_active = True
            target_user.save(update_fields=["is_active"])
            updated += 1
        write_audit_log(
            "approve_user",
            f"Approved user '{target_user.username}' from admin action.",
            actor=request.user,
            target=target_user,
            metadata={"channel": "admin", "source": "bulk_action"},
        )
    modeladmin.message_user(request, f"{updated} user(s) approved.")


@admin.action(description="Deactivate selected users")
def deactivate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f"{updated} user(s) deactivated.")


class CustomUserAdmin(DjangoUserAdmin):
    inlines = [LoginActivityInline]
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    actions = [approve_users, deactivate_users]


@admin.register(VerificationCode)
class VerificationCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "is_active", "used_count", "max_uses", "expires_at", "created_at")
    list_filter = ("is_active",)
    search_fields = ("code",)


@admin.register(VerificationCodeRequest)
class VerificationCodeRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "request_type", "status", "requested_at", "verification_code", "create_code_button")
    list_filter = ("request_type", "status", "requested_at")
    search_fields = ("name", "email", "verification_code__code")
    readonly_fields = ("requested_at",)
    actions = ("generate_code_for_selected",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:request_id>/generate-code/",
                self.admin_site.admin_view(self.generate_code_view),
                name="management_verificationcoderequest_generate_code",
            ),
        ]
        return custom_urls + urls

    def create_code_button(self, obj):
        url = reverse("admin:management_verificationcoderequest_generate_code", args=[obj.pk])
        return format_html('<a class="button" href="{}">Create Code</a>', url)

    create_code_button.short_description = "Actions"

    @admin.action(description="Generate login code for selected requests")
    def generate_code_for_selected(self, request, queryset):
        updated = 0
        emailed = 0
        for req in queryset:
            try:
                code = self._get_or_create_code(req)
                req.verification_code = code
                req.status = "resolved"
                req.save(update_fields=["verification_code", "status"])
                write_audit_log(
                    "create_code",
                    f"Generated login code for '{req.email}' from admin action.",
                    actor=request.user,
                    target=req,
                    metadata={"verification_code": code.code, "channel": "admin"},
                )
                if email_service.send_verification_code_email(
                    recipient=req.email,
                    name=req.name,
                    verification_code=code.code,
                    expires_at=code.expires_at,
                ):
                    emailed += 1
                updated += 1
            except Exception:
                logger.exception(
                    "Admin bulk generate_code failed. request_id=%s email=%s",
                    req.pk,
                    req.email,
                )
        failed = updated - emailed
        if failed:
            self.message_user(
                request,
                f"Generated code for {updated} request(s). Emailed: {emailed}. Failed to send: {failed}.",
                level=messages.WARNING,
            )
        else:
            self.message_user(request, f"Generated code for {updated} request(s). All emails sent.")

    def generate_code_view(self, request, request_id):
        req = self.get_object(request, request_id)
        if req is None:
            self.message_user(request, "Request not found.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:management_verificationcoderequest_changelist"))

        try:
            code = self._get_or_create_code(req)
            req.verification_code = code
            req.status = "resolved"
            req.save(update_fields=["verification_code", "status"])
            write_audit_log(
                "create_code",
                f"Generated login code for '{req.email}' from admin button.",
                actor=request.user,
                target=req,
                metadata={"verification_code": code.code, "channel": "admin"},
            )
            email_sent = email_service.send_verification_code_email(
                recipient=req.email,
                name=req.name,
                verification_code=code.code,
                expires_at=code.expires_at,
            )
            if email_sent:
                self.message_user(request, f"Code for {req.email} generated and emailed successfully.")
            else:
                self.message_user(
                    request,
                    f"Code for {req.email}: {code.code}. Email failed to send.",
                    level=messages.WARNING,
                )
        except Exception:
            logger.exception(
                "Admin generate_code_view failed. request_id=%s email=%s",
                req.pk,
                req.email,
            )
            self.message_user(
                request,
                "Failed to generate/send code due to a server error. Check application logs.",
                level=messages.ERROR,
            )
        return HttpResponseRedirect(reverse("admin:management_verificationcoderequest_changelist"))

    def _get_or_create_code(self, req):
        if req.verification_code and req.verification_code.is_usable():
            return req.verification_code

        return create_unique_verification_code(max_uses=1, attempts=15)


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ("user", "login_at", "ip_address")
    list_filter = ("login_at", "user")
    search_fields = ("user__username", "ip_address", "user_agent")
    readonly_fields = ("user", "login_at", "ip_address", "user_agent")

    def has_add_permission(self, request):
        return False


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "contact_number")
    search_fields = ("user__username", "contact_number")


@admin.register(Purok)
class PurokAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(FeeType)
class FeeTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(ClearanceType)
class ClearanceTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "user", "purok", "date_of_birth", "contact_number")
    list_filter = ("purok",)
    search_fields = ("first_name", "last_name", "user__username", "purok__name", "contact_number")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("resident", "attendance_type", "date", "status", "quick_actions")
    list_filter = ("attendance_type", "status", "date", "resident__purok")
    search_fields = ("resident__first_name", "resident__last_name", "resident__purok__name")
    date_hierarchy = "date"
    actions = ("mark_present", "mark_absent", "mark_late")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:attendance_id>/set-status/<str:new_status>/",
                self.admin_site.admin_view(self.set_status_view),
                name="management_attendance_set_status",
            ),
        ]
        return custom_urls + urls

    def quick_actions(self, obj):
        base = "admin:management_attendance_set_status"
        present = reverse(base, args=[obj.pk, "Present"])
        absent = reverse(base, args=[obj.pk, "Absent"])
        late = reverse(base, args=[obj.pk, "Late"])
        return format_html(
            '<a class="button" href="{}">Present</a>&nbsp;'
            '<a class="button" href="{}">Absent</a>&nbsp;'
            '<a class="button" href="{}">Late</a>',
            present,
            absent,
            late,
        )

    quick_actions.short_description = "Quick status"

    def set_status_view(self, request, attendance_id, new_status):
        obj = self.get_object(request, attendance_id)
        if obj is None:
            self.message_user(request, "Attendance record not found.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:management_attendance_changelist"))
        if new_status not in {"Present", "Absent", "Late"}:
            self.message_user(request, "Invalid status.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:management_attendance_changelist"))
        obj.status = new_status
        obj.save(update_fields=["status"])
        self.message_user(request, f"{obj.resident} marked {new_status}.")
        return HttpResponseRedirect(reverse("admin:management_attendance_changelist"))

    @admin.action(description="Mark selected attendance as Present")
    def mark_present(self, request, queryset):
        updated = queryset.update(status="Present")
        self.message_user(request, f"{updated} record(s) marked Present.")

    @admin.action(description="Mark selected attendance as Absent")
    def mark_absent(self, request, queryset):
        updated = queryset.update(status="Absent")
        self.message_user(request, f"{updated} record(s) marked Absent.")

    @admin.action(description="Mark selected attendance as Late")
    def mark_late(self, request, queryset):
        updated = queryset.update(status="Late")
        self.message_user(request, f"{updated} record(s) marked Late.")


@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    form = FeeForm
    list_display = ("resident", "amount", "fee_type", "paid", "date_paid", "mark_paid_button")
    list_filter = ("paid", "fee_type", "date_paid", "resident__purok")
    search_fields = ("resident__first_name", "resident__last_name", "resident__purok__name")
    actions = ("mark_selected_paid", "mark_selected_unpaid")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:fee_id>/mark-paid/",
                self.admin_site.admin_view(self.mark_paid_view),
                name="management_fee_mark_paid",
            ),
        ]
        return custom_urls + urls

    def mark_paid_button(self, obj):
        if obj.paid:
            return format_html('<span style="color:#2f7a4f;font-weight:700;">Paid</span>')
        url = reverse("admin:management_fee_mark_paid", args=[obj.pk])
        return format_html('<a class="button" href="{}">Mark Paid</a>', url)

    mark_paid_button.short_description = "Actions"

    def mark_paid_view(self, request, fee_id):
        fee = self.get_object(request, fee_id)
        if fee is None:
            self.message_user(request, "Fee record not found.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:management_fee_changelist"))
        fee.paid = True
        fee.date_paid = timezone.localdate()
        fee.save(update_fields=["paid", "date_paid"])
        write_audit_log(
            "mark_fee_paid",
            f"Marked fee paid for resident '{fee.resident}' from admin.",
            actor=request.user,
            target=fee,
            metadata={"channel": "admin", "amount": str(fee.amount)},
        )
        self.message_user(request, f"Fee for {fee.resident} marked as paid.")
        return HttpResponseRedirect(reverse("admin:management_fee_changelist"))

    @admin.action(description="Mark selected fees as paid")
    def mark_selected_paid(self, request, queryset):
        updated = 0
        for fee in queryset:
            fee.paid = True
            fee.date_paid = timezone.localdate()
            fee.save(update_fields=["paid", "date_paid"])
            write_audit_log(
                "mark_fee_paid",
                f"Marked fee paid for resident '{fee.resident}' from admin bulk action.",
                actor=request.user,
                target=fee,
                metadata={"channel": "admin", "amount": str(fee.amount)},
            )
            updated += 1
        self.message_user(request, f"{updated} fee(s) marked paid.")

    @admin.action(description="Mark selected fees as unpaid")
    def mark_selected_unpaid(self, request, queryset):
        updated = queryset.update(paid=False, date_paid=None)
        self.message_user(request, f"{updated} fee(s) marked unpaid.")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "fee",
        "submitted_by",
        "amount_sent",
        "gcash_reference",
        "status",
        "payment_date",
        "created_at",
        "reviewed_by",
    )
    list_filter = ("status", "payment_date", "created_at")
    search_fields = (
        "fee__resident__first_name",
        "fee__resident__last_name",
        "gcash_reference",
        "submitted_by__username",
    )
    readonly_fields = ("created_at", "reviewed_at")
    actions = ("approve_selected", "reject_selected")

    @admin.action(description="Approve selected payment transactions")
    def approve_selected(self, request, queryset):
        updated = 0
        for payment in queryset.select_related("fee", "fee__resident", "fee__fee_type"):
            if payment.status != "pending":
                continue
            fee_service.approve_payment_transaction(payment, reviewer=request.user)
            write_audit_log(
                "mark_fee_paid",
                f"Approved manual GCash payment for resident '{payment.fee.resident}' from admin.",
                actor=request.user,
                target=payment.fee,
                metadata={
                    "amount": str(payment.amount_sent),
                    "payment_reference": payment.gcash_reference,
                    "payment_channel": "manual_gcash",
                },
            )
            updated += 1
        self.message_user(request, f"{updated} payment transaction(s) approved.")

    @admin.action(description="Reject selected payment transactions")
    def reject_selected(self, request, queryset):
        updated = 0
        for payment in queryset:
            if payment.status != "pending":
                continue
            fee_service.reject_payment_transaction(payment, reviewer=request.user)
            updated += 1
        self.message_user(request, f"{updated} payment transaction(s) rejected.")


@admin.register(PurokClearance)
class PurokClearanceAdmin(admin.ModelAdmin):
    list_display = ("resident", "clearance_type", "date_issued", "remarks", "eligibility_status")
    list_filter = ("clearance_type", "date_issued", "resident__purok")
    search_fields = ("resident__first_name", "resident__last_name", "resident__purok__name", "remarks")
    date_hierarchy = "date_issued"
    actions = ("revalidate_selected_clearances",)

    def eligibility_status(self, obj):
        if obj.can_issue():
            return format_html('<span style="color:#2f7a4f;font-weight:700;">Eligible</span>')
        return format_html('<span style="color:#b13a48;font-weight:700;">Has unpaid fees</span>')

    eligibility_status.short_description = "Resident status"

    @admin.action(description="Revalidate selected clearances")
    def revalidate_selected_clearances(self, request, queryset):
        invalid = 0
        for clearance in queryset:
            if not clearance.can_issue():
                invalid += 1
        if invalid:
            self.message_user(
                request,
                f"{invalid} clearance record(s) have residents with unpaid fees.",
                level=messages.WARNING,
            )
        else:
            self.message_user(request, "All selected clearances remain valid.")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            write_audit_log(
                "issue_clearance",
                f"Issued {obj.clearance_type.name} clearance for '{obj.resident}' from admin.",
                actor=request.user,
                target=obj,
                metadata={"channel": "admin", "clearance_type": obj.clearance_type.name},
            )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "target_type", "target_id", "description")
    list_filter = ("action", "created_at")
    search_fields = ("description", "actor__username", "target_type")
    readonly_fields = ("created_at",)

    def has_add_permission(self, request):
        return False


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)



