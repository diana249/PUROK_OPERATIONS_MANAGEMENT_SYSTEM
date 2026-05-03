from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0026_resident_middle_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="resident",
            name="sitio",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
