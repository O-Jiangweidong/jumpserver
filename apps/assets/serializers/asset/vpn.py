from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from assets.models import Asset, Platform


class VPNSerializer(serializers.ModelSerializer):
    platform = serializers.SlugRelatedField(
        slug_field='name', queryset=Platform.objects.all(), label=_("Platform")
    )

    class Meta:
        model = Asset
        fields = [
            'id', 'hostname', 'ip', 'platform', 'vpn_connectivity',
        ]
