# Generated by Django 4.1.13 on 2024-06-27 01:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('terminal', '0069_endpoint_sqlserver_port_alter_appprovider_apps_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='terminal',
            name='type',
            field=models.CharField(choices=[('koko', 'KoKo'), ('guacamole', 'Guacamole'), ('omnidb', 'OmniDB'), ('xrdp', 'Xrdp'), ('lion', 'Lion'), ('core', 'Core'), ('celery', 'Celery'), ('magnus', 'Magnus'), ('razor', 'Razor'), ('tinker', 'Tinker'), ('video_worker', 'Video Worker'), ('chen', 'Chen'), ('kael', 'Kael'), ('panda', 'Panda'), ('behemoth', 'Behemoth')], default='koko', max_length=64, verbose_name='type'),
        ),
    ]
