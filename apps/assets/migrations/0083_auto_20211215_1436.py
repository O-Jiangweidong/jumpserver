# Generated by Django 3.1.13 on 2021-12-15 06:36

from django.db import migrations, models

OLD_ACTION_ALLOW = 1
NEW_ACTION_ALLOW = 9


def migrate_action(apps, schema_editor):
    model = apps.get_model("assets", "CommandFilterRule")
    model.objects.filter(action=OLD_ACTION_ALLOW).update(action=NEW_ACTION_ALLOW)


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0082_auto_20211209_1440'),
    ]

    operations = [
        migrations.RunPython(migrate_action),
        migrations.AlterField(
            model_name='commandfilterrule',
            name='action',
            field=models.IntegerField(choices=[(0, 'Deny'), (9, 'Allow'), (2, 'Reconfirm')], default=0, verbose_name='Action'),
        ),
    ]