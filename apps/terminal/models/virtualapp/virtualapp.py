import os
import random
import shutil

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db import models
from django.utils._os import safe_join
from django.utils.translation import gettext_lazy as _
from rest_framework.serializers import ValidationError

from common.db.models import JMSBaseModel
from common.utils import lazyproperty, get_logger
from common.utils.yml import yaml_load_with_i18n

__all__ = ['VirtualApp', 'VirtualAppPublication']


logger = get_logger(__name__)


class VirtualApp(JMSBaseModel):
    name = models.SlugField(max_length=128, verbose_name=_('Name'), unique=True)
    display_name = models.CharField(max_length=128, verbose_name=_('Display name'))
    version = models.CharField(max_length=16, verbose_name=_('Version'))
    author = models.CharField(max_length=128, verbose_name=_('Author'))
    is_active = models.BooleanField(default=True, verbose_name=_('Is active'))
    protocols = models.JSONField(default=list, verbose_name=_('Protocol'))
    image_name = models.CharField(max_length=128, verbose_name=_('Image name'))
    image_protocol = models.CharField(max_length=16, default='vnc', verbose_name=_('Image protocol'))
    image_port = models.IntegerField(default=5900, verbose_name=_('Image port'))
    comment = models.TextField(default='', blank=True, verbose_name=_('Comment'))
    tags = models.JSONField(default=list, verbose_name=_('Tags'))
    providers = models.ManyToManyField(
        through_fields=('app', 'provider',), through='VirtualAppPublication',
        to='AppProvider', verbose_name=_('Providers')
    )

    class Meta:
        verbose_name = _('Virtual app')

    def __str__(self):
        return self.name

    @property
    def path(self):
        return default_storage.path('virtual_apps/{}'.format(self.name))

    @lazyproperty
    def readme(self) -> str:
        readme_file = os.path.join(self.path, 'README.md')
        if os.path.isfile(readme_file):
            with open(readme_file, 'r') as f:
                return f.read()
        return ''

    @property
    def icon(self) -> str:
        path = os.path.join(self.path, 'icon.png')
        if not os.path.exists(path):
            return None
        return os.path.join(settings.MEDIA_URL, 'virtual_apps', self.name, 'icon.png')

    @staticmethod
    def validate_pkg(d):
        files = ['manifest.yml', 'icon.png', ]
        for name in files:
            path = safe_join(d, name)
            if not os.path.exists(path):
                raise ValidationError({'error': _('Applet pkg not valid, Missing file {}').format(name)})

        with open(safe_join(d, 'manifest.yml'), encoding='utf8') as f:
            manifest = yaml_load_with_i18n(f)

        if not manifest.get('name', ''):
            raise ValidationError({'error': 'Missing name in manifest.yml'})
        return manifest

    @classmethod
    def install_from_dir(cls, path):
        from terminal.serializers import VirtualAppSerializer
        manifest = cls.validate_pkg(path)
        name = manifest['name']
        instance = cls.objects.filter(name=name).first()
        serializer = VirtualAppSerializer(instance=instance, data=manifest)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        pkg_path = default_storage.path('virtual_apps/{}'.format(name))
        if os.path.exists(pkg_path):
            shutil.rmtree(pkg_path)
        shutil.copytree(path, pkg_path)
        return instance, serializer

    host_prefer_key_tpl = 'virtual_host_prefer_{}'
    connect_token_map_host = 'connect_token_map_host_{}'

    def select_panda_host(self, token_id, user, asset):
        hosts = self.providers.all()
        only_label_values = asset.get_labels().filter(
            name__in=['VirtualAppletHostOnly', '仅虚拟发布机']
        ).values_list('value', flat=True)
        if only_label_values:
            host_matched = [host for host in hosts if host.name in only_label_values]
            if host_matched:
                host = host_matched[0]
                cache.set(self.connect_token_map_host.format(token_id), str(host.terminal.remote_addr))
                return host
            else:
                logger.info("No host for only virtual app: {}".format(self.name))
                return None

        hosts = [host for host in hosts if host.load != 'offline']
        if not hosts:
            logger.info("No online host for virtual app: {}".format(self.name))
            return None

        spec_label_values = asset.get_labels().filter(
            name__in=['VirtualAppletHost', '虚拟发布机']
        ).values_list('value', flat=True)
        host_matched = [host for host in hosts if host.name in spec_label_values]
        if host_matched:
            host = random.choice(host_matched)
            cache.set(self.connect_token_map_host.format(token_id), str(host.terminal.remote_addr))
            return host

        prefer_key = self.host_prefer_key_tpl.format(user.id)
        prefer_host_id = cache.get(prefer_key, None)
        pref_host = [host for host in hosts if host.id == prefer_host_id]

        if pref_host:
            host = pref_host[0]
        else:
            host = hosts[0]
            cache.set(prefer_key, str(host.id), timeout=None)

        cache.set(self.connect_token_map_host.format(token_id), str(host.terminal.remote_addr))
        return host

    @classmethod
    def get_host_from_token(cls, token_id):
        return cache.get(cls.connect_token_map_host.format(token_id))


class VirtualAppPublication(JMSBaseModel):
    provider = models.ForeignKey(
        'AppProvider', on_delete=models.CASCADE, related_name='publications', verbose_name=_('App Provider')
    )
    app = models.ForeignKey(
        'VirtualApp', on_delete=models.CASCADE, related_name='publications', verbose_name=_('Virtual app')
    )
    status = models.CharField(max_length=16, default='pending', verbose_name=_('Status'))

    class Meta:
        verbose_name = _('Virtual app publication')
        unique_together = ('provider', 'app')
