from html import escape
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from .models import AuditLog, Fee, PurokClearance, VerificationCodeRequest

staff_required = user_passes_test(lambda user: user.is_staff)


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


def _get_filtered_audit_logs(request):
    search_query = (request.GET.get("q") or "").strip()
    selected_action = (request.GET.get("action") or "").strip()
    valid_actions = {value for value, _label in AuditLog.ACTION_CHOICES}

    if selected_action not in valid_actions:
        selected_action = ""

    logs_qs = AuditLog.objects.select_related("actor").all().order_by("-created_at")
    if selected_action:
        logs_qs = logs_qs.filter(action=selected_action)

    if search_query:
        search_filter = (
            Q(description__icontains=search_query)
            | Q(target_type__icontains=search_query)
            | Q(action__icontains=search_query)
            | Q(actor__username__icontains=search_query)
        )
        if search_query.isdigit():
            search_filter |= Q(target_id=int(search_query))
        logs_qs = logs_qs.filter(search_filter)

    logs = _attach_audit_log_resident_names(list(logs_qs))
    if search_query:
        search_text = search_query.lower()
        logs = [
            log
            for log in logs
            if (
                search_text in (log.get_action_display() or "").lower()
                or search_text in (getattr(log, "resident_name", "") or "").lower()
                or search_text in (log.description or "").lower()
                or search_text in (log.target_type or "").lower()
                or search_text in str(log.target_id or "").lower()
                or search_text in ((log.actor.username if log.actor else "") or "").lower()
            )
        ]

    return logs, search_query, selected_action


def _build_action_filters(search_query, selected_action):
    action_filters = []
    all_params = {"q": search_query} if search_query else {}
    action_filters.append(
        {
            "label": "All Actions",
            "url": f"?{urlencode(all_params)}" if all_params else "?",
            "active": not selected_action,
        }
    )
    for action_value, action_label in AuditLog.ACTION_CHOICES:
        params = {"action": action_value}
        if search_query:
            params["q"] = search_query
        action_filters.append(
            {
                "label": action_label,
                "url": f"?{urlencode(params)}",
                "active": selected_action == action_value,
            }
        )
    return action_filters


@login_required
@staff_required
def audit_logs(request):
    logs, search_query, selected_action = _get_filtered_audit_logs(request)
    paginator = Paginator(logs, 30)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    export_query = query_params.urlencode()
    pagination_query = f"&{export_query}" if export_query else ""

    context = {
        "audit_logs": page_obj,
        "search_query": search_query,
        "selected_action": selected_action,
        "action_filters": _build_action_filters(search_query, selected_action),
        "pagination_query": pagination_query,
        "export_query": export_query,
    }
    return render(request, "management/audit_logs.html", context)


@login_required
@staff_required
def audit_logs_export_word(request):
    logs, _search_query, _selected_action = _get_filtered_audit_logs(request)
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
