from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0024_alter_feetype_name_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="resident",
            name="barangay",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="resident",
            name="city",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="resident",
            name="province",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
