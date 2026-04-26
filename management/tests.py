from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import (
    Attendance,
    AuditLog,
    ClearanceType,
    Fee,
    PaymentTransaction,
    FeeType,
    Purok,
    PurokClearance,
    Resident,
    VerificationCode,
    VerificationCodeRequest,
)


class RegistrationAndResetFlowTests(TestCase):
    def test_register_consumes_code_and_creates_inactive_user(self):
        code = VerificationCode.objects.create(code="PUROK-ABC123", max_uses=1)
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser1",
                "email": "newuser1@example.com",
                "verification_code": code.code,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="newuser1")
        self.assertFalse(user.is_active)
        code.refresh_from_db()
        self.assertEqual(code.used_count, 1)
        self.assertFalse(code.is_active)

    def test_password_change_accepts_old_password_with_accidental_spaces(self):
        user = User.objects.create_user(
            username="pwchangeuser",
            email="pwchange@example.com",
            password="OldPass123!",
            is_active=True,
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("password-change"),
            {
                "old_password": "  OldPass123!  ",
                "new_password1": "NewStrongPass123!",
                "new_password2": "NewStrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("password-change-done"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass123!"))

    def test_forgot_password_request_creates_pending_reset_request(self):
        user = User.objects.create_user(
            username="resetme",
            email="resetme@example.com",
            password="OldPass123!",
            is_active=True,
        )
        response = self.client.post(
            reverse("forgot-password-request"),
            {"username": user.username, "email": user.email},
        )
        self.assertRedirects(response, reverse("password-reset-with-code"))
        req = VerificationCodeRequest.objects.get(email=user.email, request_type="password_reset")
        self.assertEqual(req.status, "pending")

    def test_password_reset_with_code_updates_password_and_consumes_code(self):
        user = User.objects.create_user(
            username="changepass",
            email="changepass@example.com",
            password="OldPass123!",
            is_active=True,
        )
        code = VerificationCode.objects.create(code="PUROK-RESET1", max_uses=1)
        response = self.client.post(
            reverse("password-reset-with-code"),
            {
                "username": user.username,
                "email": user.email,
                "login_code": code.code,
                "new_password1": "NewStrongPass123!",
                "new_password2": "NewStrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("login"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass123!"))
        code.refresh_from_db()
        self.assertEqual(code.used_count, 1)
        self.assertFalse(code.is_active)


class AdminCriticalActionsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="adminuser",
            email="admin@example.com",
            password="AdminPass123!",
            is_staff=True,
            is_active=True,
        )
        self.client.force_login(self.staff)

    def test_admin_approve_user_action_and_audit_log(self):
        target = User.objects.create_user(
            username="pendinguser",
            email="pending@example.com",
            password="PendingPass123!",
            is_staff=False,
            is_active=False,
        )
        response = self.client.post(
            reverse("pending-account-action", kwargs={"user_id": target.pk}),
            {"action": "approve"},
        )
        self.assertRedirects(response, reverse("pending-accounts"))
        target.refresh_from_db()
        self.assertTrue(target.is_active)
        self.assertTrue(
            AuditLog.objects.filter(
                action="approve_user",
                target_type="User",
                target_id=target.pk,
            ).exists()
        )

    def test_mark_fee_paid_updates_fee_and_writes_audit_log(self):
        resident_user = User.objects.create_user(
            username="resident1",
            email="resident1@example.com",
            password="ResidentPass123!",
            is_active=True,
        )
        purok = Purok.objects.create(name="Purok 1")
        fee_type, _ = FeeType.objects.get_or_create(name="Monthly")
        resident = Resident.objects.create(
            user=resident_user,
            first_name="Resident",
            last_name="One",
            purok=purok,
            date_of_birth=date(2000, 1, 1),
            contact_number="09123456789",
        )
        fee = Fee.objects.create(
            resident=resident,
            amount=100,
            fee_type=fee_type,
            paid=False,
        )
        response = self.client.post(reverse("fee-mark-paid", kwargs={"pk": fee.pk}))
        self.assertRedirects(response, reverse("fee-list"))
        fee.refresh_from_db()
        self.assertTrue(fee.paid)
        self.assertIsNotNone(fee.date_paid)
        self.assertTrue(
            AuditLog.objects.filter(
                action="mark_fee_paid",
                target_type="Fee",
                target_id=fee.pk,
            ).exists()
        )


