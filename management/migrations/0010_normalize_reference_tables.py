from django.db import migrations, models
import django.db.models.deletion


def populate_normalized_lookups(apps, schema_editor):
    Resident = apps.get_model("management", "Resident")
    Fee = apps.get_model("management", "Fee")
    PurokClearance = apps.get_model("management", "PurokClearance")
    VerificationCodeRequest = apps.get_model("management", "VerificationCodeRequest")
    Purok = apps.get_model("management", "Purok")
    FeeType = apps.get_model("management", "FeeType")
    ClearanceType = apps.get_model("management", "ClearanceType")

    for name in ["Monthly", "Annual", "Special", "Penalty"]:
        FeeType.objects.get_or_create(name=name)
    for name in ["Barangay", "Business"]:
        ClearanceType.objects.get_or_create(name=name)

    purok_map = {}
    for value in Resident.objects.order_by().values_list("purok", flat=True).distinct():
        purok_name = (value or "Unassigned").strip() or "Unassigned"
        purok_obj, _ = Purok.objects.get_or_create(name=purok_name)
        purok_map[purok_name] = purok_obj.pk

    for resident in Resident.objects.all().only("id", "purok"):
        purok_name = (resident.purok or "Unassigned").strip() or "Unassigned"
        resident.purok_lookup_id = purok_map[purok_name]
        resident.save(update_fields=["purok_lookup"])

    fee_type_map = {}
    for value in Fee.objects.order_by().values_list("fee_type", flat=True).distinct():
        fee_type_name = (value or "Special").strip() or "Special"
        fee_type_obj, _ = FeeType.objects.get_or_create(name=fee_type_name)
        fee_type_map[fee_type_name] = fee_type_obj.pk

    for fee in Fee.objects.all().only("id", "fee_type"):
        fee_type_name = (fee.fee_type or "Special").strip() or "Special"
        fee.fee_type_lookup_id = fee_type_map[fee_type_name]
        fee.save(update_fields=["fee_type_lookup"])

    clearance_type_map = {}
    for value in PurokClearance.objects.order_by().values_list("clearance_type", flat=True).distinct():
        clearance_type_name = (value or "Barangay").strip() or "Barangay"
        clearance_type_obj, _ = ClearanceType.objects.get_or_create(name=clearance_type_name)
        clearance_type_map[clearance_type_name] = clearance_type_obj.pk

    for clearance in PurokClearance.objects.all().only("id", "clearance_type"):
        clearance_type_name = (clearance.clearance_type or "Barangay").strip() or "Barangay"
        clearance.clearance_type_lookup_id = clearance_type_map[clearance_type_name]
        clearance.save(update_fields=["clearance_type_lookup"])

    for request in VerificationCodeRequest.objects.all().only("id", "notes"):
        if (request.notes or "").strip() == "password_reset":
            request.request_type = "password_reset"
        else:
            request.request_type = "login_code"
        request.save(update_fields=["request_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0009_alter_auditlog_action_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClearanceType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="FeeType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=20, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Purok",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="verificationcoderequest",
            name="request_type",
            field=models.CharField(choices=[("login_code", "Login Code"), ("password_reset", "Password Reset")], default="login_code", max_length=20),
        ),
        migrations.AddField(
            model_name="resident",
            name="purok_lookup",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="legacy_residents", to="management.purok"),
        ),
        migrations.AddField(
            model_name="fee",
            name="fee_type_lookup",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="legacy_fees", to="management.feetype"),
        ),
        migrations.AddField(
            model_name="purokclearance",
            name="clearance_type_lookup",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="legacy_clearances", to="management.clearancetype"),
        ),
        migrations.RunPython(populate_normalized_lookups, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name="resident",
            name="management__purok_15eef4_idx",
        ),
        migrations.RemoveField(model_name="resident", name="purok"),
        migrations.RemoveField(model_name="fee", name="fee_type"),
        migrations.RemoveField(model_name="purokclearance", name="clearance_type"),
        migrations.RenameField(model_name="resident", old_name="purok_lookup", new_name="purok"),
        migrations.RenameField(model_name="fee", old_name="fee_type_lookup", new_name="fee_type"),
        migrations.RenameField(model_name="purokclearance", old_name="clearance_type_lookup", new_name="clearance_type"),
        migrations.AlterField(
            model_name="resident",
            name="purok",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="residents", to="management.purok"),
        ),
        migrations.AlterField(
            model_name="fee",
            name="fee_type",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fees", to="management.feetype"),
        ),
        migrations.AlterField(
            model_name="purokclearance",
            name="clearance_type",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="clearances", to="management.clearancetype"),
        ),
    ]

