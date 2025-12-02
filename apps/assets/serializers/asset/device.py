
from assets.models import Device
from .common import AssetSerializer

__all__ = ['DeviceSerializer']


class DeviceSerializer(AssetSerializer):
    class Meta(AssetSerializer.Meta):
        model = Device
        fields = AssetSerializer.Meta.fields + ['unique_session']
