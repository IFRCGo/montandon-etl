# Generated by Django 5.1.3 on 2024-11-21 11:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('etl', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='extractiondata',
            name='source_validation_fail_reason',
            field=models.TextField(blank=True, verbose_name='validation status fail reason'),
        ),
        migrations.AddField(
            model_name='extractiondata',
            name='source_validation_status',
            field=models.IntegerField(choices=[(1, 'Success'), (2, 'Failed')], default=1, verbose_name='validation status'),
            preserve_default=False,
        ),
    ]
