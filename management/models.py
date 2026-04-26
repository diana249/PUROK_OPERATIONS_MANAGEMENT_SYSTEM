from datetime import timedelta
import secrets

from django.contrib.auth.models import User
from django.db import IntegrityError, models
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


def default_verification_expiry():
    return timezone.now() + timedelta(hours=1)


class Purok(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FeeType(models.Model):
    name = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ClearanceType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Resident(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="resident_profile",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    household_number = models.CharField(max_length=50, blank=True, default="")
    gender = models.CharField(max_length=20, blank=True, default="")
    purok = models.ForeignKey(Purok, on_delete=models.PROTECT, related_name="residents")
    age = models.PositiveIntegerField(blank=True, null=True)
    date_of_birth = models.DateField()
    place_of_birth = models.CharField(max_length=255, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    contact_number = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def has_unpaid_fees(self):
        return self.fee_set.filter(paid=False).exists()

    class Meta:
        ordering = ["last_name", "first_name"]


class Attendance(models.Model):
    STATUS_CHOICES = [("Present", "Present"), ("Absent", "Absent"), ("Late", "Late")]
    ATTENDANCE_TYPE_CHOICES = [("Meeting", "Meeting"), ("Cleaning", "Cleaning")]
    resident = models.ForeignKey(Resident, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    attendance_type = models.CharField(max_length=20, choices=ATTENDANCE_TYPE_CHOICES, default="Meeting")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["resident", "date", "attendance_type"],
                name="unique_attendance_per_resident_date_type",
            ),
        ]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["attendance_type"]),
            models.Index(fields=["resident", "date"]),
        ]



class Fee(models.Model):
    resident = models.ForeignKey(Resident, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now)
    date_paid = models.DateField(blank=True, null=True)
    fee_type = models.ForeignKey(FeeType, on_delete=models.PROTECT, related_name="fees")
    paid = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=0),
                name="fee_amount_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["paid"]),
            models.Index(fields=["date_paid"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["resident", "paid"]),
        ]

    def __str__(self):
        status = "Paid" if self.paid else "Unpaid"
        return f"{self.resident} - {self.amount} ({status})"


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name="payment_transactions")
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="payment_transactions",
    )
    gcash_reference = models.CharField(max_length=120)
    amount_sent = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    admin_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_payment_transactions",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_sent__gte=0),
                name="payment_amount_sent_non_negative",
            ),
            models.UniqueConstraint(
                fields=["fee"],
                condition=Q(status="pending"),
                name="unique_pending_payment_per_fee",
            ),
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["payment_date"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["fee", "status"]),
        ]

    def __str__(self):
        return f"{self.fee.resident} - {self.amount_sent} ({self.status})"


class PurokClearance(models.Model):
    resident = models.ForeignKey(Resident, on_delete=models.CASCADE)
    date_issued = models.DateField(default=timezone.now)
    clearance_type = models.ForeignKey(
        ClearanceType,
        on_delete=models.PROTECT,
        related_name="clearances",
    )
    remarks = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["date_issued"]),
            models.Index(fields=["resident", "date_issued"]),
        ]

    def can_issue(self):
        return not self.resident.has_unpaid_fees()

    def save(self, *args, **kwargs):
        if not self.can_issue():
            raise ValueError("Cannot issue clearance. Resident has unpaid fees.")
        super().save(*args, **kwargs)


class VerificationCode(models.Model):
    code = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(default=default_verification_expiry)
    max_uses = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_verification_codes",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_usable(self):
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return self.used_count < self.max_uses

    def mark_used(self):
        self.used_count += 1
        if self.used_count >= self.max_uses:
            self.is_active = False
        self.save(update_fields=["used_count", "is_active"])


class VerificationCodeRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("resolved", "Resolved"),
        ("sent", "Sent (Legacy)"),
        ("failed", "Failed (Legacy)"),
    ]
    REQUEST_TYPE_CHOICES = [
        ("login_code", "Login Code"),
        ("password_reset", "Password Reset"),
    ]
    name = models.CharField(max_length=150)
    email = models.EmailField()
    verification_code = models.ForeignKey(
        VerificationCode,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="requests",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default="login_code")
    requested_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["requested_at"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.email} ({self.status})"


class LoginActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_activities")
    login_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-login_at"]
        indexes = [
            models.Index(fields=["login_at"]),
            models.Index(fields=["user", "login_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} @ {self.login_at:%Y-%m-%d %H:%M:%S}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    contact_number = models.CharField(max_length=20, blank=True)
    profile_picture = models.FileField(upload_to="profile_pictures/", blank=True, null=True)

    def __str__(self):
        return self.user.username


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("approve_user", "Approve User"),
        ("create_code", "Create Login Code"),
        ("mark_fee_paid", "Mark Fee Paid"),
        ("issue_clearance", "Issue Clearance"),
    ]
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=50)
    target_id = models.PositiveIntegerField(blank=True, null=True)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} @ {self.created_at:%Y-%m-%d %H:%M:%S}"


class Notification(models.Model):
    LEVEL_CHOICES = [
        ("info", "Info"),
        ("success", "Success"),
        ("warning", "Warning"),
        ("error", "Error"),
    ]
    CATEGORY_CHOICES = [
        ("approval", "Approval"),
        ("verification", "Verification"),
        ("billing", "Billing"),
        ("clearance", "Clearance"),
        ("system", "System"),
    ]
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=150)
    message = models.TextField()
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="info")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="system")
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.title}"


def write_audit_log(action, description, actor=None, target=None, metadata=None):
    target_type = ""
    target_id = None
    if target is not None:
        target_type = target.__class__.__name__
        target_id = getattr(target, "pk", None)
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=description,
        metadata=metadata or {},
    )


def notify_user(user, title, message, *, level="info", category="system", link=""):
    if user is None:
        return None
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        level=level,
        category=category,
        link=link,
    )


def notify_staff(title, message, *, level="info", category="system", link=""):
    staff_users = User.objects.filter(is_staff=True, is_active=True).only("id")
    notifications = [
        Notification(
            user=user,
            title=title,
            message=message,
            level=level,
            category=category,
            link=link,
        )
        for user in staff_users
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)


def create_unique_verification_code(*, max_uses=1, attempts=10):
    for _ in range(attempts):
        code_value = f"PUROK-{secrets.token_hex(3).upper()}"
        try:
            return VerificationCode.objects.create(code=code_value, max_uses=max_uses)
        except IntegrityError:
            continue
    raise RuntimeError("Could not generate a unique verification code.")


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        Profile.objects.get_or_create(user=instance)

