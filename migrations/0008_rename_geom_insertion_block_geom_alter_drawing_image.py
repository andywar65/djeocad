# Generated by Django 4.1.1 on 2022-11-24 16:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("djeocad", "0007_insertion_geom"),
    ]

    operations = [
        migrations.RenameField(
            model_name="insertion",
            old_name="geom",
            new_name="block_geom",
        ),
        migrations.AlterField(
            model_name="drawing",
            name="image",
            field=models.ImageField(
                blank=True,
                max_length=200,
                null=True,
                upload_to="uploads/images/drawing/",
                verbose_name="Image",
            ),
        ),
    ]
