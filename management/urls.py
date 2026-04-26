from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from . import views_audit
from . import views_auth
from . import views_exports
from . import views_fees
from .forms import CustomPasswordChangeForm

urlpatterns = [
    path("healthz/", views_auth.healthz, name="healthz"),
    path("", views_auth.welcome, name="welcome"),
    path("request-verification-code/", views_auth.request_verification_code, name="request-verification-code"),
    path("forgot-password-request/", views_auth.forgot_password_request, name="forgot-password-request"),
    path("reset-password-with-code/", views_auth.password_reset_with_code, name="password-reset-with-code"),
    path("register/", views_auth.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="management/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            form_class=CustomPasswordChangeForm,
            template_name="management/password_change.html",
            success_url=reverse_lazy("password-change-done"),
        ),
        name="password-change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="management/password_change_done.html"
        ),
        name="password-change-done",
    ),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("residents/", views.resident_list, name="resident-list"),
    path("residents/export.doc", views.resident_export_word, name="resident-export-word"),
    path("residents/add/", views.resident_create, name="resident-add"),
    path("residents/edit/<int:pk>/", views.resident_edit, name="resident-edit"),
    path("residents/delete/<int:pk>/", views.resident_delete, name="resident-delete"),
    path("attendance/", views.attendance_list, name="attendance-list"),
    path("attendance/add/", views.attendance_create, name="attendance-add"),
    path("attendance/export.doc", views.attendance_export_word, name="attendance-export-word"),
    path("fees/", views_fees.fee_list, name="fee-list"),
    path("fees/add/", views_fees.fee_create, name="fee-add"),
    path("fees/mark-paid/<int:pk>/", views_fees.fee_mark_paid, name="fee-mark-paid"),
    path("fees/<int:pk>/submit-payment/", views_fees.fee_submit_payment, name="fee-submit-payment"),
    path("fees/<int:pk>/payment-info/", views_fees.fee_view_payment, name="fee-view-payment"),
    path("fees/payment-transactions/<int:tx_id>/<str:action>/", views_fees.fee_payment_action, name="fee-payment-action"),
    path("fees/payment-transactions/<int:tx_id>/receipt.doc", views_fees.fee_payment_receipt, name="fee-payment-receipt"),
    path("clearances/", views.clearance_list, name="clearance-list"),
    path("clearances/download/<int:pk>/", views.clearance_download, name="clearance-download"),
    path("clearances/add/", views.clearance_create, name="clearance-add"),
    path("settings/", views.user_settings, name="user-settings"),
    path("pending-tasks/", views.pending_tasks, name="pending-tasks"),
    path("pending-tasks/export.doc", views_exports.pending_tasks_export_word, name="pending-tasks-export-word"),
    path("audit-logs/", views_audit.audit_logs, name="audit-logs"),
    path("audit-logs/export.doc", views_audit.audit_logs_export_word, name="audit-logs-export-word"),
    path("pending-accounts/", views_auth.pending_accounts, name="pending-accounts"),
    path(
        "pending-accounts/<int:user_id>/action/",
        views_auth.pending_account_action,
        name="pending-account-action",
    ),
    path(
        "verification-requests/<int:request_id>/action/",
        views_auth.verification_request_action,
        name="verification-request-action",
    ),
]
