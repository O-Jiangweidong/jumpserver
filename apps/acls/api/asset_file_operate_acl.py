from orgs.mixins.api import OrgBulkModelViewSet
from .common import ACLUserAssetFilterMixin
from .. import models, serializers

__all__ = ['AssetFileOperateACLViewSet']


class AssetFileOperateACLFilter(ACLUserAssetFilterMixin):
    class Meta:
        model = models.AssetFileOperateACL
        fields = ['name', 'action']


class AssetFileOperateACLViewSet(OrgBulkModelViewSet):
    model = models.AssetFileOperateACL
    filterset_class = AssetFileOperateACLFilter
    search_fields = ['name']
    serializer_class = serializers.AssetFileOperateACLSerializer
