# -*- coding: utf-8 -*-
#
from rest_framework.generics import UpdateAPIView

from common.permissions import IsValidUser
from orgs.utils import tmp_to_root_org
from ..models import Asset
from ..serializers import MaintainAssetSerializer

__all__ = ['MaintainAssetApi']


class MaintainAssetApi(UpdateAPIView):
    serializer_class = MaintainAssetSerializer
    permission_classes = (IsValidUser,)
    page_no_limit = True

    def get_queryset(self):
        with tmp_to_root_org():
            queryset = Asset.objects.all()
        return queryset

    def check_permissions(self, request):
        obj = self.get_object()
        user = request.user
        if obj.is_offline and not user.is_superuser and f'{user.name}' != obj.maintainer:
            self.permission_denied(request)

    def perform_update(self, serializer):
        serializer.save(maintainer=self.request.user.name)
