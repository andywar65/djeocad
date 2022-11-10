# Generated by Django 4.1.1 on 2022-11-10 16:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("djeocad", "0002_alter_drawing_options_layer"),
    ]

    operations = [
        migrations.AddField(
            model_name="drawing",
            name="needs_refresh",
            field=models.BooleanField(
                default=True,
                editable=False,
                verbose_name="Refresh DXF file from layers",
            ),
        ),
        migrations.AlterField(
            model_name="drawing",
            name="title",
            field=models.CharField(
                help_text="Name of the drawing", max_length=50, verbose_name="Name"
            ),
        ),
    ]
