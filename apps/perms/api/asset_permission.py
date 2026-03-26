# -*- coding: utf-8 -*-
#

from common.views.mixins import MiddlewareMixin
from orgs.mixins.api import OrgBulkModelViewSet
from perms import serializers
from perms.filters import AssetPermissionFilter
from perms.models import AssetPermission

__all__ = ['AssetPermissionViewSet']


class AssetPermissionViewSet(MiddlewareMixin, OrgBulkModelViewSet):
    """
    资产授权列表的增删改查api
    """
    model = AssetPermission
    serializer_classes = {
        'default': serializers.AssetPermissionSerializer,
        'list': serializers.AssetPermissionListSerializer,
    }
    # filterset_class = AssetPermissionFilter
    search_fields = ('name',)
