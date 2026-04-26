from html import escape

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.utils import timezone

from django.contrib.auth.models import User

from .models import Fee, PurokClearance, VerificationCodeRequest

staff_required = user_passes_test(lambda user: user.is_staff)


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
        f"<tr><td>{escape(task)}</td><td>{count}</td><td>{escape(target)}</td><td>{escape(url)}</td></tr>"
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
