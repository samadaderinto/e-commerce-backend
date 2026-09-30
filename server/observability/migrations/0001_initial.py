from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(
        name="LogEntry",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("occurred_at", models.DateTimeField(db_index=True)),
            ("level", models.CharField(db_index=True, max_length=20)),
            ("category", models.CharField(db_index=True, max_length=80)),
            ("logger", models.CharField(blank=True, default="", max_length=160)),
            ("message", models.TextField()),
            ("route", models.CharField(blank=True, default="", max_length=255)),
            ("method", models.CharField(blank=True, default="", max_length=12)),
            ("status_code", models.PositiveSmallIntegerField(blank=True, null=True)),
            ("request_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
            ("trace_id", models.CharField(blank=True, default="", max_length=64)),
            ("user_id", models.CharField(blank=True, default="", max_length=64)),
            ("service", models.CharField(db_index=True, default="api", max_length=80)),
            ("metadata", models.JSONField(blank=True, default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ],
        options={"ordering": ("-occurred_at", "-pk")},
    ), migrations.AddIndex(model_name="logentry", index=models.Index(fields=["category", "occurred_at"], name="observabili_categor_a7780a_idx")), migrations.AddIndex(model_name="logentry", index=models.Index(fields=["level", "occurred_at"], name="observabili_level_842ed6_idx"))]
