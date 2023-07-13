# Generated by Django 4.1.1 on 2023-01-23 12:27

import djgeojson.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("djeocad", "0015_alter_layer_options_layer_linetype"),
    ]

    operations = [
        migrations.AddField(
            model_name="drawing",
            name="designx",
            field=models.FloatField(default=0, verbose_name="Design point X..."),
        ),
        migrations.AddField(
            model_name="drawing",
            name="designy",
            field=models.FloatField(default=0, verbose_name="...Y"),
        ),
        migrations.AlterField(
            model_name="insertion",
            name="geom",
            field=djgeojson.fields.GeometryCollectionField(
                default=dict, verbose_name="Entities"
            ),
        ),
    ]