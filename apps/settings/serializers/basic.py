import os
import shelve

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from orgs.models import Organization
from jumpserver.const import PROJECT_DIR


class BasicSettingSerializer(serializers.Serializer):
    PREFIX_TITLE = _('Basic')

    SITE_URL = serializers.URLField(
        required=True, label=_("Site url"),
        help_text=_(
            'External URL, email links or other system callbacks are used to access it, '
            'eg: http://dev.toecsec.org:8080'
        )
    )
    USER_GUIDE_URL = serializers.URLField(
        required=False, allow_blank=True, allow_null=True, label=_("User guide url"),
        help_text=_('User first login update profile done redirect to it')
    )
    GLOBAL_ORG_DISPLAY_NAME = serializers.CharField(
        required=False, max_length=1024, allow_blank=True, allow_null=True, label=_("Global organization name"),
        help_text=_('The name of global organization to display')
    )
    HELP_DOCUMENT_URL = serializers.URLField(
        required=False, allow_blank=True, allow_null=True, label=_("Help Docs URL"),
        help_text=_('default: http://docs.jumpserver.org')
    )
    HELP_SUPPORT_URL = serializers.URLField(
        required=False, allow_blank=True, allow_null=True, label=_("Help Support URL"),
        help_text=_('default: http://www.jumpserver.org/support/')
    )
    SERVICE_IP = serializers.IPAddressField(
        required=False, max_length=16, allow_blank=True, allow_null=True, label=_("Service IP")
    )
    SERVICE_GATEWAY = serializers.IPAddressField(
        required=False, max_length=16, allow_blank=True, allow_null=True, label=_("Service gateway")
    )
    SERVICE_SUBNET_MASK = serializers.IPAddressField(
        required=False, max_length=16, allow_blank=True, allow_null=True, label=_("Service subnet mask"),
    )
    VPN_RPC_ADDRESS = serializers.CharField(required=False, max_length=128, allow_blank=True)

    @staticmethod
    def validate_SITE_URL(s):
        if not s:
            return 'http://127.0.0.1'
        return s.strip('/')

    @staticmethod
    def _save_net_config_to_file(attrs):
        config_file = os.path.join(PROJECT_DIR, 'data', 'net_config')
        db = shelve.open(config_file)
        need_save_key = (
            'SERVICE_IP', 'SERVICE_GATEWAY', 'SERVICE_SUBNET_MASK'
        )
        for attr in need_save_key:
            value = attrs.get(attr)
            if not value:
                continue
            db[attr] = value
        db.close()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        self._save_net_config_to_file(attrs)
        __, port = settings.VPN_RPC_ADDRESS.split(':')
        attrs['VPN_RPC_ADDRESS'] = f"{attrs['SERVICE_IP']}:{port}"
        return attrs

    @staticmethod
    def validate_GLOBAL_ORG_DISPLAY_NAME(s):
        org_names = Organization.objects.values_list('name', flat=True)
        if s in org_names:
            raise serializers.ValidationError(_('Organization name already exists'))
        return s
