from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0027_resident_sitio"),
    ]

    operations = [
        migrations.AddField(
            model_name="purokclearance",
            name="resident_downloaded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
