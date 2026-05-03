from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Case, IntegerField, Value, When
from django.utils.translation import gettext_lazy as _

from .models import (
    Attendance,
    Fee,
    PaymentTransaction,
    FeeType,
    Purok,
    Profile,
    PurokClearance,
    Resident,
    VerificationCode,
)

STANDARD_PUROK_NAMES = [f"purok-{number}" for number in range(1, 16)]


def _ensure_standard_puroks():
    for purok_name in STANDARD_PUROK_NAMES:
        Purok.objects.get_or_create(name=purok_name)
    ordering = Case(
        *[
            When(name=purok_name, then=Value(position))
            for position, purok_name in enumerate(STANDARD_PUROK_NAMES, start=1)
        ],
        output_field=IntegerField(),
    )
    return Purok.objects.filter(name__in=STANDARD_PUROK_NAMES).order_by(ordering)


class ResidentForm(forms.ModelForm):
    class Meta:
        model = Resident
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "household_number",
            "gender",
            "purok",
            "sitio",
            "barangay",
            "city",
            "province",
            "date_of_birth",
            "place_of_birth",
            "address",
            "contact_number",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purok"].queryset = _ensure_standard_puroks()

class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = "__all__"
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attendance_type"].label = "Attendance Type"
        self.fields["status"].choices = [("Present", "Present"), ("Absent", "Absent")]


class FeeForm(forms.ModelForm):
    class Meta:
        model = Fee
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_fee_types = FeeType.objects.filter(
            name__in=["Penalty for Missed Meeting", "Penalty for Missed Cleaning"]
        ).order_by("name")
        self.fields["fee_type"].queryset = allowed_fee_types
        self.fields["amount"].initial = 100
        self.fields["amount"].help_text = "Penalty fees are fixed at 100 pesos."

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount != 100:
            raise forms.ValidationError("Penalty fees must be exactly 100 pesos.")
        return amount


class PaymentTransactionForm(forms.ModelForm):
    class Meta:
        model = PaymentTransaction
        fields = ["gcash_reference", "amount_sent", "payment_date", "notes"]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional note for the admin"}),
        }

    def clean_amount_sent(self):
        amount = self.cleaned_data["amount_sent"]
        if amount <= 0:
            raise forms.ValidationError("Amount sent must be greater than zero.")
        return amount


class ClearanceForm(forms.ModelForm):
    class Meta:
        model = PurokClearance
        fields = ["resident", "date_issued", "remarks"]


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    verification_code = forms.CharField(max_length=64, required=True, label="Login code")

    class Meta:
        model = User
        fields = ["username", "email", "verification_code", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._verification_code_obj = None

    def clean_verification_code(self):
        code = self.cleaned_data["verification_code"].strip()
        verification = VerificationCode.objects.filter(code=code).first()
        if verification is None:
            raise forms.ValidationError("Invalid login code.")
        if not verification.is_usable():
            raise forms.ValidationError("This login code is expired or already used.")
        self._verification_code_obj = verification
        return code

    def get_verification_code(self):
        return self._verification_code_obj


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email"]


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["profile_picture"]
        widgets = {
            "profile_picture": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }


class VerificationCodeRequestForm(forms.Form):
    name = forms.CharField(max_length=150)
    email = forms.EmailField()


class UserResidentInfoForm(forms.ModelForm):
    class Meta:
        model = Resident
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "household_number",
            "gender",
            "purok",
            "sitio",
            "barangay",
            "city",
            "province",
            "age",
            "date_of_birth",
            "place_of_birth",
            "address",
            "contact_number",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purok"].queryset = _ensure_standard_puroks()


class ForgotPasswordRequestForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = None

    def clean(self):
        cleaned_data = super().clean()
        username = (cleaned_data.get("username") or "").strip()
        email = (cleaned_data.get("email") or "").strip().lower()
        if not username or not email:
            return cleaned_data

        user = User.objects.filter(username__iexact=username).first()
        if user is None:
            raise forms.ValidationError("No account found with that username.")
        if (user.email or "").strip().lower() != email:
            raise forms.ValidationError("Email does not match that username.")

        self._user = user
        return cleaned_data

    def get_user(self):
        return self._user


class PasswordResetWithCodeForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    login_code = forms.CharField(max_length=64, label="Login code")
    new_password1 = forms.CharField(label="New password", widget=forms.PasswordInput)
    new_password2 = forms.CharField(label="Confirm new password", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = None
        self._verification_code = None

    def clean_login_code(self):
        code = (self.cleaned_data.get("login_code") or "").strip()
        verification = VerificationCode.objects.filter(code=code).first()
        if verification is None:
            raise forms.ValidationError("Invalid login code.")
        if not verification.is_usable():
            raise forms.ValidationError("This login code is expired or already used.")
        self._verification_code = verification
        return code

    def clean(self):
        cleaned_data = super().clean()
        username = (cleaned_data.get("username") or "").strip()
        email = (cleaned_data.get("email") or "").strip().lower()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")

        if not username or not email:
            return cleaned_data

        user = User.objects.filter(username__iexact=username).first()
        if user is None:
            raise forms.ValidationError("No account found with that username.")
        if (user.email or "").strip().lower() != email:
            raise forms.ValidationError("Email does not match that username.")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields didn't match.")
        if password1:
            password_validation.validate_password(password1, user=user)

        self._user = user
        return cleaned_data

    def get_user(self):
        return self._user

    def get_verification_code(self):
        return self._verification_code


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prevent browser/password-manager autofill from pre-populating fields.
        self.fields["old_password"].widget.attrs.update({"autocomplete": "off"})
        self.fields["new_password1"].widget.attrs.update({"autocomplete": "new-password"})
        self.fields["new_password2"].widget.attrs.update({"autocomplete": "new-password"})

    def clean_old_password(self):
        """
        Accept accidental leading/trailing spaces in the old-password input.
        Exact password matching is still checked first.
        """
        old_password = self.cleaned_data.get("old_password")
        if self.user.check_password(old_password):
            return old_password

        normalized_password = (old_password or "").strip()
        if normalized_password and normalized_password != old_password and self.user.check_password(normalized_password):
            return normalized_password

        raise ValidationError(
            self.error_messages["password_incorrect"],
            code="password_incorrect",
            params={"verbose_name": _("old password")},
        )

