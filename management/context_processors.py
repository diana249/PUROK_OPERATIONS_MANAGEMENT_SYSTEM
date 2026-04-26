from .models import Notification


def notification_summary(request):
    if not request.user.is_authenticated:
        return {"unread_notification_count": 0, "latest_notifications": []}
    latest = list(
        Notification.objects.filter(user=request.user)
        .only("id", "title", "level", "is_read", "created_at", "link")
        .order_by("-created_at")[:8]
    )
    unread_count = sum(1 for item in latest if not item.is_read)
    if unread_count < Notification.objects.filter(user=request.user, is_read=False).count():
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return {
        "unread_notification_count": unread_count,
        "latest_notifications": latest,
    }
