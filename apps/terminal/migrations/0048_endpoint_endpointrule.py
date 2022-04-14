# Generated by Django 3.1.14 on 2022-04-12 07:39

import common.fields.model
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.conf import settings


def migrate_endpoints(apps, schema_editor):
    endpoint_data = {
        'id': '00000000-0000-0000-0000-000000000001',
        'name': 'Default',
        'host': '',
        'https_port': 0,
        'http_port': 0,
        'created_by': 'System'
    }

    if settings.XRDP_ENABLED:
        xrdp_addr = settings.TERMINAL_RDP_ADDR
        if ':' in xrdp_addr:
            hostname, port = xrdp_addr.strip().split(':')
        else:
            hostname, port = xrdp_addr, 3389
        endpoint_data.update({
            'host': '' if hostname.strip() in ['localhost', '127.0.0.1'] else hostname.strip(),
            'rdp_port': int(port)
        })
    Endpoint = apps.get_model("terminal", "Endpoint")
    Endpoint.objects.create(**endpoint_data)


class Migration(migrations.Migration):

    dependencies = [
        ('terminal', '0047_auto_20220302_1951'),
    ]

    operations = [
        migrations.CreateModel(
            name='Endpoint',
            fields=[
                ('created_by', models.CharField(blank=True, max_length=32, null=True, verbose_name='Created by')),
                ('updated_by', models.CharField(blank=True, max_length=32, null=True, verbose_name='Updated by')),
                ('date_created', models.DateTimeField(auto_now_add=True, null=True, verbose_name='Date created')),
                ('date_updated', models.DateTimeField(auto_now=True, verbose_name='Date updated')),
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=128, unique=True, blank=True, verbose_name='Name')),
                ('host', models.CharField(max_length=256, verbose_name='Host')),
                ('https_port', common.fields.model.PortField(default=443, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(65535)], verbose_name='HTTPS Port')),
                ('http_port', common.fields.model.PortField(default=80, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(65535)], verbose_name='HTTP Port')),
                ('ssh_port', common.fields.model.PortField(default=2222, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(65535)], verbose_name='SSH Port')),
                ('rdp_port', common.fields.model.PortField(default=3389, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(65535)], verbose_name='RDP Port')),
                ('mysql_port', common.fields.model.PortField(default=33060, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(65535)], verbose_name='MySQL Port')),
                ('mariadb_port', common.fields.model.PortField(default=33061, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(65535)], verbose_name='MariaDB Port')),
                ('postgresql_port', common.fields.model.PortField(default=54320, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(65535)], verbose_name='PostgreSQL Port')),
                ('comment', models.TextField(blank=True, default='', verbose_name='Comment')),
            ],
            options={
                'verbose_name': 'Endpoint',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='EndpointRule',
            fields=[
                ('created_by', models.CharField(blank=True, max_length=32, null=True, verbose_name='Created by')),
                ('updated_by', models.CharField(blank=True, max_length=32, null=True, verbose_name='Updated by')),
                ('date_created', models.DateTimeField(auto_now_add=True, null=True, verbose_name='Date created')),
                ('date_updated', models.DateTimeField(auto_now=True, verbose_name='Date updated')),
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=128, unique=True, verbose_name='Name')),
                ('ip_group', models.JSONField(default=list, verbose_name='IP group')),
                ('priority', models.IntegerField(help_text='1-100, the lower the value will be match first', unique=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)], verbose_name='Priority')),
                ('comment', models.TextField(blank=True, default='', verbose_name='Comment')),
                ('endpoint', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rules', to='terminal.endpoint', verbose_name='Endpoint')),
            ],
            options={
                'verbose_name': 'Endpoint rule',
                'ordering': ('priority', 'name'),
            },
        ),
        migrations.RunPython(migrate_endpoints),
    ]