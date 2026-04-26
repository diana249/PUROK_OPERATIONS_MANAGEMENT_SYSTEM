from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import LoginActivity


@receiver(user_logged_in)
def track_login_activity(sender, request, user, **kwargs):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip_address = ""
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    else:
        ip_address = request.META.get("REMOTE_ADDR", "")

    LoginActivity.objects.create(
        user=user,
        ip_address=ip_address or None,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
    )
