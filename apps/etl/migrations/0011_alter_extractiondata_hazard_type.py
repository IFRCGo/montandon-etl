# Generated by Django 5.1.3 on 2024-12-31 05:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('etl', '0010_alter_gdacstransformation_item_type_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='extractiondata',
            name='hazard_type',
            field=models.CharField(blank=True, choices=[('EQ', 'Earthquake'), ('FL', 'Flood'), ('TC', 'Cyclone'), ('EP', 'Epidemic'), ('FI', 'Food Insecurity'), ('SS', 'Storm Surge'), ('DR', 'Drought'), ('TS', 'Tsunami'), ('CD', 'Cyclonic Wind'), ('WF', 'WildFire'), ('VO', 'Volcano')], max_length=100, verbose_name='hazard type'),
        ),
    ]