class AttendancePenaltyTypeTests(TestCase):
    def test_absent_cleaning_attendance_creates_cleaning_penalty_fee(self):
        from .forms import AttendanceForm
        from .services import attendance_service

        user = User.objects.create_user(
            username="attendanceuser",
            email="attendance@example.com",
            password="ResidentPass123!",
            is_active=True,
        )
        purok = Purok.objects.create(name="Purok Attendance")
        resident = Resident.objects.create(
            user=user,
            first_name="Clean",
            last_name="Resident",
            purok=purok,
            date_of_birth=date(2000, 1, 1),
            contact_number="09123456789",
        )
        form = AttendanceForm(
            data={
                "resident": resident.pk,
                "attendance_type": "Cleaning",
                "date": "2026-04-17",
                "status": "Absent",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        attendance, fee = attendance_service.create_attendance(form)
        self.assertEqual(attendance.attendance_type, "Cleaning")
        self.assertEqual(fee.fee_type.name, "Penalty for Missed Cleaning")
        self.assertEqual(fee.amount, 100)



class ManualGcashPaymentFlowTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staffpay",
            email="staffpay@example.com",
            password="StaffPass123!",
            is_staff=True,
            is_active=True,
        )
        self.user = User.objects.create_user(
            username="residentpay",
            email="residentpay@example.com",
            password="ResidentPass123!",
            is_active=True,
        )
        self.purok = Purok.objects.create(name="Purok Pay")
        self.fee_type, _ = FeeType.objects.get_or_create(name="Monthly")
        self.resident = Resident.objects.create(
            user=self.user,
            first_name="Rina",
            last_name="Pay",
            purok=self.purok,
            date_of_birth=date(2000, 5, 5),
            contact_number="09123456789",
        )
        self.fee = Fee.objects.create(
            resident=self.resident,
            amount=200,
            fee_type=self.fee_type,
            paid=False,
        )

    def test_resident_can_submit_manual_gcash_payment_transaction(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("fee-submit-payment", kwargs={"pk": self.fee.pk}),
            {
                f"fee-{self.fee.pk}-gcash_reference": "GCASH-123456",
                f"fee-{self.fee.pk}-amount_sent": "200.00",
                f"fee-{self.fee.pk}-payment_date": "2026-04-17",
                f"fee-{self.fee.pk}-notes": "Paid via GCash",
            },
        )
        self.assertRedirects(response, reverse("fee-list"))
        payment = PaymentTransaction.objects.get(fee=self.fee)
        self.assertEqual(payment.status, "pending")
        self.assertEqual(payment.submitted_by, self.user)
        self.assertEqual(payment.gcash_reference, "GCASH-123456")

    def test_staff_can_approve_manual_gcash_payment_transaction(self):
        payment = PaymentTransaction.objects.create(
            fee=self.fee,
            submitted_by=self.user,
            gcash_reference="GCASH-654321",
            amount_sent="200.00",
            payment_date=date(2026, 4, 17),
            status="pending",
        )
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("fee-payment-action", kwargs={"tx_id": payment.pk, "action": "approve"})
        )
        self.assertRedirects(response, reverse("fee-list"))
        payment.refresh_from_db()
        self.fee.refresh_from_db()
        self.assertEqual(payment.status, "approved")
        self.assertTrue(self.fee.paid)
        self.assertIsNotNone(self.fee.date_paid)

    def test_user_can_view_own_payment_information_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("fee-view-payment", kwargs={"pk": self.fee.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment Information")

    def test_user_cannot_view_other_resident_payment_information_page(self):
        other_user = User.objects.create_user(
            username="otherpayuser",
            email="otherpay@example.com",
            password="OtherPass123!",
            is_active=True,
        )
        other_resident = Resident.objects.create(
            user=other_user,
            first_name="Other",
            last_name="Resident",
            purok=self.purok,
            date_of_birth=date(2001, 1, 1),
            contact_number="09999999999",
        )
        other_fee = Fee.objects.create(
            resident=other_resident,
            amount=150,
            fee_type=self.fee_type,
            paid=False,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("fee-view-payment", kwargs={"pk": other_fee.pk}))
        self.assertRedirects(response, reverse("fee-list"))




class ApiPermissionTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staffapi",
            email="staff@example.com",
            password="StaffPass123!",
            is_staff=True,
            is_active=True,
        )
        self.user = User.objects.create_user(
            username="residentapi",
            email="residentapi@example.com",
            password="ResidentPass123!",
            is_active=True,
        )
        self.other_user = User.objects.create_user(
            username="otherresident",
            email="other@example.com",
            password="ResidentPass123!",
            is_active=True,
        )
        self.purok = Purok.objects.create(name="Purok 2")
        self.fee_type, _ = FeeType.objects.get_or_create(name="Monthly")
        self.clearance_type, _ = ClearanceType.objects.get_or_create(name="Barangay")
        self.resident = Resident.objects.create(
            user=self.user,
            first_name="Anna",
            last_name="Resident",
            purok=self.purok,
            date_of_birth=date(2001, 1, 1),
            contact_number="09111111111",
        )
        self.other_resident = Resident.objects.create(
            user=self.other_user,
            first_name="Ben",
            last_name="Resident",
            purok=self.purok,
            date_of_birth=date(2002, 2, 2),
            contact_number="09222222222",
        )
        self.fee = Fee.objects.create(
            resident=self.resident,
            amount=150,
            fee_type=self.fee_type,
            paid=True,
        )
        self.other_fee = Fee.objects.create(
            resident=self.other_resident,
            amount=175,
            fee_type=self.fee_type,
            paid=False,
        )
        self.clearance = PurokClearance.objects.create(
            resident=self.resident,
            clearance_type=self.clearance_type,
            remarks="Issued",
        )

    def test_dashboard_api_requires_login(self):
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 403)

    def test_staff_can_list_all_residents_via_api(self):
        self.client.force_login(self.staff)
        response = self.client.get("/api/residents/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(len(response.json()["results"]), 2)

    def test_resident_api_is_limited_to_own_records(self):
        self.client.force_login(self.user)
        fee_response = self.client.get("/api/fees/")
        self.assertEqual(fee_response.status_code, 200)
        self.assertEqual(fee_response.json()["count"], 1)
        self.assertEqual(fee_response.json()["results"][0]["resident"], self.resident.pk)

    def test_resident_cannot_fetch_other_resident_detail(self):
        self.client.force_login(self.user)
        response = self.client.get(f"/api/residents/{self.other_resident.pk}/")
        self.assertEqual(response.status_code, 404)


class WebPermissionAndExportSafetyTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staffedge",
            email="staffedge@example.com",
            password="StaffPass123!",
            is_staff=True,
            is_active=True,
        )
        self.user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="RegularPass123!",
            is_active=True,
        )

    def test_attendance_add_requires_login(self):
        response = self.client.get(reverse("attendance-add"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_attendance_add_redirects_non_staff(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("attendance-add"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_audit_export_escapes_html_content(self):
        self.client.force_login(self.staff)
        AuditLog.objects.create(
            actor=self.staff,
            action="approve_user",
            target_type="User",
            target_id=self.staff.pk,
            description="<script>alert('xss')</script>",
        )
        response = self.client.get(reverse("audit-logs-export-word"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("&lt;script&gt;alert", content)
        self.assertNotIn("<script>alert", content)

    def test_resident_export_escapes_html_content(self):
        self.client.force_login(self.staff)
        purok = Purok.objects.create(name="Purok <b>X</b>")
        resident_user = User.objects.create_user(
            username="resident_export_user",
            email="resident_export@example.com",
            password="ResidentPass123!",
            is_active=True,
        )
        Resident.objects.create(
            user=resident_user,
            first_name="<script>alert('x')</script>",
            last_name="Resident",
            purok=purok,
            date_of_birth=date(2000, 1, 1),
            contact_number="09123456789",
        )
        response = self.client.get(reverse("resident-export-word"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("&lt;script&gt;alert", content)
        self.assertNotIn("<script>alert", content)


class DataConstraintTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="constraints",
            email="constraints@example.com",
            password="ConstraintPass123!",
            is_active=True,
        )
        self.purok = Purok.objects.create(name="Purok Constraint")
        self.resident = Resident.objects.create(
            user=self.user,
            first_name="Con",
            last_name="Strain",
            purok=self.purok,
            date_of_birth=date(2000, 1, 1),
            contact_number="09123456789",
        )
        self.fee_type = FeeType.objects.create(name="Constraint Fee")
        self.attendance = Attendance.objects.create(
            resident=self.resident,
            attendance_type="Meeting",
            date=date(2026, 4, 20),
            status="Present",
        )

    def test_attendance_unique_constraint_blocks_duplicates(self):
        with self.assertRaises(IntegrityError):
            Attendance.objects.create(
                resident=self.resident,
                attendance_type="Meeting",
                date=self.attendance.date,
                status="Absent",
            )

    def test_only_one_pending_payment_transaction_per_fee(self):
        fee = Fee.objects.create(
            resident=self.resident,
            amount=Decimal("150.00"),
            fee_type=self.fee_type,
            paid=False,
        )
        PaymentTransaction.objects.create(
            fee=fee,
            submitted_by=self.user,
            gcash_reference="REF-ONE",
            amount_sent=Decimal("150.00"),
            status="pending",
        )
        with self.assertRaises(IntegrityError):
            PaymentTransaction.objects.create(
                fee=fee,
                submitted_by=self.user,
                gcash_reference="REF-TWO",
                amount_sent=Decimal("150.00"),
                status="pending",
            )

